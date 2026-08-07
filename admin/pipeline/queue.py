"""queue.py — the batch harvest queue. Gate 5. TRD.md §7.4, UX.md §1.1.

**Required at this project's target coverage, not a convenience.** At 150 to 300
producers a one-URL-at-a-time panel is not a workable instrument. The reference
build never needed one at 32 venues and does not have one, so this component has
no prior art here and is written from the spec.

── Four properties, each load-bearing ────────────────────────────────────────

**Strictly serial.** One job at a time. Not a concurrency limit dialled to one:
politeness to the sites being read and a single shared Anthropic rate-limit
budget both point the same way, and neither would survive someone later deciding
two at once is fine.

**Per-URL isolation.** Any failure of any kind ends that item and advances. A
batch of ten with two bad URLs produces eight drafts. A failed item never stops
the run, never rolls back an earlier item, and never leaves a partial file.

**Durable across an admin restart.** State persists to
`temp_data/harvest_queue.json` — gitignored, reconstructible, holding only URLs
and per-URL status. Never in `data/`, which `rebuild()` recreates. A forty-URL
run survives a page reload, a closed tab and a restarted browser.

**A BLOCKED row is a determination, not an error.** `Retry failed` leaves them
alone and there is no way to delete one from the UI. Blocked records are history
(UX.md §1.4.4).
"""

from __future__ import annotations

import json
import re
import sys
import threading
from datetime import date as date_type
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import BATCH_MAX_URLS, HARVEST_QUEUE_PATH  # noqa: E402
from admin.pipeline import harvest as harvest_module  # noqa: E402

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    pass


#: UX.md §1.1's queue states, in the order the summary line reports them.
STATES = ("QUEUED", "RUNNING", "STAGED", "BLOCKED", "FAILED", "SKIPPED")

_URL_LINE = re.compile(r"^https?://\S+$")


def parse_urls(raw: str, limit: int = BATCH_MAX_URLS) -> tuple[list[str], int]:
    """`(urls, ignored count)`. Blank lines and non-URLs are dropped and counted.

    UX.md §1.1: reported as a count (`3 lines ignored: not URLs`), never
    silently. Order is preserved and duplicates within one paste are dropped,
    because pasting a list twice is a slip, not an instruction to harvest twice.
    """
    urls: list[str] = []
    ignored = 0
    seen: set[str] = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if not _URL_LINE.match(line):
            ignored += 1
            continue
        if line in seen:
            continue
        seen.add(line)
        urls.append(line)
    return urls[:limit], ignored


class HarvestQueue:
    def __init__(self, path: Path = HARVEST_QUEUE_PATH) -> None:
        self.path = path
        self.items: list[dict[str, Any]] = []
        self.paused = False
        self.cancelled = False
        self._running = False
        self._lock = threading.Lock()
        #: url -> verdict ceiling, set only by UX.md §1.4.4's `Re-harvest as
        #: check` and consumed once, so a later ordinary harvest of the same URL
        #: is decided on its merits again.
        self.floors: dict[str, str] = {}
        #: Rate-limit strikes in this run. Three pauses the whole queue.
        self._rate_limit_strikes = 0

    # ── Persistence ───────────────────────────────────────────────────────

    def load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        items = data.get("items")
        if isinstance(items, list):
            self.items = [item for item in items if isinstance(item, dict) and item.get("url")]
        # A RUNNING row means the process died mid-item. It never completed, so
        # it goes back in the queue rather than being reported as a state it
        # never reached.
        for item in self.items:
            if item.get("state") == "RUNNING":
                item["state"] = "QUEUED"
                item["detail"] = ""
        self.paused = bool(data.get("paused"))
        self.floors = dict(data.get("floors") or {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": self.items, "paused": self.paused, "floors": self.floors}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    # ── Contents ──────────────────────────────────────────────────────────

    def add(self, urls: list[str]) -> int:
        for url in urls:
            self.items.append(
                {"url": url, "state": "QUEUED", "detail": "", "slug": "",
                 "offer_playwright": False}
            )
        self.save()
        return len(urls)

    def summary(self) -> str:
        """`12 queued, 1 running, 7 staged, 2 blocked, 1 failed` (UX.md §1.1)."""
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item["state"]] = counts.get(item["state"], 0) + 1
        parts = [f"{counts[state]} {state.lower()}" for state in STATES if counts.get(state)]
        return ", ".join(parts)

    # ── Controls (UX.md §1.1) ─────────────────────────────────────────────

    def pause(self) -> None:
        """Finishes the running item, then stops with the rest still QUEUED."""
        self.paused = True
        self.save()

    def resume(self) -> None:
        self.paused = False
        self._rate_limit_strikes = 0
        self.save()

    def retry_failed(self) -> int:
        """Requeues every FAILED row. BLOCKED rows are left alone, deliberately."""
        count = 0
        for item in self.items:
            if item["state"] == "FAILED":
                item.update({"state": "QUEUED", "detail": "", "offer_playwright": False})
                count += 1
        self.save()
        return count

    def clear_finished(self) -> int:
        """Removes STAGED and SKIPPED rows from view. The drafts are untouched.

        There is no `Clear all` and no way to remove a BLOCKED row: a blocked
        record is a determination about a real business and is history.
        """
        before = len(self.items)
        self.items = [item for item in self.items if item["state"] not in ("STAGED", "SKIPPED")]
        self.save()
        return before - len(self.items)

    def cancel(self) -> None:
        self.cancelled = True
        self.paused = True
        self.save()

    # ── The runner ────────────────────────────────────────────────────────

    def _next(self) -> dict[str, Any] | None:
        return next((item for item in self.items if item["state"] == "QUEUED"), None)

    def run_sync(
        self,
        *,
        log: Logger = _null_log,
        today: date_type | None = None,
    ) -> None:
        """Serial runner. Blocking; the app calls it on a worker thread.

        Guarded so two callers cannot start two runners over one list, which
        would break the one-job-at-a-time rule the whole design rests on.
        """
        with self._lock:
            if self._running:
                return
            self._running = True
        try:
            total = sum(1 for item in self.items if item["state"] in ("QUEUED", "RUNNING"))
            done = 0
            while True:
                if self.cancelled:
                    log("warn", "queue cancelled")
                    return
                if self.paused:
                    log("info", "queue paused after the current item")
                    return
                item = self._next()
                if item is None:
                    return

                item["state"] = "RUNNING"
                item["detail"] = ""
                self.save()

                floor = self.floors.pop(item["url"], None)
                try:
                    result = harvest_module.harvest_one(
                        item["url"], log=log, today=today, floor=floor
                    )
                except Exception as exc:  # noqa: BLE001
                    # Per-URL isolation is absolute. An unexpected exception is
                    # still that item's failure and nothing else's.
                    log("error", f"{item['url']}: unexpected {type(exc).__name__}: {exc}")
                    item.update({"state": "FAILED", "detail": f"{type(exc).__name__}: {exc}"})
                    self.save()
                    done += 1
                    continue

                item.update(
                    {
                        "state": result.state,
                        "detail": result.detail,
                        "slug": result.slug,
                        "offer_playwright": result.offer_playwright,
                    }
                )
                self.save()

                done += 1
                if total > 1:
                    log("info", f"batch {done} of {total} complete")

                # UX.md §1.5 row 13: repeated rate limiting pauses the queue.
                if "rate limited" in (result.detail or "").lower():
                    self._rate_limit_strikes += 1
                    if self._rate_limit_strikes >= 3:
                        self.paused = True
                        self.save()
                        log("error", "queue paused: repeated rate limiting. Resume when ready.")
                        return
        finally:
            with self._lock:
                self._running = False

    @property
    def running(self) -> bool:
        return self._running
