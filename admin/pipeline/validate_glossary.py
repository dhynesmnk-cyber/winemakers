"""validate_glossary.py — `/validate` check 11, glossary coverage. GATE 6.

From `.claude/commands/validate.md`:

    11. Glossary coverage — every enum value across every §1 vocabulary has a
        `glossary.ts` entry, and every glossary entry maps to a live enum value.
        Orphans in either direction = fail.

BOTH DIRECTIONS, and the second one is the reason this is a check rather than a
build assertion.

`config.ts` already fails the build on the first direction: `labelsFor` throws
when a tuple value has no glossary entry, because DESIGN.md §9 says a vocabulary
value with no glossary entry must fail the build rather than render blank. So
the forward direction is already guarded.

Nothing guards the reverse. A glossary entry whose enum value was renamed or
removed keeps its `/glossary/[key]/` page, keeps appearing in the index, and
defines a term the schema no longer has. It is unreachable from any producer and
says something untrue about the vocabulary. Only this check finds it.

── What is deliberately NOT covered ──────────────────────────────────────────

`VERIFIABLE_FIELDS` (SCHEMA.md §1.12) is a list of FIELD NAMES, not a vocabulary
of values, and `glossary.ts` records it as such: `COVERED_VOCABULARIES` omits it
on purpose. Treating it as a vocabulary would report thirteen false orphans.
This check reads that list rather than deciding for itself which vocabularies
count, so the exclusion lives in one place.
"""

from __future__ import annotations

from typing import Any

from .. import config as py_config
from . import ts_data

#: Vocabulary id in `glossary.ts` -> the tuple in `admin/config.py` that owns
#: its values. The mapping is spelled out rather than derived from the name,
#: because the two namings genuinely differ (`cellar-door` / `CELLAR_DOOR_STATES`)
#: and a clever derivation would silently skip whatever it failed to match.
VOCABULARY_TUPLES: dict[str, str] = {
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


def check(
    entries: list[dict[str, Any]] | None = None,
    covered: list[str] | None = None,
    tuples: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    """Both directions. Returns a list of failures, empty when clean."""
    entries = ts_data.glossary() if entries is None else entries
    covered = ts_data.covered_vocabularies() if covered is None else covered

    if tuples is None:
        tuples = {}
        for vocabulary, name in VOCABULARY_TUPLES.items():
            values = getattr(py_config, name, None)
            if values is None:
                tuples[vocabulary] = ()
            else:
                tuples[vocabulary] = tuple(values)

    errors: list[str] = []

    # Every vocabulary glossary.ts claims to cover must be one we can check.
    for vocabulary in covered:
        if vocabulary not in tuples:
            errors.append(
                f"COVERED_VOCABULARIES names {vocabulary!r}, which this check has "
                f"no config tuple for. Add it to VOCABULARY_TUPLES."
            )

    by_vocabulary: dict[str, set[str]] = {}
    seen_slugs: set[str] = set()
    for entry in entries:
        vocabulary = entry.get("vocabulary", "")
        value = entry.get("value", "")
        slug = entry.get("slug", "")

        # Slugs are URLs. A duplicate would silently drop a page.
        if slug in seen_slugs:
            errors.append(f"glossary.ts: duplicate slug {slug!r}")
        seen_slugs.add(slug)

        by_vocabulary.setdefault(vocabulary, set()).add(value)

        # Reverse direction: an entry whose value no longer exists.
        known = tuples.get(vocabulary)
        if known is None:
            errors.append(
                f"glossary.ts: {slug!r} has vocabulary {vocabulary!r}, "
                f"which is not a SCHEMA.md §1 vocabulary"
            )
        elif value not in known:
            errors.append(
                f"glossary.ts: {slug!r} defines {vocabulary}/{value!r}, which is "
                f"not a value of {VOCABULARY_TUPLES.get(vocabulary, vocabulary)}. "
                f"The enum value was renamed or removed and the entry outlived it."
            )

        # Every entry is a page, and every page needs its copy.
        for field in ("term", "short", "definition"):
            if not entry.get(field):
                errors.append(f"glossary.ts: {slug!r} has no {field}")

    # Forward direction: a vocabulary value with no entry.
    for vocabulary in covered:
        known = tuples.get(vocabulary)
        if known is None:
            continue
        have = by_vocabulary.get(vocabulary, set())
        for value in known:
            if value not in have:
                errors.append(
                    f"{VOCABULARY_TUPLES.get(vocabulary, vocabulary)} value "
                    f"{value!r} has no glossary.ts entry"
                )

    # `see_also` targets must resolve, or a glossary page links to a 404.
    for entry in entries:
        for target in entry.get("see_also") or []:
            if target not in seen_slugs:
                errors.append(
                    f"glossary.ts: {entry.get('slug')!r} see_also names "
                    f"{target!r}, which is not a glossary slug"
                )

    return errors


# =============================================================================
# Self-test
# =============================================================================


def _entry(slug: str, vocabulary: str, value: str, **extra: Any) -> dict[str, Any]:
    base = {
        "slug": slug,
        "vocabulary": vocabulary,
        "value": value,
        "term": "Term",
        "short": "One line.",
        "definition": "Two sentences. Really.",
    }
    base.update(extra)
    return base


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    tuples = {"colour": ("red", "white")}
    covered = ["colour"]
    clean = [_entry("colour-red", "colour", "red"), _entry("colour-white", "colour", "white")]

    if check(clean, covered, tuples):
        errors.append("selftest: a complete glossary was rejected")

    cases: list[tuple[str, list[dict[str, Any]]]] = [
        ("a vocabulary value with NO entry", [clean[0]]),
        (
            "an entry whose value is not in the tuple",
            clean + [_entry("colour-puce", "colour", "puce")],
        ),
        (
            "an entry in an unknown vocabulary",
            clean + [_entry("shape-round", "shape", "round")],
        ),
        (
            "a duplicate slug",
            clean + [_entry("colour-red", "colour", "white")],
        ),
        (
            "an entry with no definition",
            [clean[0], _entry("colour-white", "colour", "white", definition="")],
        ),
        (
            "a see_also pointing nowhere",
            [
                clean[0],
                _entry("colour-white", "colour", "white", see_also=["colour-teal"]),
            ],
        ),
    ]
    for label, fixture in cases:
        if not check(fixture, covered, tuples):
            errors.append(f"selftest: {label} was NOT caught")

    # The exclusion that matters: a vocabulary absent from COVERED_VOCABULARIES
    # is not required to be complete. VERIFIABLE_FIELDS is why.
    partial = [_entry("colour-red", "colour", "red")]
    if check(partial, [], tuples):
        errors.append(
            "selftest: an UNCOVERED vocabulary was required to be complete, "
            "which would report VERIFIABLE_FIELDS as thirteen orphans"
        )

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print("VALIDATE 11 FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    real = check()
    if real:
        print("VALIDATE 11 FAIL")
        for error in real:
            print(f"  {error}")
        return 1

    entries = ts_data.glossary()
    covered = ts_data.covered_vocabularies()
    print(
        f"VALIDATE 11 PASS — selftest ok; {len(entries)} glossary entries cover "
        f"every value of {len(covered)} vocabularies, with no entry outliving "
        f"its enum value"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
