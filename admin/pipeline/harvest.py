"""harvest.py — one URL, end to end. Gate 5. TRD.md §7, UX.md §1.5.

── The sequence, and why it is in this order ─────────────────────────────────

    1. deny-list screen on the DOMAIN            zero API calls
    2. fetch + extract                           zero API calls
    3. slug, and the collision check             zero API calls
    4. Harvester                                 one call, the cheap model
    5. full deny-list screen + determination     zero API calls
    6. Architect                                 one call, the prose model
    7. Gatekeeper                                one call, the cheap model
    8. finalise, geocode, write, images

TRD.md §7.5 requires the name/domain/ABN deny-list to run "before a draft enters
the queue — before the Architect is called, so a portfolio-owned label costs one
cheap call rather than three." Step 1 goes further and costs zero, because a URL
is enough to screen a domain. Steps 1 and 5 are the same check with different
inputs: step 1 has only the URL, step 5 has the name and ABN the Harvester read.

**A reject at either step aborts before any draft is written.** That is the
whole point of the ordering, and SEED.md row 1 is the fixture that proves it.

── Nothing partial is ever left behind ───────────────────────────────────────

UX.md §1.1: "A draft is written by a single atomic write at the end of the
pipeline, so an aborted item leaves nothing behind." Every failure below returns
a result; none of them has written to `_staging/` at the point it gives up.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    MODEL_ARCHITECT,
    MODEL_GATEKEEPER,
    MODEL_HARVESTER,
    PUBLISHED_DIR,
    STAGING_DIR,
)
from admin import schema  # noqa: E402
from admin.pipeline import (  # noqa: E402
    agents,
    fetcher,
    geocode,
    images,
    orchestrator,
    ownership,
)

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    pass


#: UX.md §1.1's queue states.
STAGED = "STAGED"
BLOCKED = "BLOCKED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"


@dataclass
class HarvestResult:
    state: str
    url: str
    slug: str = ""
    detail: str = ""
    #: UX.md §1.5 row 3: set when the item ended thin, so the row can offer
    #: `Retry with Playwright`. Nothing else may trigger that path.
    offer_playwright: bool = False
    unmatched: dict[str, list[str]] = field(default_factory=dict)
    ledger: agents.Ledger | None = None
    determination: Any = None

    @property
    def ok(self) -> bool:
        return self.state == STAGED


def _slug_for(name: str, url: str) -> str:
    slug = orchestrator.slugify(name)
    if slug:
        return slug
    # A producer with no usable name is not draftable, but the caller still
    # needs something to key a log line and a failed-output file on.
    return orchestrator.slugify(url.split("//")[-1].replace("/", "-")) or "unknown"


def _existing(slug: str) -> str:
    if (PUBLISHED_DIR / f"{slug}.mdx").is_file():
        return "_published"
    if (STAGING_DIR / f"{slug}.mdx").is_file():
        return "_staging"
    return ""


def harvest_one(
    url: str,
    *,
    log: Logger = _null_log,
    today: date_type | None = None,
    use_playwright: bool = False,
    allow_existing: bool = False,
    floor: str | None = None,
    fetched: fetcher.Fetched | None = None,
) -> HarvestResult:
    """Run one URL. Never raises for a per-item failure; returns the state.

    `allow_existing` is the documented re-harvest flag (UX.md §1.5 row 9). It
    still writes only to `_staging/`; nothing here can touch `_published`.

    `fetched` short-circuits step 2, for the Playwright retry path which has
    already fetched the page with a browser.
    """
    today = today or date_type.today()
    ledger = agents.Ledger()

    # ── 1. The domain screen, before anything is spent ────────────────────
    determination = ownership.screen_url(url, floor=floor)
    if floor:
        log(
            "warn",
            f"machine verdict floored at {floor}; the draft carries "
            f"verdict_overridden_from and every check rule still applies",
        )
    log("info", "ownership deny-list: domain  " + ("MATCH" if determination.hits() else "ok, no match"))
    if determination.verdict == "reject":
        _, reason = ownership.reject_reason(determination)
        path = ownership.write_blocked_record(url, "", determination)
        log("error", f"blocked before drafting — {reason}")
        log("info", f"blocked record written to {path.parent.name}/{path.name}")
        return HarvestResult(BLOCKED, url, slug=path.stem, detail=reason, determination=determination)

    # ── 2. Fetch and extract ──────────────────────────────────────────────
    if fetched is None:
        try:
            fetched = fetcher.fetch(url, log=log, use_playwright=use_playwright)
        except fetcher.RobotsDisallowed as exc:
            # UX.md §1.5 row 2: no retry offered, no override control.
            log("error", f"robots.txt disallows this fetch ({exc.rule})")
            return HarvestResult(FAILED, url, detail=f"robots.txt disallows ({exc.rule})")
        except fetcher.ThinExtraction as exc:
            log("warn", f"thin extraction: {exc.chars} chars")
            log("info", "no draft written. Retry with Playwright if the page is JS-rendered.")
            return HarvestResult(
                FAILED, url, detail=f"thin extraction: {exc.chars} chars", offer_playwright=True
            )
        except fetcher.FetchError as exc:
            log("error", f"fetch failed: {exc.reason}")
            return HarvestResult(FAILED, url, detail=f"fetch failed: {exc.reason}")

    # ── 4. Harvester ──────────────────────────────────────────────────────
    try:
        harvest = agents.call(
            "harvester",
            MODEL_HARVESTER,
            agents.load_prompt("harvester", SOURCE_URL=url, PAGE_TEXT=fetched.text),
            validate=orchestrator._validate_harvester_json,
            log=log,
            ledger=ledger,
            slug=_slug_for("", url),
        )
    except (agents.AgentError, agents.MalformedOutput) as exc:
        log("error", f"harvester failed: {exc}")
        return HarvestResult(FAILED, url, detail=f"harvester: {exc}", ledger=ledger)

    log(
        "info",
        f"harvester agent ({MODEL_HARVESTER})  ok, independence: {harvest.get('independence')}",
    )

    # ── UX.md §1.5 row 5: not a producer. Not an error state. ─────────────
    name = str(harvest.get("name") or "").strip()
    if not name:
        log("warn", "harvester could not identify a wine producer on this page")
        for note in harvest.get("confidence_notes") or []:
            log("info", f"  {note}")
        return HarvestResult(
            FAILED, url, detail="not a wine producer page", ledger=ledger
        )

    slug = _slug_for(name, url)

    # ── 5. The full determination, before the Architect ───────────────────
    determination = ownership.screen_candidate(
        url,
        name=name,
        signals=harvest.get("ownership_signals"),
        harvester_verdict=harvest.get("independence"),
        floor=floor,
    )
    populated = ownership.populated_signals(determination.signals)
    log(
        "info",
        f"ownership determination  {determination.verdict.upper()}, "
        f"{len(populated)} signal{'' if len(populated) == 1 else 's'}",
    )

    if determination.verdict == "reject":
        source_of_reject, reason = ownership.reject_reason(determination)
        path = ownership.write_blocked_record(url, name, determination)
        log("error", f"blocked before drafting — {reason}")
        if source_of_reject == "harvester" and populated:
            first = next(
                (row for row in populated if row.get("values")), None
            )
            if first and first.get("values"):
                log("info", f'  first signal: "{first["values"][0]}"')
        log("info", f"blocked record written to {path.parent.name}/{path.name}")
        return HarvestResult(
            BLOCKED, url, slug=slug, detail=reason, ledger=ledger, determination=determination
        )

    # ── 3 (deferred until the name exists). Slug collision, UX row 9 ──────
    where = _existing(slug)
    if where and not allow_existing:
        log("warn", f"slug '{slug}' exists in {where}, skipping")
        return HarvestResult(
            SKIPPED, url, slug=slug, detail=f"slug exists in {where}", ledger=ledger
        )

    previous: dict[str, Any] | None = None
    if where == "_published" and allow_existing:
        try:
            previous, _ = schema.read_mdx(PUBLISHED_DIR / f"{slug}.mdx")
        except schema.FrontmatterError:
            previous = None

    # ── 6. Architect ──────────────────────────────────────────────────────
    import json as _json

    try:
        draft_text = agents.call(
            "architect",
            MODEL_ARCHITECT,
            agents.load_prompt(
                "architect",
                HARVEST_JSON=_json.dumps(harvest, indent=2, ensure_ascii=False),
                SOURCE_URL=url,
                TODAY=today.isoformat(),
                REGION_SLUGS=", ".join(schema.REGION_SLUGS),
                SUBREGION_SLUGS=", ".join(schema.SUBREGION_SLUGS),
                VARIETY_SLUGS=", ".join(orchestrator.VARIETY_KEYS),
            ),
            validate=lambda text: text,
            log=log,
            ledger=ledger,
            slug=slug,
        )
        data, body = orchestrator._validate_mdx(agents.strip_fence(draft_text))
    except (agents.AgentError, agents.MalformedOutput) as exc:
        log("error", f"architect failed: {exc}")
        return HarvestResult(FAILED, url, slug=slug, detail=f"architect: {exc}", ledger=ledger)
    except ValueError as exc:
        log("error", f"architect returned unusable MDX: {exc}")
        path = agents.save_failed("architect", slug, draft_text)
        log("info", f"raw output saved to {path.parent.name}/{path.name}")
        return HarvestResult(FAILED, url, slug=slug, detail=f"architect: {exc}", ledger=ledger)

    log("info", f"architect agent ({MODEL_ARCHITECT})  ok, {len(body.split())} words")

    # ── 7. Gatekeeper ─────────────────────────────────────────────────────
    try:
        polished = agents.call(
            "gatekeeper",
            MODEL_GATEKEEPER,
            agents.load_prompt("gatekeeper", DRAFT_MDX=draft_text.strip()),
            validate=orchestrator._validate_mdx,
            log=log,
            ledger=ledger,
            slug=slug,
        )
        data, body = polished
    except (agents.AgentError, agents.MalformedOutput) as exc:
        # The Architect's draft is usable. Losing a producer because the
        # subeditor stage failed would be the wrong trade, so this warns and
        # keeps going with unpolished prose the reviewer can see and fix.
        log("warn", f"gatekeeper failed ({exc}); staging the unpolished draft")
    else:
        log("info", f"gatekeeper agent ({MODEL_GATEKEEPER})  ok, {len(body.split())} words")

    # ── 8. Finalise ───────────────────────────────────────────────────────
    coordinates = geocode.geocode(data.get("location"), log=log)

    data = orchestrator._finalize_frontmatter(
        data,
        harvest=harvest,
        source_url=url,
        today=today,
        determination=determination,
        coordinates=coordinates,
        previous=previous,
        log=log,
    )
    data, unmatched = orchestrator.strip_internal(data)

    # One atomic write, at the very end.
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    schema.write_mdx(STAGING_DIR / f"{slug}.mdx", data, body)
    ownership.write_sidecar(slug, determination, STAGING_DIR)

    suffix = f"  OWNERSHIP: {determination.verdict.upper()}" if determination.verdict != "clear" else ""
    log("info", f"saved to {STAGING_DIR.name}/{slug}.mdx{suffix}")

    # Candidate images are last: a failure here must not cost the draft.
    try:
        images.download_candidates(slug, fetched.html, fetched.final_url, log=log)
    except Exception as exc:  # noqa: BLE001 - UX.md §1.5 row 21, never fatal
        log("warn", f"candidate images failed ({type(exc).__name__}), draft is unaffected")

    log("info", ledger.line())
    return HarvestResult(
        STAGED,
        url,
        slug=slug,
        detail="",
        unmatched=unmatched,
        ledger=ledger,
        determination=determination,
    )
