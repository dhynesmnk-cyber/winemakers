"""article_factcheck.py — the adversarial claim audit. Gate 11, TRD.md §7.6.

**The fact-checking model is deliberately not the drafting model reviewing
itself** (CLAUDE.md Gate 11). Drafting models are poor judges of their own
confabulation, and the sentences one is least able to doubt are the ones it
invented most fluently.

That split is enforced here rather than assumed. `MODEL_FACTCHECK` and
`MODEL_ARTICLE` are separate `.env` variables (TRD.md §3), the cascade in
`admin/config.py` can legitimately collapse them in a bare local setup, and this
module warns loudly and **records the collapse in the audit file** when it
happens. An audit that does not say who checked whom cannot show the split held.

── Removed, not silently deleted ────────────────────────────────────────────

UX.md §6: "A claim the fact-check removed renders as a visible deletion with the
original text struck through and the reason beside it. A deletion that leaves no
trace is indistinguishable from a claim that was never made."

So a `removed` claim keeps its `text` verbatim in the committed audit, and the
audit is committed rather than left in staging (TRD.md §3, `data/factchecks/`).
The record outlives the review session, which is the point: months later, the
question "why does this post not say X" has an answer on disk.

── `unsupported` blocks, and that is not a failure state ────────────────────

A claim the model could not stand up stays in the body and blocks the publish
until a person resolves it. The prompt tells the model to use the verdict
freely: it costs a reviewer's attention, while a wrong `supported` costs the
guide's credibility on a page that cites its sources.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    FACTCHECK_IS_SELF_REVIEW,
    MODEL_ARTICLE,
    MODEL_FACTCHECK,
)
from admin.pipeline import blog  # noqa: E402
from admin.pipeline.agents import (  # noqa: E402
    AgentError,
    Ledger,
    MalformedOutput,
    call,
    load_prompt,
)
from admin.pipeline.article_pipeline import build_facts  # noqa: E402

Logger = Callable[[str, str], None]


def _log(level: str, message: str) -> None:
    print(f"[{level}] {message}")


_FIGURE_TAG = re.compile(r"<Figure\b[^>]*/>")

#: A bare numeral in prose that states a count this repository already holds.
#:
#: Deliberately narrow. It fires on a digit sequence FOLLOWED by one of the
#: nouns `<Figure>` can count, which is the shape of the defect UX.md §6 names —
#: "a producer count, a region count". A year, a percentage from a source and a
#: dollar figure are ordinary numerals and are not this.
_TYPED_COUNT = re.compile(
    r"\b\d[\d,]*\s+(?:published\s+)?"
    r"(?:producers?|wineries|winemakers?|regions?|sub-?regions?|entries|"
    r"glossary\s+terms?|terms?\s+in\s+the\s+glossary)\b",
    re.IGNORECASE,
)


# =============================================================================
# 1. Validation of what the model returned
# =============================================================================


def _validate_result(text: str) -> dict[str, Any]:
    """Parse and shape-check the audit. Raises `ValueError` for the one re-ask."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"the response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("the response is not a JSON object")

    for key in ("claims", "body"):
        if key not in data:
            raise ValueError(f"the response is missing {key}")

    if not isinstance(data["claims"], list):
        raise ValueError("claims must be an array")
    if not isinstance(data["body"], str) or not data["body"].strip():
        raise ValueError("body must be the corrected MDX, and it is empty")

    seen: set[str] = set()
    for index, claim in enumerate(data["claims"]):
        if not isinstance(claim, dict):
            raise ValueError(f"claims[{index}] is not an object")
        for key in ("id", "text", "verdict", "reason"):
            if not str(claim.get(key) or "").strip():
                raise ValueError(f"claims[{index}] is missing {key}")
        if claim["verdict"] not in blog.CLAIM_VERDICTS:
            raise ValueError(
                f"claims[{index}].verdict is {claim['verdict']!r}; "
                f"it must be one of {', '.join(blog.CLAIM_VERDICTS)}"
            )
        if claim["id"] in seen:
            raise ValueError(f"claims[{index}].id {claim['id']!r} is used twice")
        seen.add(claim["id"])

        # A `supported` verdict with no source is the failure this whole stage
        # exists to prevent: it asserts the claim stands up and names nothing.
        if claim["verdict"] == "supported" and not str(claim.get("source") or "").strip():
            raise ValueError(
                f"claims[{index}] is supported but names no source. "
                f"Name the source that carries it, or verdict it unsupported."
            )

        # A `removed` claim must actually be gone from the body, or the reviewer
        # sees a struck-through deletion beside the sentence still in the post.
        if claim["verdict"] == "removed" and claim["text"].strip() in data["body"]:
            raise ValueError(
                f"claims[{index}] is verdicted removed but its text is still in "
                f"the body. Delete the sentence, or verdict it unsupported."
            )

    if not isinstance(data.get("notes", []), list):
        raise ValueError("notes must be an array of strings")

    return data


# =============================================================================
# 2. The stage
# =============================================================================


def check(
    slug: str,
    *,
    log: Logger = _log,
    client: Any = None,
    ledger: Ledger | None = None,
) -> dict[str, Any]:
    """Fact-check one staged post. Writes the audit and the corrected body.

    Returns a summary: counts per verdict, and whether the post can now publish.
    """
    data, body = blog.load_post(slug)

    if FACTCHECK_IS_SELF_REVIEW:
        # Warned rather than refused. The cascade in `admin/config.py` can
        # collapse the two ids in a bare-bones local setup, and refusing would
        # mean the stage cannot run at all there. The collapse is recorded in
        # the audit below, so the file always says whether the split held.
        log(
            "warn",
            f"factcheck: MODEL_FACTCHECK and MODEL_ARTICLE are the same id "
            f"({MODEL_FACTCHECK}). This is a drafting model reviewing itself, "
            f"which is the one thing this stage exists to avoid. Set "
            f"MODEL_FACTCHECK in .env to a different model.",
        )

    sources = data.get("sources") or []
    prompt = load_prompt(
        "factcheck",
        DRAFT=body,
        SOURCES=json.dumps(sources, indent=2, ensure_ascii=False),
        FACTS=build_facts(),
    )

    result = call(
        "factcheck",
        MODEL_FACTCHECK,
        prompt,
        validate=_validate_result,
        log=log,
        ledger=ledger,
        slug=slug,
        max_tokens=8000,
        client=client,
    )

    audit = {
        "post": slug,
        "checked": date.today().isoformat(),
        "model": MODEL_FACTCHECK,
        "drafted_by": MODEL_ARTICLE,
        "claims": result["claims"],
    }
    if FACTCHECK_IS_SELF_REVIEW:
        # In the file, not only in the log. A log line scrolls away; this
        # travels with the repository and is visible to whoever reads the audit
        # later asking whether the check was worth anything.
        audit["self_review"] = True
    if result.get("notes"):
        audit["notes"] = result["notes"]

    # `notes` gains the typed-figure findings whether or not the model reported
    # them. The build refuses a typed count anyway (SCHEMA.md §9.3 rule 5), and
    # a reviewer who sees it here fixes it before the build tells them.
    typed = typed_figures(result["body"])
    if typed:
        audit.setdefault("notes", []).extend(
            f"typed figure that should be a <Figure>: {hit!r}" for hit in typed
        )

    blog.save_factcheck(slug, audit)
    blog.write_post(blog.staged_path(slug), data, result["body"])

    counts = {
        verdict: sum(1 for claim in result["claims"] if claim["verdict"] == verdict)
        for verdict in blog.CLAIM_VERDICTS
    }

    for claim in result["claims"]:
        level = {"supported": "info", "unsupported": "warn", "removed": "error"}[
            claim["verdict"]
        ]
        log(level, f"factcheck {claim['id']} {claim['verdict']}: {claim['text'][:80]}")

    log(
        "info",
        f"factcheck: {counts['supported']} supported, "
        f"{counts['unsupported']} unresolved, {counts['removed']} removed",
    )

    return {
        "slug": slug,
        "counts": counts,
        "notes": audit.get("notes", []),
        "blocks": blog.publish_blocks(slug),
    }


def typed_figures(body: str) -> list[str]:
    """Bare numerals stating a count this repository holds (SCHEMA.md §9.3 rule 5).

    `<Figure>` tags are stripped first, so the component's own rendering is never
    the thing reported. Narrow by design: a year, a percentage from a cited
    source and a dollar figure are ordinary numerals and are not counts of this
    guide's data.
    """
    return [match.group(0) for match in _TYPED_COUNT.finditer(_FIGURE_TAG.sub(" ", body))]


# =============================================================================
# 3. Self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    clean = {
        "claims": [
            {"id": "c1", "text": "The register carries no shareholder data.",
             "verdict": "supported", "reason": "ABN Lookup publishes entity name and status only.",
             "source": "https://abr.business.gov.au/"},
            {"id": "c2", "text": "Nobody publishes ownership for small wineries.",
             "verdict": "unsupported", "reason": "No listed source states this.", "source": None},
        ],
        "body": "## A heading\n\nThe register carries no shareholder data.\n",
        "notes": [],
    }
    try:
        _validate_result(json.dumps(clean))
    except ValueError as exc:
        errors.append(f"selftest: a clean result was rejected: {exc}")

    def broken(**changes: Any) -> str:
        return json.dumps({**clean, **changes})

    cases = [
        ("not json", "unparseable JSON"),
        (json.dumps([]), "a JSON array rather than an object"),
        (broken(body=""), "an empty body"),
        (broken(claims=[{**clean["claims"][0], "verdict": "probably"}]), "an unknown verdict"),
        (broken(claims=[{**clean["claims"][0], "source": None}]),
         "a supported claim naming no source"),
        (broken(claims=[{**clean["claims"][0], "reason": "  "}]), "an empty reason"),
        (broken(claims=[clean["claims"][0], {**clean["claims"][0], "id": "c1"}]),
         "a duplicate claim id"),
        (
            json.dumps({
                "claims": [{"id": "c1", "text": "The register carries no shareholder data.",
                            "verdict": "removed", "reason": "Fabricated.", "source": None}],
                "body": "## A heading\n\nThe register carries no shareholder data.\n",
            }),
            "a REMOVED claim whose text is still in the body",
        ),
    ]
    for text, why in cases:
        try:
            _validate_result(text)
        except ValueError:
            continue
        errors.append(f"selftest: the validator ACCEPTED {why}")

    # THE GATE 11 DONE-CONDITION, mechanised: a deliberately inserted false claim
    # must be deleted from the body, and its record must survive verbatim.
    false_claim = "Most producers in the guide have been in the same family for generations."
    fixture = {
        "claims": [
            {"id": "c1", "text": false_claim, "verdict": "removed",
             "reason": "Nothing in the corpus supports it and the guide does not know who "
                       "owns half these businesses.",
             "source": None},
        ],
        "body": "## A heading\n\nThe register carries no shareholder data.\n",
    }
    try:
        checked = _validate_result(json.dumps(fixture))
    except ValueError as exc:
        errors.append(f"selftest: the deletion fixture was rejected: {exc}")
    else:
        if false_claim in checked["body"]:
            errors.append("selftest: the false claim survived into the body")
        removed = [c for c in checked["claims"] if c["verdict"] == "removed"]
        if not removed:
            errors.append("selftest: the deletion was not recorded as a claim")
        elif removed[0]["text"] != false_claim:
            errors.append(
                "selftest: the removed claim's text was not retained VERBATIM. "
                "UX.md §6 renders it struck through, so a tidied copy misreports "
                "what the draft actually said."
            )
        elif not removed[0]["reason"].strip():
            errors.append("selftest: the deletion carries no reason")

    # The typed-figure scan.
    for body, should_fire in (
        ("The guide documents 97 producers.", True),
        ("There are 12 regions with entries.", True),
        ("Of 123 glossary terms, most are grapes.", True),
        ('The guide documents <Figure of="published" /> producers.', False),
        ("The vineyard was planted in 1989.", False),
        ("Tastings cost $15 at the cellar door.", False),
        ("Roughly 40 per cent of the register is unregistered.", False),
    ):
        fired = bool(typed_figures(body))
        if fired != should_fire:
            missed = "missed" if should_fire else "false-positived on"
            errors.append(f"selftest: the typed-figure scan {missed} {body!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Fact-check one staged journal post.")
    parser.add_argument("--slug", help="the staged post to check")
    args = parser.parse_args()

    errors = _selftest()
    if errors:
        print("FACTCHECK FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    if not args.slug:
        split = "COLLAPSED" if FACTCHECK_IS_SELF_REVIEW else "held"
        print(
            f"FACTCHECK — selftest ok; adversarial split {split} "
            f"(draft {MODEL_ARTICLE}, check {MODEL_FACTCHECK})"
        )
        return 0 if not FACTCHECK_IS_SELF_REVIEW else 1

    try:
        result = check(args.slug)
    except (AgentError, MalformedOutput, FileNotFoundError) as exc:
        print(f"FACTCHECK FAIL — {exc}")
        return 1

    print(f"FACTCHECK — {result['counts']}")
    for block in result["blocks"]:
        print(f"  blocked: {block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
