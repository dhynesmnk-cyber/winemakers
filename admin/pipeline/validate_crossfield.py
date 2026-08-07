"""validate_crossfield.py — `/validate` checks 9 and 10. Gate 4.

Check 9 — **certification integrity.** `organic: certified` without a named
`organic_certifier` fails; the same for `biodynamic`. A certifier named while
the state is not `certified` also fails.

Check 10 — **numeric cross-checks.** Every `tasting_fee.fee_aud` falls within
the range of dollar amounts stated in the freeform `cost` string, and
`annual_production_cases`, when present, falls inside `production_band`.

── Why these are not already covered ─────────────────────────────────────────

Check 1 asserts the same certification rule at the level of one file's
frontmatter, because zod does. These two are the *cross-field* rules of
SCHEMA.md §2a that need something zod cannot see: check 10's rules 8 and 9
compare a structured number against a freeform string and against a config
range, and SCHEMA.md §2a says plainly that this lives in Python rather than in
zod because **the regex that scrapes dollar amounts from the freeform string is
shared with the display helper. Keep that split: one regex, one home.** That
home is `admin/schema.py::dollar_amounts`, and this module calls it rather than
writing a second one.

Check 9 is separated from check 1 for a different reason. It reads the
`_published` set only, and it is the check that answers "is there an unbacked
certification claim on the live site right now?" — a question about the
published record rather than about a file being edited.

── Why an unbacked certification claim is a serious defect ───────────────────

`organic: certified` is a claim about a real business's legal standing, made in
public, on a page that business did not write. A certification claim with no
named certifier is the kind of error that damages a producer rather than the
site. CLAUDE.md's editorial guardrails put it plainly: no claim of certification
without a named certifier.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin import schema  # noqa: E402
from admin.config import (  # noqa: E402
    CERTIFICATION_STATES,
    PRODUCTION_BAND_RANGES,
    PUBLISHED_DIR,
    STAGING_DIR,
)
from admin.pipeline.validate_content import parse_frontmatter  # noqa: E402


def _files() -> list[Path]:
    """`_published` and `_staging` both.

    A staging file is what a reviewer is about to approve, and finding an
    unbacked certification claim after it has moved into `_published` is finding
    out too late — the same reasoning check 1 is built on.
    """
    found: list[Path] = []
    for directory in (PUBLISHED_DIR, STAGING_DIR):
        if directory.is_dir():
            found.extend(sorted(directory.glob("*.mdx")))
    return found


# =============================================================================
# Check 9 — certification integrity (SCHEMA.md §2a rules 2 and 3)
# =============================================================================


def certification_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for subject in ("organic", "biodynamic"):
        state = data.get(subject)
        certifier = data.get(f"{subject}_certifier")
        named = isinstance(certifier, str) and certifier.strip()

        if state not in CERTIFICATION_STATES:
            errors.append(
                f"{subject}: {state!r} is not one of {', '.join(CERTIFICATION_STATES)}"
            )
            continue

        if state == "certified" and not named:
            errors.append(
                f"{subject}_certifier: {subject} is 'certified' and no certifier is "
                f"named. Publishing an unbacked certification claim about a real "
                f"business is a labelling problem, not a formatting one "
                f"(SCHEMA.md §2a rule {2 if subject == 'organic' else 3})."
            )
        if state != "certified" and named:
            errors.append(
                f"{subject}_certifier: {certifier!r} is named while {subject} is "
                f"{state!r}. A certifier is recorded only against 'certified'; "
                f"anything else reads as a certification the producer does not hold."
            )
    return errors


def check_9_certification() -> list[str]:
    errors: list[str] = []
    for path in _files():
        data, parse_error = parse_frontmatter(path)
        if parse_error:
            errors.append(f"{path.name}: {parse_error}")
            continue
        assert data is not None
        for message in certification_errors(data):
            errors.append(f"{path.name}: {message}")
    return errors


# =============================================================================
# Check 10 — numeric cross-checks (SCHEMA.md §2a rules 8 and 9)
# =============================================================================


def numeric_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # Rule 8. A structured fee the cost string cannot corroborate is a failure,
    # and the remedy stated in SCHEMA.md is to DELETE the whole tasting_fee
    # object rather than leave an uncorroborated figure standing.
    fee_block = data.get("tasting_fee")
    if isinstance(fee_block, dict):
        fee = fee_block.get("fee_aud")
        if isinstance(fee, (int, float)) and not isinstance(fee, bool):
            cost = data.get("cost")
            amounts = schema.dollar_amounts(cost)
            if not amounts:
                errors.append(
                    f"tasting_fee.fee_aud is {fee} and the cost string states no "
                    f"dollar amount at all ({cost!r}). Delete the tasting_fee "
                    f"object rather than leave an uncorroborated figure "
                    f"(SCHEMA.md §2a rule 8)."
                )
            elif not min(amounts) <= fee <= max(amounts):
                errors.append(
                    f"tasting_fee.fee_aud is {fee}, outside the "
                    f"{min(amounts)} to {max(amounts)} stated in cost ({cost!r}). "
                    f"Delete the tasting_fee object rather than leave an "
                    f"uncorroborated figure (SCHEMA.md §2a rule 8)."
                )

        waived = fee_block.get("waived_on_purchase")
        if waived is not None and not isinstance(waived, bool):
            errors.append(
                f"tasting_fee.waived_on_purchase is {waived!r}, must be true, false or null"
            )

    # Rule 9. `unknown` has no range and never corroborates or contradicts.
    cases = data.get("annual_production_cases")
    band = data.get("production_band")
    if isinstance(cases, int) and not isinstance(cases, bool):
        bounds = PRODUCTION_BAND_RANGES.get(band)
        if bounds is not None:
            low, high = bounds
            if cases < low or (high is not None and cases > high):
                implied = schema.band_for_cases(cases)
                errors.append(
                    f"annual_production_cases is {cases}, outside production_band "
                    f"{band!r} ({low} to {high if high is not None else 'unbounded'}). "
                    f"That figure implies {implied!r} (SCHEMA.md §2a rule 9)."
                )
    return errors


def check_10_numeric() -> list[str]:
    errors: list[str] = []
    for path in _files():
        data, parse_error = parse_frontmatter(path)
        if parse_error:
            errors.append(f"{path.name}: {parse_error}")
            continue
        assert data is not None
        for message in numeric_errors(data):
            errors.append(f"{path.name}: {message}")
    return errors


# =============================================================================
# The self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    clean: dict[str, Any] = {
        "organic": "practising",
        "organic_certifier": None,
        "biodynamic": "none",
        "biodynamic_certifier": None,
        "cost": "Tastings $15 per person, waived on a six-bottle purchase",
        "tasting_fee": {"fee_aud": 15, "waived_on_purchase": True},
        "annual_production_cases": 2400,
        "production_band": "1000_5000",
    }
    found = certification_errors(clean) + numeric_errors(clean)
    if found:
        errors.append(f"selftest: clean fixture rejected: {found}")

    # A certified state WITH a named certifier is the other clean case, and it
    # has to pass or the check would block every genuinely certified producer.
    certified = {**clean, "organic": "certified", "organic_certifier": "ACO"}
    if certification_errors(certified):
        errors.append("selftest: a properly certified fixture was rejected")

    # `unknown` never contradicts a case figure, however large.
    unbanded = {**clean, "production_band": "unknown", "annual_production_cases": 999999}
    if numeric_errors(unbanded):
        errors.append("selftest: production_band 'unknown' contradicted a case figure")

    # No tasting_fee object at all is legitimate and must not fire rule 8.
    feeless = {key: value for key, value in clean.items() if key != "tasting_fee"}
    feeless["cost"] = None
    if numeric_errors(feeless):
        errors.append("selftest: a producer with no tasting fee was rejected")

    corruptions: list[tuple[str, dict[str, Any], str, Any]] = [
        (
            "certified with no certifier",
            {"organic": "certified"},
            "organic_certifier",
            certification_errors,
        ),
        (
            "certifier named while practising",
            {"organic_certifier": "ACO"},
            "organic_certifier",
            certification_errors,
        ),
        (
            "biodynamic certified with no certifier",
            {"biodynamic": "certified"},
            "biodynamic_certifier",
            certification_errors,
        ),
        (
            "biodynamic certifier while none",
            {"biodynamic_certifier": "Demeter"},
            "biodynamic_certifier",
            certification_errors,
        ),
        (
            "§2a r8 fee the cost string cannot corroborate",
            {"tasting_fee": {"fee_aud": 40, "waived_on_purchase": True}},
            "tasting_fee.fee_aud",
            numeric_errors,
        ),
        (
            "§2a r8 fee with no dollar amount in cost at all",
            {"cost": "Tastings by arrangement"},
            "tasting_fee.fee_aud",
            numeric_errors,
        ),
        (
            "§2a r9 cases outside the band",
            {"annual_production_cases": 40000},
            "annual_production_cases",
            numeric_errors,
        ),
        (
            "§2a r9 cases below the band",
            {"annual_production_cases": 200},
            "annual_production_cases",
            numeric_errors,
        ),
    ]

    for label, patch, expect, checker in corruptions:
        fixture = {**clean, **patch}
        found = checker(fixture)
        if not found:
            errors.append(f"selftest: '{label}' was NOT caught")
        elif not any(expect in message for message in found):
            errors.append(
                f"selftest: '{label}' was caught but no message named {expect!r}: {found}"
            )

    return errors


def main() -> int:
    errors = _selftest() + check_9_certification() + check_10_numeric()
    if errors:
        print(f"VALIDATE 9-10 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    print(f"VALIDATE 9-10 PASS — selftest ok; {len(_files())} file(s) checked, 0 errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
