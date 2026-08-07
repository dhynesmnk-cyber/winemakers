"""staging.py — the review queue and the approve, reject and undo actions. Gate 3.

UX.md §1.3 and §1.4. Everything here operates on `content-staging/_staging/`,
which sits outside `site/src/content` so Astro can never build a draft
(TRD.md §3). The approve action is the only thing in this system that writes to
`_published/` (CLAUDE.md rule 5).

── The queue never crashes ───────────────────────────────────────────────────

UX.md §1.3: an unreadable file is listed as `UNREADABLE` with its parse error
and never empties the queue. One hand-edited file must not cost the reviewer the
other twenty, which is the same posture `data_store.rebuild()` takes.

── Undo, not confirmation ────────────────────────────────────────────────────

UX.md §1.4: approve and reject offer a 3-second inline undo rather than a
confirmation dialog. Confirmation dialogs slow a review session; undo keeps it
fast and safe. The SERVER window is wider than the client's offer, so a click at
the boundary succeeds rather than racing the timer it is trying to beat.

Undo restores the file and rebuilds the derived data from `_published`. There is
no compensating patch to get wrong: the DB is disposable and rebuildable
(SCHEMA.md §3), so putting the file back is the whole of the reversal.

── The ownership gate ────────────────────────────────────────────────────────

*Gate 4.* The chip and the approve gate both read the determination sidecar
`ownership.py` writes. With no sidecar the chip reads `NOT DETERMINED` and
approval is blocked: `CLEAR` is a positive finding — no deny-list hit on name,
domain or ABN, and no ownership signals extracted (UX.md §1.3) — and displaying
it for a check nobody has run would be the one lie this interface must not tell.

`ownership.approval_blocks` is the whole gate and it lives in the approve
function rather than the template (UX.md §1.4.5 rule 2), so there is no route
that publishes without passing what the UI enforces.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin import mdx_preview, schema  # noqa: E402
from admin.config import (  # noqa: E402
    AU_LATITUDE_BOUNDS,
    AU_LONGITUDE_BOUNDS,
    DELETED_DIR,
    DETERMINATIONS_DIR,
    IMAGES_DIR,
    MAX_PROSE_WORDS,
    MIN_PROSE_WORDS,
    PUBLISHED_DIR,
    REJECTED_DIR,
    STALE_DRAFT_DAYS,
    STAGING_DIR,
    SUMMARY_MAX_CHARS,
    UNDO_WINDOW_SECONDS,
)
from admin.pipeline import data_store, ownership  # noqa: E402

_logger = logging.getLogger("admin.staging")

#: A callable taking `(level, message)`. The app passes the log pane's emitter;
#: the default keeps this module usable from a script and from the CLI.
Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    _logger.log(logging.WARNING if level != "info" else logging.INFO, message)


#: UX.md §1.4's reject presets, in order. Free text is always allowed as well.
REJECT_REASONS = (
    "Not an independent producer",
    "Ownership unresolved",
    "Not a wine producer",
    "Retailer or restaurant",
    "Virtual brand or private label",
    "Insufficient published facts",
    "Duplicate of an existing entry",
)


# =============================================================================
# 1. Reading the queue
# =============================================================================


def _age_words(seconds: float) -> str:
    if seconds < 3600:
        return f"{max(int(seconds // 60), 1)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def _has_candidate_images(slug: str) -> bool:
    """Candidate images are staging-only until the separate publish action (UX.md §4)."""
    directory = IMAGES_DIR / slug
    return directory.is_dir() and any(directory.iterdir())


def ownership_chip(slug: str) -> str:
    """`CLEAR`, `CHECK`, `RESOLVED`, `REJECT` or `NOT DETERMINED` (UX.md §1.3)."""
    return ownership.chip_for(ownership.read_sidecar(slug))


def flags_for(data: dict[str, Any], body: str) -> list[str]:
    """UX.md §1.3's `FLAGGED` conditions, each as a sentence.

    Deliberately narrower than `validate_frontmatter`: this is the chip that
    says "look at this one", while validation is what blocks approval.
    """
    problems: list[str] = []
    errors = schema.validate_frontmatter(data)
    if errors:
        problems.append(f"{len(errors)} field(s) fail the schema")

    location = data.get("location") or {}
    for axis, bounds in (("latitude", AU_LATITUDE_BOUNDS), ("longitude", AU_LONGITUDE_BOUNDS)):
        value = location.get(axis)
        if isinstance(value, (int, float)) and not bounds[0] <= value <= bounds[1]:
            problems.append(f"{axis} is outside Australia")

    words = mdx_preview.prose_word_count(body)
    if words < MIN_PROSE_WORDS:
        problems.append(f"prose is {words} words, under {MIN_PROSE_WORDS}")
    elif words > MAX_PROSE_WORDS:
        problems.append(f"prose is {words} words, over {MAX_PROSE_WORDS}")

    if not data.get("regions"):
        problems.append("regions is empty")
    summary = data.get("summary")
    if isinstance(summary, str) and len(summary) > SUMMARY_MAX_CHARS:
        problems.append(f"summary is {len(summary)} characters, limit is {SUMMARY_MAX_CHARS}")
    return problems


def queue_rows(directory: Path = STAGING_DIR) -> list[dict[str, Any]]:
    """Every staged draft, newest first. Never raises on a bad file."""
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    now = time.time()
    for path in directory.glob("*.mdx"):
        slug = path.stem
        try:
            modified = path.stat().st_mtime
        except OSError:
            modified = now
        age_seconds = max(now - modified, 0)
        row: dict[str, Any] = {
            "slug": slug,
            "modified": modified,
            "age": _age_words(age_seconds),
            "stale": age_seconds > STALE_DRAFT_DAYS * 86400,
            "ownership": ownership_chip(slug),
        }
        try:
            data, body = schema.read_mdx(path)
        except schema.FrontmatterError as exc:
            rows.append(
                {
                    **row,
                    "name": slug,
                    "status": "UNREADABLE",
                    "detail": str(exc),
                    "where": "",
                    "category": "",
                }
            )
            continue

        location = data.get("location") or {}
        where = ", ".join(
            part
            for part in (
                schema.region_name(data["primary_region"]) if data.get("primary_region") else "",
                str(location.get("state") or ""),
            )
            if part
        )
        problems = flags_for(data, body)
        if problems:
            status, detail = "FLAGGED", "; ".join(problems)
        elif _has_candidate_images(slug):
            status, detail = "IMG PENDING", "candidate images await the publish action"
        else:
            status, detail = "DRAFTED", ""
        rows.append(
            {
                **row,
                "name": str(data.get("name") or slug),
                "status": status,
                "detail": detail,
                "where": where,
                "category": (
                    schema.label_for("category", data["category"]) if data.get("category") else ""
                ),
            }
        )
    rows.sort(key=lambda row: row["modified"], reverse=True)
    return rows


def queue_counts(rows: list[dict[str, Any]]) -> str:
    """UX.md §1.3's header line: `9 drafted, 3 check, 1 flagged`."""
    parts = []
    for label, count in (
        ("drafted", sum(1 for row in rows if row["status"] in ("DRAFTED", "IMG PENDING"))),
        ("check", sum(1 for row in rows if row["ownership"] == "CHECK")),
        ("flagged", sum(1 for row in rows if row["status"] == "FLAGGED")),
        ("unreadable", sum(1 for row in rows if row["status"] == "UNREADABLE")),
    ):
        if count:
            parts.append(f"{count} {label}")
    return ", ".join(parts)


def duplicate_of(slug: str, data: dict[str, Any]) -> dict[str, str] | None:
    """A published or staged entry with the same normalised website or name.

    UX.md §1.4: a warning, never a block. The reviewer decides.
    """

    def normalise_host(url: Any) -> str:
        text = str(url or "").lower()
        for prefix in ("https://", "http://", "www."):
            if text.startswith(prefix):
                text = text[len(prefix) :]
        return text.split("/")[0]

    host = normalise_host(data.get("website"))
    name = str(data.get("name") or "").strip().lower()
    for directory, where in ((PUBLISHED_DIR, "published"), (STAGING_DIR, "staged")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.mdx")):
            if path.stem == slug:
                continue
            try:
                other, _ = schema.read_mdx(path)
            except schema.FrontmatterError:
                continue
            if (host and normalise_host(other.get("website")) == host) or (
                name and str(other.get("name") or "").strip().lower() == name
            ):
                return {
                    "slug": path.stem,
                    "name": str(other.get("name") or path.stem),
                    "where": where,
                }
    return None


# =============================================================================
# 2. Reading and saving one draft
# =============================================================================


def draft_path(slug: str) -> Path:
    return STAGING_DIR / f"{slug}.mdx"


def load_draft(slug: str) -> tuple[dict[str, Any], str]:
    return schema.read_mdx(draft_path(slug))


def save_draft(slug: str, frontmatter: dict[str, Any], body: str) -> None:
    """Autosave. Writes the whole file; there is no partial-field patch path."""
    schema.write_mdx(draft_path(slug), schema.coerce_dates(frontmatter), body)


# =============================================================================
# 3. The approve gate
# =============================================================================


def ownership_gate(slug: str, data: dict[str, Any]) -> list[str]:
    """What blocks approval on ownership grounds. Empty means the gate is open.

    UX.md §1.4.5 in the form the rules require: **the gate lives in the approve
    function, not in the template.** A route that publishes without passing this
    would be the hole the whole independence claim leaks through.

    Delegated whole to `ownership.approval_blocks` so the rules have one home
    and the API, the keyboard path and the CLI cannot drift from each other.
    """
    return ownership.approval_blocks(data, ownership.read_sidecar(slug))


# =============================================================================
# 4. Approve, reject, undo, unpublish
# =============================================================================

#: slug -> what it takes to reverse the last approve. In-process and deliberately
#: not persisted: the undo window is seconds long, and an undo that survived a
#: restart would be an undo nobody remembers asking for.
_UNDO: dict[str, dict[str, Any]] = {}


class ActionBlocked(Exception):
    """Approve refused. Carries the field errors the review pane highlights."""

    def __init__(self, message: str, errors: dict[str, str] | None = None, blocks: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or {}
        self.blocks = blocks or []


def _rebuild_derived(log: Logger) -> None:
    """Regenerate the DB and the derived JSON. Never rolls back a publish.

    UX.md §1.5 row 18: the derived data is disposable by design, so a failure
    here is logged with the command to run and the published file stands.
    """
    try:
        count = data_store.rebuild()
        log("info", f"derived data rebuilt, {count} published producer(s)")
    except Exception as exc:  # noqa: BLE001
        log(
            "warn",
            f"derived rebuild failed: {exc}. Run "
            f"python -m admin.pipeline.data_store --rebuild; the published file is correct.",
        )


def approve(slug: str, log: Logger = _null_log) -> dict[str, Any]:
    """UX.md §1.4's approve, in its stated order.

    1. validate the frontmatter; any failure blocks and highlights,
    2. assert the ownership gate; failure blocks with the missing element named,
    3. move the file from `_staging/` to `_published/`,
    4. move the ownership sidecar to the determinations directory,
    5. rebuild the derived data,
    6. forewords for a first-published taxonomy member — Gate 6 owns this and
       the step is named here so its absence is deliberate rather than lost.
    """
    source = draft_path(slug)
    try:
        data, body = schema.read_mdx(source)
    except schema.FrontmatterError as exc:
        raise ActionBlocked(f"{slug} could not be read: {exc}") from exc

    errors = schema.validate_frontmatter(data)
    if errors:
        log("error", f"approve blocked: {slug} has {len(errors)} field error(s)")
        raise ActionBlocked(f"{len(errors)} field(s) fail the schema", errors=errors)

    blocks = ownership_gate(slug, data)
    if blocks:
        log("error", f"approve blocked by the ownership gate: {'; '.join(blocks)}")
        raise ActionBlocked("the ownership gate is not satisfied", blocks=blocks)

    target = PUBLISHED_DIR / f"{slug}.mdx"
    target.parent.mkdir(parents=True, exist_ok=True)
    # A re-approve overwrites a published file. Keep the bytes so undo restores
    # what was there rather than leaving a hole where an entry used to be.
    previous = target.read_bytes() if target.is_file() else None
    shutil.move(str(source), str(target))
    log("info", f"published {slug} to _published/{slug}.mdx")

    sidecar = ownership.sidecar_path(slug, STAGING_DIR)
    determination = DETERMINATIONS_DIR / f"{slug}.json"
    moved_sidecar = False
    if sidecar.is_file():
        determination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(sidecar), str(determination))
        moved_sidecar = True
        log("info", f"determination retained at {determination.name}")

    _rebuild_derived(log)

    _UNDO[slug] = {
        "action": "approve",
        "at": time.monotonic(),
        "previous_published": previous,
        "sidecar": moved_sidecar,
    }
    return {"slug": slug, "undo_seconds": UNDO_WINDOW_SECONDS}


def reject(slug: str, reason: str, log: Logger = _null_log) -> dict[str, Any]:
    """Move to `_rejected/` with a one-line reason sidecar. Never hard-deletes."""
    source = draft_path(slug)
    if not source.is_file():
        raise ActionBlocked(f"{slug} is not in the staging queue")
    reason = reason.strip() or "No reason given"

    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    target = REJECTED_DIR / f"{slug}.mdx"
    shutil.move(str(source), str(target))
    (REJECTED_DIR / f"{slug}.reason.txt").write_text(
        f"{date.today().isoformat()}: {reason}\n", encoding="utf-8"
    )
    sidecar = ownership.sidecar_path(slug, STAGING_DIR)
    moved_sidecar = False
    if sidecar.is_file():
        shutil.move(str(sidecar), str(ownership.sidecar_path(slug, REJECTED_DIR)))
        moved_sidecar = True
    log("info", f"rejected {slug}: {reason}")

    _UNDO[slug] = {"action": "reject", "at": time.monotonic(), "sidecar": moved_sidecar}
    return {"slug": slug, "undo_seconds": UNDO_WINDOW_SECONDS}


def undo(slug: str, log: Logger = _null_log) -> dict[str, Any]:
    """Fully reverse the last approve or reject, inside the server window.

    UX.md §1.5 row 17: past the window the answer is the truth, and `Unpublish`
    is offered instead of a pretence that the approve can still be taken back.
    """
    record = _UNDO.get(slug)
    if record is None or time.monotonic() - record["at"] > UNDO_WINDOW_SECONDS:
        _UNDO.pop(slug, None)
        raise ActionBlocked("undo window has closed, this approval is final")

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    if record["action"] == "approve":
        published = PUBLISHED_DIR / f"{slug}.mdx"
        shutil.move(str(published), str(draft_path(slug)))
        if record.get("previous_published") is not None:
            published.write_bytes(record["previous_published"])
        if record.get("sidecar"):
            shutil.move(
                str(DETERMINATIONS_DIR / f"{slug}.json"),
                str(ownership.sidecar_path(slug, STAGING_DIR)),
            )
        _rebuild_derived(log)
    else:
        shutil.move(str(REJECTED_DIR / f"{slug}.mdx"), str(draft_path(slug)))
        (REJECTED_DIR / f"{slug}.reason.txt").unlink(missing_ok=True)
        if record.get("sidecar"):
            shutil.move(
                str(ownership.sidecar_path(slug, REJECTED_DIR)),
                str(ownership.sidecar_path(slug, STAGING_DIR)),
            )

    _UNDO.pop(slug, None)
    log("info", f"undone: {slug} is back in the staging queue")
    return {"slug": slug}


def unpublish(slug: str, log: Logger = _null_log) -> dict[str, Any]:
    """Park a published file in `DELETED_DIR`, timestamped, and rebuild.

    UX.md §1.5 row 17's alternative once the undo window has closed. Nothing in
    this system hard-deletes a producer's entry.
    """
    published = PUBLISHED_DIR / f"{slug}.mdx"
    if not published.is_file():
        raise ActionBlocked(f"{slug} is not published")
    DELETED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shutil.move(str(published), str(DELETED_DIR / f"{slug}.{stamp}.mdx"))
    log("warn", f"unpublished {slug}, parked in {DELETED_DIR.name}/")
    _rebuild_derived(log)
    return {"slug": slug}
