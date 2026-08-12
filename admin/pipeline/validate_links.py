"""validate_links.py — `/validate` check 5, the link check. GATE 6.

From `.claude/commands/validate.md`:

    5. Link check — every internal href resolves to a built page; a producer
       page exists for every slug in the derived JSON and vice versa; every
       region/subregion/variety/practice page has ≥1 producer; no page links to
       a draft; no dead programmatic routes.

Runs against `site/dist`, so `npm run build` (check 4) must have run first. It
reads the built HTML rather than the source, because the thing being checked is
what a reader actually receives: a route that Astro decided not to emit looks
fine in `src/` and 404s in production.

── Routes owned by a later gate ──────────────────────────────────────────────

`Footer.astro` links `/methodology/` (Gate 10), `/blog/` and `/rss.xml`
(Gate 11). None of those pages exists yet and all three are correct links to
have: Gate 10's done-condition is that the methodology page is live AND LINKED,
so removing the link now only to add it back is churn that also makes the footer
lose and regain entries.

They are listed in `PENDING_ROUTES` with the gate that owns each, and the list
is PRINTED ON EVERY RUN rather than silently tolerated. When a gate ships, its
entry comes out and the route becomes a hard requirement like any other. A
pending route that is still missing after its gate has shipped is exactly the
kind of thing this check exists to notice, so the list is small, explicit and
visible.

── Why `/rss.xml` is on it ───────────────────────────────────────────────────

No route table in TRD.md, UX.md or DESIGN.md mentions `/rss.xml`. It is in the
footer because the footer was written before anything generated feeds. It is
assigned to Gate 11 with the blog, which is the only content on the site a feed
would carry (decision recorded 2026-08-08, TRD.md §4.2 amendment).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from ..config import PRODUCERS_JSON_PATH, SITE_DIR, STAGING_DIR
from .forewords import targets

DIST = SITE_DIR / "dist"

#: Route -> the gate that ships it. Printed on every run. See the module
#: docstring: this is an explicit, visible, shrinking list, not a mute allow-list.
PENDING_ROUTES: dict[str, str] = {
    # `/methodology/` came off this list on 2026-08-13 when Gate 10 shipped it.
    # It is now a hard requirement like any other route, which is the point of
    # the list shrinking rather than the route being permitted quietly.
    "/blog/": "Gate 11",
    "/rss.xml": "Gate 11",
}

#: Schemes and forms that are not this site's problem.
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.IGNORECASE)
_HREF = re.compile(r"""\shref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_ENTRY_ROW = re.compile(r'<li class="entry"')


def _pages(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def _route_of(path: Path, root: Path | None = None) -> str:
    """`dist/region/x/index.html` -> `/region/x/`."""
    relative = path.relative_to(root if root is not None else DIST)
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return f"/{relative.as_posix()}"


def _resolves(href: str, root: Path | None = None) -> bool:
    """Does an internal href correspond to something in `dist`?"""
    root = root if root is not None else DIST
    target = href.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return True
    if not target.startswith("/"):
        return False  # Every internal link on this site is root-relative.

    relative = target.lstrip("/")
    if target.endswith("/") or not relative:
        return (root / relative / "index.html").is_file()
    # A file route such as /sitemap.xml, or a directory route written without
    # its trailing slash.
    return (root / relative).is_file() or (root / relative / "index.html").is_file()


def check(
    root: Path | None = None,
    producers_json: Path | None = None,
    staging_dir: Path | None = None,
    pending: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, int]]:
    """Returns `(errors, stats)`. The paths are parameters so the self-test can
    run the WHOLE check against a fixture tree rather than only its helpers."""
    root = root if root is not None else DIST
    producers_json = producers_json if producers_json is not None else PRODUCERS_JSON_PATH
    staging_dir = staging_dir if staging_dir is not None else STAGING_DIR
    pending = pending if pending is not None else PENDING_ROUTES

    errors: list[str] = []
    stats: dict[str, int] = {}

    if not root.is_dir():
        return (
            [f"{root} does not exist. Run `npm run build` (check 4) first."],
            stats,
        )

    pages = _pages(root)
    routes = {_route_of(path, root) for path in pages}
    stats["pages"] = len(pages)

    # ── 1. Every internal href resolves ───────────────────────────────────
    checked = 0
    pending_hits: dict[str, int] = {}
    for path in pages:
        text = path.read_text(encoding="utf-8", errors="replace")
        route = _route_of(path, root)
        for raw in _HREF.findall(text):
            href = html.unescape(raw).strip()
            if _EXTERNAL.match(href):
                continue
            checked += 1
            normalised = href.split("#", 1)[0].split("?", 1)[0]
            if normalised in pending:
                pending_hits[normalised] = pending_hits.get(normalised, 0) + 1
                continue
            if not _resolves(href, root):
                errors.append(f"{route} links to {href}, which is not a built page")
    stats["hrefs"] = checked

    # A pending route that has QUIETLY STARTED WORKING is worth knowing about:
    # it means the gate shipped and this list was not updated.
    for route, gate in pending.items():
        if _resolves(route, root):
            errors.append(
                f"{route} now resolves but is still listed as pending ({gate}). "
                f"Remove it from PENDING_ROUTES so it is checked like any other."
            )
    stats["pending"] = len(pending)

    # ── 2. Producer pages ↔ derived JSON, both directions ─────────────────
    producers: list[dict[str, Any]] = (
        json.loads(producers_json.read_text(encoding="utf-8"))
        if producers_json.is_file()
        else []
    )
    json_slugs = {row["slug"] for row in producers}
    built_slugs = {
        route.strip("/").split("/", 1)[1]
        for route in routes
        if route.startswith("/producer/")
    }
    for slug in sorted(json_slugs - built_slugs):
        errors.append(f"producers.json has {slug}, which has no /producer/{slug}/ page")
    for slug in sorted(built_slugs - json_slugs):
        errors.append(f"/producer/{slug}/ was built but is not in producers.json")
    stats["producers"] = len(json_slugs)

    # ── 3. No page links to a draft ───────────────────────────────────────
    staged = {path.stem for path in staging_dir.glob("*.mdx")} if staging_dir.is_dir() else set()
    drafts = staged - json_slugs
    if drafts:
        for path in pages:
            text = path.read_text(encoding="utf-8", errors="replace")
            for slug in drafts:
                if f"/producer/{slug}/" in text:
                    errors.append(
                        f"{_route_of(path, root)} links to /producer/{slug}/, which is "
                        f"still a draft in _staging"
                    )
    stats["drafts"] = len(drafts)

    # ── 4. No dead programmatic routes, in BOTH directions ────────────────
    #
    # `targets()` is the Python mirror of `taxonomy.ts`'s present-only
    # membership. Reusing it rather than recomputing here is the point: two
    # copies of "which taxonomy members have producers" is exactly the drift
    # that would let a page exist for a region with nothing in it.
    expected = {
        "region": lambda key: f"/region/{key}/",
        "state": None,  # slug is the state NAME, resolved below
        "variety": lambda key: f"/variety/{key}/",
        "practice": lambda key: f"/practice/{key.replace('_', '-')}/",
    }

    present: set[str] = set()
    for target in targets(producers):
        kind, key = target["kind"], target["key"]
        if kind == "subregion" or kind == "state":
            continue  # needs the register / state-name map; covered below
        builder = expected.get(kind)
        if builder is None:
            continue
        route = builder(key)
        present.add(route)
        if route not in routes:
            errors.append(
                f"{kind} {key} has {target['count']} published producer(s) but "
                f"no page was built at {route}"
            )

    # The other direction: a built taxonomy page with no producers on it. The
    # page's own rendered rows are the evidence, which also catches a page that
    # was built from a stale membership set.
    for path in pages:
        route = _route_of(path, root)
        if not re.match(r"^/(region|variety|practice)/[^/]+/$", route):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not _ENTRY_ROW.search(text):
            errors.append(f"{route} was built but renders no producer rows")
    stats["taxonomy_pages"] = sum(
        1
        for route in routes
        if re.match(r"^/(region|variety|practice|[a-z-]+)/[^/]*/?$", route)
    )

    # ── 5. The sitemap lists only built pages ─────────────────────────────
    sitemap = root / "sitemap.xml"
    if sitemap.is_file():
        locations = re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8"))
        stats["sitemap"] = len(locations)
        for location in locations:
            route = re.sub(r"^https?://[^/]+", "", location)
            if not _resolves(route, root):
                errors.append(f"sitemap.xml lists {route}, which is not a built page")
    else:
        errors.append("sitemap.xml was not built")

    return errors, stats


# =============================================================================
# Self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    import tempfile

    errors: list[str] = []
    global DIST
    original = DIST

    try:
        with tempfile.TemporaryDirectory() as tmp:
            DIST = Path(tmp)
            (DIST / "region" / "alpha").mkdir(parents=True)
            (DIST / "index.html").write_text(
                '<a href="/region/alpha/">Alpha</a>', encoding="utf-8"
            )
            (DIST / "region" / "alpha" / "index.html").write_text(
                '<li class="entry">x</li>', encoding="utf-8"
            )

            if not _resolves("/region/alpha/"):
                errors.append("selftest: a real page was reported as unresolvable")
            if _resolves("/region/ghost/"):
                errors.append("selftest: a missing page was reported as resolvable")
            if not _resolves("/"):
                errors.append("selftest: the root route was reported as unresolvable")

            if _route_of(DIST / "region" / "alpha" / "index.html") != "/region/alpha/":
                errors.append("selftest: _route_of mangled a directory route")
            if _route_of(DIST / "index.html") != "/":
                errors.append("selftest: _route_of mangled the root route")

            # A file route, not a directory route.
            (DIST / "sitemap.xml").write_text("<urlset/>", encoding="utf-8")
            if not _resolves("/sitemap.xml"):
                errors.append("selftest: a file route was reported as unresolvable")

            # External forms must be skipped, never resolved.
            for href in ("https://example.com/x", "mailto:a@b.c", "#main", "//cdn/x"):
                if not _EXTERNAL.match(href):
                    errors.append(f"selftest: {href!r} was not treated as external")
    finally:
        DIST = original

    errors.extend(_selftest_end_to_end())
    return errors


def _fixture_site(root: Path, *, dead_link: bool = False, empty_page: bool = False) -> None:
    """The smallest tree `check()` accepts, optionally with one defect."""
    (root / "producer" / "alpha").mkdir(parents=True)
    (root / "region" / "one").mkdir(parents=True)

    homepage = '<a href="/region/one/">One</a> <a href="/producer/alpha/">Alpha</a>'
    if dead_link:
        homepage += ' <a href="/region/ghost/">Ghost</a>'
    (root / "index.html").write_text(homepage, encoding="utf-8")
    (root / "producer" / "alpha" / "index.html").write_text("<h1>Alpha</h1>", encoding="utf-8")
    (root / "region" / "one" / "index.html").write_text(
        "<h1>One</h1>" if empty_page else '<li class="entry">Alpha</li>',
        encoding="utf-8",
    )
    (root / "sitemap.xml").write_text(
        "<urlset><loc>https://x/</loc><loc>https://x/region/one/</loc>"
        "<loc>https://x/producer/alpha/</loc></urlset>",
        encoding="utf-8",
    )


def _selftest_end_to_end() -> list[str]:
    """`check()` itself, against fixture trees.

    The helpers above are the easy half. THIS is the half that matters: a link
    check whose dead-link detection is never exercised is a check that passes
    because it found nothing to look at.
    """
    import tempfile

    errors: list[str] = []
    producers = [{"slug": "alpha"}]

    scenarios: list[tuple[str, dict[str, bool], bool]] = [
        ("a clean fixture site", {}, False),
        ("a link to a page that does not exist", {"dead_link": True}, True),
        ("a taxonomy page with no producer rows", {"empty_page": True}, True),
    ]

    for label, kwargs, should_fail in scenarios:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dist"
            root.mkdir()
            _fixture_site(root, **kwargs)
            json_path = Path(tmp) / "producers.json"
            json_path.write_text(json.dumps(producers), encoding="utf-8")

            found, _ = check(root, json_path, Path(tmp) / "nostaging", {})
            if should_fail and not found:
                errors.append(f"selftest: {label} was NOT caught")
            if not should_fail and found:
                errors.append(f"selftest: a clean fixture site was rejected: {found}")

    # A producer in the JSON with no page, and a page with no JSON row.
    for label, rows, extra_page in [
        ("a producers.json slug with no page", [{"slug": "alpha"}, {"slug": "beta"}], False),
        ("a producer page missing from producers.json", [], False),
    ]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dist"
            root.mkdir()
            _fixture_site(root)
            json_path = Path(tmp) / "producers.json"
            json_path.write_text(json.dumps(rows), encoding="utf-8")
            found, _ = check(root, json_path, Path(tmp) / "nostaging", {})
            if not found:
                errors.append(f"selftest: {label} was NOT caught")

    # A page linking to a slug still sitting in _staging.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        root.mkdir()
        _fixture_site(root)
        (root / "producer" / "draft").mkdir()
        (root / "producer" / "draft" / "index.html").write_text("x", encoding="utf-8")
        (root / "index.html").write_text(
            '<a href="/region/one/">One</a> <a href="/producer/alpha/">Alpha</a>'
            ' <a href="/producer/draft/">Draft</a>',
            encoding="utf-8",
        )
        staging = Path(tmp) / "_staging"
        staging.mkdir()
        (staging / "draft.mdx").write_text("---\nname: Draft\n---\n", encoding="utf-8")
        json_path = Path(tmp) / "producers.json"
        json_path.write_text(json.dumps(producers), encoding="utf-8")

        found, _ = check(root, json_path, staging, {})
        if not any("still a draft" in error for error in found):
            errors.append("selftest: a link to a _staging draft was NOT caught")

    # A pending route that has started resolving must be reported, so the list
    # shrinks when a gate ships instead of quietly permitting a live route.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        root.mkdir()
        _fixture_site(root)
        (root / "methodology").mkdir()
        (root / "methodology" / "index.html").write_text("x", encoding="utf-8")
        json_path = Path(tmp) / "producers.json"
        json_path.write_text(json.dumps(producers), encoding="utf-8")

        found, _ = check(root, json_path, Path(tmp) / "nostaging", {"/methodology/": "Gate 10"})
        if not any("still listed as pending" in error for error in found):
            errors.append("selftest: a pending route that now resolves was NOT reported")

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print("VALIDATE 5 FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    real, stats = check()

    for route, gate in sorted(PENDING_ROUTES.items()):
        print(f"  pending: {route} — owned by {gate}, not built yet")

    if real:
        print("VALIDATE 5 FAIL")
        for error in real:
            print(f"  {error}")
        return 1

    print(
        f"VALIDATE 5 PASS — selftest ok; {stats.get('hrefs', 0)} internal href(s) "
        f"across {stats.get('pages', 0)} page(s) all resolve, "
        f"{stats.get('producers', 0)} producer page(s) match producers.json, "
        f"{stats.get('sitemap', 0)} sitemap entries all built, "
        f"{stats.get('pending', 0)} route(s) pending a later gate"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
