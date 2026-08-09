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
    OWNERSHIP_STATES,
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

        # SCHEMA.md §2a rules 11 and 13, amended 2026-08-09. The pairing, both
        # ways: `confirmed` needs a whole source, `unconfirmed` needs none.
        #
        # The failure this is shaped to catch is `confirmed` with nothing behind
        # it, the one combination of the four that puts a claim on the page the
        # evidence does not support. `unconfirmed` carrying a stray source is
        # the milder fault — the entry under-claims — but it still fails,
        # because the states are a pairing and not a confidence ranking, and a
        # source recorded where no page renders it is a source nobody can check.
        #
        # Rule 14 needs nothing here. It requires the deny-list to be silent on
        # an `unconfirmed` entry, and the standing re-audit below already fails
        # on *any* published match in *either* state, which is the stronger
        # assertion. Rule 14's teeth are at approval time, in `approval_blocks`,
        # where a draft can still be stopped before it publishes.
        status = data.get("ownership_status")
        source = data.get("ownership_source")
        if status not in OWNERSHIP_STATES:
            errors.append(
                f"{path.name}: ownership_status is {status!r}, must be one of "
                + ", ".join(OWNERSHIP_STATES)
                + " (SCHEMA.md §1.15)"
            )
        elif status == "unconfirmed" and source is not None:
            errors.append(
                f"{path.name}: ownership_status is unconfirmed but "
                f"ownership_source is set (SCHEMA.md §2a rule 13). Either the "
                f"source names an owner, and the status is confirmed, or it "
                f"does not, and the source comes out."
            )

        if status == "confirmed" and not isinstance(source, dict):
            errors.append(
                f"{path.name}: ownership_status is confirmed but ownership_source "
                f"is missing (SCHEMA.md §2a rule 11, §4.2)"
            )
        elif isinstance(source, dict):
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
        {
            # Added 2026-08-09. The only `check`-verdict record in the fixture,
            # and the one the `unconfirmed` rules need.
            #
            # Every record above is `reject`, which never reaches the review
            # queue at all (UX.md §1.4.3) — so none of them can exercise a rule
            # about what a *reviewer* may do with a draft in front of them. A
            # `check` record is the one that does: SCHEMA.md §4.3 gives it to
            # attributions resting on trade reporting rather than a registry,
            # the draft is staged carrying the flag, and §2a rule 14 is what
            # stops the reviewer publishing it as `unconfirmed`.
            "parent": "Fixture Trade-Reported Group",
            "category": "corporate_portfolio",
            "verdict": "check",
            "labels": ["Reported Creek Wines"],
            "domains": ["reportedcreek.example"],
            "aliases": [],
            "abns": [],
            "source": "https://example.invalid/reported",
            "updated": "2026-08-07",
        },
    ],
}


#: SCHEMA.md §4.2 route 2 evidence: a statement naming who owns the business.
#:
#: Supplied by every fixture below whose subject is the *deny-list* — name,
#: domain, ABN and the place-name guards. Since 2026-08-08 a determination
#: resting on no evidence at all is `check` however clean the name is, so
#: without this those assertions would read `check` and blame name matching for
#: it. Gate 4's done-condition says a *known* independent producer returns
#: `clear`, and knowing is what this supplies.
_NAMES_ITS_OWNERS = {"statements": ["Owned by the Fixture family since 1998"]}


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []
    register = _FIXTURE_REGISTER

    def verdict(**kwargs: Any) -> str:
        return ownership.determine(register=register, **kwargs).verdict

    # ── Silence is not independence, and it is not a deny-list problem.
    #    A spotless name with no evidence behind it is `check` (SCHEMA.md §4.2).
    if verdict(name="Genuine Independent Wines", website="https://genuine.example") != "check":
        errors.append("selftest: a producer with no ownership evidence was not held at check")

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
    if verdict(
        name="Genuine Independent Wines",
        website="https://genuine.example",
        signals=_NAMES_ITS_OWNERS,
    ) != "clear":
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
        "ownership_status": "confirmed",
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

    # ── SCHEMA.md §2a rules 11, 13 and 14 — the `unconfirmed` state, added
    #    2026-08-09. Three assertions, and the third is the load-bearing one.
    #
    #    `unconfirmed` exists so a producer nobody publishes ownership for can
    #    be listed honestly. The failure mode it introduces is that it becomes
    #    the door a deny-listed label walks through: the register names a
    #    parent, no page states ownership, and a reviewer reaches for the state
    #    that does not require a source. Rule 14 is what shuts that, and it
    #    must hold even when every signal has been resolved — which is exactly
    #    the state the fixture below is in.
    unconfirmed_ok = {
        "parent_company": None,
        "ownership_status": "unconfirmed",
        "ownership_source": None,
    }
    if ownership.approval_blocks(unconfirmed_ok, resolved):
        errors.append(
            "selftest: an unconfirmed draft with a null source and a resolved "
            "determination was blocked. The state cannot publish anything."
        )

    if not ownership.approval_blocks(
        {**unconfirmed_ok, "ownership_source": {
            "source": "https://example.com/about",
            "method": "producer_statement",
            "date": date(2026, 8, 9),
        }},
        resolved,
    ):
        errors.append("selftest: unconfirmed carrying a source was approvable (r13)")

    if not ownership.approval_blocks(
        {"parent_company": None, "ownership_status": "confirmed", "ownership_source": None},
        resolved,
    ):
        errors.append("selftest: confirmed with no source was approvable (r11)")

    # A `check`-verdict hit, because that is the one that reaches a reviewer.
    # Every signal is resolved and the source is null, so the ONLY thing left
    # standing between this draft and publication is rule 14.
    hit = ownership.determine(
        name="Reported Creek Wines",
        website="https://reportedcreek.example",
        signals=_NAMES_ITS_OWNERS,
        register=register,
    )
    if hit.verdict != "check":
        errors.append(
            f"selftest: the fixture's check-verdict record returned "
            f"{hit.verdict!r}. Rule 14's fixture is not exercising a queued draft."
        )
    hit_record = hit.as_dict()
    for row in hit_record.get("signals") or []:
        row["resolution"] = "not_relevant"
    for row in hit_record.get("hits_to_resolve") or []:
        row["resolution"] = "not_relevant"
    if not ownership.approval_blocks(unconfirmed_ok, hit_record):
        errors.append(
            "selftest: a deny-list hit was approvable as unconfirmed (r14). "
            "Unconfirmed means no source names an owner; the register names one."
        )

    # ── The 2026-08-07 escalating-signal split (SCHEMA.md §4.5, UX.md §1.4.2).
    #
    #    The rule this guards has two halves and both fail silently. Losing the
    #    first re-imposes a hand resolution on every producer that states its
    #    ownership, which is the cost the amendment removed. Losing the second
    #    lets a corporate relationship through in the one key that no longer
    #    escalates on its presence alone — a wrong `clear`, which is the failure
    #    the whole module exists to prevent.
    positive = ownership.determine(
        name="Genuine Independent Wines",
        website="https://genuine.example",
        signals={"statements": ["Owned by the Broderick family since 1980"]},
        register=register,
    )
    if positive.verdict != "clear":
        errors.append(
            f"selftest: a statement naming an owning family returned "
            f"{positive.verdict!r}, not clear. The split has regressed and every "
            f"producer that states its ownership now needs a hand resolution."
        )
    if ownership.unresolved_signals(positive.signals):
        errors.append("selftest: a non-escalating statement blocked approval")
    if "no parent" not in positive.basis:
        errors.append(
            f"selftest: a clear carrying a statement must not claim no signals "
            f"were extracted. Basis was {positive.basis!r}"
        )

    for label, statement in (
        ("group phrasing", "Part of the Fixture Portfolio Group"),
        ("wholly-owned", "A wholly-owned venture since 2011"),
        ("subsidiary", "Fixture Ridge is a subsidiary of the group"),
        ("acquired", "The estate was acquired by Example Holdings in 2019"),
    ):
        flagged = ownership.determine(
            name="Genuine Independent Wines",
            website="https://genuine.example",
            signals={"statements": [statement]},
            register=register,
        )
        if flagged.verdict != "check":
            errors.append(
                f"selftest: a statement with {label} returned {flagged.verdict!r}, "
                f"not check: {statement!r}"
            )
        if not ownership.unresolved_signals(flagged.signals):
            errors.append(
                f"selftest: an escalating statement ({label}) did not require a resolution"
            )

    # Each of the four escalating keys still moves the verdict on its own.
    for key, value in (
        ("parent_company_mentions", ["Example Group"]),
        ("shared_address", "1 Fixture Road, Nowhere"),
        ("shared_contact_domain", "sales@otherlabel.example"),
    ):
        alone = verdict(
            name="Genuine Independent Wines",
            website="https://genuine.example",
            signals={key: value},
        )
        if alone != "check":
            errors.append(f"selftest: {key} alone returned {alone!r}, not check")

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
        if ownership.determine(
            name=trap, signals=_NAMES_ITS_OWNERS, register=register
        ).verdict != "clear":
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
