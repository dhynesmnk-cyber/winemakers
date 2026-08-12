"""jsonld_validator.py — `/validate` check 18, structural JSON-LD. GATE 10.

From `.claude/commands/validate.md`:

    18. JSON-LD structural validation — `Organization`, `WebSite`,
        `LocalBusiness`, `BreadcrumbList`, `FAQPage`, `ItemList`,
        `DefinedTermSet`, `DefinedTerm` across every page type.

OFFLINE, as the gate requires. No network call, no Google Rich Results request,
no vendored schema.org vocabulary. It reads `site/dist`, so `npm run build`
(check 4) must have run first — the thing under test is the markup a crawler
receives, and a builder that is correct in TypeScript but never reaches a page
has not shipped.

── What this checks that a schema linter would not ───────────────────────────

A generic validator answers "is this well-formed schema.org?". That is the
cheap half, and it is here: required keys per type, absolute URLs, consecutive
`position` values, `@id` references that resolve.

The half worth having is the AGREEMENT CHECK. `data/jsonld.ts` is written to the
rule that nothing is asserted in structured data that the page does not show,
because a field a reader cannot see is a claim nobody proofreads. That rule is
mechanised here by reading both:

- a `FAQPage` must carry exactly the question count the page renders, and a page
  with no FAQ section must carry no `FAQPage`;
- a `BreadcrumbList`'s names must be the visible crumb trail's labels, in order;
- an `ItemList` on a producer listing must count the rows the page lists;
- a `LocalBusiness`'s `url` must be the page it is on.

Structured data that drifts from its page is the failure mode this markup has;
it does not announce itself, and it is the reason the honesty rule needs a
mechanism here rather than a convention.

── The honesty rule, mechanised ──────────────────────────────────────────────

`BANNED_KEYS` fails the build on `aggregateRating`, `review`, `priceRange` and
`openingHours` anywhere in the graph. Nobody on this project has visited these
cellar doors or tasted these wines (CLAUDE.md rule 6), so there are no ratings
and no reviews to report; `priceRange` would be a guess; and `openingHours` in
schema.org's grammar would be invented structure over `cellar_door_hours`, which
is a freeform display string by schema design.

These are the four fields a well-meaning later edit adds because a rich-results
guide recommends them. The check exists so that edit fails loudly at the gate
rather than shipping a fabricated rating.

── `Winery` is refused here too ──────────────────────────────────────────────

TRD.md §2, decided 2026-08-06 and declined for v1 with sign-off: producer pages
emit generic `LocalBusiness`, never `Winery`, because a large share of this
dataset is garagiste, negociant and label-only producers with no premises a
reader can visit. CLAUDE.md Gate 10 requires any move beyond `LocalBusiness` to
be recorded as a dated TRD.md exception. `UNKNOWN_TYPE_IS_ERROR` makes that
enforceable: a new `@type` fails until it is added here deliberately, which is a
prompt to go and write the exception first.
"""

from __future__ import annotations

import html as html_module
import json
import re
import tempfile
from pathlib import Path

from ..config import SITE_DIST_DIR, SITE_URL

DIST = SITE_DIST_DIR

_LD_BLOCK = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I
)
_CRUMB_NAV = re.compile(r'<nav class="crumbs"[^>]*>(.*?)</nav>', re.S | re.I)
_CRUMB_ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_FAQ_PAIR = re.compile(r'class="faq__pair"')
_ENTRY_ROW = re.compile(r'<li class="entry"')
_POST_H1 = re.compile(r'<h1 class="post-head__title"[^>]*>(.*?)</h1>', re.S)
_POST_TIME = re.compile(r'<time datetime="(\d{4}-\d{2}-\d{2})"')
_POST_SOURCE = re.compile(r'<li[^>]*>\s*<a href="[^"]+" rel="noopener"[^>]*>')
_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]+)"', re.I)

#: Every `@type` this site is allowed to emit. See the docstring on `Winery`.
REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "Organization": ("@id", "name", "url"),
    "WebSite": ("@id", "name", "url", "publisher"),
    "BreadcrumbList": ("itemListElement",),
    "ItemList": ("name", "numberOfItems", "itemListOrder", "itemListElement"),
    "LocalBusiness": ("@id", "name", "description", "url", "address"),
    "FAQPage": ("@id", "mainEntity"),
    "DefinedTermSet": ("@id", "name", "url", "hasDefinedTerm"),
    "DefinedTerm": ("@id", "name", "description", "url", "inDefinedTermSet"),
    # Gate 11, under the dated TRD.md §2.5 exception of 2026-08-13 with
    # sign-off. The FIRST widening of this set since Gate 10 closed it, and the
    # mechanism worked exactly as designed: the build failed here until the
    # exception was written. `Blog` on the index is deliberately NOT taken — the
    # index is a listing and carries `ItemList`, like every other listing here.
    "BlogPosting": (
        "@id", "headline", "description", "url", "datePublished", "author", "publisher",
    ),
}

#: Nested types, allowed inside a parent but never as a top-level graph node.
NESTED_TYPES = {
    "ListItem",
    # `citation` entries on a BlogPosting. A source is a CreativeWork the post
    # points at, never a top-level node of its own.
    "CreativeWork",
    "PostalAddress",
    "GeoCoordinates",
    "Question",
    "Answer",
    "DefinedTerm",
}

#: CLAUDE.md rule 6, in the graph. See the docstring.
BANNED_KEYS = {
    "aggregateRating": "no ratings exist on this site; nobody here has tasted anything",
    "review": "no reviews exist on this site; nobody here has visited anything",
    "reviewCount": "implies reviews this site does not have",
    "priceRange": "the guide publishes no bottle prices; a tasting fee is not a price range",
    "openingHours": "cellar_door_hours is a freeform display string, never a parsed grid",
    "openingHoursSpecification": "same as openingHours",
    "starRating": "there are no ratings on this site",
}

#: The four routes whose page type dictates what must be present.
PRODUCER_PREFIX = "/producer/"
GLOSSARY_INDEX = "/glossary/"
GLOSSARY_PREFIX = "/glossary/"


def _pages(root: Path) -> list[Path]:
    return sorted(root.rglob("index.html"))


def _route_of(path: Path, root: Path) -> str:
    rel = path.relative_to(root).parent.as_posix()
    return "/" if rel == "." else f"/{rel}/"


def _is_listing(route: str) -> bool:
    """A page whose purpose is listing producers or listing what links to them.

    Deliberately mirrors check 17's `_is_aggregation` in spirit rather than
    importing it: that one answers "is this a route TO a producer", which
    excludes the producer pages themselves and the hubs. This one answers "does
    this page render a list that an `ItemList` should describe", which includes
    `/region/` and `/compare/` and excludes the homepage, whose producer rows
    are a fixed slice rather than a listing (TRD.md §4.6).
    """
    if route == "/":
        return False
    if route.startswith(PRODUCER_PREFIX):
        return False
    if route.startswith(("/glossary/", "/methodology")):
        return False
    parts = [p for p in route.split("/") if p]
    if not parts:
        return False
    if parts[0] in {"producers", "region", "variety", "practice", "compare"}:
        return True
    # State routes are bare single-segment slugs plus their pager.
    return len(parts) == 1 or (len(parts) == 3 and parts[1] == "page")


def _visible_crumbs(html: str) -> list[str] | None:
    """The crumb labels a reader sees, in order. `None` when there is no trail.

    Tags are stripped BEFORE the text is read, and entities are unescaped after.
    Both matter: the trail's last crumb is wrapped in a `<span>` and its links in
    an `<a>`, and a name carrying an apostrophe — Nero d'Avola — reaches the page
    as `&#39;` and would never compare equal to the JSON-LD's literal.

    This is the lesson of the 2026-08-12 dateline scan, which reported zero
    because its regex could not see the markup it was checking. Here the same
    defect went the other way and over-reported, which is the safer direction
    but the same underlying mistake.
    """
    nav = _CRUMB_NAV.search(html)
    if not nav:
        return None
    labels = []
    for item in _CRUMB_ITEM.findall(nav.group(1)):
        text = html_module.unescape(_TAG.sub("", item))
        labels.append(" ".join(text.split()))
    return labels


def _nodes(html: str, route: str, errors: list[str]) -> list[dict]:
    """Every top-level graph node on the page, with the parse errors reported."""
    out: list[dict] = []
    for index, block in enumerate(_LD_BLOCK.findall(html)):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError as exc:
            errors.append(f"{route} block {index}: JSON-LD does not parse — {exc}")
            continue
        context = payload.get("@context")
        if context != "https://schema.org":
            errors.append(
                f"{route} block {index}: @context is {context!r}, expected "
                "'https://schema.org'"
            )
        graph = payload.get("@graph")
        if not isinstance(graph, list) or not graph:
            errors.append(
                f"{route} block {index}: @graph is missing or empty; every block "
                "on this site is a graph, so a bare node is a builder that "
                "bypassed data/jsonld.ts"
            )
            continue
        out.extend(node for node in graph if isinstance(node, dict))
    return out


def _walk(node, visit) -> None:
    """Every dict in a node tree, parents before children."""
    if isinstance(node, dict):
        visit(node)
        for value in node.values():
            _walk(value, visit)
    elif isinstance(node, list):
        for item in node:
            _walk(item, visit)


def _is_absolute(value) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _check_positions(items: list, label: str, route: str, errors: list[str]) -> None:
    """`position` must run consecutively from wherever the list starts.

    A paginated series starts at an offset, so the first value is not asserted
    to be 1; the gaps are what matter. A list with a gap tells a crawler that
    entries are missing between two it can see.
    """
    positions = []
    for item in items:
        if not isinstance(item, dict):
            errors.append(f"{route}: {label} holds a non-object entry")
            return
        if item.get("@type") != "ListItem":
            errors.append(
                f"{route}: {label} entry is @type {item.get('@type')!r}, expected 'ListItem'"
            )
            return
        position = item.get("position")
        if not isinstance(position, int):
            errors.append(f"{route}: {label} entry has no integer position")
            return
        positions.append(position)
        if not item.get("name"):
            errors.append(f"{route}: {label} entry at position {position} has no name")
        target = item.get("url") or item.get("item")
        if not _is_absolute(target):
            errors.append(
                f"{route}: {label} entry at position {position} has no absolute "
                f"url/item (got {target!r})"
            )
    if positions and positions != list(range(positions[0], positions[0] + len(positions))):
        errors.append(
            f"{route}: {label} positions are not consecutive — {positions[:8]}"
        )


def _declared_ids(root: Path, pages: list[Path]) -> set[str]:
    """Every `@id` the build declares anywhere, for resolving references.

    Resolution is SITE-WIDE rather than per page, because a cross-page reference
    is the point of an `@id`: a glossary term page says it belongs to the
    glossary's `DefinedTermSet`, which is declared once on `/glossary/` rather
    than copied onto all 123 term pages. Requiring the target on the same page
    would force exactly that duplication.

    Site-wide still catches what matters — a reference to an `@id` nothing
    declares is a typo or a node that was removed, and that is what fails.
    """
    ids: set[str] = set()
    for page in pages:
        for block in _LD_BLOCK.findall(page.read_text(encoding="utf-8")):
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue  # reported by the main pass

            def collect(obj: dict) -> None:
                # A node DECLARES an @id; a reference is a lone `{"@id": ...}`.
                if len(obj) > 1 and isinstance(obj.get("@id"), str):
                    ids.add(obj["@id"])

            _walk(payload.get("@graph", []), collect)
    return ids


def _strip_tags(markup: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", markup).split())


def _check_blog_posting(
    nodes: list[dict],
    html: str,
    route: str,
    page_url: str | None,
    errors: list[str],
) -> None:
    """The agreement half for `/blog/[slug]/`. Gate 11.

    A generic linter would answer "is this well-formed BlogPosting?", which is
    the cheap half. `data/jsonld.ts` is written to the rule that nothing is
    asserted in structured data that the page does not show, so this reads both.

    The `citation` rule is the one worth having: `sources` is required on every
    post (SCHEMA.md §9.2) and printed at its foot, so a post cannot cite one
    thing to a reader and three to a crawler.
    """
    is_post = (
        route.startswith("/blog/") and route != "/blog/" and "/page/" not in route
    )

    if is_post and not nodes:
        errors.append(
            f"{route}: a post page with no BlogPosting. Every post carries one "
            "(TRD.md §2.5, 2026-08-13)."
        )
    if nodes and not is_post:
        errors.append(
            f"{route}: a BlogPosting on a page that is not a post. The journal "
            "index is a listing and carries ItemList, not Blog."
        )

    heading = _POST_H1.search(html)
    rendered_title = _strip_tags(heading.group(1)) if heading else None
    rendered_dates = _POST_TIME.findall(html)
    rendered_sources = len(_POST_SOURCE.findall(html))

    for node in nodes:
        if rendered_title and node.get("headline") != rendered_title:
            errors.append(
                f"{route}: BlogPosting headline {node.get('headline')!r} is not the "
                f"rendered <h1> {rendered_title!r}"
            )

        published = node.get("datePublished")
        if rendered_dates and published not in rendered_dates:
            errors.append(
                f"{route}: BlogPosting datePublished {published!r} is not among the "
                f"dates the page renders {rendered_dates}"
            )

        modified = node.get("dateModified")
        if modified is not None and modified not in rendered_dates:
            errors.append(
                f"{route}: BlogPosting dateModified {modified!r} is not rendered on "
                f"the page. An amendment date nobody can see is a claim about "
                f"editorial process that the page does not make."
            )

        citations = node.get("citation") or []
        if rendered_sources and len(citations) != rendered_sources:
            errors.append(
                f"{route}: BlogPosting cites {len(citations)} source(s) against "
                f"{rendered_sources} printed on the page. A post cannot cite one "
                f"thing to a reader and another to a crawler (SCHEMA.md §9.2)."
            )
        if not citations:
            errors.append(
                f"{route}: BlogPosting carries no citation. `sources` is required "
                f"on every post and this is its machine-readable half."
            )

        if page_url and node.get("url") != page_url:
            errors.append(
                f"{route}: BlogPosting url {node.get('url')!r} is not the page's "
                f"canonical {page_url!r}"
            )


def check(root: Path = DIST) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats: dict[str, int] = {"pages": 0, "nodes": 0}
    type_counts: dict[str, int] = {}

    pages = _pages(root)
    if not pages:
        return [f"no built pages under {root} — run `npm run build` first"], stats

    site_ids = _declared_ids(root, pages)

    for page in pages:
        html = page.read_text(encoding="utf-8")
        route = _route_of(page, root)
        stats["pages"] += 1

        nodes = _nodes(html, route, errors)
        stats["nodes"] += len(nodes)

        declared_ids = set()
        by_type: dict[str, list[dict]] = {}

        for node in nodes:
            node_type = node.get("@type")
            if not isinstance(node_type, str):
                errors.append(f"{route}: a graph node has no string @type")
                continue
            if node_type in NESTED_TYPES and node_type not in REQUIRED_KEYS:
                errors.append(
                    f"{route}: {node_type!r} is a nested type and must not be a "
                    "top-level graph node"
                )
                continue
            if node_type not in REQUIRED_KEYS:
                errors.append(
                    f"{route}: @type {node_type!r} is not in this site's allowed set. "
                    "Any move beyond LocalBusiness (e.g. Winery) must first be "
                    "recorded as a dated TRD.md exception with explicit sign-off "
                    "(CLAUDE.md Gate 10)."
                )
                continue

            type_counts[node_type] = type_counts.get(node_type, 0) + 1
            by_type.setdefault(node_type, []).append(node)
            if isinstance(node.get("@id"), str):
                declared_ids.add(node["@id"])

            for key in REQUIRED_KEYS[node_type]:
                if node.get(key) in (None, "", [], {}):
                    errors.append(f"{route}: {node_type} is missing required key {key!r}")

        # Whole-tree rules: banned keys, null values, unresolved @id references.
        references: list[str] = []

        def visit(obj: dict) -> None:
            for key, value in obj.items():
                if key in BANNED_KEYS:
                    errors.append(
                        f"{route}: {key!r} is banned in this site's structured data "
                        f"— {BANNED_KEYS[key]} (CLAUDE.md rule 6)"
                    )
                if value is None:
                    errors.append(
                        f"{route}: {key!r} is null. Absent is absent — a null in "
                        "structured data reads as a claim that the value is known "
                        "to be nothing (data/jsonld.ts, omitEmpty)"
                    )
            if set(obj.keys()) == {"@id"} and isinstance(obj["@id"], str):
                references.append(obj["@id"])

        for node in nodes:
            _walk(node, visit)

        for reference in references:
            if reference not in declared_ids and reference not in site_ids:
                errors.append(
                    f"{route}: reference to @id {reference!r} resolves to no node "
                    "anywhere in the build"
                )

        # ── Every page carries the publisher and the site ──────────────────
        for required in ("Organization", "WebSite"):
            if required not in by_type:
                errors.append(f"{route}: no {required} node")

        canonical = _CANONICAL.search(html)
        page_url = canonical.group(1) if canonical else None

        # ── BreadcrumbList must be the visible trail ───────────────────────
        visible = _visible_crumbs(html)
        crumb_nodes = by_type.get("BreadcrumbList", [])
        if visible is not None and not crumb_nodes:
            errors.append(
                f"{route}: the page renders a crumb trail but emits no BreadcrumbList"
            )
        for node in crumb_nodes:
            items = node.get("itemListElement") or []
            _check_positions(items, "BreadcrumbList", route, errors)
            names = [item.get("name") for item in items if isinstance(item, dict)]
            if visible is not None and names != visible:
                errors.append(
                    f"{route}: BreadcrumbList names {names} do not match the visible "
                    f"trail {visible}"
                )

        # ── ItemList on the listing pages ──────────────────────────────────
        list_nodes = by_type.get("ItemList", [])
        if _is_listing(route) and not list_nodes:
            errors.append(f"{route}: a listing page with no ItemList (UX.md §488)")
        rows = len(_ENTRY_ROW.findall(html))
        for node in list_nodes:
            items = node.get("itemListElement") or []
            _check_positions(items, "ItemList", route, errors)
            total = node.get("numberOfItems")
            if not isinstance(total, int) or total < len(items):
                errors.append(
                    f"{route}: ItemList numberOfItems {total!r} is below the "
                    f"{len(items)} entries it lists"
                )
            if rows and len(items) != rows:
                errors.append(
                    f"{route}: ItemList holds {len(items)} entries but the page "
                    f"renders {rows} producer rows"
                )

        # ── FAQPage must match the rendered section exactly ────────────────
        rendered_pairs = len(_FAQ_PAIR.findall(html))
        faq_nodes = by_type.get("FAQPage", [])
        if rendered_pairs and not faq_nodes:
            errors.append(
                f"{route}: the page renders {rendered_pairs} FAQ pair(s) and emits "
                "no FAQPage"
            )
        if faq_nodes and not rendered_pairs:
            errors.append(
                f"{route}: a FAQPage is emitted for a page that renders no FAQ "
                "section. Structured data for content that is not on the page is "
                "the one thing this markup is penalised for."
            )
        for node in faq_nodes:
            questions = node.get("mainEntity") or []
            if len(questions) != rendered_pairs:
                errors.append(
                    f"{route}: FAQPage carries {len(questions)} question(s) against "
                    f"{rendered_pairs} rendered on the page"
                )
            for question in questions:
                if not isinstance(question, dict) or question.get("@type") != "Question":
                    errors.append(f"{route}: FAQPage mainEntity holds a non-Question")
                    continue
                if not question.get("name"):
                    errors.append(f"{route}: a Question has no name")
                answer = question.get("acceptedAnswer")
                if not isinstance(answer, dict) or not answer.get("text"):
                    errors.append(
                        f"{route}: Question {question.get('name')!r} has no answer text"
                    )

        # ── BlogPosting must agree with the post it sits on (Gate 11) ──────
        _check_blog_posting(
            by_type.get("BlogPosting", []), html, route, page_url, errors
        )

        # ── Producer pages ─────────────────────────────────────────────────
        if route.startswith(PRODUCER_PREFIX):
            business = by_type.get("LocalBusiness", [])
            if not business:
                errors.append(f"{route}: a producer page with no LocalBusiness")
            for node in business:
                if page_url and node.get("url") != page_url:
                    errors.append(
                        f"{route}: LocalBusiness url {node.get('url')!r} is not the "
                        f"page's canonical {page_url!r}"
                    )
                address = node.get("address")
                if not isinstance(address, dict) or address.get("@type") != "PostalAddress":
                    errors.append(f"{route}: LocalBusiness address is not a PostalAddress")
                elif address.get("addressCountry") != "AU":
                    errors.append(
                        f"{route}: LocalBusiness addressCountry is "
                        f"{address.get('addressCountry')!r}, expected 'AU'"
                    )
                geo = node.get("geo")
                if geo is not None:
                    if not isinstance(geo, dict) or geo.get("@type") != "GeoCoordinates":
                        errors.append(f"{route}: LocalBusiness geo is not GeoCoordinates")
                    elif not (
                        isinstance(geo.get("latitude"), (int, float))
                        and isinstance(geo.get("longitude"), (int, float))
                    ):
                        errors.append(
                            f"{route}: LocalBusiness geo has a non-numeric coordinate. "
                            "Both or neither — a half-coordinate is not a place."
                        )
                founding = node.get("foundingDate")
                if founding is not None and not re.fullmatch(r"\d{4}", str(founding)):
                    errors.append(
                        f"{route}: foundingDate {founding!r} is not a bare four-digit "
                        "year. The guide knows the year and inventing a month would "
                        "be inventing a fact."
                    )

        # ── Glossary ───────────────────────────────────────────────────────
        if route == GLOSSARY_INDEX:
            if "DefinedTermSet" not in by_type:
                errors.append(f"{route}: the glossary index emits no DefinedTermSet")
            for node in by_type.get("DefinedTermSet", []):
                terms = node.get("hasDefinedTerm") or []
                for term in terms:
                    if not isinstance(term, dict) or term.get("@type") != "DefinedTerm":
                        errors.append(f"{route}: hasDefinedTerm holds a non-DefinedTerm")
                        break
                    if not term.get("name") or not _is_absolute(term.get("url")):
                        errors.append(
                            f"{route}: a DefinedTerm in the set has no name or no "
                            "absolute url"
                        )
                        break
        elif route.startswith(GLOSSARY_PREFIX):
            terms = by_type.get("DefinedTerm", [])
            if not terms:
                errors.append(f"{route}: a glossary term page with no DefinedTerm")
            for node in terms:
                parent = node.get("inDefinedTermSet")
                if not isinstance(parent, dict) or not isinstance(parent.get("@id"), str):
                    errors.append(
                        f"{route}: DefinedTerm does not reference its DefinedTermSet"
                    )

    stats.update({f"type:{name}": count for name, count in type_counts.items()})
    return errors, stats


# ═══════════════════════════════════════════════════════════════════════════
# Self-test — the fixtures the gate's done-condition names
# ═══════════════════════════════════════════════════════════════════════════

_HEAD = (
    '<link rel="canonical" href="{url}"/>'
    '<script type="application/ld+json">{ld}</script>'
)


def _graph(*nodes) -> str:
    return json.dumps({"@context": "https://schema.org", "@graph": list(nodes)})


def _org() -> dict:
    return {
        "@type": "Organization",
        "@id": f"{SITE_URL}/#organization",
        "name": "winelister",
        "url": f"{SITE_URL}/",
    }


def _site() -> dict:
    return {
        "@type": "WebSite",
        "@id": f"{SITE_URL}/#website",
        "name": "winelister",
        "url": f"{SITE_URL}/",
        "publisher": {"@id": f"{SITE_URL}/#organization"},
    }


def _business(url: str, **overrides) -> dict:
    node = {
        "@type": "LocalBusiness",
        "@id": f"{url}#business",
        "name": "Fixture Wines",
        "description": "A fixture.",
        "url": url,
        "address": {"@type": "PostalAddress", "addressRegion": "SA", "addressCountry": "AU"},
    }
    node.update(overrides)
    return node


def _crumbs(url: str, labels: list[str]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": label,
                "item": f"{SITE_URL}/" if index == 0 else url,
            }
            for index, label in enumerate(labels)
        ],
    }


def _crumb_html(labels: list[str]) -> str:
    items = "".join(f"<li><span>{label}</span></li>" for label in labels)
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>'


def _write(root: Path, route: str, head: str, body: str = "") -> None:
    target = root / route.strip("/") / "index.html" if route != "/" else root / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"<html><head>{head}</head><body>{body}</body></html>", "utf-8")


def _post(url: str, *, sources: int = 2) -> dict:
    """A BlogPosting node. Gate 11."""
    return {
        "@type": "BlogPosting",
        "@id": f"{url}#post",
        "headline": "A fixture post",
        "description": "A summary.",
        "url": url,
        "datePublished": "2026-08-13",
        "author": {"@id": f"{SITE_URL}/#organization"},
        "publisher": {"@id": f"{SITE_URL}/#organization"},
        "citation": [
            {"@type": "CreativeWork", "name": f"Source {n}", "url": f"https://example.com/{n}"}
            for n in range(sources)
        ],
    }


def _post_html(labels: list[str], *, sources: int = 2) -> str:
    """The rendered half every BlogPosting agreement rule is checked against."""
    printed = "".join(
        f'<li><a href="https://example.com/{n}" rel="noopener">Source {n}</a></li>'
        for n in range(sources)
    )
    return (
        _crumb_html(labels)
        + '<h1 class="post-head__title">A fixture post</h1>'
        + '<p class="post-head__dateline mono mono-caps">Australia · '
        + '<time datetime="2026-08-13">13 August 2026</time></p>'
        + f'<ul class="post-sources__list mono">{printed}</ul>'
    )


def _post_fixture(root: Path, *, mutate=None) -> None:
    """A minimal but VALID post page. Gate 11.

    A separate fixture from `_fixture`, because a post is a different page
    type: it carries a BlogPosting and no LocalBusiness, and every rule it is
    checked against is about agreement with what the page prints.
    """
    url = f"{SITE_URL}/blog/fixture/"
    labels = ["Home", "Journal", "A fixture post"]

    nodes = [_org(), _site(), _post(url), _crumbs(url, labels)]
    body = _post_html(labels)

    if mutate:
        nodes, body = mutate(nodes, body)

    _write(root, "/blog/fixture/", _HEAD.format(url=url, ld=_graph(*nodes)), body)


def _fixture(root: Path, *, mutate=None) -> None:
    """A minimal but VALID dist. `mutate` breaks exactly one thing."""
    producer_url = f"{SITE_URL}/producer/fixture/"
    labels = ["Home", "Fixture Wines"]

    business = _business(producer_url)
    crumbs = _crumbs(producer_url, labels)
    faq = {
        "@type": "FAQPage",
        "@id": f"{producer_url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "Who owns it?",
                "acceptedAnswer": {"@type": "Answer", "text": "Nobody has published it."},
            }
        ],
    }
    nodes = [_org(), _site(), business, crumbs, faq]
    body = _crumb_html(labels) + '<div class="faq__pair"><h3>Who owns it?</h3></div>'

    if mutate:
        nodes, body = mutate(nodes, body)

    _write(
        root,
        "/producer/fixture/",
        _HEAD.format(url=producer_url, ld=_graph(*nodes)),
        body,
    )


def _selftest() -> list[str]:
    """Every rule this check exists for, proved by deliberate violation.

    A check whose fixtures are all valid asserts only that it runs. Each case
    below breaks one thing and requires the error to NAME that thing — an error
    is not evidence if it fires for an unrelated reason.
    """
    errors: list[str] = []

    def run(mutate=None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dist"
            _fixture(root, mutate=mutate)
            found, _ = check(root)
            return found

    clean = run()
    if clean:
        errors.append(f"selftest: the CLEAN fixture failed — {clean[:3]}")

    cases: list[tuple[str, object, str]] = [
        (
            "a fabricated rating",
            lambda n, b: ([*n[:2], {**n[2], "aggregateRating": {"ratingValue": 5}}, *n[3:]], b),
            "aggregateRating",
        ),
        (
            "a fabricated review",
            lambda n, b: ([*n[:2], {**n[2], "review": {"reviewBody": "lovely"}}, *n[3:]], b),
            "review",
        ),
        (
            "a guessed price range",
            lambda n, b: ([*n[:2], {**n[2], "priceRange": "$$"}, *n[3:]], b),
            "priceRange",
        ),
        (
            "parsed opening hours",
            lambda n, b: ([*n[:2], {**n[2], "openingHours": "Mo-Fr 10:00-17:00"}, *n[3:]], b),
            "openingHours",
        ),
        (
            "Winery instead of LocalBusiness",
            lambda n, b: ([*n[:2], {**n[2], "@type": "Winery"}, *n[3:]], b),
            "TRD.md exception",
        ),
        (
            "a null value",
            lambda n, b: ([*n[:2], {**n[2], "foundingDate": None}, *n[3:]], b),
            "null",
        ),
        (
            "a missing required key",
            lambda n, b: (
                [*n[:2], {k: v for k, v in n[2].items() if k != "address"}, *n[3:]],
                b,
            ),
            "missing required key",
        ),
        (
            "an unresolved @id reference",
            lambda n, b: (
                [n[0], {**n[1], "publisher": {"@id": f"{SITE_URL}/#nobody"}}, *n[2:]],
                b,
            ),
            "resolves to no node anywhere",
        ),
        (
            "a breadcrumb that disagrees with the visible trail",
            lambda n, b: (
                [*n[:3], _crumbs(f"{SITE_URL}/producer/fixture/", ["Home", "Wrong"]), n[4]],
                b,
            ),
            "do not match the visible trail",
        ),
        (
            "a gap in the breadcrumb positions",
            lambda n, b: (
                [
                    *n[:3],
                    {
                        **n[3],
                        "itemListElement": [
                            n[3]["itemListElement"][0],
                            {**n[3]["itemListElement"][1], "position": 5},
                        ],
                    },
                    n[4],
                ],
                b,
            ),
            "not consecutive",
        ),
        (
            "an FAQ count that disagrees with the page",
            lambda n, b: (n, b + '<div class="faq__pair"><h3>Second</h3></div>'),
            "against 2 rendered",
        ),
        (
            "an FAQPage on a page with no FAQ section",
            lambda n, b: (n, b.replace('<div class="faq__pair"><h3>Who owns it?</h3></div>', "")),
            "renders no FAQ section",
        ),
        (
            "a LocalBusiness url that is not its page",
            lambda n, b: ([*n[:2], {**n[2], "url": f"{SITE_URL}/producer/other/"}, *n[3:]], b),
            "is not the page's canonical",
        ),
        (
            "a half-coordinate",
            lambda n, b: (
                [
                    *n[:2],
                    {**n[2], "geo": {"@type": "GeoCoordinates", "latitude": -34.9}},
                    *n[3:],
                ],
                b,
            ),
            "half-coordinate is not a place",
        ),
        (
            "an invented founding month",
            lambda n, b: ([*n[:2], {**n[2], "foundingDate": "1981-06"}, *n[3:]], b),
            "four-digit year",
        ),
        (
            "a missing publisher node",
            lambda n, b: (n[1:], b),
            "no Organization node",
        ),
    ]

    # ── The blog cases — Gate 11 ───────────────────────────────────────────
    def run_post(mutate=None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dist"
            _post_fixture(root, mutate=mutate)
            found, _ = check(root)
            return found

    clean_post = run_post()
    if clean_post:
        errors.append(f"selftest: the CLEAN post fixture failed — {clean_post[:3]}")

    post_cases: list[tuple[str, object, str]] = [
        (
            "a headline that is not the rendered <h1>",
            lambda n, b: ([*n[:2], {**n[2], "headline": "Something else"}, *n[3:]], b),
            "is not the rendered <h1>",
        ),
        (
            "a datePublished the page does not print",
            lambda n, b: ([*n[:2], {**n[2], "datePublished": "2020-01-01"}, *n[3:]], b),
            "is not among the dates the page renders",
        ),
        (
            "a dateModified nobody can see",
            lambda n, b: ([*n[:2], {**n[2], "dateModified": "2027-01-01"}, *n[3:]], b),
            "is not rendered on",
        ),
        (
            "fewer citations than the page prints",
            lambda n, b: ([*n[:2], _post(f"{SITE_URL}/blog/fixture/", sources=1), *n[3:]], b),
            "against 2 printed on the page",
        ),
        (
            "no citation at all",
            lambda n, b: (
                [*n[:2], {k: v for k, v in n[2].items() if k != "citation"}, *n[3:]], b),
            "carries no citation",
        ),
        (
            "a url that is not the page",
            lambda n, b: ([*n[:2], {**n[2], "url": f"{SITE_URL}/blog/other/"}, *n[3:]], b),
            "is not the page's canonical",
        ),
        (
            "a post page with no BlogPosting",
            lambda n, b: ([n[0], n[1], n[3]], b),
            "a post page with no BlogPosting",
        ),
        (
            "Blog taken as a type on top of BlogPosting",
            lambda n, b: ([*n[:2], {**n[2], "@type": "Blog"}, *n[3:]], b),
            "not in this site's allowed set",
        ),
        (
            "a rating on a post",
            lambda n, b: ([*n[:2], {**n[2], "aggregateRating": {"ratingValue": 5}}, *n[3:]], b),
            "aggregateRating",
        ),
    ]

    for label, mutate, expected in post_cases:
        found = run_post(mutate)
        if not any(expected in error for error in found):
            errors.append(
                f"selftest: {label} was not caught by a message naming "
                f"{expected!r} (got {found[:2] or 'nothing'})"
            )

    for label, mutate, expected in cases:
        found = run(mutate)
        if not any(expected in error for error in found):
            errors.append(
                f"selftest: {label} was not caught by a message naming "
                f"{expected!r} (got {found[:2] or 'nothing'})"
            )

    # Two cases that break the block itself rather than a node inside it.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        _write(root, "/", '<script type="application/ld+json">{not json}</script>')
        found, _ = check(root)
        if not any("does not parse" in error for error in found):
            errors.append("selftest: unparseable JSON-LD was not caught")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "dist"
        _write(
            root,
            "/",
            '<script type="application/ld+json">'
            '{"@context":"https://example.com","@graph":[]}</script>',
        )
        found, _ = check(root)
        if not any("@context" in error for error in found):
            errors.append("selftest: a wrong @context was not caught")

    return errors


def main() -> int:
    problems = _selftest()
    if problems:
        print("VALIDATE 18 FAIL — selftest")
        for problem in problems:
            print(f"  {problem}")
        return 1

    errors, stats = check()

    if errors:
        print(f"VALIDATE 18 FAIL — {len(errors)} problem(s)")
        for error in errors[:40]:
            print(f"  {error}")
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more")
        return 1

    types = ", ".join(
        f"{key.split(':', 1)[1]} {value}"
        for key, value in sorted(stats.items())
        if key.startswith("type:")
    )
    print(
        f"VALIDATE 18 PASS — selftest ok; {stats['nodes']} JSON-LD node(s) across "
        f"{stats['pages']} page(s) structurally valid and in agreement with the "
        f"pages they describe ({types})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
