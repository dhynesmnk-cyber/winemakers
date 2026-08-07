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
    "rather": r"\brather\b(?!\s+than\b)",
    # `the kind of evidence` is nominal. `kind of good` is the hedge.
    "kind of": r"(?<!the )(?<!this )(?<!that )(?<!what )(?<!a )\bkind of\b",
    "sort of": r"(?<!the )(?<!this )(?<!that )(?<!what )(?<!a )\bsort of\b",
    # The tasting sense of `finish` is a NOUN and takes a determiner or an
    # adjective: "a long finish", "the finish". The verb is ordinary
    # viticulture — "the heat a Bordeaux variety needs to finish", "picking
    # starts after the plains have finished — and fires constantly on correct
    # copy. Observed on the first real draft this pipeline produced.
    "finish": r"\b(?:the|a|an|its|long|short|clean|dry|crisp|lingering|tannic)\s+finish\b",
}


def _pattern_for(phrase: str) -> re.Pattern[str]:
    """Word-boundary match, so `finish` does not fire on `finished`."""
    if phrase in _OVERRIDES:
        return re.compile(_OVERRIDES[phrase], re.IGNORECASE)
    return re.compile(r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b", re.IGNORECASE)


def lint_text(text: str, lists: dict[str, list[str]] | None = None) -> list[dict]:
    """`[{line, kind, phrase, excerpt}]` for one document's prose."""
    lists = lists if lists is not None else load_lists()
    masked = _mask(text)
    hits: list[dict] = []

    for line_number, line in enumerate(masked.splitlines(), start=1):
        if not line.strip():
            continue
        for info, label in LIST_LABELS.items():
            for phrase in lists.get(info, []):
                if _pattern_for(phrase).search(line):
                    hits.append(
                        {
                            "line": line_number,
                            "kind": label,
                            "phrase": phrase,
                            "excerpt": line.strip()[:100],
                        }
                    )
        # The em-dash ban is a character, not a list.
        if "—" in line:
            hits.append(
                {"line": line_number, "kind": "em dash", "phrase": "—",
                 "excerpt": line.strip()[:100]}
            )
        for pair in lists.get("us-spellings", []):
            if _pattern_for(pair).search(line):
                hits.append(
                    {"line": line_number, "kind": "US spelling", "phrase": pair,
                     "excerpt": line.strip()[:100]}
                )
    return hits


def _body_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


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
                     "hedge", "not-X-but-Y", "US spelling"):
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
    ):
        if lint_text(clean, lists):
            errors.append(f"selftest: a false positive on {clean!r}")
        if not lint_text(dirty, lists):
            errors.append(f"selftest: an override swallowed the real hedge in {dirty!r}")

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print(f"VALIDATE 6 FAIL — {len(errors)} self-test issue(s)")
        for message in errors:
            print(f"  {message}")
        return 1

    results = run()
    total = sum(len(hits) for _, hits in results)

    # METHODOLOGY.md asked to be linted against this list once it existed.
    methodology = ROOT / "METHODOLOGY.md"
    extra = lint_text(methodology.read_text(encoding="utf-8")) if methodology.is_file() else []

    if not results and not extra:
        published = len(list(PUBLISHED_DIR.glob("*.mdx")))
        print(f"VALIDATE 6 PASS — register lint clean across {published} published file(s)")
        return 0

    print(f"VALIDATE 6 WARN — {total} hit(s) across {len(results)} file(s). Warnings, not failures.")
    for path, hits in results:
        for hit in hits:
            rel = path.relative_to(ROOT)
            print(f"  {rel}:{hit['line']}  {hit['kind']}: {hit['phrase']!r}")
            print(f"      {hit['excerpt']}")
    for hit in extra:
        print(f"  METHODOLOGY.md:{hit['line']}  {hit['kind']}: {hit['phrase']!r}")
        print(f"      {hit['excerpt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
