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
import re
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
    STATIC_DIR,
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


#: Where a harvested draft sits now (UX.md §1.1, amended 2026-08-13), in the
#: order `draft_location` tests them.
DRAFT_LOCATIONS = ("staging", "published", "rejected", "gone")


def draft_location(slug: str) -> str:
    """One of `DRAFT_LOCATIONS`, for a slug the harvest reported as `STAGED`.

    A `STAGED` queue row records what the harvest did and is history, exactly
    like a `BLOCKED` one. Where the draft went afterwards is a separate and
    perishable fact, and the row used to assert the stale half of it: the queue
    survives restarts while the draft leaves `_staging/` on the first approve,
    so the row went on offering a link to a review-queue row that had gone.

    Resolved on read and never stored. `harvest_queue.json` holds URLs and
    per-URL status only, and a cached location would be one more thing that
    goes stale between an approve and the next render, which is the whole
    defect this answers.

    Staging is tested first because `undo` moves a file back into it: a draft
    approved and then un-approved inside the window is in the review queue
    again, and the newest true answer is the one to report.
    """
    if not slug:
        return "gone"
    if (STAGING_DIR / f"{slug}.mdx").is_file():
        return "staging"
    if (PUBLISHED_DIR / f"{slug}.mdx").is_file():
        return "published"
    if (REJECTED_DIR / f"{slug}.mdx").is_file():
        return "rejected"
    return "gone"


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


#: Lint categories that are absolute bans, and therefore block approval.
#:
#: Added 2026-08-09 (Gate 8). Every list here is enumerated in
#: `PROMPTS/gatekeeper.md` and matched deterministically by check 6, so a model
#: is the wrong thing to enforce them with: the Gatekeeper passed a draft using
#: `curated` twice, which is ban 1 in `PROMPTS/architect.md` and a plain string
#: match. A regex that already scores 100% costs nothing to run at the gate.
#:
#: `conditional claim` is deliberately ABSENT. Those four phrases —
#: `single-vineyard`, `old vines`, `family-owned`, `award-winning` — are
#: conditional by definition: each is permitted when the entry states its
#: evidence, which only a reader can confirm. Of thirteen hits across one real
#: batch, seven were entries correctly naming the owning family or attributing
#: the claim and flagging the gap. Blocking those would train a reviewer to
#: override the gate, which is worse than not having one.
#: `US spelling` was in this tuple for one afternoon and came out on evidence.
#: Run against 85 real drafts it blocked six on `program`, and the six were not
#: one thing:
#:
#:   * `the Life After Racing program` — a PROPER NOUN, the name of a real
#:     scheme. "Correcting" it would misstate a named thing, which is a worse
#:     error than the one being prevented;
#:   * `an event program` — a genuine breach of the house rule;
#:   * `a Cabernet-led red program`, `a referral program`, `a membership
#:     program` — senses the house rule does not reach. gatekeeper.md's own
#:     prose under the list says `program` stays `program` for software and a
#:     programme of events is a `programme`, which is a judgement about sense
#:     that a string match cannot make.
#:
#: So it stays a check 6 warning, where a human judges it, and the gate keeps
#: only categories where the match is the fault. The distinction this tuple is
#: drawing is not "how serious" but "can a regex be sure".
BLOCKING_LINT_KINDS = (
    "banned word",
    "hedge",
    "tasting descriptor",
    "first-person visit tell",
    "not-X-but-Y",
    "project vocabulary",
    "em dash",
)


def editorial_gate(body: str, data: dict[str, Any]) -> list[str]:
    """What blocks approval on editorial grounds. Empty means the gate is open.

    Lints the body plus the two other places a reader sees prose — `summary`
    and the FAQ answers — because check 6 covers all three and a ban that
    applied only to the body would let `curated` publish in a summary.
    """
    from admin.pipeline import validate_register

    parts = [body, str(data.get("summary") or "")]
    for pair in data.get("faq") or []:
        if isinstance(pair, dict):
            parts.append(str(pair.get("question") or ""))
            parts.append(str(pair.get("answer") or ""))

    blocks: list[str] = []
    for hit in validate_register.lint_text("\n".join(parts)):
        if hit["kind"] in BLOCKING_LINT_KINDS:
            blocks.append(
                f"{hit['kind']}: {hit['phrase']!r} — {hit['excerpt'][:70]}"
            )
    return blocks


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
    2a. assert the editorial gate; an absolute ban blocks with the phrase named,
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

    editorial = editorial_gate(body, data)
    if editorial:
        log("error", f"approve blocked by the editorial gate: {'; '.join(editorial)}")
        raise ActionBlocked("the editorial gate is not satisfied", blocks=editorial)

    target = PUBLISHED_DIR / f"{slug}.mdx"
    target.parent.mkdir(parents=True, exist_ok=True)
    # A re-approve overwrites a published file. Keep the bytes so undo restores
    # what was there rather than leaving a hole where an entry used to be.
    previous = target.read_bytes() if target.is_file() else None
    shutil.move(str(source), str(target))
    log("info", f"published {slug} to _published/{slug}.mdx")

    sidecar = ownership.sidecar_path(slug, STAGING_DIR)
    determination = ownership.sidecar_path(slug, DETERMINATIONS_DIR)
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
                str(ownership.sidecar_path(slug, DETERMINATIONS_DIR)),
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


def regeocode(slug: str, log: Logger = _null_log) -> dict[str, Any]:
    """Look the address up again and write the coordinates onto a published entry.

    *Gate 5.* Null coordinates never block a publish (SCHEMA.md §2, UX.md §1.5
    row 10) and `geocode.geocode` never raises, so a geocoder that is refusing
    requests is completely silent: producers simply publish without a map pin.
    Basket Range Wine published that way on 2026-08-07 with a placeholder
    `GEOCODER_USER_AGENT` in `.env`, and there was no way to repair it short of
    re-running the whole URL through three paid agent calls to fix two numbers.

    This is that repair. It touches `location.latitude` and `location.longitude`
    and nothing else: no agent runs, no prose changes, no determination is
    re-made. A miss is reported and leaves the entry exactly as it was, because
    a producer with no pin is a first-class entry and not a failure state.

    Runs against a staged draft or a published entry, whichever holds the slug.
    The cache is bypassed deliberately: the caller is here because the last
    answer was wrong, and a cached miss would return the same wrong answer.
    """
    from admin.pipeline import geocode  # local: keeps the geocoder off the import path

    # Staging first, then published — the same posture as
    # `ownership.determination_for`. Most misses are caught at review time,
    # before the entry publishes, and a reviewer looking at a draft with no pin
    # should not have to publish it first to fix it.
    path = STAGING_DIR / f"{slug}.mdx"
    published = path.is_file() is False
    if published:
        path = PUBLISHED_DIR / f"{slug}.mdx"
    if not path.is_file():
        raise ActionBlocked(f"{slug} is neither staged nor published")

    try:
        data, body = schema.read_mdx(path)
    except schema.FrontmatterError as exc:
        raise ActionBlocked(f"{slug} could not be read: {exc}") from exc

    location = data.get("location") or {}
    query = geocode.build_query(location)
    if not query:
        raise ActionBlocked(
            f"{slug} has no address or suburb to geocode. A label-only producer "
            f"has nowhere to put a pin, which is a first-class entry, not a fault."
        )

    log("info", f"geocoding {slug}: {query}")
    latitude, longitude = geocode.geocode(location, log=log, use_cache=False)
    if latitude is None or longitude is None:
        # The warning naming the cause has already gone to the log from
        # `geocode`. Do not overwrite good coordinates with nulls on a miss.
        return {"slug": slug, "found": False, "query": query}

    before = (location.get("latitude"), location.get("longitude"))
    data["location"] = {**location, "latitude": latitude, "longitude": longitude}
    schema.write_mdx(path, data, body)
    log(
        "info",
        f"{slug}: {before[0]}, {before[1]} -> {latitude}, {longitude}",
    )
    # Only a published entry is in the derived data. Rebuilding for a draft
    # would be a no-op that reads as though something happened.
    if published:
        _rebuild_derived(log)
    return {
        "slug": slug,
        "found": True,
        "query": query,
        "latitude": latitude,
        "longitude": longitude,
    }


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


def _selftest_locations() -> list[str]:
    """`draft_location` must name all four whereabouts, and the JS must too.

    Written with the fix for the engagement of 2026-08-13 (second), where a
    `STAGED` queue row went on offering a link to a review-queue row that had
    been approved away days earlier, and the click did nothing at all.

    The case that earns its keep is the fifth: a slug in `_staging` **and** in
    `_published` is an approve that was undone inside the window, and it must
    read `staging`. Get that precedence backwards and the one draft a reviewer
    is actively working on is the one whose link disappears.
    """
    import tempfile

    errors: list[str] = []
    globals_ = globals()
    saved = {name: globals_[name] for name in ("STAGING_DIR", "PUBLISHED_DIR", "REJECTED_DIR")}

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        for name, sub in (
            ("STAGING_DIR", "_staging"),
            ("PUBLISHED_DIR", "_published"),
            ("REJECTED_DIR", "_rejected"),
        ):
            globals_[name] = root / sub
            globals_[name].mkdir()
        try:
            (globals_["STAGING_DIR"] / "in-the-queue.mdx").write_text("x", encoding="utf-8")
            (globals_["PUBLISHED_DIR"] / "approved.mdx").write_text("x", encoding="utf-8")
            (globals_["REJECTED_DIR"] / "refused.mdx").write_text("x", encoding="utf-8")
            # An approve taken back inside the undo window: the file is in both.
            (globals_["STAGING_DIR"] / "undone.mdx").write_text("x", encoding="utf-8")
            (globals_["PUBLISHED_DIR"] / "undone.mdx").write_text("x", encoding="utf-8")

            for slug, expected in (
                ("in-the-queue", "staging"),
                ("approved", "published"),
                ("refused", "rejected"),
                ("harvested-then-deleted", "gone"),
                ("undone", "staging"),
                ("", "gone"),
            ):
                found = draft_location(slug)
                if found != expected:
                    errors.append(
                        f"draft_location({slug!r}) is {found!r}, expected {expected!r}"
                    )
                if found not in DRAFT_LOCATIONS:
                    errors.append(f"draft_location({slug!r}) returned {found!r}, off the vocabulary")
        finally:
            globals_.update(saved)

    # The row is rendered by admin.js, which maps every whereabouts except
    # `staging` to words. `staging` draws the link instead, so it has no label.
    # A value added here and not there would render its own enum name at a
    # reviewer, which is the four-surface lesson in miniature.
    source = (STATIC_DIR / "admin.js").read_text(encoding="utf-8")
    block = re.search(r"const LOCATED_WORDS = \{(.*?)\};", source, re.DOTALL)
    if block is None:
        errors.append("admin.js has no LOCATED_WORDS map")
    else:
        labelled = set(re.findall(r"^\s*(\w+):", block.group(1), re.MULTILINE))
        expected = set(DRAFT_LOCATIONS) - {"staging"}
        for missing in sorted(expected - labelled):
            errors.append(f"admin.js LOCATED_WORDS has no wording for {missing!r}")
        for extra in sorted(labelled - expected):
            errors.append(f"admin.js LOCATED_WORDS carries {extra!r}, not in DRAFT_LOCATIONS")
    return errors
