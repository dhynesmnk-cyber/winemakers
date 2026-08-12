"""schema.py — the admin frontmatter editor's field contract. Gate 3.

**CONSUMER 4 OF 4 (CLAUDE.md rule 7).** The other three are the zod schema
(`site/src/content/config.ts`), the SQLite DDL (`admin/pipeline/data_store.py`)
and the Harvester JSON validator (`admin/pipeline/orchestrator.py`, Gate 5).
A field added to one and not the others is the highest-risk-if-broken failure in
the build. `/validate` check 13 diffs the four surfaces and the `schema-change`
skill fires on any edit to this file.

The field tuple below is what check 13 reads. It is written as a flat literal on
purpose: the check parses it with a regex, and a comprehension or a type
annotation carrying its own brackets would parse as an empty set, which agrees
with everything.

── What this module owns ─────────────────────────────────────────────────────

1. The field list and each field's editor metadata: which group it belongs to,
   what it is called in words, and which vocabulary constrains it.
2. Reading and writing staged MDX, frontmatter and body, without disturbing
   either.
3. **Validation, mirroring the zod schema field for field.** The review pane
   must show every failing field at once with its own message (UX.md §1.4), and
   approve must block on the same rules the Astro build would fail on. A draft
   that passes here and fails `npm run build` is this module being wrong.

── Words, never codes ────────────────────────────────────────────────────────

UX.md §1.4: controls are labelled with words, there is no badge system and no
abbreviation codes anywhere in this editor. Display terms come from
`site/src/data/glossary.ts` rather than from a second hand-typed copy: the
glossary is the authority for all 121 of them (CONSTANTS-REQUIRED.md §2.4), and
a second copy is a drift surface nobody would ever check.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin.config import (  # noqa: E402
    CATEGORIES,
    CELLAR_DOOR_STATES,
    CERTIFICATION_STATES,
    CONFIDENCE_TIERS,
    DENY_LIST_CHECKS,
    FAQ_MAX_ITEMS,
    FRUIT_SOURCE,
    LOGISTICS_KEYS,
    OWNERSHIP_EVIDENCE_METHODS,
    OWNERSHIP_STATES,
    PRACTICE_KEYS,
    PRODUCTION_BAND_RANGES,
    PRODUCTION_BANDS,
    ROOT,
    STATES,
    SUMMARY_MAX_CHARS,
    VARIETY_KEYS,
    VERIFIABLE_FIELDS,
    VESSEL_KEYS,
    WINE_STYLE_KEYS,
    AU_LATITUDE_BOUNDS,
    AU_LONGITUDE_BOUNDS,
)

GLOSSARY_TS_PATH = ROOT / "site" / "src" / "data" / "glossary.ts"
REGIONS_TS_PATH = ROOT / "site" / "src" / "data" / "regions.ts"


# =============================================================================
# 1. The field list
#
# SCHEMA.md §2's table, in its order. Nothing is derived here: check 13 reads
# this tuple as text, so it stays a flat literal.
#
# Never write the name of this tuple followed by a colon or an equals sign
# anywhere above its definition. The check's regex would match the prose and
# parse the wrong brackets.
# =============================================================================

KNOWN_FIELDS = (
    "name",
    "parent_company",
    "ownership_status",
    "ownership_source",
    "audit_exemptions",
    "category",
    "founded_year",
    "website",
    "location",
    "regions",
    "primary_region",
    "subregions",
    "cellar_door",
    "cellar_door_hours",
    "cost",
    "tasting_fee",
    "minimum_age",
    "organic",
    "organic_certifier",
    "biodynamic",
    "biodynamic_certifier",
    "fruit_source",
    "practices",
    "vessels",
    "varieties",
    "wine_styles",
    "production_band",
    "annual_production_cases",
    "buy_online",
    "ships_nationally",
    "shop_url",
    "logistics",
    "verification",
    "change_log",
    "summary",
    "drafted",
    "verified",
    "source_url",
    "image",
    "image_source",
    "image_caption",
    "faq",
)


# =============================================================================
# 2. The display vocabulary, read from glossary.ts
# =============================================================================

#: `glossary.ts` vocabulary id -> the config tuple it glosses. The ids are
#: kebab-cased and the tuples are not, so the mapping is written out.
_VOCABULARY_IDS = {
    "category": "CATEGORIES",
    "cellar-door": "CELLAR_DOOR_STATES",
    "certification": "CERTIFICATION_STATES",
    "fruit-source": "FRUIT_SOURCE",
    "production-band": "PRODUCTION_BANDS",
    "practice": "PRACTICE_KEYS",
    "logistics": "LOGISTICS_KEYS",
    "vessel": "VESSEL_KEYS",
    "wine-style": "WINE_STYLE_KEYS",
    "variety": "VARIETY_KEYS",
    "confidence-tier": "CONFIDENCE_TIERS",
    "ownership-evidence": "OWNERSHIP_EVIDENCE_METHODS",
    "ownership-state": "OWNERSHIP_STATES",
    "state": "STATES",
}


def _read_glossary_terms() -> dict[tuple[str, str], str]:
    """`(vocabulary id, value) -> term`, parsed out of `glossary.ts`.

    Python cannot import a TypeScript module, and this file loads without a
    build step by design (CONSTANTS-REQUIRED.md §1), so it is read as text.
    `schema_surfaces.py` already reads the same file the same way for
    `VARIETY_SLUGS`; this follows that precedent rather than inventing a second
    mechanism.

    `glossary.ts` contains NUL bytes, deliberately, as a map-key separator that
    cannot collide with a slug. They make the file binary to `grep` and to every
    line-based tool. `read_text` is unbothered by them.
    """
    text = GLOSSARY_TS_PATH.read_text(encoding="utf-8")
    entries = re.findall(
        r'vocabulary:\s*"([^"]+)",\s*\n\s*value:\s*"([^"]+)",\s*\n\s*term:\s*"([^"]+)"',
        text,
    )
    return {(vocabulary, value): term for vocabulary, value, term in entries}


_GLOSSARY_TERMS = _read_glossary_terms()


def label_for(vocabulary: str, value: str) -> str:
    """The display term for an enum member. Falls back to the value humanised.

    A missing term is a glossary gap for `/validate` check 11 to report at Gate
    6, not a reason for the editor to render an empty control.
    """
    return _GLOSSARY_TERMS.get((vocabulary, value)) or value.replace("_", " ")


def options_for(vocabulary: str, values: tuple[str, ...]) -> list[dict[str, str]]:
    """`[{value, label}]` for a select or a multi-select, in tuple order."""
    return [{"value": value, "label": label_for(vocabulary, value)} for value in values]


# =============================================================================
# 3. The GI register, read from regions.ts
# =============================================================================


def _ts_object_records(text: str, array_name: str) -> list[dict[str, Any]]:
    """Top-level `{...}` records of an exported TS array, as flat dicts.

    Handles both the one-line and the multi-line record shapes `regions.ts`
    uses. Only string and string-array values are read, which is all the editor
    needs; numbers and booleans in these files are metadata the admin does not
    render.
    """
    # `= [`, not the first `[`: the declaration's own type annotation is
    # `readonly Region[]`, whose empty brackets come first and would end the
    # scan before it started.
    start = text.index("= [", text.index(f"export const {array_name}")) + 2
    depth = 0
    records: list[dict[str, Any]] = []
    buffer: list[str] = []
    for char in text[start:]:
        if char == "{":
            depth += 1
        if depth:
            buffer.append(char)
        if char == "}":
            depth -= 1
            if depth == 0:
                body = "".join(buffer)
                buffer = []
                record: dict[str, Any] = dict(
                    re.findall(r'(\w+):\s*"([^"]*)"', body)
                )
                for key, values in re.findall(r"(\w+):\s*\[([^\]]*)\]", body):
                    record[key] = re.findall(r'"([^"]+)"', values)
                records.append(record)
        if char == "]" and depth == 0:
            break
    return records


def _read_regions() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = REGIONS_TS_PATH.read_text(encoding="utf-8")
    return _ts_object_records(text, "REGIONS"), _ts_object_records(text, "SUBREGIONS")


_REGIONS, _SUBREGIONS = _read_regions()

REGION_SLUGS = tuple(record["slug"] for record in _REGIONS)
SUBREGION_SLUGS = tuple(record["slug"] for record in _SUBREGIONS)
REGION_NAMES = {record["slug"]: record["name"] for record in _REGIONS}
SUBREGION_NAMES = {record["slug"]: record["name"] for record in _SUBREGIONS}

#: subregion slug -> its parent region slug. SCHEMA.md §2a rule 5 constrains the
#: editor's subregion picker to the subregions of the regions actually selected.
SUBREGION_PARENT = {record["slug"]: record["region"] for record in _SUBREGIONS}


def region_name(slug: str) -> str:
    return REGION_NAMES.get(slug, slug)


def subregion_name(slug: str) -> str:
    return SUBREGION_NAMES.get(slug, slug)


# =============================================================================
# 4. Editor metadata — UX.md §1.4's field groups, in order
#
# Group 1, Ownership, is pinned first and cannot be collapsed. Gate 3 renders
# the two ownership FIELDS (`parent_company` and `ownership_source`), which are
# frontmatter and therefore this editor's business. The determination itself —
# the verdict, the deny-list rows, the signals table and their resolutions
# (UX.md §1.4.1 to §1.4.6) — is Gate 4 and is deliberately absent here.
# =============================================================================

GROUPS = (
    ("ownership", "Ownership"),
    ("identity", "Identity"),
    ("place", "Place"),
    ("visiting", "Visiting"),
    ("farming", "Farming and making"),
    ("wines", "Wines"),
    ("scale", "Scale and commerce"),
    ("logistics", "Logistics"),
    ("faq", "Questions"),
    ("provenance", "Provenance"),
)

#: field -> editor spec. `widget` names the control the template renders;
#: `vocab` is the glossary vocabulary id where one constrains the field.
FIELDS: dict[str, dict[str, Any]] = {
    "parent_company": {
        "group": "ownership",
        "label": "Parent company",
        "widget": "nullable_text",
        "help": (
            "null means independent, and it is the only publishable value "
            "(SCHEMA.md §4.1)."
        ),
    },
    "ownership_status": {
        "group": "ownership",
        "label": "Ownership status",
        "widget": "select",
        "vocab": "ownership-state",
        "values": OWNERSHIP_STATES,
        "required": True,
        "help": (
            "confirmed needs a source naming who owns the business. "
            "unconfirmed publishes with a visible notice and makes no "
            "independence claim (SCHEMA.md §1.15)."
        ),
    },
    "ownership_source": {"group": "ownership", "label": "Ownership source", "widget": "ownership_source"},
    "name": {"group": "identity", "label": "Name", "widget": "text", "required": True},
    "category": {
        "group": "identity",
        "label": "Category",
        "widget": "select",
        "vocab": "category",
        "values": CATEGORIES,
        "required": True,
    },
    "founded_year": {"group": "identity", "label": "Founded", "widget": "number"},
    "website": {"group": "identity", "label": "Website", "widget": "url", "required": True},
    "summary": {
        "group": "identity",
        "label": "Summary",
        "widget": "summary",
        "required": True,
        "max_chars": SUMMARY_MAX_CHARS,
    },
    "location": {"group": "place", "label": "Location", "widget": "location", "required": True},
    "regions": {
        "group": "place",
        "label": "Regions",
        "widget": "region_multiselect",
        "required": True,
        "help": "Where the fruit comes from, not where the winery is.",
    },
    "primary_region": {
        "group": "place",
        "label": "Primary region",
        "widget": "primary_region_select",
        "required": True,
    },
    "subregions": {"group": "place", "label": "Subregions", "widget": "subregion_multiselect"},
    "cellar_door": {
        "group": "visiting",
        "label": "Cellar door",
        "widget": "select",
        "vocab": "cellar-door",
        "values": CELLAR_DOOR_STATES,
        "required": True,
    },
    "cellar_door_hours": {"group": "visiting", "label": "Cellar door hours", "widget": "text"},
    "cost": {"group": "visiting", "label": "Cost", "widget": "text"},
    "tasting_fee": {"group": "visiting", "label": "Tasting fee", "widget": "tasting_fee"},
    "minimum_age": {"group": "visiting", "label": "Minimum age", "widget": "number"},
    "organic": {
        "group": "farming",
        "label": "Organic",
        "widget": "certification",
        "vocab": "certification",
        "values": CERTIFICATION_STATES,
        "required": True,
    },
    "organic_certifier": {"group": "farming", "label": "Organic certifier", "widget": "certifier"},
    "biodynamic": {
        "group": "farming",
        "label": "Biodynamic",
        "widget": "certification",
        "vocab": "certification",
        "values": CERTIFICATION_STATES,
        "required": True,
    },
    "biodynamic_certifier": {"group": "farming", "label": "Biodynamic certifier", "widget": "certifier"},
    "fruit_source": {
        "group": "farming",
        "label": "Fruit source",
        "widget": "select",
        "vocab": "fruit-source",
        "values": FRUIT_SOURCE,
        "required": True,
    },
    "practices": {
        "group": "farming",
        "label": "Practices",
        "widget": "toggles",
        "vocab": "practice",
        "values": PRACTICE_KEYS,
        "required": True,
    },
    "vessels": {
        "group": "farming",
        "label": "Vessels",
        "widget": "multiselect",
        "vocab": "vessel",
        "values": VESSEL_KEYS,
    },
    "varieties": {
        "group": "wines",
        "label": "Varieties",
        "widget": "multiselect",
        "vocab": "variety",
        "values": VARIETY_KEYS,
    },
    "wine_styles": {
        "group": "wines",
        "label": "Wine styles",
        "widget": "multiselect",
        "vocab": "wine-style",
        "values": WINE_STYLE_KEYS,
    },
    "production_band": {
        "group": "scale",
        "label": "Production band",
        "widget": "select",
        "vocab": "production-band",
        "values": PRODUCTION_BANDS,
        "required": True,
    },
    "annual_production_cases": {"group": "scale", "label": "Annual production, cases", "widget": "number"},
    "buy_online": {"group": "scale", "label": "Sells online", "widget": "boolean", "required": True},
    "ships_nationally": {"group": "scale", "label": "Ships nationally", "widget": "boolean", "required": True},
    "shop_url": {"group": "scale", "label": "Shop address", "widget": "url"},
    "logistics": {
        "group": "logistics",
        "label": "Logistics",
        "widget": "toggles_optional",
        "vocab": "logistics",
        "values": LOGISTICS_KEYS,
    },
    "faq": {"group": "faq", "label": "Questions", "widget": "faq", "max_items": FAQ_MAX_ITEMS},
    # Read-only in the editor by design. An exemption is a judgement recorded
    # against evidence, not a checkbox a reviewer ticks to clear a blocking
    # hit — the review pane surfaces the deny-list row and its resolution, and
    # writing the durable record is a deliberate edit to the file.
    "audit_exemptions": {
        "group": "provenance",
        "label": "Audit exemptions",
        "widget": "readonly_audit_exemptions",
    },
    "verification": {"group": "provenance", "label": "Verification", "widget": "readonly_verification"},
    "change_log": {"group": "provenance", "label": "Change log", "widget": "readonly_change_log"},
    "drafted": {"group": "provenance", "label": "Drafted", "widget": "readonly_date"},
    "verified": {"group": "provenance", "label": "Verified", "widget": "verified_date"},
    "source_url": {"group": "provenance", "label": "Source", "widget": "readonly_url"},
    "image": {"group": "provenance", "label": "Image", "widget": "readonly_image"},
    "image_source": {"group": "provenance", "label": "Image source", "widget": "readonly_text"},
    "image_caption": {"group": "provenance", "label": "Image caption", "widget": "readonly_text"},
}

#: The two lists are the same set or the editor is rendering a field the
#: contract does not have, or hiding one it does. Asserted at import so it fails
#: on the first request rather than quietly at a gate exit.
assert set(FIELDS) == set(KNOWN_FIELDS), (
    f"FIELDS and the field tuple disagree: "
    f"{sorted(set(FIELDS) ^ set(KNOWN_FIELDS))}"
)


def fields_in_group(group: str) -> list[tuple[str, dict[str, Any]]]:
    """The group's fields, in SCHEMA.md §2's field order."""
    return [
        (name, FIELDS[name])
        for name in KNOWN_FIELDS
        if FIELDS[name]["group"] == group
    ]


# =============================================================================
# 5. Reading and writing MDX
# =============================================================================


class _NoAliasDumper(yaml.SafeDumper):
    """Never emit YAML anchors or aliases.

    PyYAML deduplicates equal objects by reference, so the single `date.today()`
    shared across `verification`, `drafted` and `verified` came out as
    `date: &id001 2026-08-07` followed by eight `date: *id001` and
    `drafted: *id001`. That is valid YAML and it round-trips correctly, but the
    frontmatter is the canonical record of this project and a reviewer edits it
    by hand in the review pane. A date they cannot read is a date they cannot
    check, and `verified: *id001` invites someone to "fix" it into nonsense.

    Observed on the first real draft the pipeline produced.
    """

    def ignore_aliases(self, data):  # noqa: ANN001, ANN201
        return True


class _BlockSequenceDumper(_NoAliasDumper):
    """Indents block sequences under their key, as every hand-written file does.

    PyYAML's default writes a sequence flush with its parent key. The sample
    producer, the Harvester's output and every file a person has edited use the
    indented form, and a dumper that reformats the whole file on the first
    autosave makes every subsequent diff unreadable.
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: FBT001,FBT002
        return super().increase_indent(flow, False)


class FrontmatterError(ValueError):
    """The file could not be parsed at all. UX.md §1.3's `UNREADABLE` chip."""


def read_mdx(path: Path) -> tuple[dict[str, Any], str]:
    """`(frontmatter, body)`. Raises `FrontmatterError` on an unusable file.

    Deliberately lenient about the CONTENT of the frontmatter: an invalid value
    is a field error the review pane shows and the reviewer fixes. Only a file
    whose frontmatter cannot be parsed at all is unreadable.

    **The underscore trap, worth knowing about.** PyYAML implements YAML 1.1,
    where an underscore is a digit separator, so a hand-written
    `production_band: 1000_5000` loads as the integer 10005000 while Astro's
    YAML 1.2 parser reads the string. Two of the five `PRODUCTION_BANDS` members
    have that shape. Nothing is coerced here: `validate_frontmatter` reports it
    as the field error it is, and `write_mdx` quotes the value on the next save,
    which repairs the file. Silently accepting the integer would leave the two
    consumers disagreeing about the same file, which is the exact failure
    `/validate` check 13 exists to prevent.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FrontmatterError(str(exc)) from exc
    return parse_mdx_text(text)


def parse_mdx_text(text: str) -> tuple[dict[str, Any], str]:
    """`(frontmatter, body)` from MDX already in memory.

    Extracted from `read_mdx` at Gate 5 so the pipeline can validate what an
    agent returned without writing it to disk first. Same parser, same errors,
    same leniency about content: a draft that fails here failed to be an MDX
    file at all, which is the content tier's business, while a draft with a bad
    *value* is the reviewer's and must reach them.
    """
    if not text.startswith("---"):
        raise FrontmatterError("missing frontmatter delimiter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise FrontmatterError("unterminated frontmatter block")
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"unparseable YAML: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return data, parts[2].lstrip("\n")


def write_mdx(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write frontmatter and body back, in SCHEMA.md §2's field order.

    Ordering by the contract rather than by the incoming dict keeps a hand-
    edited file and a pipeline-written one byte-comparable, and keeps an
    autosave from reshuffling the file under the reviewer on every keystroke.
    Unknown keys are preserved and written last: a `.strict()` violation is the
    reviewer's to see and delete, never this function's to silently swallow.
    """
    ordered: dict[str, Any] = {}
    for field in KNOWN_FIELDS:
        if field in frontmatter:
            ordered[field] = frontmatter[field]
    for field in frontmatter:
        if field not in ordered:
            ordered[field] = frontmatter[field]

    dumped = yaml.dump(
        ordered,
        Dumper=_BlockSequenceDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10**9,
    )
    body = body.strip("\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{dumped}---\n\n{body}\n", encoding="utf-8")


def coerce_dates(value: Any) -> Any:
    """Turn `YYYY-MM-DD` strings back into dates, recursively.

    The browser sends JSON, which has no date type, so every date arrives as a
    string. YAML writes a real date unquoted and a string quoted, and the two
    files would differ on every autosave otherwise.
    """
    if isinstance(value, dict):
        return {key: coerce_dates(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [coerce_dates(inner) for inner in value]
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return value
    return value


def as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


# =============================================================================
# 6. Validation — the zod schema, mirrored
#
# Every rule here exists in `site/src/content/config.ts`. When one changes
# there it changes here, in the same commit (CLAUDE.md rule 7).
#
# EVERY failing field is reported, never the first (UX.md §1.4). A reviewer who
# fixes one error and resubmits to find another is a reviewer who stops at forty
# producers.
# =============================================================================

_URL = re.compile(r"^https?://\S+$")


def _is_url(value: Any) -> bool:
    return isinstance(value, str) and bool(_URL.match(value))


def _check_enum(errors: dict[str, str], data: dict, field: str, values: tuple[str, ...]) -> None:
    value = data.get(field)
    if value not in values:
        errors[field] = (
            f"{field} must be one of {', '.join(values)}"
            + (f", not {value!r}" if value is not None else "")
        )


def _check_optional_string_array(
    errors: dict[str, str], data: dict, field: str, values: tuple[str, ...], label: str
) -> None:
    members = data.get(field)
    if members is None:
        return
    if not isinstance(members, list):
        errors[field] = f"{field} must be a list"
        return
    unknown = [member for member in members if member not in values]
    if unknown:
        errors[field] = f"{field} has values outside {label}: {', '.join(map(str, unknown))}"
    elif len(set(members)) != len(members):
        errors[field] = f"{field} must not contain duplicates"


#: Dollar amounts in a freeform `cost` string. SCHEMA.md §2a rule 8: ONE REGEX,
#: ONE HOME. `/validate` check 10 cross-checks `tasting_fee.fee_aud` against the
#: amounts this finds, and the review pane displays them beside the fee input so
#: the reviewer sees the corroboration or its absence without running the check.
#: The admin's JavaScript never reimplements it.
_DOLLARS = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")


def dollar_amounts(cost: Any) -> list[float]:
    """Every dollar figure stated in a `cost` string, in the order stated."""
    if not isinstance(cost, str):
        return []
    return [float(match) for match in _DOLLARS.findall(cost)]


def band_for_cases(cases: Any) -> str | None:
    """The `PRODUCTION_BANDS` member a case figure implies, or None.

    Shown beside the figure in the editor so an inconsistency is visible before
    `/validate` check 10 catches it (UX.md §1.4).
    """
    if not isinstance(cases, int) or isinstance(cases, bool) or cases < 0:
        return None
    for band, bounds in PRODUCTION_BAND_RANGES.items():
        if bounds is None:
            continue
        low, high = bounds
        if cases >= low and (high is None or cases <= high):
            return band
    return None


def validate_frontmatter(data: dict[str, Any]) -> dict[str, str]:
    """`{field: message}` for every rule the zod schema would fail on.

    An empty dict means the Astro build would accept this file.
    """
    errors: dict[str, str] = {}

    unknown = [key for key in data if key not in KNOWN_FIELDS]
    if unknown:
        # `.strict()` in zod. An unknown key is a typo, a hand-edit against the
        # contract, or a field added to one consumer and not the other three.
        errors["_unknown"] = (
            f"unknown field(s) not in the contract: {', '.join(sorted(unknown))}. "
            f"The zod schema is .strict() and the build would fail on this."
        )

    # ── Identity ──────────────────────────────────────────────────────────
    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        errors["name"] = "name is required"
    _check_enum(errors, data, "category", CATEGORIES)
    if not _is_url(data.get("website")):
        errors["website"] = "website must be a URL"
    founded = data.get("founded_year")
    if founded is not None and not (isinstance(founded, int) and 1000 <= founded <= 9999):
        errors["founded_year"] = "founded_year must be a four-digit year, or null"

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors["summary"] = "summary is required"
    elif len(summary) > SUMMARY_MAX_CHARS:
        errors["summary"] = (
            f"summary is {len(summary)} characters, limit is {SUMMARY_MAX_CHARS}"
        )

    # ── Ownership ─────────────────────────────────────────────────────────
    if "parent_company" not in data:
        errors["parent_company"] = (
            "parent_company must be present. An absent key is an undetermined "
            "producer, which is not publishable (SCHEMA.md §2)."
        )
    elif data["parent_company"] is not None and not isinstance(data["parent_company"], str):
        errors["parent_company"] = "parent_company must be a string or null"

    # SCHEMA.md §2a rules 11 and 13. Amended 2026-08-09: `ownership_source` is
    # required on `confirmed` and forbidden on `unconfirmed`, rather than
    # required outright. The editor is the surface a reviewer actually drives,
    # so both directions carry the sentence explaining which value to pick
    # instead of only naming the rule.
    status = data.get("ownership_status")
    if status not in OWNERSHIP_STATES:
        errors["ownership_status"] = (
            f"ownership_status must be one of {', '.join(OWNERSHIP_STATES)}"
        )

    ownership = data.get("ownership_source")
    if status == "unconfirmed":
        if ownership is not None:
            errors["ownership_source"] = (
                "ownership_status is unconfirmed, so ownership_source must be "
                "null. If this source names who owns the business, set "
                "ownership_status to confirmed instead."
            )
    elif not isinstance(ownership, dict):
        errors["ownership_source"] = (
            "ownership_status is confirmed, so ownership_source is required. "
            "If no source names the owner, set ownership_status to unconfirmed."
        )
    else:
        if not str(ownership.get("source") or "").strip():
            errors["ownership_source"] = "ownership_source needs a source"
        elif ownership.get("method") not in OWNERSHIP_EVIDENCE_METHODS:
            errors["ownership_source"] = (
                f"ownership_source.method must be one of "
                f"{', '.join(OWNERSHIP_EVIDENCE_METHODS)}"
            )
        elif as_date(ownership.get("date")) is None:
            errors["ownership_source"] = "ownership_source needs a date"
        extra = set(ownership) - {"source", "method", "date"}
        if extra:
            errors["ownership_source"] = (
                f"ownership_source has unknown key(s): {', '.join(sorted(extra))}"
            )

    # ── Place ─────────────────────────────────────────────────────────────
    location = data.get("location")
    if not isinstance(location, dict):
        errors["location"] = "location is required"
    else:
        if location.get("state") not in STATES:
            errors["location"] = f"location.state must be one of {', '.join(STATES)}"
        for axis, bounds in (
            ("latitude", AU_LATITUDE_BOUNDS),
            ("longitude", AU_LONGITUDE_BOUNDS),
        ):
            value = location.get(axis)
            if value is None:
                continue
            if not isinstance(value, (int, float)) or not bounds[0] <= value <= bounds[1]:
                errors["location"] = (
                    f"{axis} is out of range for Australia "
                    f"({bounds[0]} to {bounds[1]}), got {value}"
                )
        # `address` and `suburb` are optional *strings* (SCHEMA.md §2), not
        # nullable ones — the zod schema accepts the key absent or a string and
        # nothing else. The Harvester's wire format says the opposite ("null
        # over guess", §5), so a draft arrives carrying explicit nulls and
        # `_finalize_frontmatter` drops them (§6). This is the belt: without a
        # type check here the approve gate passed a null that the Astro build
        # then rejected, which put the failure a whole stage downstream of the
        # surface that should have caught it.
        for key in ("address", "suburb"):
            if key not in location:
                continue
            value = location.get(key)
            if not isinstance(value, str) or not value.strip():
                errors["location"] = (
                    f"location.{key} must be a non-empty string when present, "
                    f"got {value!r}. Where it is unknown, omit the key."
                )

        extra = set(location) - {"address", "suburb", "state", "latitude", "longitude"}
        if extra:
            errors["location"] = f"location has unknown key(s): {', '.join(sorted(extra))}"

    regions = data.get("regions")
    if not isinstance(regions, list) or not regions:
        errors["regions"] = "regions needs at least one member"
        regions = []
    else:
        unknown_regions = [slug for slug in regions if slug not in REGION_SLUGS]
        if unknown_regions:
            errors["regions"] = (
                f"regions not in the GI register: {', '.join(map(str, unknown_regions))}"
            )

    primary = data.get("primary_region")
    if primary not in REGION_SLUGS:
        errors["primary_region"] = "primary_region must be a region slug from regions.ts"
    elif primary not in regions:
        # SCHEMA.md §2a rule 4.
        errors["primary_region"] = (
            f"primary_region \"{primary}\" is not in regions "
            f"[{', '.join(regions)}] (SCHEMA.md §2a rule 4)"
        )

    subregions = data.get("subregions")
    if subregions is not None:
        if not isinstance(subregions, list):
            errors["subregions"] = "subregions must be a list"
        else:
            unknown_subs = [slug for slug in subregions if slug not in SUBREGION_SLUGS]
            orphans = [
                slug
                for slug in subregions
                if slug in SUBREGION_PARENT and SUBREGION_PARENT[slug] not in regions
            ]
            if unknown_subs:
                errors["subregions"] = (
                    f"subregions not in the GI register: {', '.join(map(str, unknown_subs))}"
                )
            elif orphans:
                # SCHEMA.md §2a rule 5. `/validate` check 12 owns the full
                # sweep; catching it here is where it is cheapest to read.
                errors["subregions"] = (
                    f"{', '.join(orphans)} belongs to a region this producer does "
                    f"not list (SCHEMA.md §2a rule 5)"
                )

    # ── Visiting ──────────────────────────────────────────────────────────
    _check_enum(errors, data, "cellar_door", CELLAR_DOOR_STATES)
    hours = data.get("cellar_door_hours")
    if data.get("cellar_door") == "none" and hours not in (None, ""):
        errors["cellar_door_hours"] = (
            "cellar_door_hours must be omitted when cellar_door is none "
            "(SCHEMA.md §2a rule 7)"
        )

    fee = data.get("tasting_fee")
    if fee is not None:
        if not isinstance(fee, dict):
            errors["tasting_fee"] = "tasting_fee must be an object, or omitted entirely"
        else:
            extra = set(fee) - {"fee_aud", "waived_on_purchase"}
            amount = fee.get("fee_aud")
            waived = fee.get("waived_on_purchase")
            if extra:
                errors["tasting_fee"] = f"tasting_fee has unknown key(s): {', '.join(sorted(extra))}"
            elif amount is not None and (
                not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount < 0
            ):
                errors["tasting_fee"] = "tasting_fee.fee_aud must be a number or null"
            elif waived is not None and not isinstance(waived, bool):
                errors["tasting_fee"] = "tasting_fee.waived_on_purchase must be true, false or null"

    age = data.get("minimum_age")
    if age is not None and (not isinstance(age, int) or isinstance(age, bool) or age <= 0):
        errors["minimum_age"] = "minimum_age must be a positive whole number, or null"

    # ── Farming and making ────────────────────────────────────────────────
    for subject in ("organic", "biodynamic"):
        _check_enum(errors, data, subject, CERTIFICATION_STATES)
        certifier_key = f"{subject}_certifier"
        certifier = data.get(certifier_key)
        rule = 2 if subject == "organic" else 3
        if data.get(subject) == "certified" and not certifier:
            errors[certifier_key] = (
                f"{subject}: certified requires a named {certifier_key} "
                f"(SCHEMA.md §2a rule {rule}). Where no certifier is named, the "
                f"correct value is practising."
            )
        if data.get(subject) != "certified" and certifier:
            errors[certifier_key] = (
                f"{certifier_key} must be null unless {subject} is certified "
                f"(SCHEMA.md §2a rule {rule})"
            )

    _check_enum(errors, data, "fruit_source", FRUIT_SOURCE)

    practices = data.get("practices")
    if not isinstance(practices, dict):
        errors["practices"] = "practices is required, with all four keys"
    else:
        missing = [key for key in PRACTICE_KEYS if key not in practices]
        extra = set(practices) - set(PRACTICE_KEYS)
        wrong = [key for key, value in practices.items() if not isinstance(value, bool)]
        if missing:
            errors["practices"] = f"practices is missing {', '.join(missing)}"
        elif extra:
            errors["practices"] = f"practices has unknown key(s): {', '.join(sorted(extra))}"
        elif wrong:
            errors["practices"] = f"practices values must be true or false: {', '.join(wrong)}"

    _check_optional_string_array(errors, data, "vessels", VESSEL_KEYS, "VESSEL_KEYS")
    _check_optional_string_array(errors, data, "varieties", VARIETY_KEYS, "VARIETY_KEYS")
    _check_optional_string_array(errors, data, "wine_styles", WINE_STYLE_KEYS, "WINE_STYLE_KEYS")

    # ── Scale and commerce ────────────────────────────────────────────────
    _check_enum(errors, data, "production_band", PRODUCTION_BANDS)
    cases = data.get("annual_production_cases")
    if cases is not None and (not isinstance(cases, int) or isinstance(cases, bool) or cases < 0):
        errors["annual_production_cases"] = "annual_production_cases must be a whole number, or null"

    for flag in ("buy_online", "ships_nationally"):
        if not isinstance(data.get(flag), bool):
            errors[flag] = f"{flag} must be true or false"

    shop_url = data.get("shop_url")
    if data.get("buy_online") is True and not shop_url:
        errors["shop_url"] = "shop_url is required when buy_online is true (SCHEMA.md §2a rule 6)"
    elif shop_url is not None and not _is_url(shop_url):
        errors["shop_url"] = "shop_url must be a URL, or null"

    logistics = data.get("logistics")
    if logistics is not None:
        if not isinstance(logistics, dict):
            errors["logistics"] = "logistics must be an object, or omitted entirely"
        else:
            extra = set(logistics) - set(LOGISTICS_KEYS)
            wrong = [key for key, value in logistics.items() if not isinstance(value, bool)]
            if extra:
                errors["logistics"] = f"logistics has unknown key(s): {', '.join(sorted(extra))}"
            elif wrong:
                errors["logistics"] = f"logistics values must be true or false: {', '.join(wrong)}"

    # ── Audit exemptions (SCHEMA.md §2, §2a rules 15 and 16) ──────────────
    #
    # Mirrors the zod `.superRefine()` half for half. Both halves of rule 15
    # cannot be checked here either: exactness needs the live register, and
    # /validate check 8 owns that.
    exemptions = data.get("audit_exemptions")
    if exemptions is not None:
        if not isinstance(exemptions, list):
            errors["audit_exemptions"] = "audit_exemptions must be a list"
        else:
            required = {"check", "matched", "parent", "register_updated", "date", "note"}
            for index, entry in enumerate(exemptions):
                if not isinstance(entry, dict):
                    errors["audit_exemptions"] = f"audit_exemptions[{index}] must be an object"
                    break
                if set(entry) != required:
                    errors["audit_exemptions"] = (
                        f"audit_exemptions[{index}] must carry exactly "
                        f"{', '.join(sorted(required))}"
                    )
                    break
                if entry.get("check") not in DENY_LIST_CHECKS:
                    errors["audit_exemptions"] = (
                        f"audit_exemptions[{index}].check must be one of "
                        f"{', '.join(DENY_LIST_CHECKS)}"
                    )
                    break
                if entry.get("check") != "name":
                    errors["audit_exemptions"] = (
                        f"audit_exemptions[{index}].check is "
                        f"{entry.get('check')!r}; only a contained name match is "
                        f"exemptable (SCHEMA.md §2a rule 15). A domain or ABN hit "
                        f"identifies the entity itself."
                    )
                    break
                missing = [
                    key
                    for key in ("matched", "parent", "note")
                    if not str(entry.get(key) or "").strip()
                ]
                if missing:
                    errors["audit_exemptions"] = (
                        f"audit_exemptions[{index}] needs a non-empty "
                        f"{', '.join(missing)}"
                    )
                    break
                undated = [
                    key for key in ("register_updated", "date") if as_date(entry.get(key)) is None
                ]
                if undated:
                    errors["audit_exemptions"] = (
                        f"audit_exemptions[{index}] needs a valid "
                        f"{', '.join(undated)}"
                    )
                    break
            else:
                # Rule 16. Only reached when every entry above parsed.
                if exemptions and data.get("ownership_status") != "confirmed":
                    errors["ownership_status"] = (
                        "a producer carrying an audit_exemptions entry must be "
                        "ownership_status: confirmed (SCHEMA.md §2a rule 16)"
                    )

    # ── Provenance ────────────────────────────────────────────────────────
    verification = data.get("verification")
    if verification is not None:
        if not isinstance(verification, dict):
            errors["verification"] = "verification must be an object"
        else:
            extra = set(verification) - set(VERIFIABLE_FIELDS)
            if extra:
                errors["verification"] = (
                    f"verification names field(s) not in VERIFIABLE_FIELDS: "
                    f"{', '.join(sorted(extra))}"
                )
            else:
                for field, record in verification.items():
                    if not isinstance(record, dict):
                        errors["verification"] = f"verification.{field} must be an object"
                        break
                    if not str(record.get("source") or "").strip():
                        errors["verification"] = f"verification.{field} needs a source"
                        break
                    if record.get("tier") not in CONFIDENCE_TIERS:
                        errors["verification"] = (
                            f"verification.{field}.tier must be one of "
                            f"{', '.join(CONFIDENCE_TIERS)}"
                        )
                        break
                    if as_date(record.get("date")) is None:
                        errors["verification"] = f"verification.{field} needs a date"
                        break

    change_log = data.get("change_log")
    if change_log is not None:
        if not isinstance(change_log, list):
            errors["change_log"] = "change_log must be a list"
        else:
            for entry in change_log:
                if not isinstance(entry, dict) or set(entry) != {
                    "field",
                    "from",
                    "to",
                    "date",
                    "trigger",
                }:
                    errors["change_log"] = (
                        "each change_log entry needs exactly field, from, to, date and trigger"
                    )
                    break

    for field in ("drafted", "verified"):
        if as_date(data.get(field)) is None:
            errors[field] = f"{field} must be a date (YYYY-MM-DD)"
    if not _is_url(data.get("source_url")):
        errors["source_url"] = "source_url must be a URL"

    # ── Image, SCHEMA.md §2a rule 1 ───────────────────────────────────────
    if data.get("image"):
        if not data.get("image_source"):
            errors["image_source"] = (
                "image_source is required when image is present (SCHEMA.md §2a rule 1). "
                "A published photograph always carries visible source attribution."
            )
        elif not _is_url(data["image_source"]):
            errors["image_source"] = "image_source must be a URL"
        if not data.get("image_caption"):
            errors["image_caption"] = (
                "image_caption is required when image is present (SCHEMA.md §2a rule 1)"
            )

    # ── FAQ ───────────────────────────────────────────────────────────────
    faq = data.get("faq")
    if faq is not None:
        if not isinstance(faq, list):
            errors["faq"] = "faq must be a list"
        elif len(faq) > FAQ_MAX_ITEMS:
            errors["faq"] = f"faq is capped at {FAQ_MAX_ITEMS} pairs (SCHEMA.md §2)"
        else:
            for pair in faq:
                if (
                    not isinstance(pair, dict)
                    or set(pair) != {"question", "answer"}
                    or not str(pair.get("question") or "").strip()
                    or not str(pair.get("answer") or "").strip()
                ):
                    errors["faq"] = "each faq entry needs a question and an answer"
                    break

    return errors
