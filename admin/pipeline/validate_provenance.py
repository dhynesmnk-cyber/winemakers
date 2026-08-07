"""validate_provenance.py — `/validate` check 14. Gate 4.

Every populated `VERIFIABLE_FIELDS` entry carries a `{source, tier, date}`
record, and **no tier is lower than the same field's tier in the previous
commit** (SCHEMA.md §2a rule 12, §2b).

── The no-downgrade rule and why git is the right oracle ─────────────────────

SCHEMA.md §2b: on a re-harvest, a field already at an equal-or-stronger tier is
**preserved, never downgraded** (`CONFIDENCE_TIER_RANK`). That is a rule about
change over time, so checking it needs a previous state to compare against, and
this project has exactly one durable record of previous state: git.

The comparison is against `HEAD`, read with `git show`. A file not in `HEAD` is
new and has nothing to downgrade from. A repository with no commits, or a git
that is unavailable, reports the fact and skips that half rather than passing
silently — a check that cannot run must never look like a check that passed.

── Why a downgrade matters more than it looks ────────────────────────────────

`observed_on_visit` and `operator_confirmed` are the two tiers this project
cannot generate. The pipeline only ever sets `published_by_producer`
(SCHEMA.md §1.11), so the stronger tiers only ever arrive from a person who did
the work. A silent downgrade discards that person's work and replaces it with a
machine's weaker claim, and nothing else in the system would notice.

`parent_company` is on `VERIFIABLE_FIELDS` deliberately, and UX.md §1.4.6 makes
its `{source, tier, date}` block the durable public half of the ownership
determination. That is the entry this check exists for above all the others.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    CONFIDENCE_TIER_RANK,
    CONFIDENCE_TIERS,
    PUBLISHED_DIR,
    ROOT,
    VERIFIABLE_FIELDS,
)
from admin.pipeline.validate_content import parse_frontmatter  # noqa: E402

#: A verifiable field counts as populated when it carries a real value. `None`,
#: `""` and `[]` are all "the producer does not state this", and a field the
#: producer does not state carries no verification record (SCHEMA.md §2b).
_EMPTY = (None, "", [], {})


def is_populated(value: Any) -> bool:
    return value not in _EMPTY


# =============================================================================
# 1. Every populated verifiable field carries a record
# =============================================================================


def provenance_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    verification = data.get("verification")
    if verification is None:
        verification = {}
    if not isinstance(verification, dict):
        return ["verification: must be an object keyed by field name"]

    for field in VERIFIABLE_FIELDS:
        # `parent_company` is handled below. `null` is its publishable value, so
        # `is_populated` is False for every publishable producer and the general
        # rules here would read its record as one for an unstated field.
        if field == "parent_company":
            continue
        populated = is_populated(data.get(field))
        record = verification.get(field)

        if populated and record is None:
            errors.append(
                f"verification.{field}: {field} is populated and carries no "
                f"{{source, tier, date}} record (SCHEMA.md §2a rule 12)"
            )
            continue
        if record is None:
            continue
        if not populated:
            errors.append(
                f"verification.{field}: a record exists but {field} is not "
                f"populated. A field the producer does not state carries none."
            )
            continue
        if not isinstance(record, dict):
            errors.append(f"verification.{field}: must be {{source, tier, date}}")
            continue

        if not str(record.get("source") or "").strip():
            errors.append(f"verification.{field}.source: required, non-empty")
        tier = record.get("tier")
        if tier not in CONFIDENCE_TIERS:
            errors.append(
                f"verification.{field}.tier: {tier!r} must be one of "
                + ", ".join(CONFIDENCE_TIERS)
            )
        stamp = record.get("date")
        if not isinstance(stamp, (date, datetime)) and not str(stamp or "").strip():
            errors.append(f"verification.{field}.date: required")

    # `parent_company` always carries a record, whatever its value. `null` is a
    # positive assertion of independence rather than an empty field, and UX.md
    # §1.4.6 makes this block the durable public half of the determination.
    if "parent_company" in data:
        record = verification.get("parent_company")
        if record is None:
            errors.append(
                "verification.parent_company: missing. `parent_company: null` is a "
                "positive assertion of independence, not an empty field, and it is "
                "the durable public record of the determination (UX.md §1.4.6)."
            )
        elif not isinstance(record, dict):
            errors.append("verification.parent_company: must be {source, tier, date}")
        else:
            if not str(record.get("source") or "").strip():
                errors.append("verification.parent_company.source: required, non-empty")
            if record.get("tier") not in CONFIDENCE_TIERS:
                errors.append(
                    f"verification.parent_company.tier: {record.get('tier')!r} must be "
                    + "one of "
                    + ", ".join(CONFIDENCE_TIERS)
                )
            stamp = record.get("date")
            if not isinstance(stamp, (date, datetime)) and not str(stamp or "").strip():
                errors.append("verification.parent_company.date: required")

    return errors


# =============================================================================
# 2. No tier is lower than the same field's tier in the previous commit
# =============================================================================


def _git(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return result.returncode, result.stdout


def _previous_tiers(relative: str) -> dict[str, str] | None:
    """`{field: tier}` as of `HEAD`, or `None` when the file is new there."""
    code, text = _git("show", f"HEAD:{relative}")
    if code != 0 or not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    verification = data.get("verification")
    if not isinstance(verification, dict):
        return {}
    return {
        field: record["tier"]
        for field, record in verification.items()
        if isinstance(record, dict) and record.get("tier") in CONFIDENCE_TIER_RANK
    }


def downgrade_errors(path: Path, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return errors

    previous = _previous_tiers(relative)
    if previous is None:
        return errors  # new file at HEAD: nothing to downgrade from

    verification = data.get("verification")
    verification = verification if isinstance(verification, dict) else {}
    for field, was in previous.items():
        record = verification.get(field)
        now = record.get("tier") if isinstance(record, dict) else None
        if now is None:
            errors.append(
                f"verification.{field}: was {was!r} at HEAD and now carries no "
                f"record. A tier is preserved, never dropped (SCHEMA.md §2b)."
            )
            continue
        if CONFIDENCE_TIER_RANK.get(now, -1) < CONFIDENCE_TIER_RANK[was]:
            errors.append(
                f"verification.{field}.tier: downgraded from {was!r} to {now!r}. "
                f"A re-harvest upgrades and never silently downgrades "
                f"(SCHEMA.md §1.11, §2b). {'The stronger tiers only ever come from a person who did the work.' if CONFIDENCE_TIER_RANK[was] >= 2 else ''}"
            )
    return errors


def check_14_provenance() -> tuple[list[str], list[str]]:
    """`(errors, notes)` across `_published`."""
    errors: list[str] = []
    notes: list[str] = []
    if not PUBLISHED_DIR.is_dir():
        return errors, notes

    code, _ = _git("rev-parse", "--verify", "HEAD")
    comparable = code == 0
    if not comparable:
        notes.append(
            "no HEAD to compare against, so the no-downgrade half of this check "
            "did not run. This is not a pass."
        )

    for path in sorted(PUBLISHED_DIR.glob("*.mdx")):
        data, parse_error = parse_frontmatter(path)
        if parse_error:
            errors.append(f"{path.name}: {parse_error}")
            continue
        assert data is not None
        for message in provenance_errors(data):
            errors.append(f"{path.name}: {message}")
        if comparable:
            for message in downgrade_errors(path, data):
                errors.append(f"{path.name}: {message}")
    return errors, notes


# =============================================================================
# 3. The self-test
# =============================================================================


def _record(tier: str = "published_by_producer") -> dict[str, Any]:
    return {"source": "https://example.invalid/about", "tier": tier, "date": date(2026, 8, 7)}


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    clean: dict[str, Any] = {
        "parent_company": None,
        "organic": "practising",
        "biodynamic": "none",
        "fruit_source": "estate",
        "production_band": "under_1000",
        "founded_year": 2003,
        "varieties": ["shiraz"],
        "verification": {
            "parent_company": _record(),
            "organic": _record(),
            "biodynamic": _record(),
            "fruit_source": _record(),
            "production_band": _record(),
            "founded_year": _record(),
            "varieties": _record(),
        },
    }
    found = provenance_errors(clean)
    if found:
        errors.append(f"selftest: clean fixture rejected: {found}")

    # A field the producer does not state carries no record, and that is clean.
    sparse = {
        key: value for key, value in clean.items() if key not in ("founded_year", "varieties")
    }
    sparse["verification"] = {
        key: value
        for key, value in clean["verification"].items()
        if key not in ("founded_year", "varieties")
    }
    if provenance_errors(sparse):
        errors.append("selftest: a producer with unstated fields was rejected")

    corruptions: list[tuple[str, Any, str]] = [
        (
            "a populated field with no record",
            {**clean, "verification": {k: v for k, v in clean["verification"].items() if k != "organic"}},
            "verification.organic",
        ),
        (
            "parent_company null with no record",
            {**clean, "verification": {k: v for k, v in clean["verification"].items() if k != "parent_company"}},
            "verification.parent_company",
        ),
        (
            "a record for an unpopulated field",
            {**clean, "verification": {**clean["verification"], "tasting_fee": _record()}},
            "verification.tasting_fee",
        ),
        (
            "an unknown tier",
            {**clean, "verification": {**clean["verification"], "organic": _record("probably")}},
            "verification.organic.tier",
        ),
        (
            "a record with no source",
            {**clean, "verification": {**clean["verification"], "organic": {"tier": "published_by_producer", "date": date(2026, 8, 7)}}},
            "verification.organic.source",
        ),
        (
            "a record with no date",
            {**clean, "verification": {**clean["verification"], "organic": {"source": "https://x.invalid", "tier": "published_by_producer"}}},
            "verification.organic.date",
        ),
    ]
    for label, fixture, expect in corruptions:
        found = provenance_errors(fixture)
        if not found:
            errors.append(f"selftest: '{label}' was NOT caught")
        elif not any(expect in message for message in found):
            errors.append(
                f"selftest: '{label}' was caught but no message named {expect!r}: {found}"
            )

    # ── The no-downgrade comparison, exercised without touching git.
    for was, now, should_fail in (
        ("operator_confirmed", "published_by_producer", True),
        ("observed_on_visit", "unverified", True),
        ("published_by_producer", "operator_confirmed", False),
        ("published_by_producer", "published_by_producer", False),
    ):
        downgraded = CONFIDENCE_TIER_RANK[now] < CONFIDENCE_TIER_RANK[was]
        if downgraded is not should_fail:
            errors.append(
                f"selftest: the tier ranking is wrong, {was!r} -> {now!r} "
                f"reported downgraded={downgraded}"
            )

    return errors


def main() -> int:
    found, notes = check_14_provenance()
    errors = _selftest() + found
    for note in notes:
        print(f"  note: {note}")
    if errors:
        print(f"VALIDATE 14 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    published = len(list(PUBLISHED_DIR.glob("*.mdx"))) if PUBLISHED_DIR.is_dir() else 0
    print(
        f"VALIDATE 14 PASS — selftest ok; {published} published producer(s) carry a "
        f"complete provenance block and no tier is lower than at HEAD"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
