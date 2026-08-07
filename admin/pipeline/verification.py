"""verification.py — the provenance block and the change log. Gate 5.

SCHEMA.md §2b, named there by module and function. `/validate` check 14
(`validate_provenance.py`) is the enforcement surface for everything this module
produces, and the two are deliberately written against each other: this builds
exactly the set of records that check asserts, no more and no fewer.

── The three rules that shape the output ────────────────────────────────────

1. **A record exists for exactly the populated verifiable fields.** A field the
   producer does not state carries none. Check 14 fails a record for an
   unpopulated field as well as a missing record for a populated one, and it is
   right to: a `{source, tier, date}` block against an empty field asserts
   provenance for nothing, which is worse than silence because it looks like
   diligence.

2. **`parent_company` always carries a record**, whatever its value. `null` is
   its publishable value, so it is never "populated", and the general rule above
   would leave the single most important determination on the page with no
   provenance at all. UX.md §1.4.6 makes this block the durable, committed half
   of the ownership determination, the sidecar being gitignored working state.

3. **A tier is never downgraded on re-harvest.** A field verified by a registry
   lookup or confirmed by the operator does not drop back to
   `published_by_producer` because a later scrape re-read the same web page.
   Provenance only ever improves (`CONFIDENCE_TIER_RANK`, SCHEMA.md §1.11).

   **Rule 3 holds only while the value is unchanged.** A record describes the
   evidence for a *particular value*, so preserving it across a value change
   would point the audit trail at a source that stated something else, which is
   the exact failure this block exists to prevent. When a value moves, the
   record is re-stamped to the harvest that supports the new value. If that is
   a downgrade — a field an operator confirmed, now changed and re-evidenced
   only by the producer's own website — check 14 fails it and a human decides.
   That is the correct place for the decision: the alternative is the pipeline
   silently lending `operator_confirmed` to a value no operator ever saw.
"""

from __future__ import annotations

import sys
from datetime import date as date_type
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    CONFIDENCE_TIER_RANK,
    CONFIDENCE_TIERS,
    VERIFIABLE_FIELDS,
)

#: Mirrors `validate_provenance.is_populated`. The two must agree exactly, and
#: the check is the authority: this module builds what that module asserts.
_EMPTY: tuple[Any, ...] = (None, "", [], {})


def is_populated(value: Any) -> bool:
    return value not in _EMPTY


def _tier_rank(tier: Any) -> int:
    return CONFIDENCE_TIER_RANK.get(str(tier), -1)


def _record(source: str, tier: str, stamp: date_type) -> dict[str, Any]:
    return {"source": source, "tier": tier, "date": stamp}


def build_verification(
    data: dict[str, Any],
    *,
    source_url: str,
    today: date_type,
    tier: str = "published_by_producer",
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The `verification` block for one producer.

    `previous` is the **prior frontmatter** on a re-harvest, not just its
    `verification` block: deciding whether to keep a record needs the prior
    value as well as the prior tier (rule 3).

    `tier` defaults to `published_by_producer`, which is what a harvest of a
    producer's own website establishes and the strongest thing it can establish
    (SCHEMA.md §6). A harvest never mints `observed_on_visit` or
    `operator_confirmed`; only a human can.
    """
    if tier not in CONFIDENCE_TIERS:
        raise ValueError(f"tier {tier!r} is not one of {', '.join(CONFIDENCE_TIERS)}")

    previous = previous if isinstance(previous, dict) else {}
    prior_block = previous.get("verification")
    prior_block = prior_block if isinstance(prior_block, dict) else {}

    def keep(field: str) -> dict[str, Any] | None:
        """The prior record, when it still describes this value at this strength."""
        prior = prior_block.get(field)
        if not isinstance(prior, dict):
            return None
        if _tier_rank(prior.get("tier")) < _tier_rank(tier):
            return None
        if _comparable(previous.get(field)) != _comparable(data.get(field)):
            # The value moved. The old record evidences the old value.
            return None
        return dict(prior)

    out: dict[str, Any] = {}

    for field in VERIFIABLE_FIELDS:
        if field == "parent_company":
            continue
        if not is_populated(data.get(field)):
            # No record. Not an empty one: check 14 fails a record whose field
            # is unpopulated, and it is the same rule read from the other side.
            continue
        out[field] = keep(field) or _record(source_url, tier, today)

    # Rule 2. Always present, whatever `parent_company` holds.
    if "parent_company" in data:
        out["parent_company"] = keep("parent_company") or _record(source_url, tier, today)

    # Emit in VERIFIABLE_FIELDS order so a re-harvest that changes nothing
    # produces a byte-identical block and the diff stays readable.
    return {field: out[field] for field in VERIFIABLE_FIELDS if field in out}


# =============================================================================
# The change log — computed, never hand-maintained (SCHEMA.md §2b)
# =============================================================================


def _comparable(value: Any) -> Any:
    """Lists compare as sets: reordering `varieties` is not a change."""
    if isinstance(value, list):
        return sorted(str(item) for item in value)
    if isinstance(value, dict):
        return {str(k): _comparable(v) for k, v in sorted(value.items())}
    if isinstance(value, (date_type,)):
        return value.isoformat()
    return value


def _render(value: Any) -> Any:
    """What goes in the log entry. Dates as strings so the YAML stays flat."""
    if isinstance(value, date_type):
        return value.isoformat()
    if isinstance(value, list):
        return [_render(item) for item in value]
    return value


def compute_change_log(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    today: date_type,
    trigger: str = "re-harvest",
) -> list[dict[str, Any]]:
    """One `{field, from, to, date, trigger}` entry per verifiable field that moved.

    Walks `VERIFIABLE_FIELDS` only. A change to `summary` or to the body is not
    a provenance event and does not belong in an audit trail of the facts.

    Returns the prior log with new entries appended, so the history accumulates
    rather than being replaced by the most recent diff.
    """
    entries: list[dict[str, Any]] = []
    for field in VERIFIABLE_FIELDS:
        before = previous.get(field)
        after = current.get(field)
        if _comparable(before) == _comparable(after):
            continue
        entries.append(
            {
                "field": field,
                "from": _render(before),
                "to": _render(after),
                "date": today,
                "trigger": trigger,
            }
        )

    existing = previous.get("change_log")
    existing = list(existing) if isinstance(existing, list) else []
    return existing + entries
