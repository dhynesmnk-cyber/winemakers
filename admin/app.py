"""app.py — the admin control hub. Gate 3. UX.md §1, TRD.md §6.

FastAPI, Jinja2 and hand-written vanilla JS. No React, no SPA framework, no
bundler, no CDN script tag (TRD.md §2.1). One screen, not a set of pages the
reviewer navigates between: reviewing 300 producers is the job this interface
exists for, and a click-per-producer navigation gets abandoned at forty.

── What is wired at this gate, and what is deliberately not ──────────────────

Gate 3 is the hub shell and the staging queue. The harvest pipeline is stubbed:
the panel, the queue and the log pane are real and the runner reports that the
pipeline itself lands at Gate 5, rather than pretending to draft anything. The
independence panel (UX.md §1.4.1 to §1.4.6), the Blocked list and the deploy
strip's actions are Gates 4 and 7; their panes render with their empty states so
the screen's shape is right and nothing silently goes missing later.

── The one rule that is enforced in the server, not the template ─────────────

UX.md §1.4.5 rule 2: there is no API route that publishes without passing the
same gate the UI enforces. `staging.approve` is that gate. Every publish path in
this file goes through it, and there is no force flag.

── Auth ──────────────────────────────────────────────────────────────────────

HTTP Basic via `ADMIN_USERNAME` / `ADMIN_PASSWORD`, compared with
`hmac.compare_digest`. Both blank means no prompt, which is the local-dev case
only; credentials are mandatory whenever the app is reachable beyond localhost
(TRD.md §6.7).
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin import mdx_preview, schema  # noqa: E402
from admin.config import (  # noqa: E402
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    BATCH_MAX_URLS,
    BLOCKED_DIR,
    CATEGORIES,
    CELLAR_DOOR_STATES,
    CERTIFICATION_STATES,
    CONTENT_STAGING_DIR,
    FAQ_MAX_ITEMS,
    FRUIT_SOURCE,
    LOGISTICS_KEYS,
    MAX_LOG_LINES,
    OWNERSHIP_EVIDENCE_METHODS,
    OWNERSHIP_JSON_PATH,
    PRACTICE_KEYS,
    PRODUCTION_BANDS,
    PUBLISHED_DIR,
    SITE_DIST_DIR,
    SITE_URL,
    STAGING_DIR,
    STATES,
    STATIC_DIR,
    SUMMARY_MAX_CHARS,
    TEMPLATES_DIR,
    UNDO_CLIENT_SECONDS,
    VARIETY_KEYS,
    VESSEL_KEYS,
    WINE_STYLE_KEYS,
)
from admin.pipeline import (  # noqa: E402
    deploy as deploy_module,
    fetcher,
    harvest as harvest_module,
    images,
    ownership,
    queue as queue_module,
    staging,
)

_logger = logging.getLogger("admin.app")

#: UX.md §1: the hub header carries the site name. `SITE_NAME` is a placeholder
#: until the brand is chosen, and it is never guessed here.
SITE_NAME = "Independent Australian Winemakers"


# =============================================================================
# 1. The log bus — UX.md §1.2
#
# "Trust in the pipeline comes from visibility. Never replace this with a
# spinner." One pane for harvest, approve, image publish and deploy: there is
# one log, not four.
# =============================================================================


class LogBus:
    """A ring buffer plus a fan-out to every open SSE connection.

    The buffer is what makes a reopened hub useful: reattaching to a running job
    and replaying the current item's log is the difference between a tool you
    can close and one you have to babysit.
    """

    def __init__(self, capacity: int = MAX_LOG_LINES) -> None:
        self.capacity = capacity
        self.lines: list[dict[str, str]] = []
        self.subscribers: set[asyncio.Queue] = set()
        #: Set at startup. The pipeline runs on a worker thread (it is blocking
        #: by design, TRD.md §7.4), and `asyncio.Queue` is not thread-safe, so a
        #: log line emitted off-loop is hopped back onto it. Without this the
        #: SSE fan-out corrupts under exactly the load it exists to show.
        self.loop: asyncio.AbstractEventLoop | None = None

    def _fanout(self, line: dict[str, str]) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(line)
            except asyncio.QueueFull:  # pragma: no cover - a stalled reader
                self.subscribers.discard(queue)

    def emit(self, level: str, message: str) -> None:
        line = {
            "at": datetime.now().strftime("%H:%M:%S"),
            "level": level if level in ("info", "warn", "error") else "info",
            "message": message,
        }
        self.lines.append(line)
        if len(self.lines) > self.capacity:
            # Drops from the top, per UX.md §1.2.
            del self.lines[: len(self.lines) - self.capacity]

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if self.loop is not None and running is not self.loop:
            self.loop.call_soon_threadsafe(self._fanout, line)
        else:
            self._fanout(line)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.capacity * 2)
        self.subscribers.add(queue)
        return queue


BUS = LogBus()


def log(level: str, message: str) -> None:
    BUS.emit(level, message)


# =============================================================================
# 2. The harvest queue — UX.md §1.1, TRD.md §7.4
#
# Server-held, not browser state, so a forty-URL run survives a page reload, a
# closed tab and a restarted browser. One job at a time, serial, never
# concurrent.
#
# WIRED AT GATE 5. `admin.pipeline.queue` owns the state machine and the
# persistence; this module owns the HTTP surface and the thread the runner
# occupies. `run_sync` blocks by design, so it is dispatched with
# `asyncio.to_thread` and the log bus hops its lines back onto the loop.
# =============================================================================


#: The one queue. Loaded from disk at startup so a restart reattaches to the
#: run rather than losing it (TRD.md §7.4).
QUEUE = queue_module.HarvestQueue()


def _start_runner() -> None:
    """Dispatch the blocking runner onto a worker thread, once.

    `run_sync` guards itself against a second concurrent runner, so calling
    this while a run is in flight is a no-op rather than a race.
    """
    if QUEUE.running:
        return
    asyncio.create_task(asyncio.to_thread(QUEUE.run_sync, log=log))


# =============================================================================
# 3. The app
# =============================================================================

app = FastAPI(title=f"{SITE_NAME} — control hub", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
_basic = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    """Both blank means no prompt, which is the local-dev case only."""
    if not ADMIN_USERNAME and not ADMIN_PASSWORD:
        return
    supplied_user = credentials.username if credentials else ""
    supplied_password = credentials.password if credentials else ""
    ok_user = hmac.compare_digest(supplied_user, ADMIN_USERNAME)
    ok_password = hmac.compare_digest(supplied_password, ADMIN_PASSWORD)
    if not (ok_user and ok_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorised",
            headers={"WWW-Authenticate": "Basic"},
        )


for directory in (STAGING_DIR, CONTENT_STAGING_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# DESIGN.md §8: the hub inherits the palette, both modes. `tokens.css` is served
# straight out of the site rather than copied, so the admin cannot drift from the
# six tokens the public site uses. Its `@theme` block is a Tailwind directive a
# browser ignores, and the admin has no use for the aliases in it.
_SITE_STYLES_DIR = SITE_DIST_DIR.parent / "src" / "styles"
if _SITE_STYLES_DIR.is_dir():
    app.mount("/site-styles", StaticFiles(directory=str(_SITE_STYLES_DIR)), name="site-styles")

if SITE_DIST_DIR.is_dir():
    # The preview links the real shipped CSS out of the last build (UX.md §1.4).
    # `/fonts` is mounted as well because `global.css` addresses the three faces
    # absolutely, and a preview in fallback faces is a preview in a different
    # skin.
    app.mount("/site-dist", StaticFiles(directory=str(SITE_DIST_DIR)), name="site-dist")
    if (SITE_DIST_DIR / "fonts").is_dir():
        app.mount("/fonts", StaticFiles(directory=str(SITE_DIST_DIR / "fonts")), name="fonts")


def _json_safe(value: Any) -> Any:
    """Dates as ISO strings. JSON has no date type and YAML hands back real ones."""
    if isinstance(value, dict):
        return {key: _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


# =============================================================================
# 4. The screen
# =============================================================================


def _editor_config() -> dict[str, Any]:
    """Everything `admin.js` needs to build the editor, from the field contract.

    The field list, its groups and its vocabularies come from `admin/schema.py`
    (consumer 4 of 4). Nothing about the contract is retyped in JavaScript: a
    field added there appears in the editor, and a field removed there
    disappears from it.
    """
    # A LIST, not a dict. Jinja's `tojson` sorts object keys, so a dict would
    # reach the browser in alphabetical order and the editor would render
    # `ownership_source` above `parent_company` and the rest of every group out
    # of SCHEMA.md §2's order. A list keeps the contract's order.
    fields: list[dict[str, Any]] = []
    for group, _title in schema.GROUPS:
        for name, spec in schema.fields_in_group(group):
            fields.append(
                {
                    "name": name,
                    "group": spec["group"],
                    "label": spec["label"],
                    "widget": spec["widget"],
                    "required": bool(spec.get("required")),
                    "help": spec.get("help", ""),
                    "values": list(spec.get("values", ())),
                }
            )
    return {
        "groups": [{"key": key, "title": title} for key, title in schema.GROUPS],
        "fields": fields,
        "summaryMax": SUMMARY_MAX_CHARS,
        "faqMax": FAQ_MAX_ITEMS,
        "undoSeconds": UNDO_CLIENT_SECONDS,
        "practiceKeys": schema.options_for("practice", PRACTICE_KEYS),
        "logisticsKeys": schema.options_for("logistics", LOGISTICS_KEYS),
        "options": {
            "category": schema.options_for("category", CATEGORIES),
            "cellar_door": schema.options_for("cellar-door", CELLAR_DOOR_STATES),
            "certification": schema.options_for("certification", CERTIFICATION_STATES),
            "fruit_source": schema.options_for("fruit-source", FRUIT_SOURCE),
            "production_band": schema.options_for("production-band", PRODUCTION_BANDS),
            "state": schema.options_for("state", STATES),
            "vessels": schema.options_for("vessel", VESSEL_KEYS),
            "varieties": schema.options_for("variety", VARIETY_KEYS),
            "wine_styles": schema.options_for("wine-style", WINE_STYLE_KEYS),
            "ownership_method": schema.options_for(
                "ownership-evidence", OWNERSHIP_EVIDENCE_METHODS
            ),
            "regions": [
                {"value": slug, "label": schema.region_name(slug)}
                for slug in schema.REGION_SLUGS
            ],
            "subregions": [
                {
                    "value": slug,
                    "label": schema.subregion_name(slug),
                    "region": schema.SUBREGION_PARENT[slug],
                }
                for slug in schema.SUBREGION_SLUGS
            ],
        },
    }


@app.get("/", response_class=HTMLResponse)
async def hub(request: Request, _: None = Depends(require_auth)) -> HTMLResponse:
    rows = staging.queue_rows()
    ownership_updated = ""
    if OWNERSHIP_JSON_PATH.is_file():
        try:
            ownership_updated = str(
                json.loads(OWNERSHIP_JSON_PATH.read_text(encoding="utf-8")).get("updated", "")
            )
        except (OSError, json.JSONDecodeError):
            ownership_updated = ""

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "site_name": SITE_NAME,
            "site_url": SITE_URL,
            "rows": rows,
            "counts": staging.queue_counts(rows),
            "queue_summary": QUEUE.summary(),
            "queue_items": QUEUE.items,
            "batch_max": BATCH_MAX_URLS,
            "reject_reasons": staging.REJECT_REASONS,
            "ownership_updated": ownership_updated,
            "published_count": (
                len(list(PUBLISHED_DIR.glob("*.mdx"))) if PUBLISHED_DIR.is_dir() else 0
            ),
            # Rendered server-side so the strip carries its status on first
            # paint rather than after a fetch (UX.md §1.6: always visible).
            "deploy": deploy_module.status_summary(),
            "editor_config": _editor_config(),
        },
    )


def _derived_hints(data: dict[str, Any]) -> dict[str, Any]:
    """The two figures the editor displays beside an input rather than computes.

    Both live in Python: the dollar-amount regex is shared with `/validate`
    check 10 (SCHEMA.md §2a rule 8, one regex one home), and the band ranges are
    a config constant. The admin's JavaScript displays them and reimplements
    neither.
    """
    return {
        "cost_amounts": schema.dollar_amounts(data.get("cost")),
        "implied_band": schema.band_for_cases(data.get("annual_production_cases")),
    }


def _ownership_panel(slug: str) -> dict[str, Any] | None:
    """The determination as the review pane renders it (UX.md §1.4.1 to §1.4.3).

    Returns `None` when no determination exists, which the pane renders as its
    own state rather than as an empty `clear` panel. A draft with no
    determination is not a clean draft; it is one nothing has looked at.
    """
    sidecar = ownership.read_sidecar(slug)
    if not sidecar:
        return None
    signals = sidecar.get("signals") or []
    # Amended 2026-08-07 (UX.md §1.4.2): the pane must say which rows hold the
    # entry and which are recorded as evidence, or a reviewer cannot tell why a
    # populated row carries no obligation. Computed here, beside the rule.
    escalating = {row["key"] for row in ownership.escalating_signals(signals)}
    return {
        **sidecar,
        "chip": ownership.chip_for(sidecar),
        "unresolved": len(ownership.unresolved_signals(signals)),
        "populated": len(ownership.populated_signals(signals)),
        "escalating_keys": sorted(escalating),
        "flagged_statements": ownership.statements_name_a_group(signals),
        "unresolved_hits": len(
            ownership.unresolved_hits(sidecar.get("hits_to_resolve") or [])
        ),
        # Display helpers live in Python beside the normalisers they depend on.
        # The admin's JavaScript renders them and reimplements neither.
        "abn_display": {
            row["key"]: {
                "formatted": [ownership.format_abn(item) for item in row["items"]],
                "lookup": [ownership.abr_lookup_url(item) for item in row["items"]],
            }
            for row in signals
            if row.get("key") == "abn"
        },
        "resolutions": [
            {
                "value": value,
                "label": ownership.RESOLUTION_LABELS[value],
                "note_required": value in ownership.RESOLUTIONS_REQUIRING_NOTE,
            }
            for value in ownership.RESOLUTIONS
        ],
        "signal_labels": dict(ownership.SIGNAL_LABELS),
        "check_labels": ownership.CHECK_LABELS,
    }


@app.get("/api/queue")
async def api_queue(_: None = Depends(require_auth)) -> JSONResponse:
    rows = staging.queue_rows()
    return JSONResponse({"rows": rows, "counts": staging.queue_counts(rows)})


@app.get("/api/draft/{slug}")
async def api_draft(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    try:
        data, body = staging.load_draft(slug)
    except schema.FrontmatterError as exc:
        return JSONResponse({"slug": slug, "unreadable": str(exc)}, status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{slug} is not in the staging queue") from None

    return JSONResponse(
        {
            "slug": slug,
            "frontmatter": _json_safe(data),
            "body": body,
            "errors": schema.validate_frontmatter(data),
            "ownership_blocks": staging.ownership_gate(slug, data),
            "ownership_chip": staging.ownership_chip(slug),
            "ownership": _ownership_panel(slug),
            "flags": staging.flags_for(data, body),
            "duplicate": staging.duplicate_of(slug, data),
            "words": mdx_preview.prose_word_count(body),
            **_derived_hints(data),
        }
    )


@app.put("/api/draft/{slug}")
async def api_save(slug: str, request: Request, _: None = Depends(require_auth)) -> JSONResponse:
    """Debounced autosave. A save that fails says so; it never fails silently."""
    payload = await request.json()
    frontmatter = payload.get("frontmatter")
    if not isinstance(frontmatter, dict):
        raise HTTPException(status_code=400, detail="frontmatter must be an object")
    body = payload.get("body")
    if body is None:
        _, body = staging.load_draft(slug)
    try:
        staging.save_draft(slug, frontmatter, str(body))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"save failed: {exc}") from exc

    data, body_text = staging.load_draft(slug)
    return JSONResponse(
        {
            "saved": datetime.now().strftime("%H:%M"),
            "errors": schema.validate_frontmatter(data),
            "ownership_blocks": staging.ownership_gate(slug, data),
            "flags": staging.flags_for(data, body_text),
            "words": mdx_preview.prose_word_count(body_text),
            **_derived_hints(data),
        }
    )


@app.put("/api/draft/{slug}/ownership")
async def api_save_ownership(
    slug: str, request: Request, _: None = Depends(require_auth)
) -> JSONResponse:
    """Record signal resolutions and the conflict note onto the sidecar.

    **The verdict is never editable** (UX.md §1.4.5 rule 4). This route accepts
    resolutions, notes and the conflict note, and nothing else — a payload
    carrying a `verdict` is rejected rather than ignored, because silently
    dropping it would let a caller believe it had set one. CLAUDE.md rule 8 in
    interface form: there is no control anywhere in this hub that sets the
    verdict by hand.
    """
    sidecar = ownership.read_sidecar(slug)
    if sidecar is None:
        raise HTTPException(status_code=404, detail=f"{slug} has no ownership determination")

    payload = await request.json()
    if "verdict" in payload:
        raise HTTPException(
            status_code=400,
            detail=(
                "the verdict is never editable (UX.md §1.4.5 rule 4). Record "
                "evidence and resolutions; the gate is then satisfied or it is not."
            ),
        )

    submitted = payload.get("resolutions")
    if submitted is not None:
        if not isinstance(submitted, dict):
            raise HTTPException(status_code=400, detail="resolutions must be an object")
        # Signal rows and deny-list hit rows share one keyspace and one control,
        # so a reviewer resolves both the same way.
        rows = (sidecar.get("signals") or []) + (sidecar.get("hits_to_resolve") or [])
        for row in rows:
            if row.get("key") not in submitted:
                continue
            entry = submitted[row["key"]] or {}
            resolution = str(entry.get("resolution") or "").strip()
            if resolution and resolution not in ownership.RESOLUTIONS:
                raise HTTPException(
                    status_code=400, detail=f"unknown resolution {resolution!r}"
                )
            row["resolution"] = resolution or None
            row["note"] = str(entry.get("note") or "").strip()

    if "conflict_note" in payload:
        # UX.md §1.4.2: written to the sidecar's confidence_notes and surfaced
        # on every later visit to this draft. It is not published frontmatter.
        note = str(payload.get("conflict_note") or "").strip()
        notes = [
            line
            for line in (sidecar.get("confidence_notes") or [])
            if not str(line).startswith("Conflict noted:")
        ]
        if note:
            notes.append(f"Conflict noted: {note}")
        sidecar["confidence_notes"] = notes

    ownership.write_sidecar(slug, sidecar)
    try:
        data, _body = staging.load_draft(slug)
    except (schema.FrontmatterError, FileNotFoundError):
        data = {}
    return JSONResponse(
        {
            "saved": datetime.now().strftime("%H:%M"),
            "ownership": _ownership_panel(slug),
            "ownership_chip": staging.ownership_chip(slug),
            "ownership_blocks": staging.ownership_gate(slug, data),
        }
    )


@app.get("/preview/{slug}", response_class=HTMLResponse)
async def preview(slug: str, _: None = Depends(require_auth)) -> HTMLResponse:
    """The draft in the public site's real styles, for the review pane iframe."""
    try:
        data, body = staging.load_draft(slug)
    except (schema.FrontmatterError, FileNotFoundError) as exc:
        return HTMLResponse(
            f"<!doctype html><meta charset='utf-8'><body style='font:14px system-ui;padding:2rem'>"
            f"<p>This draft cannot be rendered: {exc}</p></body>",
            status_code=200,
        )
    return HTMLResponse(mdx_preview.render_document(data, body))


# =============================================================================
# 5. The actions
# =============================================================================


def _action_response(result: dict[str, Any]) -> JSONResponse:
    rows = staging.queue_rows()
    return JSONResponse({**result, "rows": rows, "counts": staging.queue_counts(rows)})


@app.post("/api/draft/{slug}/approve")
async def api_approve(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    try:
        return _action_response(staging.approve(slug, log))
    except staging.ActionBlocked as exc:
        return JSONResponse(
            {"blocked": str(exc), "errors": exc.errors, "ownership_blocks": exc.blocks},
            status_code=422,
        )


@app.post("/api/draft/{slug}/reject")
async def api_reject(slug: str, request: Request, _: None = Depends(require_auth)) -> JSONResponse:
    payload = await request.json()
    try:
        return _action_response(staging.reject(slug, str(payload.get("reason", "")), log))
    except staging.ActionBlocked as exc:
        return JSONResponse({"blocked": str(exc)}, status_code=422)


@app.post("/api/draft/{slug}/undo")
async def api_undo(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    try:
        return _action_response(staging.undo(slug, log))
    except staging.ActionBlocked as exc:
        # UX.md §1.5 row 17: say so, and offer Unpublish rather than pretend.
        return JSONResponse({"blocked": str(exc), "offer_unpublish": True}, status_code=409)


@app.post("/api/draft/{slug}/unpublish")
async def api_unpublish(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    try:
        return _action_response(staging.unpublish(slug, log))
    except staging.ActionBlocked as exc:
        return JSONResponse({"blocked": str(exc)}, status_code=422)


@app.post("/api/draft/{slug}/geocode")
async def api_regeocode(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    """Repair the coordinates on a staged or published entry (UX.md §1.5 row 10).

    Runs in a thread: `geocode` enforces Nominatim's one-request-per-second
    policy with a blocking sleep, which must not stall the event loop.
    """
    try:
        result = await asyncio.to_thread(staging.regeocode, slug, log)
    except staging.ActionBlocked as exc:
        return JSONResponse({"blocked": str(exc)}, status_code=422)
    if not result["found"]:
        return JSONResponse(
            {
                "found": False,
                "detail": (
                    f"No coordinates found for {result['query']}. The entry is "
                    f"unchanged and still publishes without a map pin."
                ),
            }
        )
    return _action_response(result)


# =============================================================================
# 6. Harvest
# =============================================================================


@app.post("/api/harvest")
async def api_harvest(request: Request, _: None = Depends(require_auth)) -> JSONResponse:
    """Single URL and batch share one runner (UX.md §1.1)."""
    payload = await request.json()
    raw = payload.get("urls") or payload.get("url") or ""
    if not isinstance(raw, str):
        raw = "\n".join(str(line) for line in raw)

    valid, ignored = queue_module.parse_urls(raw)
    submitted = len([line for line in raw.splitlines() if line.strip()])
    over = max(submitted - ignored - len(valid), 0)

    notes: list[str] = []
    if ignored:
        notes.append(f"{ignored} line{'s' if ignored != 1 else ''} ignored: not URLs")
    if over:
        notes.append(f"{over} beyond the {BATCH_MAX_URLS} URL cap were not queued")
    for note in notes:
        log("warn", note)

    if valid:
        QUEUE.add(valid)
        log("info", f"queued {len(valid)} URL{'s' if len(valid) != 1 else ''}")
        _start_runner()
    return JSONResponse(
        {"queued": len(valid), "notes": notes, "items": QUEUE.items, "summary": QUEUE.summary()}
    )


@app.post("/api/harvest/playwright")
async def api_harvest_playwright(
    request: Request, _: None = Depends(require_auth)
) -> JSONResponse:
    """UX.md §1.5 rows 3 and 1a. The ONLY path that reaches Playwright.

    User-triggered per URL, never automatic (CLAUDE.md stack constraints). The
    row must actually be offering it, which means the item either ended thin
    (row 3) or was refused with a status a browser can clear (row 1a). This is
    not a general "fetch harder" button, and offering it anywhere else would
    make a headless browser the default way this project reads a website.

    The refusing branch stays authoritative: `offer_playwright` is cleared on
    the item before the run starts, so a page that blocks Playwright too ends
    FAILED without offering the same button again.
    """
    payload = await request.json()
    url = str(payload.get("url") or "").strip()
    item = next((row for row in QUEUE.items if row["url"] == url), None)
    if item is None or not item.get("offer_playwright"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Playwright is offered only on an item that ended with a thin "
                "extraction, or that the site refused with a 403 or 503"
            ),
        )
    if QUEUE.running:
        raise HTTPException(status_code=409, detail="a harvest is already running")

    item.update(state="RUNNING", detail="", offer_playwright=False)
    QUEUE.save()

    def run() -> None:
        try:
            fetched = fetcher.fetch(url, log=log, use_playwright=True)
        except Exception as exc:  # noqa: BLE001
            log("error", f"Playwright fetch failed: {exc}")
            item.update(state="FAILED", detail=f"playwright: {exc}")
            QUEUE.save()
            return
        result = harvest_module.harvest_one(url, log=log, fetched=fetched)
        item.update(
            state=result.state,
            detail=result.detail,
            slug=result.slug,
            offer_playwright=result.offer_playwright,
        )
        QUEUE.save()

    asyncio.create_task(asyncio.to_thread(run))
    return JSONResponse({"items": QUEUE.items, "summary": QUEUE.summary()})


@app.get("/api/harvest/queue")
async def api_harvest_queue(_: None = Depends(require_auth)) -> JSONResponse:
    return JSONResponse({"items": QUEUE.items, "summary": QUEUE.summary(), "paused": QUEUE.paused})


@app.post("/api/harvest/control/{action}")
async def api_harvest_control(action: str, _: None = Depends(require_auth)) -> JSONResponse:
    if action == "pause":
        QUEUE.pause()
        log("info", "queue will pause after the current item")
    elif action == "resume":
        QUEUE.cancelled = False
        QUEUE.resume()
        log("info", "queue resumed")
        _start_runner()
    elif action == "retry-failed":
        # BLOCKED rows are left alone: a block is a determination, not a
        # transient error (UX.md §1.1).
        retried = QUEUE.retry_failed()
        log("info", f"requeued {retried} failed URL(s)")
        _start_runner()
    elif action == "clear-finished":
        QUEUE.clear_finished()
    elif action == "cancel":
        QUEUE.cancel()
        log("warn", "queue cancelled after the current item")
    else:
        raise HTTPException(status_code=404, detail=f"no such queue control: {action}")
    return JSONResponse({"items": QUEUE.items, "summary": QUEUE.summary(), "paused": QUEUE.paused})


# =============================================================================
# 7. The log stream and the deny-list viewer
# =============================================================================


@app.get("/events")
async def events(request: Request, _: None = Depends(require_auth)) -> StreamingResponse:
    """SSE. The client falls back to polling `/api/log` if this drops."""
    queue = BUS.subscribe()
    replay = list(BUS.lines)

    async def stream():
        try:
            for line in replay:
                yield f"data: {json.dumps(line)}\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(line)}\n\n"
        finally:
            BUS.subscribers.discard(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/log")
async def api_log(_: None = Depends(require_auth)) -> JSONResponse:
    return JSONResponse({"lines": BUS.lines})


@app.get("/api/ownership")
async def api_ownership(_: None = Depends(require_auth)) -> JSONResponse:
    """Read-only. The hub never edits `data/ownership.json` (UX.md §1.4.5 rule 7)."""
    if not OWNERSHIP_JSON_PATH.is_file():
        raise HTTPException(status_code=404, detail="data/ownership.json is not present")
    return JSONResponse(json.loads(OWNERSHIP_JSON_PATH.read_text(encoding="utf-8")))


# =============================================================================
# 8. The Blocked list — UX.md §1.4.4
#
# An `independence: reject` aborts the run before a draft is written, and no
# file lands in `_staging/`. That is correct behaviour, and it still needs an
# on-screen state, because an abort a reviewer cannot see is a silent failure.
#
# Blocked records are never deleted. They are the record of what the site
# refused and why.
# =============================================================================


@app.get("/api/blocked")
async def api_blocked(_: None = Depends(require_auth)) -> JSONResponse:
    return JSONResponse({"rows": ownership.blocked_rows()})


@app.get("/api/blocked/{slug}")
async def api_blocked_record(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    """The same signals table and deny-list block the review pane uses, read-only."""
    record = ownership.read_blocked(slug)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no blocked record for {slug}")
    return JSONResponse(record)


@app.post("/api/blocked/{slug}/reharvest")
async def api_blocked_reharvest(
    slug: str, request: Request, _: None = Depends(require_auth)
) -> JSONResponse:
    """The two re-harvest actions, which differ by the source of the reject.

    **Deny-list reject** — `reharvest` only. There is no override action, in
    this route or anywhere else: the only route is to correct
    `data/ownership.json`, and the re-harvest then runs the URL again from
    scratch so the corrected deny-list is what decides. The interface never
    lets a click overrule the deny-list, because the deny-list is the artefact
    `/validate` check 8 audits against.

    **Harvester signal reject** — `reharvest-as-check` as well, which re-runs
    the URL with the machine verdict floored at `check` so the draft enters the
    queue with every `check` rule applying. It downgrades a machine abort to a
    human decision. It never skips the human decision.
    """
    record = ownership.read_blocked(slug)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no blocked record for {slug}")

    payload = await request.json()
    action = str(payload.get("action") or "reharvest")
    if action not in ("reharvest", "reharvest-as-check"):
        raise HTTPException(status_code=400, detail=f"no such action: {action}")

    if action == "reharvest-as-check" and record.get("source_of_reject") != "harvester":
        raise HTTPException(
            status_code=409,
            detail=(
                "this was a deny-list reject. There is no override in the "
                "interface; correct data/ownership.json and re-harvest "
                "(UX.md §1.4.4)."
            ),
        )

    ownership.record_reharvest(slug, action)
    url = str(record.get("url") or "")
    QUEUE.add([url])
    if action == "reharvest-as-check":
        QUEUE.floors[url] = "check"
        QUEUE.save()
        log("warn", f"re-harvesting {url} with the machine verdict floored at check")
    else:
        log("info", f"re-harvesting {url} against the current deny-list")
    _start_runner()
    return JSONResponse(
        {"queued": url, "action": action, "rows": ownership.blocked_rows()}
    )


@app.on_event("startup")
async def _startup() -> None:
    """Reattach to whatever the last process was doing.

    UX.md §1.1: "Reopening the hub reattaches to the running job and replays the
    log buffer for the current item." A restart mid-batch must not lose the
    other thirty-nine URLs.
    """
    BUS.loop = asyncio.get_running_loop()
    QUEUE.load()
    outstanding = sum(1 for item in QUEUE.items if item["state"] == "QUEUED")
    if outstanding:
        log("info", f"reattached to a queue with {outstanding} URL(s) still to run")
        if not QUEUE.paused:
            _start_runner()


# =============================================================================
# 8. Images — UX.md §4
#
# Publishing an image is a separate deliberate action from approving the prose,
# and it is one write: the three frontmatter fields AND the body tag.
# =============================================================================


@app.get("/api/draft/{slug}/images")
async def api_images(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    """The candidate strip. Each entry carries its source URL as visible text."""
    manifest = images.read_manifest(slug)
    data = None
    try:
        data, _body = staging.load_draft(slug)
    except Exception:  # noqa: BLE001 - a published producer has no staged draft
        data = None
    return JSONResponse(
        {
            "images": manifest.get("images", []),
            "suggested_caption": images.suggest_caption(data or {}),
            "published": bool((data or {}).get("image")),
        }
    )


@app.get("/api/draft/{slug}/images/{filename}")
async def api_image_file(
    slug: str, filename: str, _: None = Depends(require_auth)
) -> Any:
    """Serve one candidate thumbnail out of gitignored temp_data."""
    from fastapi.responses import FileResponse

    # A candidate name is generated by the pipeline as `NN.ext`; anything else
    # is not ours and must not be used to walk out of the directory.
    if not re.fullmatch(r"[0-9]{2}\.[a-z]{3,4}", filename):
        raise HTTPException(status_code=404, detail="no such candidate image")
    path = images.candidate_dir(slug) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no such candidate image")
    return FileResponse(path)


@app.post("/api/draft/{slug}/image")
async def api_publish_image(
    slug: str, request: Request, _: None = Depends(require_auth)
) -> JSONResponse:
    """UX.md §4 step 3. One action: resize, three fields, and the body tag.

    Blocked while the ownership determination is unresolved (UX.md §4 step 7).
    Approve is blocked in that state anyway; stating it here closes the path
    where an image is published to a draft that then never publishes.
    """
    payload = await request.json()
    filename = str(payload.get("file") or "")
    caption = str(payload.get("caption") or "").strip()
    alt = str(payload.get("alt") or "").strip()

    try:
        data, _body = staging.load_draft(slug)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"no staged draft for {slug}") from exc

    blocks = ownership.approval_blocks(data, ownership.read_sidecar(slug))
    if blocks:
        raise HTTPException(
            status_code=409,
            detail="the ownership determination is unresolved: " + "; ".join(blocks),
        )

    try:
        result = images.publish_image(
            slug, filename, caption=caption, alt=alt, log=log
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(result)


@app.delete("/api/draft/{slug}/image")
async def api_remove_image(slug: str, _: None = Depends(require_auth)) -> JSONResponse:
    """UX.md §4 step 4. The exact reverse, staged or published, one action."""
    try:
        result = images.remove_image(slug, log=log)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    staging._rebuild_derived(log)
    return JSONResponse(result)


# =============================================================================
# 9. Deploy — UX.md §1.6, TRD.md §6.5
#
# The only path from disk to live. Every write in this system stops at "updated
# on disk" and waits for a human to click Deploy (TRD.md §2.4): there is no
# automatic push path in this build and none is to be added.
#
# The run streams into the same log pane as everything else, so the POST returns
# as soon as the thread is dispatched. A Netlify poll can take six minutes and a
# request that waited for it would look like a hung browser, which is the
# spinner UX.md §1.2 forbids.
# =============================================================================


@app.get("/api/deploy")
async def api_deploy_status(_: None = Depends(require_auth)) -> JSONResponse:
    return JSONResponse(deploy_module.status_summary())


@app.get("/api/deploy/preview")
async def api_deploy_preview(_: None = Depends(require_auth)) -> JSONResponse:
    """The exact file list to be committed, with the change type per file."""
    return JSONResponse(deploy_module.preview_payload())


@app.post("/api/deploy")
async def api_deploy(request: Request, _: None = Depends(require_auth)) -> JSONResponse:
    """Start the deploy. One lock, so no two paths can race a push."""
    payload = await request.json()
    message = str(payload.get("message") or "")

    if not deploy_module.DEPLOY_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a deploy is already running")

    def run() -> None:
        try:
            for line in deploy_module.run_deploy(message):
                log(line.level, line.text)
        except Exception as exc:  # noqa: BLE001 - a crash here must still be visible
            log("error", f"deploy failed: {exc}")
            _logger.exception("deploy crashed")
        finally:
            deploy_module.DEPLOY_LOCK.release()

    asyncio.create_task(asyncio.to_thread(run))
    return JSONResponse({"started": True}, status_code=202)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"ok": True, "staged": len(staging.queue_rows())})
