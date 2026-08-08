"""validate_taxonomy.py — `/validate` check 12, the region taxonomy lint. GATE 6.

From `.claude/commands/validate.md`:

    12. Region taxonomy lint — every `primary_region` exists in `regions.ts`;
        every `regions[]` member exists; every `subregions[]` member belongs to
        a region listed in that producer's `regions[]`; every state in `STATES`
        has ≥1 region.

Four assertions, three about published producers and one about the register
itself. The fourth is the one that matters before there is any data: if a state
has no region, a producer in that state has no region slug to use and cannot be
published at all, so the register is broken in a way no producer file reveals.
It is why the Northern Territory carries a `registered_as: "none"` placeholder
entry rather than being left out.

── The overlap with zod, and why this is not redundant ───────────────────────

The zod schema already refuses a bad `primary_region` at build time, and SCHEMA.md
§2a rule 5 already refuses an orphan subregion. This check runs the same
assertions against the SAME files from the other side, in Python, without Astro.

That is deliberate rather than duplicated effort. `_published` is the source of
truth and the DB is disposable, so a check that only ever runs inside the site
build cannot tell you the register is broken until the build is already failing.
This one runs in a bare clone with no npm install, and it reads regions.ts
directly rather than through the schema that imports it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import PUBLISHED_DIR, STAGING_DIR, STATES
from . import ts_data
from .data_store import read_frontmatter


# =============================================================================
# 1. The four assertions
# =============================================================================


def check_register(
    regions: list[dict[str, Any]] | None = None,
    subregions: list[dict[str, Any]] | None = None,
    states: tuple[str, ...] = STATES,
) -> list[str]:
    """The register's own integrity, independent of any producer."""
    regions = ts_data.regions() if regions is None else regions
    subregions = ts_data.subregions() if subregions is None else subregions
    errors: list[str] = []

    slugs = {r["slug"] for r in regions}
    if len(slugs) != len(regions):
        seen: set[str] = set()
        for region in regions:
            if region["slug"] in seen:
                errors.append(f"regions.ts: duplicate region slug {region['slug']}")
            seen.add(region["slug"])

    sub_slugs: set[str] = set()
    for sub in subregions:
        if sub["slug"] in sub_slugs:
            errors.append(f"regions.ts: duplicate subregion slug {sub['slug']}")
        sub_slugs.add(sub["slug"])
        if sub["region"] not in slugs:
            errors.append(
                f"regions.ts: subregion {sub['slug']} names parent region "
                f"{sub['region']}, which is not a region"
            )

    # Every subregion listed on a region must exist, and vice versa. A region
    # that lists a subregion the SUBREGIONS array does not define would render a
    # link row entry with no page behind it.
    for region in regions:
        for slug in region.get("subregions", []):
            if slug not in sub_slugs:
                errors.append(
                    f"regions.ts: region {region['slug']} lists subregion {slug}, "
                    f"which is not defined in SUBREGIONS"
                )
    for sub in subregions:
        parent = next((r for r in regions if r["slug"] == sub["region"]), None)
        if parent is not None and sub["slug"] not in parent.get("subregions", []):
            errors.append(
                f"regions.ts: subregion {sub['slug']} claims region "
                f"{sub['region']}, which does not list it back"
            )

    # THE ASSERTION THAT BITES BEFORE THERE IS ANY DATA.
    for state in states:
        if not any(state in r.get("states", []) for r in regions):
            errors.append(
                f"regions.ts: state {state} has no region. A producer there would "
                f"have no region slug to use and could not be published."
            )

    return errors


def check_producers(
    directories: list[Path] | None = None,
    regions: list[dict[str, Any]] | None = None,
    subregions: list[dict[str, Any]] | None = None,
) -> tuple[list[str], int]:
    """Every published and staged producer against the register."""
    regions = ts_data.regions() if regions is None else regions
    subregions = ts_data.subregions() if subregions is None else subregions

    region_slugs = {r["slug"] for r in regions}
    sub_parent = {s["slug"]: s["region"] for s in subregions}

    if directories is None:
        directories = [PUBLISHED_DIR, STAGING_DIR]

    errors: list[str] = []
    count = 0

    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.mdx")):
            slug = path.stem
            # read_frontmatter, NOT parse_frontmatter or iter_published. Both
            # of those apply the DB-insertability bar and drop anything short of
            # it, which is right for a rebuild and wrong here: check 1 owns
            # schema completeness, and a file missing `category` must still have
            # its regions checked rather than vanishing from this count without
            # a word.
            try:
                data = read_frontmatter(path)
            except (ValueError, OSError, UnicodeDecodeError) as exc:
                errors.append(f"{slug}: frontmatter could not be read ({exc})")
                continue
            count += 1
            listed = data.get("regions") or []

            for member in listed:
                if member not in region_slugs:
                    errors.append(
                        f"{slug}: regions[] names {member}, which is not in regions.ts"
                    )

            primary = data.get("primary_region")
            if primary and primary not in region_slugs:
                errors.append(
                    f"{slug}: primary_region {primary} is not in regions.ts"
                )
            # SCHEMA.md §2a rule 4. zod owns it; asserted here too because this
            # check runs without Astro.
            elif primary and primary not in listed:
                errors.append(
                    f"{slug}: primary_region {primary} is not among its regions[] "
                    f"({', '.join(listed) or 'empty'})"
                )

            for member in data.get("subregions") or []:
                parent = sub_parent.get(member)
                if parent is None:
                    errors.append(
                        f"{slug}: subregions[] names {member}, which is not in regions.ts"
                    )
                elif parent not in listed:
                    # SCHEMA.md §2a rule 5.
                    errors.append(
                        f"{slug}: subregion {member} belongs to region {parent}, "
                        f"which the producer does not list in regions[]"
                    )

    return errors, count


def run() -> tuple[list[str], int]:
    errors = check_register()
    producer_errors, count = check_producers()
    return errors + producer_errors, count


# =============================================================================
# 2. Self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    good_regions = [
        {"slug": "alpha", "name": "Alpha", "states": ["SA"], "subregions": ["a-one"]},
        {"slug": "beta", "name": "Beta", "states": ["VIC"], "subregions": []},
    ]
    good_subs = [{"slug": "a-one", "name": "A One", "region": "alpha", "registered": True}]

    if check_register(good_regions, good_subs, states=("SA", "VIC")):
        errors.append("selftest: a clean register was rejected")

    # A state with no region.
    if not check_register(good_regions, good_subs, states=("SA", "VIC", "WA")):
        errors.append("selftest: a state with NO region was not caught")

    # A subregion whose parent does not list it back.
    orphan = [{"slug": "a-one", "name": "A One", "region": "beta", "registered": True}]
    if not check_register(good_regions, orphan, states=("SA", "VIC")):
        errors.append("selftest: a subregion its parent does not list back was not caught")

    # A region listing a subregion that does not exist.
    dangling = [
        {"slug": "alpha", "name": "Alpha", "states": ["SA"], "subregions": ["nope"]},
        {"slug": "beta", "name": "Beta", "states": ["VIC"], "subregions": []},
    ]
    if not check_register(dangling, [], states=("SA", "VIC")):
        errors.append("selftest: a region listing an undefined subregion was not caught")

    # ── The producer half, against real MDX in a temp directory ───────────
    #
    # These four assertions are the ones that run against live content on every
    # gate exit, so they get fixtures rather than being trusted because the
    # register half passed.
    errors.extend(_selftest_producers(good_regions, good_subs))

    return errors


def _fixture_mdx(*, regions_list: list[str], primary: str, subs: list[str]) -> str:
    """The smallest frontmatter this check reads. Not schema-complete: check 1
    owns schema validity, and a fixture that had to satisfy the whole contract
    would break every time an unrelated field moved."""
    lines = [
        "---",
        "name: Fixture",
        "regions:",
        *[f"  - {slug}" for slug in regions_list],
        f"primary_region: {primary}",
    ]
    if subs:
        lines.append("subregions:")
        lines.extend(f"  - {slug}" for slug in subs)
    lines += ["---", "", "Body."]
    return "\n".join(lines) + "\n"


def _selftest_producers(
    regions: list[dict[str, Any]], subs: list[dict[str, Any]]
) -> list[str]:
    import tempfile

    errors: list[str] = []
    cases = [
        ("clean", dict(regions_list=["alpha"], primary="alpha", subs=["a-one"]), False),
        (
            "a regions[] member not in the register",
            dict(regions_list=["nope"], primary="nope", subs=[]),
            True,
        ),
        (
            "a primary_region not among regions[]",
            dict(regions_list=["alpha"], primary="beta", subs=[]),
            True,
        ),
        (
            "a subregion whose region the producer does not list",
            dict(regions_list=["beta"], primary="beta", subs=["a-one"]),
            True,
        ),
        (
            "a subregion not in the register",
            dict(regions_list=["alpha"], primary="alpha", subs=["nope"]),
            True,
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for label, kwargs, should_fail in cases:
            path = directory / "fixture.mdx"
            path.write_text(_fixture_mdx(**kwargs), encoding="utf-8")
            found, count = check_producers([directory], regions, subs)
            if count != 1:
                errors.append(f"selftest: fixture {label!r} was not read (count={count})")
            if should_fail and not found:
                errors.append(f"selftest: {label} was NOT caught")
            if not should_fail and found:
                errors.append(f"selftest: a clean producer was rejected: {found}")

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print("VALIDATE 12 FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    real_errors, count = run()
    if real_errors:
        print("VALIDATE 12 FAIL")
        for error in real_errors:
            print(f"  {error}")
        return 1

    regions = ts_data.regions()
    subregions = ts_data.subregions()
    print(
        f"VALIDATE 12 PASS — selftest ok; {len(regions)} regions and "
        f"{len(subregions)} subregions internally consistent, all {len(STATES)} "
        f"states reachable, {count} producer file(s) agree with the register"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
