"""validate_editorial.py — `/validate` check 21, the editorial-gate self-test.

Engagement/Gate 8, 2026-08-09.

**A test, not an assertion.** Check 6 reports what the published corpus says
right now; this asks whether the approve action *would refuse* a draft carrying
an absolute ban. Check 15 exists for the same reason on the deploy guard, and
the reasoning is identical: the reference implementation left a guard covered
only by a manual gate exit, and that is the one place the discipline lapsed.

── Why the gate exists ───────────────────────────────────────────────────────

The Gatekeeper stage passed a real draft using `curated` twice. That is ban 1
in `PROMPTS/architect.md` and a plain string on an enumerated list in
`PROMPTS/gatekeeper.md`, which check 6 matches deterministically at no cost. A
model is the wrong instrument for a fixed list: it scores below a regex and
charges for the privilege. So the enumerated bans are enforced at the approve
gate by the same matcher check 6 uses, and the model's budget stays on the
judgement the lists cannot express.

── What must NOT block ───────────────────────────────────────────────────────

`conditional claim` is excluded, and the exclusion is asserted here rather than
merely commented. `single-vineyard`, `old vines`, `family-owned` and
`award-winning` are permitted when the entry states the evidence, so whether a
hit is a fault depends on the rest of the entry. In one real batch, seven of
thirteen hits were entries correctly naming the owning family or attributing
the claim and reporting the gap. A gate that blocked those would teach a
reviewer to route around it, which is worse than no gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.pipeline import staging  # noqa: E402

#: (label, prose, must_block). Each blocking case names a different list, so a
#: category dropped from BLOCKING_LINT_KINDS fails here rather than silently
#: stopping being enforced.
CASES: tuple[tuple[str, str, bool], ...] = (
    (
        "banned word",
        "The producer offers a curated selection of estate wines.",
        True,
    ),
    (
        "em dash",
        "The vineyard sits above the valley — the fruit ripens late.",
        True,
    ),
    (
        "US spelling",
        "The winery has a long history of organic farming and color in its wines.",
        True,
    ),
    (
        "first-person visit tell",
        "When we visited the cellar door the tasting room was busy.",
        True,
    ),
    (
        "tasting descriptor outside a Pull",
        "The shiraz shows a long finish and firm tannins.",
        True,
    ),
    (
        "conditional claim must NOT block",
        "The producer states the business is family-owned; the Harvey family "
        "are named on the site as the current owners.",
        False,
    ),
    (
        "clean prose must NOT block",
        "The estate block is a little over a hectare planted in the 1990s. "
        "The producer states that the fruit is farmed organically and holds no "
        "certificate for it.",
        False,
    ),
)


def _selftest() -> list[str]:
    errors: list[str] = []

    for label, prose, must_block in CASES:
        blocks = staging.editorial_gate(prose, {})
        if must_block and not blocks:
            errors.append(f"{label}: expected the gate to refuse, it allowed")
        if not must_block and blocks:
            errors.append(f"{label}: expected the gate to allow, it refused with {blocks}")

    # The gate must read the summary and the FAQ, not the body alone. A ban that
    # applied only to the body would let `curated` publish in a summary, which
    # is reader-facing on every aggregation page.
    if not staging.editorial_gate("", {"summary": "A curated range of wines."}):
        errors.append("summary is not linted: a banned word in `summary` was allowed")
    faq = {"faq": [{"question": "What is on offer?", "answer": "A curated flight."}]}
    if not staging.editorial_gate("", faq):
        errors.append("faq answers are not linted: a banned word in an answer was allowed")

    # A <Pull> is verbatim producer speech and is masked by check 6's linter.
    # The gate inherits that, so a producer's own tasting note inside a marked
    # quotation must not block.
    pull = (
        "<Pull attribution=\"The producer, on their wines page\">\n"
        "A long finish and firm tannins.\n"
        "</Pull>\n"
    )
    if staging.editorial_gate(pull, {}):
        errors.append("a <Pull> quotation blocked; quoted producer speech must not")

    # The categories the gate claims to enforce must all still exist in the
    # linter, or a rename would silently disarm one.
    from admin.pipeline import validate_register

    known = set(validate_register.LIST_LABELS.values()) | {"US spelling", "em dash"}
    for kind in staging.BLOCKING_LINT_KINDS:
        if kind not in known:
            errors.append(f"BLOCKING_LINT_KINDS names {kind!r}, which the linter never emits")
    if "conditional claim" in staging.BLOCKING_LINT_KINDS:
        errors.append("conditional claim must not be a blocking kind")

    return errors


def run() -> list[str]:
    """Report any staged draft the gate would currently refuse.

    Advisory, like check 6: a draft in the queue has not published, and the
    gate is what stops it. This lists them so a reviewer knows what is waiting.
    """
    from admin import schema
    from admin.config import STAGING_DIR

    notes: list[str] = []
    for path in sorted(STAGING_DIR.glob("*.mdx")):
        try:
            data, body = schema.read_mdx(path)
        except Exception:  # noqa: BLE001
            continue
        for block in staging.editorial_gate(body, data):
            notes.append(f"{path.name}: {block}")
    return notes


def main() -> int:
    errors = _selftest()
    if errors:
        print(f"VALIDATE 21 FAIL — {len(errors)} error(s)")
        for line in errors:
            print(f"  {line}")
        return 1

    notes = run()
    print(
        f"VALIDATE 21 PASS — selftest ok; {len(CASES)} gate case(s) exercised, "
        f"{len(notes)} staged draft(s) currently refused"
    )
    for line in notes:
        print(f"  blocked: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
