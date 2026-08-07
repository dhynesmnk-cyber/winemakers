"""validate_ownership.py — `/validate` check 8. Gate 4.

The check that guards the reason the site exists:

- no producer published without an `ownership_source` carrying a non-empty
  source and a date;
- **no producer published with a non-null `parent_company`**;
- zero hits when every published name, domain and ABN is re-checked against the
  `data/ownership.json` deny-list.

**The re-check matters as much as the first pass.** `ownership.json` grows, and
a producer published cleanly in March can become a deny-list hit in September
because somebody bought them. Nothing else in this system notices that. This
check is what turns the register from a gate a producer passes once into a
standing audit of everything already published.

The ABN comes from the retained determination sidecar in `DETERMINATIONS_DIR`,
not from frontmatter — an ABN is pipeline evidence, not published record
(SCHEMA.md §2 has no ABN field, deliberately). A published producer with no
retained determination is itself reported: UX.md §1.4.6 requires the sidecar to
survive the approve, and a missing one means a producer was published by some
route that bypassed the hub.

**The self-test pattern.** This project has no test framework. `_selftest()`
runs as part of the check itself, so the regression fails the same command that
runs the real check. It exercises the deny-list against a fixture register
rather than against `data/ownership.json`, so the guarantees hold whatever the
real register happens to contain on the day.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    DETERMINATIONS_DIR,
    OWNERSHIP_EVIDENCE_METHODS,
    PUBLISHED_DIR,
)
from admin.pipeline import ownership  # noqa: E402
from admin.pipeline.validate_content import parse_frontmatter  # noqa: E402


# =============================================================================
# 1. The check
# =============================================================================


def _published_files() -> list[Path]:
    return sorted(PUBLISHED_DIR.glob("*.mdx")) if PUBLISHED_DIR.is_dir() else []


def _determination_abn(slug: str) -> tuple[str | None, bool]:
    """`(abn, determination_present)` from the retained sidecar."""
    record = ownership.read_sidecar(slug, DETERMINATIONS_DIR)
    if record is None:
        return None, False
    for row in record.get("signals") or []:
        if row.get("key") == "abn" and row.get("items"):
            return str(row["items"][0]), True
    return None, True


def check_8_ownership() -> tuple[list[str], list[str]]:
    """`(errors, notes)` for every published producer, per file.

    Errors fail the check. Notes are reported and do not: see `_determination_abn`
    and the `notes` block below for the one thing that is deliberately advisory.
    """
    errors: list[str] = []
    notes: list[str] = []
    register = ownership.load_register()

    if register.get("_missing"):
        return [
            "data/ownership.json is not present. The deny-list is one of the two "
            "inputs to every determination and nothing can be audited without it."
        ], notes
    if register.get("_error"):
        return [f"data/ownership.json could not be read: {register['_error']}"], notes

    for path in _published_files():
        slug = path.stem
        data, parse_error = parse_frontmatter(path)
        if parse_error:
            errors.append(f"{path.name}: {parse_error}")
            continue
        assert data is not None

        # SCHEMA.md §2a rule 10. The one that has no exception anywhere.
        parent = data.get("parent_company")
        if "parent_company" not in data:
            errors.append(
                f"{path.name}: parent_company is absent. The key is always present; "
                f"an absent key is an undetermined producer, which is not publishable "
                f"(SCHEMA.md §2)."
            )
        elif parent is not None:
            errors.append(
                f"{path.name}: parent_company is {parent!r}. Only null is publishable "
                f"(SCHEMA.md §4.1). This producer must be unpublished."
            )

        # SCHEMA.md §2a rule 11 and §4.2. A source and a date, both.
        source = data.get("ownership_source")
        if not isinstance(source, dict):
            errors.append(f"{path.name}: ownership_source is missing (SCHEMA.md §4.2)")
        else:
            if not str(source.get("source") or "").strip():
                errors.append(f"{path.name}: ownership_source.source is empty")
            if not isinstance(source.get("date"), (date, datetime)) and not str(
                source.get("date") or ""
            ).strip():
                errors.append(f"{path.name}: ownership_source.date is missing")
            method = source.get("method")
            if method not in OWNERSHIP_EVIDENCE_METHODS:
                errors.append(
                    f"{path.name}: ownership_source.method is {method!r}, must be one of "
                    + ", ".join(OWNERSHIP_EVIDENCE_METHODS)
                )

        # The standing re-audit. Name, domain and ABN, each independently.
        abn, has_determination = _determination_abn(slug)
        if not has_determination:
            # ADVISORY, NOT A FAILURE, and the reason is worth stating.
            #
            # `DETERMINATIONS_DIR` sits under `content-staging/`, which is
            # gitignored volume state, so a determination does not travel with
            # the repository. Failing on its absence would fail this check on
            # every fresh clone, which would train whoever runs it to ignore
            # the result — the worst thing that can happen to this check.
            #
            # The DURABLE public record is the committed frontmatter:
            # `ownership_source` above, and `verification.parent_company`,
            # which check 14 asserts. The sidecar is the working evidence
            # behind it. So its absence is reported and does not fail.
            notes.append(
                f"{path.name}: no retained determination in "
                f"{DETERMINATIONS_DIR.name}/. The committed frontmatter still "
                f"carries the durable record; this is the working evidence, and "
                f"it does not travel with the repository."
            )

        for row in ownership.deny_list_check(
            data.get("name"), data.get("website"), abn, register=register
        ):
            if not row.match:
                continue
            match = row.match
            errors.append(
                f"{path.name}: published producer now matches the deny-list on "
                f"{ownership.CHECK_LABELS[match.check]} — {match.matched!r} in "
                f"{match.matched_in} under {match.parent} "
                f"(record verdict {match.record_verdict}, applied as {match.verdict}, "
                f"source {match.source or 'not recorded'}). "
                f"Re-run the determination and unpublish if it holds."
            )
    return errors, notes


# =============================================================================
# 2. The self-test
#
# Runs against a fixture register, never against data/ownership.json, so the
# guarantees below hold on a day when somebody has edited the real file.
#
# The three-ways-independently requirement is Gate 4's done-condition, and it
# is asserted here rather than demonstrated by hand once at a gate exit.
# =============================================================================

_FIXTURE_REGISTER: dict[str, Any] = {
    "updated": "2026-08-07",
    "owners": [
        {
            "parent": "Fixture Portfolio Group",
            "category": "corporate_portfolio",
            "verdict": "reject",
            "labels": ["Fixture Ridge", "Stanley"],
            "domains": ["fixtureridge.example"],
            "aliases": ["Fixture Portfolio Limited"],
            "abns": [{"abn": "11 222 333 444", "entity": "Fixture Ridge"}],
            "source": "https://example.invalid/fixture",
            "updated": "2026-08-07",
        },
        {
            # SCHEMA.md §4.4's two named categories, the highest-volume false
            # positive. Both reject, so the fixture proves the path exists
            # whatever verdicts the real register's records happen to carry.
            "parent": "Fixture Supermarket Group",
            "category": "retailer_private_label",
            "verdict": "reject",
            "labels": ["Fixture Creek Estate"],
            "domains": ["fixturesupermarket.example"],
            "aliases": [],
            "abns": [],
            "source": "https://example.invalid/supermarket",
            "updated": "2026-08-07",
        },
        {
            "parent": "Fixture Brand Holdings",
            "category": "virtual_brand",
            "verdict": "reject",
            "labels": ["Hollow Hill Wines"],
            "domains": ["hollowhill.example"],
            "aliases": [],
            "abns": [],
            "source": "https://example.invalid/virtual",
            "updated": "2026-08-07",
        },
    ],
}


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []
    register = _FIXTURE_REGISTER

    def verdict(**kwargs: Any) -> str:
        return ownership.determine(register=register, **kwargs).verdict

    # ── Gate 4's done-condition: rejected by name, by domain and by ABN, each
    #    on its own, with the other two inputs absent.
    for label, kwargs in (
        ("by name", {"name": "Fixture Ridge"}),
        ("by domain", {"website": "https://fixtureridge.example/about"}),
        ("by ABN", {"signals": {"abn": "11 222 333 444"}}),
    ):
        found = verdict(**kwargs)
        if found != "reject":
            errors.append(
                f"selftest: a deny-listed label was not rejected {label}: got {found!r}"
            )

    # ── The two §4.4 categories most likely to slip through.
    if verdict(name="Fixture Creek Estate") != "reject":
        errors.append("selftest: a supermarket private label was not rejected by name")
    if verdict(website="https://fixturesupermarket.example") != "reject":
        errors.append("selftest: a supermarket private label was not rejected by domain")
    if verdict(name="Hollow Hill Wines") != "reject":
        errors.append("selftest: a virtual brand was not rejected by name")
    if verdict(website="https://hollowhill.example") != "reject":
        errors.append("selftest: a virtual brand was not rejected by domain")

    # ── A known independent producer comes back clear.
    if verdict(name="Genuine Independent Wines", website="https://genuine.example") != "clear":
        errors.append("selftest: an unlisted producer did not come back clear")

    # ── An ambiguous parent mention is `check`, and check is not reject.
    ambiguous = ownership.determine(
        name="Ambiguous Wines",
        website="https://ambiguous.example",
        signals={"parent_company_mentions": ["part of the Example family of wineries"]},
        register=register,
    )
    if ambiguous.verdict != "check":
        errors.append(
            f"selftest: an ambiguous parent mention returned {ambiguous.verdict!r}, not check"
        )
    if not ownership.unresolved_signals(ambiguous.signals):
        errors.append("selftest: an extracted signal did not require a resolution")

    # ── `check` never auto-publishes: the gate must block while a signal is
    #    unresolved, and must still block on a recorded source alone.
    complete = {
        "parent_company": None,
        "ownership_source": {
            "source": "https://ambiguous.example/about",
            "method": "producer_statement",
            "date": date(2026, 8, 7),
        },
    }
    if not ownership.approval_blocks(complete, ambiguous.as_dict()):
        errors.append("selftest: a check with an unresolved signal was approvable")

    # ── Resolving every signal opens the gate, and only then.
    resolved = ambiguous.as_dict()
    for row in resolved["signals"]:
        if row["populated"]:
            row["resolution"] = "not_relevant"
    if ownership.approval_blocks(complete, resolved):
        errors.append("selftest: a fully resolved check was still blocked")
    if ownership.chip_for(resolved) != "RESOLVED":
        errors.append("selftest: a fully resolved check did not chip RESOLVED")

    # ── A non-null parent_company blocks unconditionally, with no override.
    owned = {**complete, "parent_company": "Fixture Portfolio Group"}
    if not any("parent_company" in block for block in ownership.approval_blocks(owned, resolved)):
        errors.append("selftest: a non-null parent_company did not block approval")

    # ── An absent determination blocks. `check` never auto-publishes and
    #    neither does a draft nothing has looked at.
    if not ownership.approval_blocks(complete, None):
        errors.append("selftest: a draft with no determination was approvable")

    # ── A `reject` hit is never offered a resolution control (UX.md §1.4.4).
    rejected = ownership.determine(name="Fixture Ridge", register=register)
    if rejected.hits_to_resolve:
        errors.append("selftest: a reject hit was offered a resolution, which is an override")

    # ── The Harvester never decides alone: its `clear` cannot clear a hit.
    overruled = ownership.determine(
        name="Fixture Ridge", harvester_verdict="clear", register=register
    )
    if overruled.verdict != "reject":
        errors.append(
            f"selftest: a Harvester `clear` relaxed a deny-list reject to "
            f"{overruled.verdict!r}"
        )

    # ── The register's own two traps must not fire on a place name.
    for trap in ("Stanley Lane Wines", "Tatachilla Road Vineyard"):
        if ownership.determine(name=trap, register=register).verdict != "clear":
            errors.append(f"selftest: name matching fired on the place name in {trap!r}")

    # ── But the exact label still rejects.
    if verdict(name="Stanley") != "reject":
        errors.append("selftest: the exact deny-listed label was suppressed by the place guard")

    # ── A contained match is floored to check and never rejects.
    contained = ownership.determine(name="Fixture Ridge Cellars", register=register)
    if contained.verdict != "check":
        errors.append(
            f"selftest: a partial name match returned {contained.verdict!r}, not check"
        )

    # ── Absence from the register is never read as a whitelist.
    missing = ownership.determine(name="Anything", register={"owners": [], "_missing": True})
    if missing.verdict == "clear":
        errors.append("selftest: a missing register produced a clear verdict")

    return errors


def main() -> int:
    found, notes = check_8_ownership()
    errors = _selftest() + found
    for note in notes:
        print(f"  note: {note}")
    if errors:
        print(f"VALIDATE 8 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    published = len(_published_files())
    print(
        f"VALIDATE 8 PASS — selftest ok; {published} published producer(s) carry an "
        f"ownership_source and a null parent_company, and none matches the deny-list "
        f"(register updated {ownership.register_updated() or 'undated'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
