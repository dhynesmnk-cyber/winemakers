"""validate_register.py — `/validate` check 6, the register lint. Gate 5.

Greps every `_published` body for the banned-word list, first-person visit tells
and unsourced tasting descriptors.

── Warnings, not failures ────────────────────────────────────────────────────

validate.md is explicit: "Warnings, not failures — a human judges them — but
list every hit with file and line". So `main()` exits 0 with hits and the suite
still passes. That is the right call for a lint whose job is to catch register
drift a person then reads in context, and the wrong call for anything factual,
which is why the certification, ownership and provenance checks all fail hard
and this one does not.

── There is exactly one copy of every list ───────────────────────────────────

The lists are parsed out of `PROMPTS/gatekeeper.md`, which is where they are
authored and where a non-programmer edits them. Retyping sixty words into a
Python module would create a second copy that drifts from the prompt the
Gatekeeper is actually run with, and the first symptom would be a lint that
passes copy the model was never told to avoid.

── What is deliberately not linted ───────────────────────────────────────────

`<Pull>` blocks are masked before matching. They are verbatim quotations from
the producer, the Gatekeeper prompt tells the model to leave them untouched, and
a producer calling their own wine "plush" inside a marked quotation is a fact
about what they published, not the directory adopting the word. Masking rather
than deleting keeps the line numbers true.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import PROMPTS_DIR, PUBLISHED_DIR, ROOT  # noqa: E402

GATEKEEPER_PROMPT = PROMPTS_DIR / "gatekeeper.md"

#: fence info-string -> how a hit is described in the report.
LIST_LABELS = {
    "banned-words": "banned word",
    "hedge-words": "hedge",
    "tasting-descriptors": "tasting descriptor",
    "visit-tells": "first-person visit tell",
    "not-x-but-y": "not-X-but-Y",
    # Added at Gate 6. This project's own build vocabulary, which must never
    # reach a reader. It fires almost entirely on the hand-authored data files
    # rather than on model output — see the block's note in gatekeeper.md.
    "project-vocabulary": "project vocabulary",
    # Added at Gate 7. Authored in gatekeeper.md since Gate 5 and never loaded,
    # so the four terms CLAUDE.md's editorial guardrails name by hand —
    # `single-vineyard`, `old vines`, `family-owned`, `award-winning` — were
    # going unlinted while a skill file claimed otherwise. Exactly the drift
    # CLAUDE.md's 2026-08-07 amendment warns about, and the first symptom was
    # always going to be a lint passing copy nobody checked.
    #
    # This list is conditional, not banned. A hit means "name the vineyard, the
    # vine age, the family or the award, or write what the entry supports" —
    # never "delete the phrase". A lint cannot see whether the evidence is
    # there, which is why it belongs in a warn tier a human reads.
    "conditional-claims": "conditional claim",
}


def _fenced_list(text: str, info: str) -> list[str]:
    """Entries of a ```<info> fenced block. `#` lines are comments."""
    match = re.search(rf"^```{re.escape(info)}\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    out = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # `conditional-claims` and `us-spellings` are tab-separated pairs.
        out.append(line.split("\t")[0].strip())
    return out


def load_lists() -> dict[str, list[str]]:
    """Every list, from the one place they are authored."""
    if not GATEKEEPER_PROMPT.is_file():
        return {}
    text = GATEKEEPER_PROMPT.read_text(encoding="utf-8")
    lists = {info: _fenced_list(text, info) for info in LIST_LABELS}
    lists["us-spellings"] = _fenced_list(text, "us-spellings")
    return lists


# =============================================================================
# Masking
# =============================================================================

_PULL = re.compile(r"<Pull\b.*?</Pull>", re.DOTALL)
_MDX_COMMENT = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
_TAG = re.compile(r"<TippedPhoto\b.*?/>", re.DOTALL)


def _mask(text: str) -> str:
    """Blank out regions that are not the directory's own prose, keeping lines."""

    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    for pattern in (_MDX_COMMENT, _PULL, _TAG):
        text = pattern.sub(blank, text)
    return text


# =============================================================================
# The lint
# =============================================================================


#: One or more whitespace characters, bridging at most one line break.
#:
#: Prose here is hand-wrapped at about 76 columns, so a multi-word phrase
#: routinely straddles a newline. Matching line by line missed every one of
#: them: "it could be argued" was caught flat and invisible wrapped.
#:
#: A single `>` after the break is consumed because a wrapped line inside a
#: markdown blockquote carries the marker again — the sentence continues and
#: the marker is punctuation, not prose. METHODOLOGY.md's concession wraps
#: exactly this way.
#:
#: A blank line is a paragraph break and is deliberately not bridged, so the
#: lint cannot assemble a phrase out of two paragraphs that never held one.
_GAP = r"(?=\s)[ \t]*(?:\n[ \t]*>?[ \t]*)?"


#: Phrases whose banned sense is narrower than the word.
#:
#: These mirror exceptions PROMPTS/gatekeeper.md already states in prose, and
#: they are here rather than in the list because the list is a list of words and
#: this is grammar. Without them the lint fires on its own house style: the
#: shipped sample entry uses "rather than" as a plain contrast, which the
#: Gatekeeper prompt explicitly calls fine, and a check that flags correct copy
#: on every run is a check people learn to skim past.
_OVERRIDES = {
    # `rather than` is a contrast, not a hedge. `rather good` is the hedge.
    "rather": rf"\brather\b(?!{_GAP}than\b)",
    # `would fairly call` is the justly sense, modifying a verb of
    # characterisation. `fairly good` is the hedge, modifying an adjective.
    # METHODOLOGY.md concedes the strict rule excludes businesses people
    # "would fairly call independent" — the sentence admitting what the rule
    # costs, which is the writer doing the work rather than declining it.
    "fairly": (
        rf"\bfairly\b(?!{_GAP}(?:call|calls|called|calling|say|says|said"
        rf"|describe|describes|described|claim|claims|claimed"
        rf"|treat|treats|treated)\b)"
    ),
    # `the kind of evidence` is nominal. `kind of good` is the hedge. The
    # lookbehinds use `\s` rather than a literal space so they still hold when
    # the determiner ends a wrapped line; Python needs them fixed-width.
    "kind of": rf"(?<!the\s)(?<!this\s)(?<!that\s)(?<!what\s)(?<!a\s)\bkind{_GAP}of\b",
    "sort of": rf"(?<!the\s)(?<!this\s)(?<!that\s)(?<!what\s)(?<!a\s)\bsort{_GAP}of\b",
    # The tasting sense of `finish` is a NOUN and takes a determiner or an
    # adjective: "a long finish", "the finish". The verb is ordinary
    # viticulture — "the heat a Bordeaux variety needs to finish", "picking
    # starts after the plains have finished — and fires constantly on correct
    # copy. Observed on the first real draft this pipeline produced.
    "finish": rf"\b(?:the|a|an|its|long|short|clean|dry|crisp|lingering|tannic){_GAP}finish\b",
    # `Experience the difference` is the brochure imperative. `whose experience
    # the record puts at thirty vintages` is an ordinary noun followed by an
    # ordinary determiner, and the two share a character sequence and nothing
    # else. Require the imperative: no article or possessive in front of it.
    #
    # Added 2026-08-09 (Gate 8) when the editorial approve gate refused a real
    # draft on this match. An advisory warning on a false positive costs a
    # reader's attention; a *blocking* gate on one costs the gate its
    # authority, because the reviewer learns to route around it.
    "experience the": (
        rf"(?<!\bhis\s)(?<!\bher\s)(?<!\bits\s)(?<!\bour\s)(?<!\btheir\s)"
        rf"(?<!\bwhose\s)(?<!\bthe\s)(?<!\ban\s)(?<!\bno\s)"
        rf"\bexperience{_GAP}the\b"
    ),
    # `notes of cherry` is the tasting descriptor. `the record's note of an
    # onsite winery` is the plain sense of the word, and this project's own
    # register uses it constantly, because reporting what the record does and
    # does not say is the house style. Require a sensory object.
    # `\s+` rather than `_GAP` here, deliberately. `_GAP` ends in `[ \t]*`,
    # which can backtrack to zero width, and then the negative lookahead is
    # tested against the space instead of the following word and always passes.
    # `\s+` must consume at least one character, so the lookahead lands where
    # it is meant to.
    "note of": r"\bnotes?\s+of\s+(?!an?\b|the\b|its\b|any\b|this\b|that\b)",
}


def _pattern_for(phrase: str) -> re.Pattern[str]:
    """Word-boundary match, so `finish` does not fire on `finished`."""
    if phrase in _OVERRIDES:
        return re.compile(_OVERRIDES[phrase], re.IGNORECASE)
    return re.compile(r"\b" + re.escape(phrase).replace(r"\ ", _GAP) + r"\b", re.IGNORECASE)


def lint_text(text: str, lists: dict[str, list[str]] | None = None) -> list[dict]:
    """`[{line, kind, phrase, excerpt}]` for one document's prose."""
    lists = lists if lists is not None else load_lists()
    masked = _mask(text)
    hits: list[dict] = []

    lines = masked.splitlines()

    def collect(phrase: str, label: str) -> None:
        """One hit per phrase per line, matched over the whole document.

        Searching the whole text rather than each line is what lets a phrase
        that wraps still count. Line numbers come from the match offset, which
        is sound because `_mask` blanks quoted lines without removing them.
        """
        seen: set[int] = set()
        for match in _pattern_for(phrase).finditer(masked):
            line_number = masked.count("\n", 0, match.start()) + 1
            if line_number in seen:
                continue
            seen.add(line_number)
            excerpt = lines[line_number - 1].strip()[:100] if line_number <= len(lines) else ""
            hits.append(
                {"line": line_number, "kind": label, "phrase": phrase, "excerpt": excerpt}
            )

    for info, label in LIST_LABELS.items():
        for phrase in lists.get(info, []):
            collect(phrase, label)

    for pair in lists.get("us-spellings", []):
        collect(pair, "US spelling")

    # The em-dash ban is a character, not a list, and cannot wrap.
    for line_number, line in enumerate(lines, start=1):
        if "—" in line:
            hits.append(
                {"line": line_number, "kind": "em dash", "phrase": "—",
                 "excerpt": line.strip()[:100]}
            )

    hits.sort(key=lambda hit: (hit["line"], hit["kind"], hit["phrase"]))
    return hits


def _body_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


def _shipped_text(path: Path) -> str:
    """The reader-facing half of a frontmatter'd markdown document.

    Frontmatter lines are BLANKED rather than dropped, so a reported line number
    still points at the real line in the file. `_body_of` above returns the body
    alone, which is right for MDX because its hits are reported against the body
    it lints; here the hits are reported against the file a person will open.

    Added at Gate 10, when METHODOLOGY.md gained frontmatter and started being
    rendered as a page. From that point the file has two halves with different
    audiences: the body is published prose and the frontmatter carries build
    notes in YAML comments. Linting the notes reported the words a build note is
    made of, which is a hit nobody can act on.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join([""] * (index + 1) + lines[index + 1 :])
    # An unterminated frontmatter fence is a malformed file, not a licence to
    # skip the lint. Read the whole thing.
    return text


def _frontmatter_prose(path: Path) -> str:
    """`summary` and the FAQ answers are read by the public too (SEED.md row 2)."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    lines = []
    for line in parts[1].splitlines():
        if re.match(r"^\s*(summary|question|answer|-\s+question|-\s+answer):", line):
            lines.append(line)
        else:
            lines.append("")
    return "\n".join(lines)


def run(directory: Path = PUBLISHED_DIR) -> list[tuple[Path, list[dict]]]:
    lists = load_lists()
    results: list[tuple[Path, list[dict]]] = []
    for path in sorted(directory.glob("*.mdx")):
        hits = lint_text(_body_of(path), lists) + lint_text(_frontmatter_prose(path), lists)
        if hits:
            results.append((path, hits))
    return results


# =============================================================================
# The hand-authored data files — added at Gate 6, 2026-08-08
#
# `regions.ts` and `glossary.ts` carry a lot of reader-facing prose: 121
# glossary terms with their definitions, and a `note` on twenty-odd regions and
# subregions. CLAUDE.md is explicit that the editorial guardrails "apply to
# anything a reader sees", and until Gate 6 nothing rendered any of it, so
# nothing linted it either.
#
# The cost of that showed on the first region page ever built, which opened with
# "A Gate 8 coverage region." Four region notes and three subregion notes had
# drifted into project shorthand with nothing watching.
# =============================================================================

#: Field -> whether it is prose a reader sees. `slug`, `value` and `vocabulary`
#: are identifiers and are deliberately absent: `not_x_but_y` as a slug is not
#: a not-X-but-Y construction.
_GLOSSARY_PROSE_FIELDS = ("term", "short", "definition", "excludes")
_REGION_PROSE_FIELDS = ("note",)


def _line_of(text: str, needle: str) -> int:
    """The 1-indexed line a parsed string sits on, found by locating it in the
    source. Parsed values lose their position, and a hit reported without a line
    is a hit nobody can act on."""
    index = text.find(needle[:60])
    return text.count("\n", 0, index) + 1 if index != -1 else 0


def lint_data_files(lists: dict[str, list[str]] | None = None) -> list[tuple[Path, list[dict]]]:
    """Reader-facing prose in `regions.ts` and `glossary.ts`."""
    from . import ts_data

    lists = lists if lists is not None else load_lists()
    results: list[tuple[Path, list[dict]]] = []

    sources: list[tuple[Path, list[dict], tuple[str, ...], str]] = [
        (ts_data.REGIONS_TS_PATH, ts_data.regions(), _REGION_PROSE_FIELDS, "slug"),
        (ts_data.REGIONS_TS_PATH, ts_data.subregions(), _REGION_PROSE_FIELDS, "slug"),
        (ts_data.GLOSSARY_TS_PATH, ts_data.glossary(), _GLOSSARY_PROSE_FIELDS, "slug"),
    ]

    per_file: dict[Path, list[dict]] = {}
    for path, entries, fields, key in sources:
        text = path.read_text(encoding="utf-8")
        for entry in entries:
            for field in fields:
                value = entry.get(field)
                if not isinstance(value, str) or not value.strip():
                    continue
                for hit in lint_text(value, lists):
                    hit = dict(hit)
                    hit["line"] = _line_of(text, value)
                    hit["excerpt"] = f"{entry.get(key)}.{field}: {value[:80]}"
                    per_file.setdefault(path, []).append(hit)

    for path, hits in per_file.items():
        hits.sort(key=lambda hit: (hit["line"], hit["kind"], hit["phrase"]))
        results.append((path, hits))
    return results


# =============================================================================
# The self-test — validate.md's pattern
# =============================================================================

_CLEAN = """
The estate block is a little over a hectare, planted in the 1990s and taken over
by the current owners with the rows already in the ground. Everything else is
purchased fruit.
"""

_DIRTY = """
Nestled in the rolling hills, this iconic winery boasts a stunning cellar door.
When we arrived we were greeted with notes of plush, generous fruit.
This is not just a winery, it is arguably somewhat of a hidden gem.
The color of the vineyard in autumn is truly breathtaking.
Their award-winning single-vineyard bottling comes from family-owned old vines.
"""

_QUOTED = """
The producer describes the wine in their own words.

<Pull attribution="The producer, on their wines page">
  Dense and plush, a real crowd pleaser thanks to the generosity of fruit
  characters.
</Pull>

Production sits under a thousand cases.
"""


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []
    lists = load_lists()

    for info in LIST_LABELS:
        if not lists.get(info):
            errors.append(
                f"selftest: the {info} list parsed empty from PROMPTS/gatekeeper.md. "
                f"An empty list matches nothing and makes this check a no-op."
            )

    if lint_text(_CLEAN, lists):
        errors.append("selftest: clean copy produced hits")

    dirty = lint_text(_DIRTY, lists)
    for expected in ("banned word", "first-person visit tell", "tasting descriptor",
                     "hedge", "not-X-but-Y", "US spelling", "conditional claim"):
        if not any(hit["kind"] == expected for hit in dirty):
            errors.append(f"selftest: the dirty fixture produced no {expected} hit")

    # A quotation is the producer talking. It must not be linted.
    if lint_text(_QUOTED, lists):
        errors.append(
            "selftest: a <Pull> quotation was linted. Producer quotations are "
            "verbatim and the Gatekeeper is told to leave them untouched."
        )

    # Masking must preserve line numbers, or every hit points at the wrong line.
    if len(_mask(_QUOTED).splitlines()) != len(_QUOTED.splitlines()):
        errors.append("selftest: masking changed the line count")

    # Word boundaries: `finish` must not fire on `finished`.
    if lint_text("picking often starts weeks after the plains have finished.", lists):
        errors.append("selftest: a word-boundary false positive on 'finished'")

    # The narrowed senses. Each pair is (must not fire, must fire), so an
    # override that swallows the real hedge fails here rather than silently
    # turning a rule off.
    for clean, dirty in (
        ("the producer is explicit about this rather than leaving a reader to infer.",
         "the wine is rather good."),
        ("a person records the kind of evidence relied on.",
         "the cellar door is kind of hard to find."),
        ("the west-facing blocks get the heat a Bordeaux variety needs to finish.",
         "the wine has a long finish."),
        ("businesses that many people would fairly call independent.",
         "the cellar door is fairly easy to find."),
    ):
        if lint_text(clean, lists):
            errors.append(f"selftest: a false positive on {clean!r}")
        if not lint_text(dirty, lists):
            errors.append(f"selftest: an override swallowed the real hedge in {dirty!r}")

    # Hand-wrapped prose. Every multi-word phrase and every narrowed sense has
    # to survive a line break, in both directions — the ban must still fire
    # when the phrase wraps, and the exemption must still hold when it does.
    for wrapped, should_fire in (
        ("the ownership is undocumented and it could be\nargued either way.", True),
        ("the estate is something\nof a special case in the region.", True),
        ("the wine has a long\nfinish.", True),
        ("businesses that many people would fairly\ncall independent.", False),
        ("the producer is explicit rather\nthan leaving a reader to infer.", False),
        ("a person records the kind\nof evidence relied on.", False),
        ("the heat a Bordeaux variety needs to\nfinish.", False),
        # The same wrap inside a markdown blockquote, marker and all.
        ("> businesses many would fairly\n> call independent.", False),
        ("> the ownership is undocumented and it could be\n> argued either way.", True),
    ):
        fired = bool(lint_text(wrapped, lists))
        if fired != should_fire:
            missed = "did not fire across a line break" if should_fire else "fired across a line break"
            errors.append(f"selftest: {missed} on {wrapped!r}")

    # A blank line is a paragraph break, not a wrap. Bridging it would let the
    # lint assemble a phrase from two paragraphs that never contained one.
    if lint_text("the winemaker notes\n\nof the four blocks, two are dry-grown.", lists):
        errors.append("selftest: a phrase was assembled across a paragraph break")

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print(f"VALIDATE 6 FAIL — {len(errors)} self-test issue(s)")
        for message in errors:
            print(f"  {message}")
        return 1

    results = run()

    # METHODOLOGY.md asked to be linted against this list once it existed. It
    # joins `results` rather than printing beneath them, so the count line
    # covers it too. A warnings-only check is read by its total; a hit outside
    # the total is a hit nobody judges, and this one printed `0 hit(s) across
    # 0 file(s)` above a listed hit until 2026-08-07.
    #
    # Body only since Gate 10, 2026-08-13: the file now ships as `/methodology/`
    # and its frontmatter carries build notes rather than published prose.
    methodology = ROOT / "METHODOLOGY.md"
    if methodology.is_file():
        extra = lint_text(_shipped_text(methodology))
        if extra:
            results.append((methodology, extra))

    # regions.ts and glossary.ts, reader-facing since Gate 6.
    results.extend(lint_data_files())

    total = sum(len(hits) for _, hits in results)

    if not results:
        published = len(list(PUBLISHED_DIR.glob("*.mdx")))
        print(
            f"VALIDATE 6 PASS — register lint clean across {published} published "
            f"file(s), METHODOLOGY.md, regions.ts and glossary.ts"
        )
        return 0

    print(f"VALIDATE 6 WARN — {total} hit(s) across {len(results)} file(s). Warnings, not failures.")
    for path, hits in results:
        for hit in hits:
            rel = path.relative_to(ROOT)
            print(f"  {rel}:{hit['line']}  {hit['kind']}: {hit['phrase']!r}")
            print(f"      {hit['excerpt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
