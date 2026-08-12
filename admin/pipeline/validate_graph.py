"""validate_graph.py — `/validate` check 17, the internal-linking graph. GATE 9.

From `.claude/commands/validate.md`:

    17. Internal-linking graph — every published producer is linked from ≥3
        aggregation pages; every comparison and region page is reachable from a
        hub; zero orphans. Pages below the minimum-producer threshold must
        skip-and-log, visible in the build output, never fail.

Runs against `site/dist`, so `npm run build` (check 4) must have run first, for
the same reason check 5 does: the thing being checked is the graph a reader and
a crawler actually receive. A link that exists in a component but lands on a
route Astro never emitted is not a link.

── Why "≥3 aggregation pages" is the rule ────────────────────────────────────

UX.md §2.4: "A producer page is a hub, not a terminus." The number is
`MIN_AGGREGATION_LINKS`, mirrored in `config.ts` and `config.py`, and it is 3
because every published producer should be reachable by at least three
independent routes — its region, its state and the A to Z index at minimum,
before any variety, practice or comparison page is counted. A producer sitting
on fewer than three is one taxonomy edit away from being unreachable except by
search, which UX.md §2.1 is explicit is "an accelerator ... never the only route
to anything".

The count is of DISTINCT AGGREGATION PAGES, not of links: a region page that
happens to link a producer twice (name and thumbnail, as `ProducerEntry` does)
is still one route to it.

── What counts as an aggregation page ────────────────────────────────────────

A page that lists producers as its purpose: the homepage, `/producers/` and its
pager, region, subregion, state, variety, practice, and now `/compare/[slug]/`.
Deliberately NOT other producer pages — a producer linking to a sibling is
lateral movement, not an aggregation route, and counting it would let a cluster
of cross-linked producers satisfy the rule while sitting off every listing.

── The threshold half is checked by recomputing it ───────────────────────────

The skip-and-log behaviour lives in `comparisons.ts`, which is TypeScript, and
this check is Python. Rather than parse the build log — which would assert that
a message was printed, not that the right pages exist — the expected comparison
set is recomputed here from `producers.json` and `MIN_COMPARISON_PRODUCERS`, and
`dist` is asserted to hold exactly that set. A threshold that stopped being
applied shows up as a built page this check did not expect; a threshold applied
too aggressively shows up as a missing one.

`MIN_COMPARISON_PRODUCERS` is read from `admin/config.py`, which check 13
already proves is an exact mirror of `config.ts`. That is what makes recomputing
here legitimate rather than a second, drifting copy of the rule.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from ..config import (
    MIN_AGGREGATION_LINKS,
    MIN_COMPARISON_PRODUCERS,
    PRODUCERS_JSON_PATH,
    SITE_DIR,
)

DIST = SITE_DIR / "dist"

HREF = re.compile(r'href="([^"]+)"', re.I)

#: The hubs whose children must be reachable from them. `/compare/` is Gate 9's
#: and `/region/` is Gate 6's; both are named in the check's own wording.
HUBS: dict[str, str] = {
    "/compare/": "/compare/",
    "/region/": "/region/",
}


def _pages(root: Path) -> list[Path]:
    return sorted(root.rglob("index.html"))


def _route_of(path: Path, root: Path) -> str:
    rel = path.relative_to(root).parent.as_posix()
    return "/" if rel == "." else f"/{rel}/"


def _is_aggregation(route: str) -> bool:
    """A page whose purpose is listing producers. See the module docstring."""
    if route == "/":
        return True
    if route.startswith("/producer/"):
        return False  # a producer page is not a route TO a producer
    return route.startswith(
        ("/producers/", "/region/", "/variety/", "/practice/", "/compare/")
    ) or _is_state_route(route)


#: State routes are bare single-segment slugs (`/south-australia/`), so they
#: cannot be matched by prefix without also catching `/glossary/` and friends.
_NON_STATE_ROOTS = {
    "producers",
    "region",
    "variety",
    "practice",
    "compare",
    "glossary",
    "producer",
    "methodology",
    "blog",
}


def _is_state_route(route: str) -> bool:
    """`/south-australia/` and its pager `/south-australia/page/2/`.

    The pager matters: at the current corpus every state listing runs to several
    pages, so a producer on page 2 of its state is reachable from that state and
    counting only page 1 would report it as under-linked. The other aggregation
    families are caught by prefix, which already includes their `page/` segments.
    """
    parts = [p for p in route.split("/") if p]
    if not parts or parts[0] in _NON_STATE_ROOTS:
        return False
    return len(parts) == 1 or (len(parts) == 3 and parts[1] == "page")


def _links(page: Path) -> set[str]:
    """Every internal route this page links to, normalised to a trailing slash."""
    out: set[str] = set()
    for href in HREF.findall(page.read_text(encoding="utf-8")):
        href = href.split("#")[0].split("?")[0]
        if not href.startswith("/") or href.startswith("//"):
            continue
        if not href.endswith("/"):
            # `/sitemap.xml` and friends are files, not routes.
            if "." in href.rsplit("/", 1)[-1]:
                continue
            href += "/"
        out.add(href)
    return out


def _expected_comparisons(producers: list[dict]) -> set[str]:
    """Recompute the comparison set `comparisons.ts` should have built."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for producer in producers:
        for region in producer.get("regions") or []:
            for variety in producer.get("varieties") or []:
                counts[(variety, region)] += 1
    return {
        f"/compare/{variety}-in-{region}/"
        for (variety, region), n in counts.items()
        if n >= MIN_COMPARISON_PRODUCERS
    }


def check(root: Path | None = None, producers_json: Path | None = None):
    """The graph check. Returns (errors, stats)."""
    root = root or DIST
    errors: list[str] = []
    stats: dict[str, int] = {}

    if not root.is_dir():
        return ([f"{root} does not exist — run `npm run build` first (check 4)."], stats)

    pages = _pages(root)
    routes = {_route_of(p, root) for p in pages}

    # route -> the set of pages linking to it
    inbound: dict[str, set[str]] = defaultdict(set)
    for page in pages:
        source = _route_of(page, root)
        for target in _links(page):
            if target in routes:
                inbound[target].add(source)

    stats["pages"] = len(pages)

    # ── 1. Every producer reachable from ≥ MIN_AGGREGATION_LINKS aggregations ──
    producer_routes = sorted(r for r in routes if r.startswith("/producer/"))
    stats["producers"] = len(producer_routes)

    under = []
    for route in producer_routes:
        sources = {s for s in inbound.get(route, set()) if _is_aggregation(s)}
        if len(sources) < MIN_AGGREGATION_LINKS:
            under.append((route, sorted(sources)))
    for route, sources in under:
        errors.append(
            f"{route} is linked from {len(sources)} aggregation page(s), "
            f"needs {MIN_AGGREGATION_LINKS}: {', '.join(sources) or 'none'}"
        )

    # ── 2. Hub reachability ───────────────────────────────────────────────────
    for hub, prefix in HUBS.items():
        if hub not in routes:
            errors.append(f"hub {hub} was not built")
            continue
        hub_page = root / hub.strip("/") / "index.html"
        hub_links = _links(hub_page)
        children = sorted(
            r for r in routes if r.startswith(prefix) and r != hub and _depth(r) == _depth(hub) + 1
        )
        for child in children:
            if child not in hub_links:
                errors.append(f"{child} is not linked from its hub {hub}")
        stats[f"hub{hub}"] = len(children)

    # ── 3. Zero orphans ───────────────────────────────────────────────────────
    orphans = [
        r
        for r in sorted(routes)
        if r != "/" and not inbound.get(r) and r not in HUBS
    ]
    for route in orphans:
        errors.append(f"{route} is an orphan — no page links to it")

    # ── 4. The comparison threshold actually skipped ──────────────────────────
    path = producers_json or PRODUCERS_JSON_PATH
    if path.is_file():
        producers = json.loads(path.read_text(encoding="utf-8"))
        expected = _expected_comparisons(producers)
        built = {r for r in routes if r.startswith("/compare/") and r != "/compare/"}
        for extra in sorted(built - expected):
            errors.append(
                f"{extra} was built but is under the {MIN_COMPARISON_PRODUCERS}-producer "
                "threshold — the skip is not being applied"
            )
        for missing in sorted(expected - built):
            errors.append(
                f"{missing} clears the threshold but was not built — "
                "the skip is being applied too aggressively"
            )
        stats["comparisons"] = len(built)

    return errors, stats


def _depth(route: str) -> int:
    return len([p for p in route.split("/") if p])


# ══════════════════════════════════════════════════════════════════════════════
# Self-test — the mechanised form of the gate's "deliberately thinned fixture".
# ══════════════════════════════════════════════════════════════════════════════


def _write(root: Path, route: str, links: list[str]) -> None:
    page = root / route.strip("/") / "index.html" if route != "/" else root / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f'<a href="{href}">x</a>' for href in links)
    page.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")


def _fixture(root: Path, *, orphan=False, thin_built=False, under_linked=False) -> Path:
    """A miniature site that passes, plus whichever defect is asked for."""
    producers = ["/producer/a/", "/producer/b/", "/producer/c/", "/producer/d/"]

    # Three aggregation routes link every producer: region, state, A to Z. The
    # homepage links the hubs and the two listings that have none of their own,
    # so the clean fixture carries no orphan.
    _write(root, "/", ["/region/", "/compare/", "/producers/", "/south-australia/"])
    _write(root, "/region/", ["/region/testville/"])
    _write(root, "/region/testville/", producers)

    # `under_linked` drops one producer from the state page AND the comparison,
    # leaving it on region and A to Z only — two, below MIN_AGGREGATION_LINKS.
    # Dropping it from one alone would leave three, which still passes.
    linked = producers[:-1] if under_linked else producers
    _write(root, "/south-australia/", linked)
    _write(root, "/producers/", producers)

    _write(root, "/compare/", ["/compare/shiraz-in-testville/"])
    _write(root, "/compare/shiraz-in-testville/", linked)

    for route in producers:
        _write(root, route, ["/region/testville/"])

    if orphan:
        _write(root, "/glossary/lonely/", [])

    if thin_built:
        # A pair with 4 producers is legitimate; this one has 2 and must not exist.
        _write(root, "/compare/gamay-in-testville/", producers[:2])
        _write(root, "/compare/", ["/compare/shiraz-in-testville/", "/compare/gamay-in-testville/"])

    data = [
        {"slug": s.strip("/").split("/")[-1], "regions": ["testville"], "varieties": ["shiraz"]}
        for s in producers
    ]
    # Two of them also work gamay — under the threshold of 4, so no page.
    data[0]["varieties"] = ["shiraz", "gamay"]
    data[1]["varieties"] = ["shiraz", "gamay"]

    json_path = root.parent / "producers.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    return json_path


def _selftest() -> list[str]:
    """Must pass a clean fixture and catch each defect."""
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        jp = _fixture(root)
        found, _ = check(root, jp)
        if found:
            errors.append(f"selftest: clean fixture reported {found}")

    # A page nothing links to.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        jp = _fixture(root, orphan=True)
        found, _ = check(root, jp)
        if not any("orphan" in e for e in found):
            errors.append("selftest: an orphan page was not caught")

    # A producer on fewer than MIN_AGGREGATION_LINKS aggregation pages.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        jp = _fixture(root, under_linked=True)
        found, _ = check(root, jp)
        if not any("aggregation page" in e for e in found):
            errors.append("selftest: an under-linked producer was not caught")

    # THE THINNED FIXTURE the gate's done-condition names: a comparison under
    # the threshold must be absent from dist. Its presence is the failure, and
    # the check must REPORT it rather than the build having died on it.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        jp = _fixture(root, thin_built=True)
        found, _ = check(root, jp)
        if not any("threshold" in e for e in found):
            errors.append("selftest: a below-threshold comparison page was not caught")

    return errors


def main() -> int:
    problems = _selftest()
    if problems:
        print("VALIDATE 17 FAIL — selftest")
        for problem in problems:
            print(f"  {problem}")
        return 1

    errors, stats = check()

    if errors:
        print("VALIDATE 17 FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    print(
        f"VALIDATE 17 PASS — selftest ok; {stats.get('producers', 0)} producer page(s) "
        f"each linked from ≥{MIN_AGGREGATION_LINKS} aggregation pages, "
        f"{stats.get('comparisons', 0)} comparison page(s) match the "
        f"{MIN_COMPARISON_PRODUCERS}-producer threshold and are reachable from "
        f"their hub, zero orphans across {stats.get('pages', 0)} page(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
