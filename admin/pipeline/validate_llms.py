"""validate_llms.py — `/validate` check 19, `llms.txt` integrity. GATE 10.

From `.claude/commands/validate.md`:

    19. `llms.txt` integrity — references only live routes

Runs against `site/dist`, so `npm run build` (check 4) must have run first.

── Why this check exists separately from check 5 ─────────────────────────────

Check 5 walks the internal hrefs in built HTML. `llms.txt` is plain text served
outside the page graph, so nothing in check 5 has ever read it, and a dead link
in it would fail silently forever.

The consequence of a dead link differs too, which is the real argument for a
separate check. A reader who follows a broken link on a page sees a 404 and
knows. The reader of this file is a model, which will repeat what the file says
without being able to check it, and a hallucinated route in a directory whose
whole claim is documentary accuracy is a worse failure than a 404.

── The numeric claim is verified, not trusted ────────────────────────────────

The endpoint states the ownership split in prose — "48 of the 97 entries are
ownership confirmed" — because a model summarising this site without it will
report 97 producers as independent, which is not what the site claims. That
sentence is the one place `llms.txt` asserts a figure rather than a link, so it
is recomputed here from `producers.json` and required to match.

TRD.md §4.2 has this generated rather than committed for the same reason the
sitemap is. This check is what makes that guarantee testable from outside the
generator: the file is compared against what was actually built, not against the
functions that built it.

── The origin is read from the build, not from `admin/config.py` ─────────────

`config.py`'s `SITE_URL` is overridden by `.env` at runtime, so it answers "what
does this machine think the site is" rather than "what did this build emit". The
two can differ, and on a machine whose `.env` still carries the placeholder from
`.env.example` they do. Taking the origin from `dist`'s own canonical makes this
check self-consistent: it compares the file against the build it was built with,
which is the only comparison that means anything here.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from ..config import PRODUCERS_JSON_PATH, SITE_DIST_DIR, SITE_URL

DIST = SITE_DIST_DIR
LLMS = "llms.txt"

_CANONICAL = re.compile(r'<link rel="canonical" href="(https?://[^/"]+)', re.I)


def _origin(root: Path) -> str:
    """The origin this build emitted, read from the homepage's canonical.

    Falls back to `config.py`'s `SITE_URL` only when there is no built homepage
    to read, which is the case the self-test fixtures exercise.
    """
    home = root / "index.html"
    if home.is_file():
        found = _CANONICAL.search(home.read_text(encoding="utf-8"))
        if found:
            return found.group(1)
    return SITE_URL


_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# `\s+` between every word, never a literal space: the endpoint emits this
# sentence on one line today, and a later edit that wraps the prose would
# otherwise make the check silently stop finding the claim it exists to verify.
# A check that reports "the claim is gone" when the claim merely moved is the
# same class of defect as a regex that cannot see the markup it is checking.
_SPLIT_CLAIM = re.compile(
    r"(\d+)\s+of\s+the\s+(\d+)\s+entries\s+are\s+\*\*ownership\s+confirmed\*\*"
)
_UNCONFIRMED_CLAIM = re.compile(r"(\d+)\s+are\s+\*\*ownership\s+not\s+confirmed\*\*")

#: Sections and pages the file must carry. A file that quietly stopped listing
#: the methodology page would still pass a pure dead-link check, and the
#: methodology page is the one link this file exists to hand over.
REQUIRED_LINKS = ("/methodology/", "/glossary/", "/region/", "/producers/")


def _resolves(root: Path, path: str) -> bool:
    """Does this site-relative path correspond to something the build emitted?"""
    clean = path.split("#")[0].split("?")[0]
    if clean.startswith("/"):
        clean = clean[1:]
    if clean == "":
        return (root / "index.html").is_file()
    if clean.endswith("/"):
        return (root / clean / "index.html").is_file()
    # A file route such as `/llms.txt` or `/sitemap.xml`.
    return (root / clean).is_file() or (root / clean / "index.html").is_file()


def check(root: Path = DIST, producers_json: Path = PRODUCERS_JSON_PATH) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats: dict[str, int] = {"links": 0}

    target = root / LLMS
    if not target.is_file():
        return [
            f"{LLMS} was not built. TRD.md §4.2 requires it as an endpoint; "
            f"expected it at {target}"
        ], stats

    text = target.read_text(encoding="utf-8")
    lines = text.splitlines()
    origin = _origin(root)

    # ── Shape ──────────────────────────────────────────────────────────────
    if not lines or not lines[0].startswith("# "):
        errors.append(f"{LLMS} does not open with an H1 title")
    if not any(line.startswith("> ") for line in lines[:6]):
        errors.append(f"{LLMS} carries no blockquote summary under its title")
    if not any(line.startswith("## ") for line in lines):
        errors.append(f"{LLMS} has no H2 sections")

    # ── Every link is absolute, on this site, and live ─────────────────────
    seen: set[str] = set()
    for label, url in _LINK.findall(text):
        stats["links"] += 1
        if not url.startswith(("http://", "https://")):
            errors.append(
                f"{LLMS}: {label!r} links to {url!r}, which is not an absolute URL. "
                "This file is read away from the site, so a relative path has "
                "nothing to resolve against."
            )
            continue
        if not url.startswith(f"{origin}/"):
            errors.append(
                f"{LLMS}: {label!r} links off-site to {url!r}. This file lists this "
                f"site's own routes, and this build's origin is {origin}."
            )
            continue
        path = url[len(origin) :]
        seen.add(path)
        if not _resolves(root, path):
            errors.append(
                f"{LLMS}: {label!r} references {path}, which the build did not emit"
            )

    for required in REQUIRED_LINKS:
        if required not in seen:
            errors.append(f"{LLMS} does not link {required}")

    # ── The one numeric claim ──────────────────────────────────────────────
    if producers_json.is_file():
        rows = json.loads(producers_json.read_text(encoding="utf-8"))
        confirmed = sum(1 for row in rows if row.get("ownership_status") == "confirmed")
        total = len(rows)
        unconfirmed = total - confirmed

        match = _SPLIT_CLAIM.search(text)
        if not match:
            errors.append(
                f"{LLMS} no longer states the ownership split. A model summarising "
                "this site without it reports every entry as independent, which is "
                "not what the site claims."
            )
        elif (int(match.group(1)), int(match.group(2))) != (confirmed, total):
            errors.append(
                f"{LLMS} claims {match.group(1)} of {match.group(2)} confirmed; "
                f"producers.json has {confirmed} of {total}"
            )

        unconfirmed_match = _UNCONFIRMED_CLAIM.search(text)
        if unconfirmed_match and int(unconfirmed_match.group(1)) != unconfirmed:
            errors.append(
                f"{LLMS} claims {unconfirmed_match.group(1)} unconfirmed; "
                f"producers.json has {unconfirmed}"
            )

    return errors, stats


# ═══════════════════════════════════════════════════════════════════════════
# Self-test
# ═══════════════════════════════════════════════════════════════════════════

#: The self-test's own origin, fixed rather than read from `config.py`. `.env`
#: overrides `SITE_URL` at runtime, so a fixture built from it would assert a
#: different thing on different machines — and on one whose `.env` carries the
#: placeholder, the off-site case would accidentally point AT the origin and
#: prove nothing. A self-test must not depend on the environment it runs in.
_FIXTURE_ORIGIN = "https://fixture.invalid"

_GOOD = """# winelister

> A field guide to independent Australian winemakers.

## About the word independent

Every entry is in one of two ownership states. 2 of the 3 entries are **ownership
confirmed**, meaning a dated source names who owns the business. 1 are **ownership
not confirmed**, meaning no such source was found.

## Definitions and method

- [Methodology]({site}/methodology/): the definition
- [Glossary]({site}/glossary/): the terms

## Regions

- [All regions]({site}/region/): 1 region

## Optional

- [All producers]({site}/producers/): 3 producers
"""


def _fixture(root: Path, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    # A homepage carrying the canonical, because that is where `_origin` reads
    # the build's own origin from.
    (root / "index.html").write_text(
        f'<html><head><link rel="canonical" href="{_FIXTURE_ORIGIN}/"/></head></html>',
        "utf-8",
    )
    for route in ("methodology", "glossary", "region", "producers"):
        (root / route).mkdir(parents=True, exist_ok=True)
        (root / route / "index.html").write_text("<html></html>", "utf-8")
    (root / LLMS).write_text(body, "utf-8")

    producers = root / "producers.json"
    producers.write_text(
        json.dumps(
            [
                {"slug": "a", "ownership_status": "confirmed"},
                {"slug": "b", "ownership_status": "confirmed"},
                {"slug": "c", "ownership_status": "unconfirmed"},
            ]
        ),
        "utf-8",
    )
    return producers


def _selftest() -> list[str]:
    """Each case breaks one thing and requires the error to name it."""
    errors: list[str] = []

    def run(body: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dist"
            producers = _fixture(root, body.format(site=_FIXTURE_ORIGIN))
            found, _ = check(root, producers)
            return found

    clean = run(_GOOD)
    if clean:
        errors.append(f"selftest: the CLEAN fixture failed — {clean[:3]}")

    cases: list[tuple[str, str, str]] = [
        (
            "a dead route",
            _GOOD.replace("{site}/glossary/", "{site}/nowhere/"),
            "which the build did not emit",
        ),
        (
            "a relative link",
            _GOOD.replace("({site}/methodology/)", "(/methodology/)"),
            "not an absolute URL",
        ),
        (
            "an off-site link",
            _GOOD.replace("({site}/glossary/)", "(https://somewhere-else.invalid/glossary/)"),
            "links off-site",
        ),
        (
            "a dropped methodology link",
            _GOOD.replace("- [Methodology]({site}/methodology/): the definition\n", ""),
            "does not link /methodology/",
        ),
        (
            "no H1",
            _GOOD.replace("# winelister", "winelister"),
            "does not open with an H1",
        ),
        (
            "no summary blockquote",
            _GOOD.replace("> A field guide", "A field guide"),
            "no blockquote summary",
        ),
        (
            "a wrong ownership split",
            _GOOD.replace("2 of the 3 entries", "3 of the 3 entries"),
            "producers.json has 2 of 3",
        ),
        (
            "a wrong unconfirmed count",
            _GOOD.replace("1 are **ownership\nnot confirmed**", "9 are **ownership\nnot confirmed**"),
            "producers.json has 1",
        ),
        (
            "the split claim removed",
            _GOOD.replace("2 of the 3 entries are **ownership\nconfirmed**", "Some are confirmed"),
            "no longer states the ownership split",
        ),
    ]

    for label, body, expected in cases:
        found = run(body)
        if not any(expected in error for error in found):
            errors.append(
                f"selftest: {label} was not caught by a message naming "
                f"{expected!r} (got {found[:2] or 'nothing'})"
            )

    # A missing file is its own case: there is nothing to parse.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        root.mkdir(parents=True)
        found, _ = check(root, root / "producers.json")
        if not any("was not built" in error for error in found):
            errors.append("selftest: a missing llms.txt was not caught")

    return errors


def main() -> int:
    problems = _selftest()
    if problems:
        print("VALIDATE 19 FAIL — selftest")
        for problem in problems:
            print(f"  {problem}")
        return 1

    errors, stats = check()

    if errors:
        print(f"VALIDATE 19 FAIL — {len(errors)} problem(s)")
        for error in errors[:40]:
            print(f"  {error}")
        return 1

    print(
        f"VALIDATE 19 PASS — selftest ok; {stats['links']} link(s) in {LLMS} all "
        "resolve to built routes, and its ownership split matches producers.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
