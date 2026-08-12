"""article_pipeline.py — brief, then draft, then house voice. Gate 11, TRD.md §7.6.

`article_brief` -> `article_draft` + `house_voice`. The fourth stage,
`factcheck`, lives in `article_factcheck.py` because it runs on a different model
and that separation is the point (CLAUDE.md Gate 11).

── The facts block is the whole world ───────────────────────────────────────

`build_facts` decides what a post can truthfully say, exactly as
`forewords.build_facts` does for an aggregation page. Every prompt here says
that anything not in the input does not go in the output, so what is assembled
there is the boundary. Everything in it comes from the guide's own published
entries, its registers, or the topic the editor typed. Nothing is inferred.

── The figures are offered, not described ───────────────────────────────────

The model is handed the `<Figure>` queries that resolve, with their current
values, and told to use the tag rather than the number. Handing it the value is
deliberate: a brief written blind to the actual counts proposes an argument the
data does not support, and the first anyone would know is the fact-check.

The value shown is a fact at that moment and the TAG is what ships, so the post
stays right after the next harvest. This is the one place in the project where a
model sees a number it must not copy, and both prompts say so in as many words.

── Why the house voice stage may not delete ─────────────────────────────────

`house_voice` is told it is not a fact-checker and must not remove a claim it
doubts. That is not politeness to the drafting stage: a claim deleted there
leaves no trace, and UX.md §6 requires a removed claim to render struck through
with its reason. Only the fact-check stage deletes, and only into a record.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    ARTICLE_STAGING_DIR,
    MODEL_ARTICLE,
    MODEL_BRIEF,
    PRACTICE_KEYS,
    PRODUCERS_JSON_PATH,
)
from admin.pipeline import blog, ts_data  # noqa: E402
from admin.pipeline.agents import (  # noqa: E402
    AgentError,
    Ledger,
    MalformedOutput,
    call,
    load_prompt,
)
from admin.pipeline.validate_register import lint_text, load_lists  # noqa: E402

Logger = Callable[[str, str], None]


def _log(level: str, message: str) -> None:
    print(f"[{level}] {message}")


#: The brief's required keys. A brief missing one of these is not a brief the
#: drafting stage can work from, and the content tier re-asks naming it.
BRIEF_KEYS = ("title", "summary", "dateline", "angle", "sections", "figures", "sources", "problems")

#: Word bounds from `article_draft.md`. Enforced rather than hoped for: under the
#: floor means the brief was thin, which is a problem to report rather than pad
#: around, and over the ceiling means the draft added something the brief did not
#: carry.
MIN_WORDS = 600
MAX_WORDS = 1100


# =============================================================================
# 1. The figures a post may state — SCHEMA.md §9.5's closed set, resolved
# =============================================================================


def _published() -> list[dict[str, Any]]:
    if not PRODUCERS_JSON_PATH.is_file():
        return []
    return json.loads(PRODUCERS_JSON_PATH.read_text(encoding="utf-8"))


def available_figures(producers: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Every `<Figure>` query that resolves right now, with its current value.

    Mirrors `site/src/data/figures.ts`, which is the build-time authority. The
    duplication is real and is the same shape as `forewords.targets` mirroring
    `taxonomy.ts`: this side runs in Python before a build exists, that side runs
    during one. **The build is what enforces the set** — an unlisted query fails
    `astro build` naming the file — so a drift here costs a wasted call rather
    than a wrong number on a page.

    Only members with at least one producer are offered. A query for an empty
    region is legal and answers 0, but offering it to a model is inviting a
    sentence about a region this guide does not document.
    """
    rows = _published() if producers is None else producers

    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        for region in row.get("regions") or []:
            counts[("region", region)] += 1
        for sub in row.get("subregions") or []:
            counts[("subregion", sub)] += 1
        if row.get("state"):
            counts[("state", row["state"])] += 1
        for variety in row.get("varieties") or []:
            counts[("variety", variety)] += 1
        for key in PRACTICE_KEYS:
            if (row.get("practices") or {}).get(key) is True:
                counts[("practice", key)] += 1
        if row.get("ownership_status"):
            counts[("ownership", row["ownership_status"])] += 1

    out: list[dict[str, Any]] = [
        {"of": "published", "member": None, "value": len(rows),
         "note": "every published producer"},
        {"of": "regions", "member": None,
         "value": len({r for (kind, r) in counts if kind == "region"}),
         "note": "regions with at least one published producer"},
        {"of": "glossary", "member": None, "value": len(ts_data.glossary()),
         "note": "glossary terms"},
    ]

    names = {r["slug"]: r["name"] for r in ts_data.regions()}
    subnames = {s["slug"]: s["name"] for s in ts_data.subregions()}
    for (kind, member), value in sorted(counts.items()):
        label = {
            "region": names.get(member, member),
            "subregion": subnames.get(member, member),
        }.get(kind, member)
        out.append({"of": kind, "member": member, "value": value, "note": label})
    return out


def figures_block(figures: list[dict[str, Any]]) -> str:
    """The figures as the prompts see them: the tag, its value, and what it is."""
    lines = []
    for figure in figures:
        tag = (
            f'<Figure of="{figure["of"]}" />'
            if figure["member"] is None
            else f'<Figure of="{figure["of"]}" member="{figure["member"]}" />'
        )
        lines.append(f"{tag}  -> {figure['value']}   ({figure['note']})")
    return "\n".join(lines)


# =============================================================================
# 2. The facts block
# =============================================================================


def build_facts(producers: list[dict[str, Any]] | None = None) -> str:
    """Everything the brief stage is allowed to know about the guide itself.

    Deliberately about the GUIDE and its registers rather than about individual
    producers. A post is editorial writing about how this directory works and
    what the public record does and does not carry; handing the model 97
    producer records invites a post that is a list of producers, which is what
    the region pages already are.
    """
    rows = _published() if producers is None else producers

    regions = {r["slug"]: r for r in ts_data.regions()}
    present = sorted({r for row in rows for r in (row.get("regions") or [])})
    confirmed = sum(1 for r in rows if r.get("ownership_status") == "confirmed")
    unconfirmed = sum(1 for r in rows if r.get("ownership_status") == "unconfirmed")

    lines = [
        "THE GUIDE",
        f"Published producers: {len(rows)}",
        f"Ownership confirmed: {confirmed}. Ownership unconfirmed: {unconfirmed}.",
        f"Regions documented: {', '.join(regions.get(s, {}).get('name', s) for s in present)}",
        f"Registered GI regions in the register: {len(ts_data.regions())}",
        f"Registered GI sub-regions in the register: "
        f"{sum(1 for s in ts_data.subregions() if s.get('registered'))} "
        f"(of {len(ts_data.subregions())} listed, the rest being districts in "
        f"common trade use rather than registered GIs)",
        f"Glossary terms: {len(ts_data.glossary())}",
        "",
        "THE INDEPENDENCE RULE",
        "A producer is listed only where it has no corporate owner. Any corporate",
        "ownership blocks publication, including a minority stake and including",
        "membership of a multi-label family or portfolio group.",
        "Every published entry carries parent_company: null. There are no exceptions.",
        "",
        "THE THREE EVIDENCE ROUTES, and what each can and cannot show",
        "producer_statement: the producer's own published page naming who owns the",
        "  business. Carries most of this guide, because it is the only route that",
        "  states ownership directly. Small wineries overwhelmingly do not publish one.",
        "trade_source: a regional association or trade register. Lists MEMBERSHIP",
        "  rather than ownership, which is a different fact.",
        "registry: the Australian Business Register. Identifies the entity operating",
        "  a business and carries NO shareholder data, so it cannot show that a",
        "  company has no parent above it. It is used to reject on a deny-list hit",
        "  and to corroborate, and it never clears a producer on its own. The",
        "  register that would carry shareholding is ASIC's, and an extract is a",
        "  paid product this project does not fund.",
        "",
        "THE TWO OWNERSHIP STATES",
        "confirmed: a dated source positively states who owns the business. The site",
        "  makes its independence claim for the entry and names the evidence.",
        "unconfirmed: no such source was found. The entry publishes with a visible",
        "  notice and the site makes NO independence claim for it. It is ignorance,",
        "  never tolerance: parent_company must still be null, and a deny-list hit",
        "  is never publishable in this state.",
    ]
    return "\n".join(lines)


# =============================================================================
# 3. Stage one — the brief
# =============================================================================


def _validate_brief(text: str) -> dict[str, Any]:
    """Parse and shape-check the brief. Raises `ValueError` for the one re-ask."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"the response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("the response is not a JSON object")

    missing = [key for key in BRIEF_KEYS if key not in data]
    if missing:
        raise ValueError(f"the brief is missing required key(s): {', '.join(missing)}")

    if not isinstance(data["sections"], list) or not data["sections"]:
        raise ValueError("sections must be a non-empty array")

    for index, section in enumerate(data["sections"]):
        if not isinstance(section, dict):
            raise ValueError(f"sections[{index}] is not an object")
        for key in ("heading", "covers", "evidence"):
            if not section.get(key):
                raise ValueError(f"sections[{index}] is missing {key}")
        if not isinstance(section["evidence"], list) or not section["evidence"]:
            # The rule the prompt states: a section with no evidence is a section
            # the drafting stage will fabricate.
            raise ValueError(
                f"sections[{index}] ({section.get('heading')!r}) has no evidence. "
                f"Drop the section or move what it wanted to say into problems."
            )

    if not isinstance(data["sources"], list) or not data["sources"]:
        raise ValueError("sources must carry at least one {title, url}")
    for index, source in enumerate(data["sources"]):
        if not isinstance(source, dict) or not source.get("title") or not source.get("url"):
            raise ValueError(f"sources[{index}] needs both a title and a url")
        if not str(source["url"]).startswith(("http://", "https://")):
            raise ValueError(f"sources[{index}].url is not an absolute URL")

    if len(str(data["summary"])) > blog.SUMMARY_MAX:
        raise ValueError(
            f"summary is {len(str(data['summary']))} characters; "
            f"the limit is {blog.SUMMARY_MAX}"
        )

    for key in ("title", "dateline", "angle"):
        if not str(data[key]).strip():
            raise ValueError(f"{key} is empty")

    return data


def write_brief(
    topic: str,
    *,
    log: Logger = _log,
    client: Any = None,
    ledger: Ledger | None = None,
) -> dict[str, Any]:
    """Stage one. Returns the brief."""
    figures = available_figures()
    prompt = load_prompt(
        "article_brief",
        TOPIC=topic,
        FACTS=build_facts(),
        FIGURES=figures_block(figures),
    )
    brief = call(
        "article_brief",
        MODEL_BRIEF,
        prompt,
        validate=_validate_brief,
        log=log,
        ledger=ledger,
        slug=blog.slugify(topic),
        max_tokens=4000,
        client=client,
    )
    if brief.get("problems"):
        # Printed rather than buried: this is the list of things the topic wanted
        # and the evidence would not support, and it is what a reviewer most
        # needs to see before a word is drafted.
        for problem in brief["problems"]:
            log("warn", f"brief: {problem}")
    return brief


# =============================================================================
# 4. Stage two — the draft, then the house voice
# =============================================================================

_FIGURE_TAG = re.compile(r"<Figure\b[^>]*/>")
_PULL = re.compile(r"<Pull\b.*?</Pull>", re.DOTALL)


def _word_count(body: str) -> int:
    """Prose words: components and their attributes are not the author's prose."""
    text = _FIGURE_TAG.sub(" ", body)
    text = re.sub(r"^#{1,6}\s.*$", " ", text, flags=re.MULTILINE)
    return len(text.split())


def _validate_draft(text: str) -> str:
    """The contract `article_draft.md` states, enforced. Raises for the re-ask."""
    body = text.strip()
    if not body:
        raise ValueError("the response was empty")

    if body.startswith("---"):
        raise ValueError(
            "the response starts with frontmatter. Return the MDX BODY only; "
            "the frontmatter is written by the pipeline from the brief"
        )

    if re.search(r"^#\s", body, re.MULTILINE):
        raise ValueError(
            "the body carries a `#` heading. The page renders the title as its "
            "<h1>; use `##` for sections"
        )

    words = _word_count(body)
    if words < MIN_WORDS:
        raise ValueError(f"the draft is {words} words; write {MIN_WORDS} to {MAX_WORDS}")
    if words > MAX_WORDS:
        raise ValueError(f"the draft is {words} words; write no more than {MAX_WORDS}")

    if body.count("<Pull") != body.count("</Pull>"):
        raise ValueError("a <Pull> is not closed")

    for match in _FIGURE_TAG.finditer(body):
        if 'of="' not in match.group(0):
            raise ValueError(f"a <Figure> has no `of` attribute: {match.group(0)}")

    return body


def _lint_blockers(body: str) -> list[str]:
    """The absolute bans, in the body the house-voice stage returned.

    Masked exactly as `/validate` check 6 masks: a `<Pull>` is somebody's
    published words and the prompts tell every stage to leave a quotation alone.

    Only the ABSOLUTE bans block. `conditional claim` is excluded for the reason
    check 21 excludes it: `single-vineyard`, `old vines`, `family-owned` and
    `award-winning` are permitted where the text states their evidence, so a
    blocking gate on them would teach a reviewer to route around it.
    """
    blocking = {
        "banned word",
        "hedge",
        "tasting descriptor",
        "first-person visit tell",
        "not-X-but-Y",
        "em dash",
        "US spelling",
        "project vocabulary",
    }
    return [
        f"line {hit['line']}: {hit['kind']} {hit['phrase']!r}"
        for hit in lint_text(body, load_lists())
        if hit["kind"] in blocking
    ]


def draft_article(
    brief: dict[str, Any],
    *,
    log: Logger = _log,
    client: Any = None,
    ledger: Ledger | None = None,
) -> str:
    """Stages two and three. Returns the polished MDX body.

    The house-voice pass runs after the draft and is checked against the lint
    afterwards. A body that still carries an absolute ban after the polish is
    RE-ASKED at the house-voice stage rather than accepted with a warning: the
    lists are enumerated, a model is the wrong instrument for a fixed list, and
    check 21 recorded what happens when one is trusted with one.
    """
    slug = blog.slugify(str(brief.get("title", "article")))
    figures = figures_block(available_figures())

    body = call(
        "article_draft",
        MODEL_ARTICLE,
        load_prompt(
            "article_draft",
            BRIEF=json.dumps(brief, indent=2, ensure_ascii=False),
            FIGURES=figures,
        ),
        validate=_validate_draft,
        log=log,
        ledger=ledger,
        slug=slug,
        max_tokens=8000,
        client=client,
    )

    def validate_polished(text: str) -> str:
        polished = _validate_draft(text)
        hits = _lint_blockers(polished)
        if hits:
            raise ValueError(
                "the polished body still carries banned register: "
                + "; ".join(hits[:6])
                + ". Rewrite those without it and change nothing else"
            )
        return polished

    return call(
        "house_voice",
        MODEL_ARTICLE,
        load_prompt("house_voice", DRAFT=body),
        validate=validate_polished,
        log=log,
        ledger=ledger,
        slug=slug,
        max_tokens=8000,
        client=client,
    )


# =============================================================================
# 5. The whole chain, into a staged draft
# =============================================================================


def run(
    topic: str,
    *,
    log: Logger = _log,
    client: Any = None,
) -> dict[str, Any]:
    """`article_brief` -> `article_draft` -> `house_voice`, into `_blog_staging`.

    The fact-check is NOT run here. It is a separate action on a different model
    and the reviewer triggers it, which keeps the split visible in the interface
    rather than hidden inside one button (UX.md §6).
    """
    ledger = Ledger()

    brief = write_brief(topic, log=log, client=client, ledger=ledger)
    body = draft_article(brief, log=log, client=client, ledger=ledger)

    slug = blog.slugify(str(brief["title"]))
    if blog.path_for(slug) is not None:
        slug = f"{slug}-{date.today().isoformat()}"

    ARTICLE_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    blog.brief_path(slug).write_text(
        json.dumps(brief, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    blog.write_post(
        blog.staged_path(slug),
        {
            "title": brief["title"],
            "summary": brief["summary"],
            "dateline": brief["dateline"],
            "published": date.today(),
            "sources": brief["sources"],
            "factcheck": slug,
        },
        body,
    )

    log("info", ledger.line())
    log("info", f"blog: staged {slug} ({_word_count(body)} words). Fact-check it before publishing.")
    return {"slug": slug, "brief": brief, "words": _word_count(body)}


# =============================================================================
# 6. Self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    good_brief = {
        "title": "What an unconfirmed ownership notice means",
        "summary": "Half the entries carry a notice saying we have not confirmed who owns them.",
        "dateline": "Australia",
        "angle": "The notice is a statement about evidence, not a grade.",
        "sections": [
            {"heading": "What it says", "covers": "The two states.",
             "evidence": ["confirmed carries a dated source"]},
        ],
        "figures": [{"of": "ownership", "member": "unconfirmed", "why": "the central number"}],
        "sources": [{"title": "ABN Lookup", "url": "https://abr.business.gov.au/"}],
        "problems": [],
    }
    try:
        _validate_brief(json.dumps(good_brief))
    except ValueError as exc:
        errors.append(f"selftest: a clean brief was rejected: {exc}")

    bad_briefs = [
        ("not json at all", "unparseable JSON"),
        (json.dumps([1, 2]), "a JSON array rather than an object"),
        (json.dumps({**good_brief, "sources": []}), "no sources"),
        (json.dumps({**good_brief, "sources": [{"title": "x", "url": "not-a-url"}]}),
         "a relative source URL"),
        (json.dumps({**good_brief, "sections": []}), "no sections"),
        (json.dumps({**good_brief, "sections": [
            {"heading": "h", "covers": "c", "evidence": []}]}),
         "a section with no evidence"),
        (json.dumps({**good_brief, "summary": "x" * 200}), "an over-long summary"),
        (json.dumps({**good_brief, "title": "  "}), "an empty title"),
        (json.dumps({k: v for k, v in good_brief.items() if k != "problems"}),
         "no problems key"),
    ]
    for text, why in bad_briefs:
        try:
            _validate_brief(text)
        except ValueError:
            continue
        errors.append(f"selftest: the brief validator ACCEPTED {why}")

    # The draft contract.
    clean_body = "## A heading\n\n" + ("word " * (MIN_WORDS + 20))
    try:
        _validate_draft(clean_body)
    except ValueError as exc:
        errors.append(f"selftest: a clean draft was rejected: {exc}")

    bad_drafts = [
        ("", "an empty response"),
        ("---\ntitle: x\n---\n\nbody", "frontmatter"),
        ("# Title\n\n" + ("word " * (MIN_WORDS + 20)), "a `#` heading"),
        ("short", "a draft under the word floor"),
        ("## H\n\n" + ("word " * (MAX_WORDS + 50)), "a draft over the word ceiling"),
        ("## H\n\n<Pull>unclosed\n\n" + ("word " * (MIN_WORDS + 20)), "an unclosed <Pull>"),
    ]
    for text, why in bad_drafts:
        try:
            _validate_draft(text)
        except ValueError:
            continue
        errors.append(f"selftest: the draft validator ACCEPTED {why}")

    # The lint gate. Each of these must block; a <Pull> must not.
    for text, why in (
        ("This iconic winery is renowned for its wines.", "banned words"),
        ("The wine is arguably somewhat good.", "hedges"),
        ("The wines show notes of citrus.", "a tasting descriptor"),
        ("When we arrived we were greeted warmly.", "a visit tell"),
        ("It is not just a winery, it is a destination.", "not-X-but-Y"),
        ("The colour — or rather color — is deep.", "an em dash and a US spelling"),
    ):
        if not _lint_blockers(text):
            errors.append(f"selftest: the lint gate PASSED {why}: {text!r}")

    quoted = (
        "The producer describes it in their own words.\n\n"
        "<Pull>\nDense and plush, a real crowd pleaser.\n</Pull>\n\n"
        "Production sits under a thousand cases.\n"
    )
    if _lint_blockers(quoted):
        errors.append("selftest: the lint gate blocked a <Pull> quotation")

    # `_word_count` must not count a component's attributes as prose. A body of
    # nothing but Figure tags is an empty post, and counting the tags would let
    # it clear the floor.
    if _word_count('<Figure of="published" /> ' * 200) > 10:
        errors.append("selftest: <Figure> attributes were counted as prose")

    # `available_figures` must mirror the closed set and offer only present members.
    fixture = [
        {"regions": ["adelaide-hills"], "subregions": [], "state": "SA",
         "varieties": ["chardonnay"], "practices": {"wild_ferment": True, "unfined": False},
         "ownership_status": "confirmed"},
    ]
    offered = {(f["of"], f["member"]) for f in available_figures(fixture)}
    for expected in [
        ("published", None), ("regions", None), ("glossary", None),
        ("region", "adelaide-hills"), ("state", "SA"),
        ("variety", "chardonnay"), ("practice", "wild_ferment"),
        ("ownership", "confirmed"),
    ]:
        if expected not in offered:
            errors.append(f"selftest: available_figures missed {expected}")
    if ("practice", "unfined") in offered:
        errors.append("selftest: available_figures offered a practice flagged FALSE")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft one journal post.")
    parser.add_argument("--topic", help="what the post should be about")
    parser.add_argument("--figures", action="store_true", help="list the resolvable figures")
    args = parser.parse_args()

    errors = _selftest()
    if errors:
        print("ARTICLE PIPELINE FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    if args.figures or not args.topic:
        figures = available_figures()
        print(f"ARTICLE PIPELINE — selftest ok; {len(figures)} figure(s) resolvable")
        for line in figures_block(figures).splitlines()[:20]:
            print(f"  {line}")
        if len(figures) > 20:
            print(f"  ... and {len(figures) - 20} more")
        return 0

    try:
        result = run(args.topic)
    except (AgentError, MalformedOutput) as exc:
        print(f"ARTICLE PIPELINE FAIL — {exc}")
        return 1
    print(f"ARTICLE PIPELINE — staged {result['slug']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
