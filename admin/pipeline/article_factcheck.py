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

#: This stage's output budget, and it is deliberately the largest in the build.
#:
#: Measured on the first live run rather than guessed. The stage returns the
#: WHOLE corrected body plus one record per claim carrying the verbatim
#: sentence, so its output is roughly the size of the post again — and the
#: checking model reasons at length before writing any of it, because reading
#: adversarially is what it was asked to do.
#:
#: At 8000 the first real run spent the entire budget on reasoning and emitted
#: no text at all. See `agents._truncated` for what that looked like from the
#: outside and why it was worse than a plain failure.
FACTCHECK_MAX_TOKENS = 32000

#: A bare numeral in prose that states a count this repository already holds.
#:
#: Deliberately narrow. It fires on a digit sequence followed by one of the
#: nouns `<Figure>` can count, which is the shape of the defect UX.md §6 names —
#: "a producer count, a region count". A year, a percentage from a source and a
#: dollar figure are ordinary numerals and are not this.
#:
#: **The gap is why this is not simply `\d+\s+producers`.** The first version
#: required the noun adjacent, and the live post said `97 independent Australian
#: winemakers`, which it read straight past. The fixture had said `97
#: producers` and passed, so the fixture was testing what it was written
#: against rather than the shape of the sentence people write. Up to three
#: modifiers are now allowed between.
#:
#: `_GAP_WORD` excludes determiners, prepositions and copulas on purpose. They
#: are what separates a count from a year: `97 independent Australian
#: winemakers` is a count, and `in 2019 the region had` is not, and the
#: difference is visible in the words between rather than in the numeral.
_GAP_WORD = (
    r"(?!(?:the|a|an|of|in|on|at|to|and|or|per|for|with|from|by|is|are|was|"
    r"were|had|have|has|that|which|its|their)\b)[a-z][a-z-]*\s+"
)

_COUNTABLE_NOUN = (
    r"(?:producers?|wineries|winemakers?|regions?|sub-?regions?|entries|"
    r"glossary\s+terms?|terms?\s+in\s+the\s+glossary)"
)

_TYPED_COUNT = re.compile(
    rf"\b\d[\d,]*\s+(?:published\s+)?(?:{_GAP_WORD}){{0,3}}{_COUNTABLE_NOUN}\b",
    re.IGNORECASE,
)

#: A four-digit year. Excluded only when modifiers sit between it and the noun:
#: `2000 producers` reads as a count and is caught, while `2019 vintage
#: producers` does not and is not. Without this, any sentence pairing a year
#: with one of the nouns three words later would fail a check that must never
#: fire on correct copy (check 21's lesson: a blocking gate on a false positive
#: costs the gate its authority).
_YEAR = re.compile(r"^(?:19|20)\d\d$")


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

    Refuses a published post. The gate is HERE rather than only in the route,
    for the reason `blog.publish` and `blog.delete_draft` both state: a CLI call
    or a later caller must not be able to route around it. This one had the
    guard only in the route, so `--slug <published>` read the post out of
    `_published`, wrote the corrected body to `_blog_staging`, and left the slug
    in both directories at once.
    """
    if blog.is_published(slug):
        raise ValueError(
            f"{slug} is published. A post is fact-checked before it publishes, "
            f"not after (UX.md §6)."
        )

    data, body = blog.load_post(slug)

    # The audit is keyed by what the POST says its audit is called, which is what
    # `publish_blocks`, check 22 and the resolve-claim route all read. Keying it
    # by the slug instead was equal for every post the pipeline creates and would
    # have diverged silently the first time the field was edited — writing an
    # audit nobody reads, while the publish gate reported a missing one.
    audit_name = str(data.get("factcheck") or slug)

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
        max_tokens=FACTCHECK_MAX_TOKENS,
        client=client,
    )

    audit = {
        "post": audit_name,
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

    blog.save_factcheck(audit_name, audit)
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
    hits: list[str] = []
    for match in _TYPED_COUNT.finditer(_FIGURE_TAG.sub(" ", body)):
        text = match.group(0)
        leading = text.split()[0].replace(",", "")
        # A year followed by modifiers is prose about a year, not a count.
        if _YEAR.match(leading) and len(text.split()) > 2:
            continue
        hits.append(text)
    return hits


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
    #
    # The first four `True` cases are the ones the live corpus exposed: the
    # original pattern required the noun ADJACENT to the numeral, and every
    # sentence a person actually writes puts adjectives in between. The `False`
    # cases are the false positives that would make this a check people route
    # around, and the year pair is the boundary between the two.
    for body, should_fire in (
        ("The guide documents 97 producers.", True),
        ("The guide documents 97 independent Australian winemakers.", True),
        ("It lists 36 published producers in the Adelaide Hills.", True),
        ("There are 12 registered regions with entries.", True),
        ("Of 123 glossary terms, most are grapes.", True),
        ("A total of 2,400 producers would be a different guide.", True),
        ('The guide documents <Figure of="published" /> producers.', False),
        ("The vineyard was planted in 1989.", False),
        ("Tastings cost $15 at the cellar door.", False),
        ("Roughly 40 per cent of the register is unregistered.", False),
        # A year followed by modifiers is prose about a year, not a count.
        ("In 2019 the region had a difficult vintage.", False),
        ("The 2021 vintage produced wines the guide does not describe.", False),
        # The gap has a bound. Six words between is a different sentence.
        ("There were 40 reasons nobody has ever counted these regions.", False),
    ):
        fired = bool(typed_figures(body))
        if fired != should_fire:
            missed = "missed" if should_fire else "false-positived on"
            errors.append(f"selftest: the typed-figure scan {missed} {body!r}")

    # `check` must refuse a published post in the MODULE, not only in the route.
    #
    # The injected client makes the test safe to run on every `/validate`: if the
    # guard were missing, the stage would reach the model, and a self-test that
    # can spend money when it fails is a self-test nobody dares run. It raises
    # instead, and the wrong exception type is what reports the missing guard.
    class _NoCalls:
        class messages:
            @staticmethod
            def create(**_kwargs: Any) -> Any:
                raise AssertionError("the model was called")

    published = [row["slug"] for row in blog.post_rows() if row["status"] == "published"]
    if published:
        try:
            check(published[0], log=lambda _level, _message: None, client=_NoCalls())
        except ValueError:
            pass
        except AssertionError:
            errors.append(
                "selftest: check() reached the model for a PUBLISHED post. The guard "
                "belongs in the module, not only in the route — a CLI call must not "
                "be able to route around it (UX.md §6)."
            )
        else:
            errors.append("selftest: check() ACCEPTED a published post")

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
    except (AgentError, MalformedOutput, FileNotFoundError, ValueError) as exc:
        # `ValueError` is the published-post refusal. A refusal is a result, not
        # a crash, and a traceback would read as one.
        print(f"FACTCHECK FAIL — {exc}")
        return 1

    print(f"FACTCHECK — {result['counts']}")
    for block in result["blocks"]:
        print(f"  blocked: {block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
