"""validate_content.py — `/validate` checks 1 and 2. Gate 1.

Check 1 — schema validation of every MDX file in `_published` AND `_staging`,
against the SCHEMA.md §2 contract.
Check 2 — slug integrity across both directories.

**Why this exists when zod already validates.** The zod schema runs at build
time over `_published` only, because the collection loader deliberately points
there and nowhere else. Staging files are never seen by Astro. But a staging
file is exactly what a reviewer is about to approve, and finding out it is
invalid *after* it has been moved into `_published` is finding out too late.
UX.md §1.4 requires the admin to block approval on a schema-invalid staging
file, and this module is what tells it.

So the two validators are not redundant: zod guards the build, this guards the
queue. They must agree, which is what CLAUDE.md rule 7 and `/validate` check 13
are about.

**The self-test pattern.** This project has no test framework — no pytest, no
CI. Each validator carries its own fixture self-test that runs as part of the
check itself, so the regression fails the same command that runs the real check
(see `.claude/commands/validate.md`). `_selftest()` must catch a corrupted
fixture and pass a clean one.
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    AU_LATITUDE_BOUNDS,
    AU_LONGITUDE_BOUNDS,
    CATEGORIES,
    CELLAR_DOOR_STATES,
    CERTIFICATION_STATES,
    CONFIDENCE_TIERS,
    FRUIT_SOURCE,
    LOGISTICS_KEYS,
    OWNERSHIP_EVIDENCE_METHODS,
    PRACTICE_KEYS,
    PRODUCTION_BANDS,
    PUBLISHED_DIR,
    STAGING_DIR,
    STATES,
    VARIETY_KEYS,
    VERIFIABLE_FIELDS,
    VESSEL_KEYS,
    WINE_STYLE_KEYS,
)

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
URL = re.compile(r"^https?://")

#: Region and subregion slugs are the one vocabulary that lives in TypeScript
#: only (`site/src/data/regions.ts`), because it is the site's taxonomy and the
#: admin has no reason to own it. Parsed rather than mirrored, so there is no
#: fourth hand-kept copy to drift.
_REGIONS_TS = Path(__file__).resolve().parents[2] / "site" / "src" / "data" / "regions.ts"


def _region_slugs() -> tuple[set[str], dict[str, str]]:
    """Return (region slugs, {subregion slug: parent region slug})."""
    text = _REGIONS_TS.read_text(encoding="utf-8")
    regions = set(re.findall(r'slug:\s*"([^"]+)",\s*\n\s*name:[^\n]*\n\s*zone:', text))
    subs = dict(
        re.findall(
            r'slug:\s*"([^"]+)",\s*\n\s*name:[^\n]*\n\s*region:\s*"([^"]+)"', text
        )
    )
    return regions, subs


REGION_SLUGS, SUBREGION_PARENT = _region_slugs()


def parse_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Split an MDX file into (frontmatter dict, error)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, "no frontmatter block"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "unterminated frontmatter block"
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return None, f"unparseable YAML: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


# Field name -> (required, checker). A checker returns an error string or None.
def _enum(values: tuple[str, ...]):
    def check(v: Any) -> str | None:
        return None if v in values else f"must be one of {', '.join(values)}, got {v!r}"

    return check


def _str(v: Any) -> str | None:
    return None if isinstance(v, str) and v.strip() else "must be a non-empty string"


def _url(v: Any) -> str | None:
    return None if isinstance(v, str) and URL.match(v) else "must be an http(s) URL"


def _bool(v: Any) -> str | None:
    return None if isinstance(v, bool) else "must be a boolean"


def _date(v: Any) -> str | None:
    return None if isinstance(v, (date, datetime)) else "must be a YYYY-MM-DD date"


def _nullable(check):
    return lambda v: None if v is None else check(v)


def _list_of(check, *, unique: bool = False):
    def run(v: Any) -> str | None:
        if not isinstance(v, list):
            return "must be a list"
        for item in v:
            err = check(item)
            if err:
                return f"item {item!r}: {err}"
        if unique and len(set(map(str, v))) != len(v):
            return "must not contain duplicates"
        return None

    return run


def validate_frontmatter(data: dict[str, Any]) -> list[str]:
    """Every SCHEMA.md §2 rule this layer owns. Returns field-level errors."""
    errors: list[str] = []

    def field(name: str, check, *, required: bool) -> None:
        if name not in data:
            if required:
                errors.append(f"{name}: required field is missing")
            return
        err = check(data[name])
        if err:
            errors.append(f"{name}: {err}")

    field("name", _str, required=True)
    # parent_company: the KEY is always present. An absent key is an
    # undetermined producer, which is not publishable (SCHEMA.md §2).
    field("parent_company", _nullable(_str), required=True)
    field("category", _enum(CATEGORIES), required=True)
    field("website", _url, required=True)
    field("cellar_door", _enum(CELLAR_DOOR_STATES), required=True)
    field("organic", _enum(CERTIFICATION_STATES), required=True)
    field("biodynamic", _enum(CERTIFICATION_STATES), required=True)
    field("fruit_source", _enum(FRUIT_SOURCE), required=True)
    field("production_band", _enum(PRODUCTION_BANDS), required=True)
    field("buy_online", _bool, required=True)
    field("ships_nationally", _bool, required=True)
    field("drafted", _date, required=True)
    field("verified", _date, required=True)
    field("source_url", _url, required=True)
    field("primary_region", _enum(tuple(sorted(REGION_SLUGS))), required=True)
    field("regions", _list_of(_enum(tuple(sorted(REGION_SLUGS)))), required=True)
    field(
        "subregions",
        _list_of(_enum(tuple(sorted(SUBREGION_PARENT)))),
        required=False,
    )
    field("vessels", _list_of(_enum(VESSEL_KEYS), unique=True), required=False)
    field("varieties", _list_of(_enum(VARIETY_KEYS), unique=True), required=False)
    field("wine_styles", _list_of(_enum(WINE_STYLE_KEYS), unique=True), required=False)
    field("cellar_door_hours", _nullable(_str), required=False)
    field("cost", _nullable(_str), required=False)
    field("organic_certifier", _nullable(_str), required=False)
    field("biodynamic_certifier", _nullable(_str), required=False)
    field("shop_url", _nullable(_url), required=False)

    if isinstance(data.get("regions"), list) and not data["regions"]:
        errors.append("regions: must list at least one region")

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary: required, non-empty string")
    elif len(summary) > 160:
        errors.append(f"summary: {len(summary)} chars, max 160")

    # location — only `state` is required.
    location = data.get("location")
    if not isinstance(location, dict):
        errors.append("location: required object")
    else:
        if location.get("state") not in STATES:
            errors.append(f"location.state: must be one of {', '.join(STATES)}")
        for axis, bounds in (
            ("latitude", AU_LATITUDE_BOUNDS),
            ("longitude", AU_LONGITUDE_BOUNDS),
        ):
            value = location.get(axis)
            if value is None:
                continue  # Null coordinates do NOT block publication.
            if not isinstance(value, (int, float)):
                errors.append(f"location.{axis}: must be a number or null")
            elif not bounds[0] <= value <= bounds[1]:
                errors.append(
                    f"location.{axis}: {value} outside Australia ({bounds[0]}..{bounds[1]})"
                )

    # ownership_source — no producer publishes without a determination.
    ownership = data.get("ownership_source")
    if not isinstance(ownership, dict):
        errors.append("ownership_source: required object {source, method, date}")
    else:
        if not isinstance(ownership.get("source"), str) or not ownership["source"].strip():
            errors.append("ownership_source.source: required, non-empty")
        if ownership.get("method") not in OWNERSHIP_EVIDENCE_METHODS:
            errors.append(
                "ownership_source.method: must be one of "
                + ", ".join(OWNERSHIP_EVIDENCE_METHODS)
            )
        if _date(ownership.get("date")):
            errors.append("ownership_source.date: required YYYY-MM-DD date")

    # practices — strict, exactly the four keys, all required.
    practices = data.get("practices")
    if not isinstance(practices, dict):
        errors.append("practices: required object with exactly the four §1.6 keys")
    else:
        missing = set(PRACTICE_KEYS) - set(practices)
        extra = set(practices) - set(PRACTICE_KEYS)
        if missing:
            errors.append(f"practices: missing {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"practices: unknown key(s) {', '.join(sorted(extra))}")
        for key, value in practices.items():
            if key in PRACTICE_KEYS and not isinstance(value, bool):
                errors.append(f"practices.{key}: must be a boolean")

    logistics = data.get("logistics")
    if logistics is not None:
        if not isinstance(logistics, dict):
            errors.append("logistics: must be an object or omitted")
        else:
            for key, value in logistics.items():
                if key not in LOGISTICS_KEYS:
                    errors.append(f"logistics: unknown key {key!r}")
                elif not isinstance(value, bool):
                    errors.append(f"logistics.{key}: must be a boolean")

    verification = data.get("verification")
    if verification is not None:
        if not isinstance(verification, dict):
            errors.append("verification: must be an object or omitted")
        else:
            for key, record in verification.items():
                if key not in VERIFIABLE_FIELDS:
                    errors.append(f"verification: {key!r} is not a verifiable field")
                    continue
                if not isinstance(record, dict):
                    errors.append(f"verification.{key}: must be {{source, tier, date}}")
                    continue
                if record.get("tier") not in CONFIDENCE_TIERS:
                    errors.append(
                        f"verification.{key}.tier: must be one of "
                        + ", ".join(CONFIDENCE_TIERS)
                    )
                if not isinstance(record.get("source"), str):
                    errors.append(f"verification.{key}.source: required string")
                if _date(record.get("date")):
                    errors.append(f"verification.{key}.date: required date")

    faq = data.get("faq")
    if faq is not None:
        if not isinstance(faq, list):
            errors.append("faq: must be a list or omitted")
        elif len(faq) > 8:
            errors.append(f"faq: {len(faq)} pairs, hard cap 8")

    errors.extend(_cross_field(data))
    return errors


def _cross_field(data: dict[str, Any]) -> list[str]:
    """SCHEMA.md §2a rules that zod also owns. Kept in step deliberately."""
    errors: list[str] = []

    # Rule 1 — image co-requirements.
    if data.get("image"):
        for key in ("image_source", "image_caption"):
            if not data.get(key):
                errors.append(f"{key}: required when image is present (§2a rule 1)")

    # Rules 2 and 3 — certification requires a NAMED certifier, both ways.
    for subject, rule in (("organic", 2), ("biodynamic", 3)):
        state = data.get(subject)
        certifier = data.get(f"{subject}_certifier")
        if state == "certified" and not certifier:
            errors.append(
                f"{subject}_certifier: {subject} is certified but no certifier is "
                f"named (§2a rule {rule}). Publishing an unbacked certification "
                f"claim about a real business is a labelling problem."
            )
        if state != "certified" and certifier:
            errors.append(
                f"{subject}_certifier: must be null unless {subject} is certified "
                f"(§2a rule {rule})"
            )

    # Rule 4 — primary_region must be a member of regions.
    regions = data.get("regions")
    primary = data.get("primary_region")
    if isinstance(regions, list) and primary is not None and primary not in regions:
        errors.append(
            f"primary_region: {primary!r} is not in regions {regions} (§2a rule 4)"
        )

    # Rule 5 — every subregion must belong to a region this producer lists.
    if isinstance(regions, list):
        for sub in data.get("subregions") or []:
            parent = SUBREGION_PARENT.get(sub)
            if parent is None:
                errors.append(f"subregions: {sub!r} is not a known subregion")
            elif parent not in regions:
                errors.append(
                    f"subregions: {sub!r} belongs to {parent!r}, which is not in "
                    f"regions {regions} (§2a rule 5)"
                )

    # Rule 6 — buy_online requires a shop_url.
    if data.get("buy_online") and not data.get("shop_url"):
        errors.append("shop_url: required when buy_online is true (§2a rule 6)")

    # Rule 7 — cellar_door: none forbids cellar_door_hours.
    if data.get("cellar_door") == "none" and data.get("cellar_door_hours") is not None:
        errors.append(
            "cellar_door_hours: must be omitted when cellar_door is none (§2a rule 7)"
        )

    return errors


def check_1_schema() -> list[str]:
    """Every MDX in `_published` and `_staging`, per file, per field."""
    errors: list[str] = []
    for directory in (PUBLISHED_DIR, STAGING_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.mdx")):
            data, parse_error = parse_frontmatter(path)
            if parse_error:
                errors.append(f"{path.name}: {parse_error}")
                continue
            assert data is not None
            for message in validate_frontmatter(data):
                errors.append(f"{path.name}: {message}")
    return errors


def check_2_slugs() -> list[str]:
    """No duplicates across the two directories; kebab-case; never a field."""
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for directory in (PUBLISHED_DIR, STAGING_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.mdx")):
            slug = path.stem
            if not KEBAB.match(slug):
                errors.append(f"{path.name}: filename is not kebab-case")
            if slug in seen:
                errors.append(
                    f"{path.name}: duplicate slug {slug!r}, also at {seen[slug]}"
                )
            seen[slug] = path
            data, _ = parse_frontmatter(path)
            if data and "slug" in data:
                errors.append(
                    f"{path.name}: 'slug' is not a frontmatter field; it is derived "
                    f"from the filename everywhere (SCHEMA.md §2)"
                )
    return errors


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one.

    A constraint nobody has watched fail has not been verified, so this runs
    every time the real check runs rather than living in a test suite that
    nobody executes.
    """
    errors: list[str] = []

    clean: dict[str, Any] = {
        "name": "Selftest Wines",
        "parent_company": None,
        "ownership_source": {
            "source": "https://example.com/about",
            "method": "producer_statement",
            "date": date(2026, 8, 7),
        },
        "category": "garagiste",
        "website": "https://example.com",
        "location": {"state": "SA", "latitude": -34.9, "longitude": 138.7},
        "regions": ["adelaide-hills"],
        "primary_region": "adelaide-hills",
        "cellar_door": "none",
        "organic": "none",
        "organic_certifier": None,
        "biodynamic": "none",
        "biodynamic_certifier": None,
        "fruit_source": "purchased",
        "practices": {k: False for k in PRACTICE_KEYS},
        "production_band": "unknown",
        "buy_online": False,
        "ships_nationally": False,
        "summary": "A self-test fixture.",
        "drafted": date(2026, 8, 7),
        "verified": date(2026, 8, 7),
        "source_url": "https://example.com/about",
    }

    found = validate_frontmatter(clean)
    if found:
        errors.append(f"selftest: clean fixture rejected: {found}")

    # Each corruption must be caught, and the message must name the field.
    corruptions: list[tuple[str, dict[str, Any], str]] = [
        ("missing required field", {"parent_company": ...}, "parent_company"),
        ("bad enum", {"category": "boutique_winery"}, "category"),
        ("summary over 160", {"summary": "x" * 161}, "summary"),
        ("bad state", {"location": {"state": "XX"}}, "location.state"),
        ("coords outside Australia", {"location": {"state": "SA", "latitude": 51.5}}, "latitude"),
        ("practices missing a key", {"practices": {"unfined": True}}, "practices"),
        ("practices extra key", {"practices": {**{k: False for k in PRACTICE_KEYS}, "low_intervention": True}}, "practices"),
        ("§2a r2 certified, no certifier", {"organic": "certified"}, "organic_certifier"),
        ("§2a r2 certifier without certified", {"organic_certifier": "ACO"}, "organic_certifier"),
        ("§2a r4 primary_region not in regions", {"primary_region": "yarra-valley"}, "primary_region"),
        ("§2a r5 subregion wrong parent", {"subregions": ["red-hill"]}, "subregions"),
        ("§2a r6 buy_online without shop_url", {"buy_online": True}, "shop_url"),
        ("§2a r7 hours on cellar_door none", {"cellar_door_hours": "Weekends"}, "cellar_door_hours"),
        ("unknown region slug", {"regions": ["not-a-region"], "primary_region": "not-a-region"}, "regions"),
        ("duplicate varieties", {"varieties": ["shiraz", "shiraz"]}, "varieties"),
        ("ownership_source missing", {"ownership_source": ...}, "ownership_source"),
    ]

    for label, patch, expect_field in corruptions:
        fixture = {**clean}
        for key, value in patch.items():
            if value is ...:
                fixture.pop(key, None)
            else:
                fixture[key] = value
        found = validate_frontmatter(fixture)
        if not found:
            errors.append(f"selftest: '{label}' was NOT caught")
        elif not any(expect_field in message for message in found):
            errors.append(
                f"selftest: '{label}' was caught but no message named "
                f"{expect_field!r}: {found}"
            )

    return errors


def main() -> int:
    errors = _selftest() + check_1_schema() + check_2_slugs()
    if errors:
        print(f"VALIDATE 1-2 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    published = len(list(PUBLISHED_DIR.glob("*.mdx"))) if PUBLISHED_DIR.is_dir() else 0
    staged = len(list(STAGING_DIR.glob("*.mdx"))) if STAGING_DIR.is_dir() else 0
    print(
        f"VALIDATE 1-2 PASS — selftest ok; {published} published, {staged} staged, "
        f"0 errors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
