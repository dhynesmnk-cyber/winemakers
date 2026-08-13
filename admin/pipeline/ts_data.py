"""ts_data.py — read the hand-authored TypeScript data files from Python.

GATE 6.

``site/src/data/regions.ts`` and ``site/src/data/glossary.ts`` are hand-authored
TypeScript, and three Python consumers need what is in them:

    * ``/validate`` check 11, glossary coverage in both directions
    * ``/validate`` check 12, region taxonomy lint
    * ``forewords.py``, which needs a region's register facts and a term's
      definition to build a fact set

``schema_surfaces.py`` already reads these files, but only ever pulls flat
string tuples with a targeted regex, which is right for what it needs and not
enough here: a region carries a zone, a state list, a registration level, a
subregion list and a note, and matching all five with one expression per field
is how a parser silently returns the wrong region's ``note``.

So this parses the array literal properly.

── Why not run Node ──────────────────────────────────────────────────────────

Because it would make a Python check depend on a working npm install and a
TypeScript loader to tell you a glossary entry is missing. ``/validate`` has to
run in a bare clone; the pipeline fixtures already hold that line and this holds
it too.

── What it does NOT do ───────────────────────────────────────────────────────

This is not a TypeScript parser. It reads the subset those two files actually
use: array and object literals of strings, numbers, booleans and null, with bare
identifier keys, trailing commas, and line and block comments between members.
It deliberately fails loudly on anything else rather than guessing, because a
parser that silently returns a partial register would make check 12 pass by
finding nothing to complain about.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import SITE_DIR

REGIONS_TS_PATH = SITE_DIR / "src" / "data" / "regions.ts"
GLOSSARY_TS_PATH = SITE_DIR / "src" / "data" / "glossary.ts"
FIGURES_TS_PATH = SITE_DIR / "src" / "data" / "figures.ts"


class TsParseError(Exception):
    """The source did not match the subset this module reads."""


# =============================================================================
# 1. A tiny recursive-descent reader for the object-literal subset
# =============================================================================

_WS = re.compile(r"\s+")
_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class _Reader:
    def __init__(self, text: str, offset: int = 0) -> None:
        self.text = text
        self.i = offset

    # ── lexing helpers ────────────────────────────────────────────────────
    def skip(self) -> None:
        """Whitespace and comments, repeatedly, until neither matches."""
        while True:
            start = self.i
            for pattern in (_WS, _LINE_COMMENT, _BLOCK_COMMENT):
                match = pattern.match(self.text, self.i)
                if match:
                    self.i = match.end()
            if self.i == start:
                return

    def peek(self) -> str:
        self.skip()
        return self.text[self.i] if self.i < len(self.text) else ""

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise TsParseError(self._where(f"expected {char!r}"))
        self.i += 1

    def _where(self, message: str) -> str:
        line = self.text.count("\n", 0, self.i) + 1
        snippet = self.text[self.i : self.i + 40].replace("\n", "\\n")
        return f"{message} at line {line}, near {snippet!r}"

    # ── values ────────────────────────────────────────────────────────────
    def value(self) -> Any:
        char = self.peek()
        if char == '"':
            return self.string()
        if char == "[":
            return self.array()
        if char == "{":
            return self.obj()
        if self.text.startswith("true", self.i):
            self.i += 4
            return True
        if self.text.startswith("false", self.i):
            self.i += 5
            return False
        if self.text.startswith("null", self.i):
            self.i += 4
            return None
        match = _NUMBER.match(self.text, self.i)
        if match:
            self.i = match.end()
            raw = match.group(0)
            return float(raw) if ("." in raw or "e" in raw.lower()) else int(raw)
        raise TsParseError(self._where("unrecognised value"))

    def string(self) -> str:
        self.expect('"')
        out: list[str] = []
        while True:
            if self.i >= len(self.text):
                raise TsParseError("unterminated string")
            char = self.text[self.i]
            if char == '"':
                self.i += 1
                return "".join(out)
            if char == "\\":
                self.i += 1
                esc = self.text[self.i]
                if esc == "u":
                    out.append(chr(int(self.text[self.i + 1 : self.i + 5], 16)))
                    self.i += 5
                    continue
                if esc not in _ESCAPES:
                    raise TsParseError(self._where(f"unknown escape \\{esc}"))
                out.append(_ESCAPES[esc])
                self.i += 1
                continue
            out.append(char)
            self.i += 1

    def array(self) -> list[Any]:
        self.expect("[")
        items: list[Any] = []
        while True:
            if self.peek() == "]":
                self.i += 1
                return items
            items.append(self.value())
            if self.peek() == ",":
                self.i += 1

    def obj(self) -> dict[str, Any]:
        self.expect("{")
        out: dict[str, Any] = {}
        while True:
            char = self.peek()
            if char == "}":
                self.i += 1
                return out
            if char == '"':
                key = self.string()
            else:
                match = _IDENT.match(self.text, self.i)
                if not match:
                    raise TsParseError(self._where("expected a key"))
                key = match.group(0)
                self.i = match.end()
            self.expect(":")
            out[key] = self.value()
            if self.peek() == ",":
                self.i += 1


def parse_const_array(text: str, name: str) -> list[Any]:
    """The array literal assigned to ``export const NAME``.

    Tolerates an inline type annotation (``: readonly Region[]``), which is why
    the opening bracket is found by scanning forward from the ``=`` rather than
    by matching the declaration in one expression.
    """
    match = re.search(rf"export const {re.escape(name)}\b", text)
    if not match:
        raise TsParseError(f"no `export const {name}` in the source")

    equals = text.find("=", match.end())
    if equals == -1:
        raise TsParseError(f"{name}: no assignment found")

    reader = _Reader(text, equals + 1)
    if reader.peek() != "[":
        raise TsParseError(f"{name}: assigned value is not an array literal")
    return reader.array()


# =============================================================================
# 2. The two files
# =============================================================================


def _read(path: Path) -> str:
    if not path.is_file():
        raise TsParseError(f"not found: {path}")
    return path.read_text(encoding="utf-8")


def regions(path: Path = REGIONS_TS_PATH) -> list[dict[str, Any]]:
    """`REGIONS` from regions.ts, each a dict with the Region interface's keys."""
    return parse_const_array(_read(path), "REGIONS")


def subregions(path: Path = REGIONS_TS_PATH) -> list[dict[str, Any]]:
    """`SUBREGIONS` from regions.ts."""
    return parse_const_array(_read(path), "SUBREGIONS")


def zones(path: Path = REGIONS_TS_PATH) -> list[dict[str, Any]]:
    """`ZONES` from regions.ts. Zones are not routed; check 12 reads them anyway."""
    return parse_const_array(_read(path), "ZONES")


def glossary(path: Path = GLOSSARY_TS_PATH) -> list[dict[str, Any]]:
    """`GLOSSARY` from glossary.ts, every entry, in authored order."""
    return parse_const_array(_read(path), "GLOSSARY")


def state_names(path: Path = GLOSSARY_TS_PATH) -> dict[str, str]:
    """`{"SA": "South Australia", ...}`, derived from the glossary.

    `config.ts` builds its `STATE_NAMES` the same way, from the same entries.
    Deriving it here rather than adding a literal map to `admin/config.py` keeps
    the count of hand-kept copies at one: a second Python copy would be a drift
    surface that check 13 would then have to police for no gain.
    """
    return {
        entry["value"]: entry["term"]
        for entry in glossary(path)
        if entry.get("vocabulary") == "state"
    }


def covered_vocabularies(path: Path = GLOSSARY_TS_PATH) -> list[str]:
    """`COVERED_VOCABULARIES` — the vocabularies check 11 must have full coverage of.

    `VERIFIABLE_FIELDS` is deliberately absent from it: a list of field names is
    not a vocabulary of values, and treating it as one produces false orphans.
    """
    text = _read(path)
    match = re.search(
        r"export const COVERED_VOCABULARIES[^=]*=\s*\[(.*?)\]", text, re.DOTALL
    )
    if not match:
        raise TsParseError("no COVERED_VOCABULARIES in glossary.ts")
    return re.findall(r'"([^"]+)"', match.group(1))


# =============================================================================
# 3. Self-test — the project's no-test-framework pattern
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    clean = """
    // A leading comment.
    export const THINGS: readonly Thing[] = [
      {
        slug: "one",
        name: "One \\"quoted\\" name",
        zone: null,
        states: ["VIC", "NSW"],
        registered: true,
        count: 42,
        /* a block comment between members */
        note: "A note with a \\u00e9 in it, and a comma, and a semicolon;",
      },
      { slug: "two", name: "Two", zone: "Z", states: [], registered: false },
    ] as const;
    """
    try:
        parsed = parse_const_array(clean, "THINGS")
    except TsParseError as exc:
        errors.append(f"selftest: clean fixture failed to parse: {exc}")
        return errors

    if len(parsed) != 2:
        errors.append(f"selftest: expected 2 members, parsed {len(parsed)}")
    else:
        first = parsed[0]
        expected = {
            "slug": "one",
            "name": 'One "quoted" name',
            "zone": None,
            "states": ["VIC", "NSW"],
            "registered": True,
            "count": 42,
            "note": "A note with a é in it, and a comma, and a semicolon;",
        }
        for key, want in expected.items():
            if first.get(key) != want:
                errors.append(
                    f"selftest: THINGS[0].{key} parsed as {first.get(key)!r}, "
                    f"expected {want!r}"
                )
        if parsed[1].get("registered") is not False:
            errors.append("selftest: `false` did not survive the round trip")

    # A truncated literal must RAISE, not return a short list. A parser that
    # silently returns what it managed to read would make check 12 pass by
    # having found nothing to complain about.
    broken = 'export const THINGS = [{ slug: "one", name: "One" '
    try:
        parse_const_array(broken, "THINGS")
        errors.append("selftest: a truncated array literal did NOT raise")
    except TsParseError:
        pass

    try:
        parse_const_array("const OTHER = [];", "THINGS")
        errors.append("selftest: a missing export did NOT raise")
    except TsParseError:
        pass

    return errors


def main() -> int:
    errors = _selftest()

    # Then the real files, so a parse regression against the actual register
    # fails here rather than inside whichever check runs first.
    try:
        counts = (
            f"{len(regions())} regions, {len(subregions())} subregions, "
            f"{len(zones())} zones, {len(glossary())} glossary entries, "
            f"{len(covered_vocabularies())} covered vocabularies"
        )
    except TsParseError as exc:
        errors.append(f"parsing the real data files failed: {exc}")
        counts = ""

    if errors:
        print("TS DATA FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    print(f"TS DATA PASS — selftest ok; parsed {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
