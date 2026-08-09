"""orchestrator.py — the Harvester JSON validator and the pipeline's own fields.

Gate 5. TRD.md §7.1, SCHEMA.md §5 and §6.

── THIS FILE IS ONE OF THE FOUR SCHEMA SURFACES ──────────────────────────────

CLAUDE.md rule 7. Any vocabulary change lands in all four consumers in the same
commit, name-matched:

    1. the zod schema                site/src/content/config.ts
    2. the SQLite DDL                admin/pipeline/data_store.py
    3. the Harvester JSON validator  THIS FILE
    4. the admin frontmatter editor  admin/schema.py

`/validate` check 13 diffs them and fails on disagreement. The `schema-change`
skill fires on any edit here. The constants below are the surface check 13
reads, which is why they are module-level tuples with declared meanings rather
than literals buried inside functions.

── What this module owns, and what it deliberately does not ──────────────────

It owns the *contract*: what a Harvester response must contain to be usable, and
which frontmatter fields the pipeline stamps rather than trusting an agent to
produce. It does not own the sequence — `harvest.py` runs that.

── Why determinations are re-imposed rather than trusted ─────────────────────

SCHEMA.md §6 and TRD.md §7.6 both say the Harvester's `determinations` are
re-imposed onto the finished frontmatter, and that it is "enforced rather than
trusted to survive two rewrite passes." That is the single most important thing
this file does. `organic: certified` is a labelling claim about a real business,
and the stage that decided it is the one that read the page. Two prose rewrites
sit between that decision and the file on disk, and neither of them is looking
at the source. So the extractor's finding is stamped back over whatever the
writers produced, every time.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date as date_type
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    CATEGORIES,
    CERTIFICATION_STATES,
    FRUIT_SOURCE,
    PRACTICE_KEYS,
    STATES,
    VARIETY_KEYS,
)
from admin import schema  # noqa: E402
from admin.pipeline import ownership as ownership_module  # noqa: E402
from admin.pipeline import verification as verification_module  # noqa: E402

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    pass


# =============================================================================
# 1. The Harvester contract — SCHEMA.md §5
# =============================================================================

#: SCHEMA.md §5, verbatim. Every key must be present for the response to be
#: usable. `confidence_notes` is required because its absence is indistinguishable
#: from "nothing to flag", and those are very different states.
HARVESTER_REQUIRED_KEYS = (
    "name",
    "website",
    "location",
    "regions",
    "category",
    "ownership_signals",
    "independence",
    "determinations",
    "facts",
    "confidence_notes",
)

#: SCHEMA.md §5's `ownership_signals`. Mirrors `ownership.SIGNAL_KEYS`, which is
#: the surface that renders them (UX.md §1.4.2).
HARVESTER_SIGNAL_KEYS = (
    "parent_company_mentions",
    "abn",
    "shared_address",
    "shared_contact_domain",
    "statements",
)

#: SCHEMA.md §5's `facts` buckets.
HARVESTER_FACT_KEYS = (
    "vineyard",
    "varieties",
    "winemaking",
    "tastings",
    "pricing",
    "hours",
    "setting",
    "history",
    "people",
    "other",
)

#: SCHEMA.md §4.5.
INDEPENDENCE_VERDICTS = ("clear", "check", "reject")

#: Full state names and the common long forms, to the `STATES` codes. Keys are
#: lower-cased with spaces and full stops stripped, so "South Australia",
#: "south australia" and "S.A." all land.
_STATE_NAMES = {
    "victoria": "VIC",
    "newsouthwales": "NSW",
    "queensland": "QLD",
    "southaustralia": "SA",
    "westernaustralia": "WA",
    "tasmania": "TAS",
    "northernterritory": "NT",
    "australiancapitalterritory": "ACT",
    "vic": "VIC",
    "nsw": "NSW",
    "qld": "QLD",
    "sa": "SA",
    "wa": "WA",
    "tas": "TAS",
    "nt": "NT",
    "act": "ACT",
}

#: SCHEMA.md §6: which frontmatter fields the Harvester's `determinations`
#: block owns outright. `determinations` key -> frontmatter field.
#:
#: CHECK 13 READS THIS. Every value must be a member of `schema.KNOWN_FIELDS`.
DETERMINATION_FIELDS = {
    "organic": "organic",
    "organic_certifier": "organic_certifier",
    "biodynamic": "biodynamic",
    "biodynamic_certifier": "biodynamic_certifier",
    "fruit_source": "fruit_source",
    "practices": "practices",
    "varieties": "varieties",
}

#: SCHEMA.md §6, the full list of fields the pipeline stamps after the
#: Gatekeeper returns. No agent's output survives in any of these.
#:
#: CHECK 13 READS THIS. Every entry must be a member of `schema.KNOWN_FIELDS`.
PIPELINE_OWNED_FIELDS = (
    "source_url",
    "website",
    "drafted",
    "verified",
    "organic",
    "organic_certifier",
    "biodynamic",
    "biodynamic_certifier",
    "fruit_source",
    "practices",
    "varieties",
    "location",
    "verification",
    "change_log",
    "parent_company",
    "ownership_status",
    "ownership_source",
)


class HarvesterJSONError(ValueError):
    """Fails the content tier. The message is appended to the one re-ask."""


def _validate_harvester_json(text: str) -> dict[str, Any]:
    """Parseability, object-ness, and every required key (TRD.md §7.1).

    Raises `HarvesterJSONError` (a `ValueError`), which is what
    `agents.call` catches to spend its single re-ask.

    Deliberately shallow beyond the key set. A missing key is a broken response
    and the model can fix it from the message; a *wrong value* inside a present
    key is a judgement the reviewer makes with the page in front of them, and
    re-asking for it would burn the retry on something the model already
    believes it got right.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HarvesterJSONError(f"response is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise HarvesterJSONError(
            f"response must be a JSON object, got {type(parsed).__name__}"
        )

    missing = [key for key in HARVESTER_REQUIRED_KEYS if key not in parsed]
    if missing:
        raise HarvesterJSONError(
            "response is missing required key(s): " + ", ".join(missing)
        )

    verdict = parsed.get("independence")
    if verdict not in INDEPENDENCE_VERDICTS:
        raise HarvesterJSONError(
            f"independence must be one of {', '.join(INDEPENDENCE_VERDICTS)}, "
            f"got {verdict!r}"
        )

    # Normalise the nested shapes so downstream code never guards for them.
    signals = parsed.get("ownership_signals")
    if not isinstance(signals, dict):
        raise HarvesterJSONError("ownership_signals must be an object")
    for key in HARVESTER_SIGNAL_KEYS:
        signals.setdefault(key, [] if key.endswith("s") else None)

    facts = parsed.get("facts")
    if not isinstance(facts, dict):
        raise HarvesterJSONError("facts must be an object")
    for key in HARVESTER_FACT_KEYS:
        facts.setdefault(key, [])

    determinations = parsed.get("determinations")
    if not isinstance(determinations, dict):
        raise HarvesterJSONError("determinations must be an object")
    practices = determinations.get("practices")
    if not isinstance(practices, dict):
        determinations["practices"] = {key: False for key in PRACTICE_KEYS}
    else:
        for key in PRACTICE_KEYS:
            practices.setdefault(key, False)

    if not isinstance(parsed.get("confidence_notes"), list):
        parsed["confidence_notes"] = []
    if not isinstance(parsed.get("regions"), list):
        parsed["regions"] = []
    if not isinstance(parsed.get("location"), dict):
        parsed["location"] = {}

    return parsed


# =============================================================================
# 2. The MDX contract, for the two prose stages
# =============================================================================


def _validate_mdx(text: str) -> tuple[dict[str, Any], str]:
    """Frontmatter must parse and the body must not be empty.

    Same shallowness rule as above: this is "did the agent return an MDX file",
    not "is this producer correct". Field-level validation is `admin.schema`'s
    job and it runs at approve time with a human present.
    """
    stripped = text.strip()
    if not stripped.startswith("---"):
        raise ValueError("output must begin with a `---` frontmatter fence")
    try:
        data, body = schema.parse_mdx_text(stripped)
    except schema.FrontmatterError as exc:
        raise ValueError(f"frontmatter did not parse: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("frontmatter is empty")
    if not body.strip():
        raise ValueError("body is empty")
    return data, body


# =============================================================================
# 3. Slug matching — UX.md §1.5 rows 11 and 12
#
# "Never silently dropped, because a silent drop is how a producer's actual
# varieties disappear."
# =============================================================================

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("'", "").replace("’", "")
    # Fold diacritics before the non-alphanumeric sweep. The §1 vocabularies
    # are ASCII slugs — `albarino`, `gewurztraminer`, `gruner-veltliner`,
    # `pedro-ximenez`, `blaufrankisch` — so a correctly spelled name has to
    # reduce to the same key. Without this the sweep turned every accent into
    # a hyphen and `Albariño` became `albari-o`, matching nothing: five
    # varieties already in the vocabulary were unreachable by their real
    # names, and row 11 dropped them as "unmatched". Observed on SEED.md row 2.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return _NON_ALNUM.sub("-", text).strip("-")


def _variety_lookup() -> dict[str, str]:
    """`normalised name -> slug`, from the slugs themselves and glossary terms."""
    lookup = {slug: slug for slug in VARIETY_KEYS}
    for (vocabulary, value), term in schema._GLOSSARY_TERMS.items():
        if vocabulary == "variety" and value in VARIETY_KEYS:
            lookup[slugify(term)] = value
    return lookup


def _region_lookup() -> dict[str, str]:
    lookup = {slug: slug for slug in schema.REGION_SLUGS}
    for slug, name in schema.REGION_NAMES.items():
        lookup[slugify(name)] = slug
    return lookup


def _subregion_lookup() -> dict[str, str]:
    lookup = {slug: slug for slug in schema.SUBREGION_SLUGS}
    for slug, name in schema.SUBREGION_NAMES.items():
        lookup[slugify(name)] = slug
    return lookup


def match_slugs(
    values: Any, lookup: dict[str, str]
) -> tuple[list[str], list[str]]:
    """`(matched slugs, unmatched raw strings)`, order preserved, deduplicated."""
    matched: list[str] = []
    unmatched: list[str] = []
    for raw in values if isinstance(values, list) else []:
        slug = lookup.get(slugify(raw))
        if slug is None:
            if str(raw).strip():
                unmatched.append(str(raw).strip())
        elif slug not in matched:
            matched.append(slug)
    return matched, unmatched


# =============================================================================
# 4. `_finalize_frontmatter` — SCHEMA.md §6
# =============================================================================


def _finalize_frontmatter(
    data: dict[str, Any],
    *,
    harvest: dict[str, Any],
    source_url: str,
    today: date_type,
    determination: Any = None,
    coordinates: tuple[float | None, float | None] = (None, None),
    previous: dict[str, Any] | None = None,
    log: Logger = _null_log,
) -> dict[str, Any]:
    """Stamp every pipeline-owned field over whatever the agents produced.

    Returns the finished frontmatter. Never raises on a field-level problem:
    approval-time validation is where a human sees those, with the editor open.
    """
    data = dict(data)
    determinations = harvest.get("determinations") or {}

    # ── Provenance and identity ───────────────────────────────────────────
    data["source_url"] = source_url
    if not str(data.get("website") or "").strip():
        data["website"] = source_url
    data["drafted"] = (previous or {}).get("drafted") or today
    data["verified"] = today

    # ── The determinations, re-imposed (SCHEMA.md §6) ─────────────────────
    for key in ("organic", "biodynamic"):
        state = determinations.get(key)
        if state in CERTIFICATION_STATES:
            data[key] = state
        certifier = determinations.get(f"{key}_certifier")
        certifier = str(certifier).strip() if certifier else None
        # SCHEMA.md §2a rules 2 and 3: a certifier exists only alongside
        # `certified`, and `certified` cannot exist without one. Enforced here
        # so the pair is always internally consistent before a human sees it.
        if data.get(key) == "certified" and not certifier:
            data[key] = "practising"
            log(
                "warn",
                f"{key}: certified was claimed with no named certifier, "
                f"recorded as practising (SCHEMA.md §2a rule {2 if key == 'organic' else 3})",
            )
            certifier = None
        if data.get(key) != "certified":
            certifier = None
        data[f"{key}_certifier"] = certifier

    fruit_source = determinations.get("fruit_source")
    if fruit_source in FRUIT_SOURCE:
        data["fruit_source"] = fruit_source
    data.setdefault("fruit_source", "purchased")

    practices = determinations.get("practices") or {}
    data["practices"] = {key: bool(practices.get(key, False)) for key in PRACTICE_KEYS}

    # ── Varieties and regions: matched, with every drop reported ──────────
    varieties, unmatched = match_slugs(determinations.get("varieties"), _variety_lookup())
    stated = len(varieties) + len(unmatched)
    if stated:
        log("info", f"varieties matched {len(varieties)} of {stated}")
    for raw in unmatched:
        log("warn", f'unmatched variety: "{raw}", not in VARIETY_KEYS')
    if varieties:
        data["varieties"] = varieties
    else:
        data.pop("varieties", None)
    data["unmatched_varieties"] = unmatched  # stripped below; carried for the log

    regions, unmatched_regions = match_slugs(harvest.get("regions"), _region_lookup())
    for raw in unmatched_regions:
        log("warn", f'unmatched region: "{raw}", not in regions.ts')
    if regions:
        data["regions"] = regions
        if data.get("primary_region") not in regions:
            data["primary_region"] = regions[0]
    else:
        # UX.md §1.5 row 12: the draft is still written so a human can supply
        # the region from the address. Approval is blocked by schema validation.
        log(
            "warn",
            "regions empty after slug matching, draft written for a human to complete",
        )

    subregions, unmatched_subregions = match_slugs(
        data.get("subregions"), _subregion_lookup()
    )
    for raw in unmatched_subregions:
        log("warn", f'unmatched subregion: "{raw}", not in regions.ts')
    subregions = [
        slug
        for slug in subregions
        if schema.SUBREGION_PARENT.get(slug) in (data.get("regions") or [])
    ]
    if subregions:
        data["subregions"] = subregions
    else:
        data.pop("subregions", None)

    # ── Coordinates come from the geocoder alone (TRD.md §7.6) ────────────
    location = dict(data.get("location") or {})

    # `state` is a closed vocabulary and a full state name maps to it with no
    # ambiguity, so normalise rather than hand the reviewer a validation error
    # they can only fix one way. Observed live: the first real draft came back
    # with `South Australia`, which fails check 1 on a value that was correct in
    # substance. The prompt now names the codes as well; this is the belt.
    state = str(location.get("state") or "").strip()
    if state and state not in STATES:
        normalised = _STATE_NAMES.get(state.lower().replace(".", "").replace(" ", ""))
        if normalised:
            log("info", f"state normalised: {state!r} -> {normalised!r}")
            location["state"] = normalised

    latitude, longitude = coordinates
    location["latitude"] = latitude
    location["longitude"] = longitude
    data["location"] = location

    # ── Ownership: null by definition, sourced from the determination ─────
    data["parent_company"] = None
    if determination is not None:
        source = getattr(determination, "basis", "") or ""
        # `ownership_source` is in PIPELINE_OWNED_FIELDS: no agent's output
        # survives here. It was nonetheless deferring to whatever the Architect
        # wrote whenever that carried a source, and the Architect's prompt asks
        # it for a `method` — so the model picked one. On a page that states no
        # ownership it picked `producer_statement`, which is the determination
        # deciding itself from prose, the one thing CLAUDE.md rule 8 forbids.
        #
        # `producer_statement` claims the source names who owns the business.
        # It is true only when the Harvester extracted such a statement. With
        # no statement there is no route to name honestly, so the field is left
        # for a human exactly as UX.md §1.5 row 12 leaves empty `regions`, and
        # approval stays blocked until it is filled (`approval_blocks`).
        #
        # Amended 2026-08-09: the else-branch no longer leaves the draft in a
        # state that can never publish. It stamps `unconfirmed`, which is the
        # honest record of "we looked and nobody publishes this" and is
        # publishable with its notice. What did NOT change is the bar for
        # `confirmed` — it still requires an extracted statement, and no agent's
        # `method` survives into it.
        if ownership_module.states_ownership(getattr(determination, "signals", []) or []):
            data["ownership_status"] = "confirmed"
            data["ownership_source"] = {
                "source": source_url,
                "method": "producer_statement",
                "date": today,
            }
        else:
            data["ownership_status"] = "unconfirmed"
            data["ownership_source"] = None
            log(
                "warn",
                "no ownership statement extracted, so this draft is unconfirmed: "
                "it publishes carrying a visible notice that the site has not "
                "confirmed who owns the business, and makes no independence "
                "claim for it. A reviewer recording a real source moves it to "
                "confirmed.",
            )
        if source:
            log("info", f"ownership determination recorded: {source}")

    # ── Provenance block and change log (SCHEMA.md §2b) ───────────────────
    unmatched_varieties = data.pop("unmatched_varieties", [])
    data["verification"] = verification_module.build_verification(
        data, source_url=source_url, today=today, previous=previous
    )
    if previous:
        change_log = verification_module.compute_change_log(
            previous, data, today=today, trigger="re-harvest"
        )
        if change_log:
            data["change_log"] = change_log

    data["_unmatched"] = {
        "varieties": unmatched_varieties,
        "regions": unmatched_regions,
        "subregions": unmatched_subregions,
    }
    return data


def strip_internal(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split the internal `_unmatched` bag off before the file is written.

    It is carried on the dict so the caller can surface it (UX.md §1.5 row 11's
    `Unmatched` line) without a second return value threaded through every
    stage, and it never reaches disk: `.strict()` would fail the build on it.
    """
    data = dict(data)
    unmatched = data.pop("_unmatched", {"varieties": [], "regions": [], "subregions": []})
    return data, unmatched
