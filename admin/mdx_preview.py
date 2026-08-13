"""mdx_preview.py — the review pane's rendered preview. Gate 3.

UX.md §1.4: the preview renders the staged MDX **using the actual public
producer-page styles, by importing the same CSS the site ships**. Reviewing in a
different skin from what ships is how errors slip through, so nothing here
restates a rule from `global.css` or `tokens.css`. The document this module
builds links the built stylesheet out of `site/dist/` and is served into an
iframe, so the site's `body`, `html` and `:root` rules apply to the preview and
to nothing else on the admin screen.

── Why this renders the page rather than the file ────────────────────────────

The reviewer is deciding whether a page is fit to publish. A syntax-highlighted
MDX file does not answer that question: the fact row, the dateline, the appendix
and the provenance close are all assembled from the structured fields, and they
are most of what a reader sees. So this mirrors `pages/producer/[slug].astro`,
in the same order DESIGN.md §7 fixes: name, dateline, fact row, prose, plate,
FAQ, appendix, provenance.

── The two things read out of the site rather than duplicated ────────────────

1. **The stylesheet**, from the last `npm run build`. No build, no styles, and
   the preview says so plainly rather than rendering unstyled and looking
   broken.
2. **Astro's scoped-style attributes.** Astro compiles a component's `<style>`
   block to `[data-astro-cid-xxxx]` selectors. The hash is derived from the
   component's path and is stable between builds, so it is read off a built
   producer page and stamped back onto the matching elements here. Without it
   the scoped half of the page's styling silently would not apply.

── The honesty rule (CLAUDE.md rule 6) ───────────────────────────────────────

This module renders what the draft says and adds nothing. There is no synthetic
sample text, no placeholder tasting note, no filler where a field is empty.
Present-only display is the same rule the public page follows: a field the
producer does not state renders nothing at all.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin import schema  # noqa: E402
from admin.config import (  # noqa: E402
    PRACTICE_KEYS,
    ROOT,
    SITE_DIST_DIR,
)

ICON_PATHS_TS = ROOT / "site" / "src" / "icons" / "paths.ts"

#: DESIGN.md §6's size table, for the two contexts this preview renders.
_ICON_SIZE_FACT_ROW = 18
_ICON_SIZE_CHIP = 14


# =============================================================================
# 1. What is read out of the built site
# =============================================================================


def stylesheet_hrefs() -> list[str]:
    """The built stylesheets, as URLs under the admin's `/site-dist` mount."""
    astro_dir = SITE_DIST_DIR / "_astro"
    if not astro_dir.is_dir():
        return []
    return [f"/site-dist/_astro/{path.name}" for path in sorted(astro_dir.glob("*.css"))]


def _built_producer_page() -> str:
    """Any built producer page, as the donor for the scoped-style attributes."""
    for path in sorted((SITE_DIST_DIR / "producer").glob("*/index.html")):
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def _cid_for_class(built: str, class_name: str) -> str:
    """The `data-astro-cid-*` attribute on the built element with this class.

    Fails soft to an empty string: a preview missing a scoped margin is worth
    having, and a preview that raises because the site has not been built is
    not.
    """
    match = re.search(
        rf'<\w+[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"([^>]*)>', built
    )
    if not match:
        return ""
    cid = re.search(r"data-astro-cid-[a-z0-9]+", match.group(1))
    return f" {cid.group(0)}" if cid else ""


def _read_icon_paths() -> dict[str, list[str]]:
    """`ICON_PATHS` out of `paths.ts`. The glyph set is hand-authored TypeScript.

    Python cannot import it and the file loads without a build step by design
    (CONSTANTS-REQUIRED.md §1), so it is read as text — the same approach
    `schema_surfaces.py` takes to `glossary.ts`.
    """
    try:
        text = ICON_PATHS_TS.read_text(encoding="utf-8")
    except OSError:
        return {}
    block = text.split("export const ICON_PATHS", 1)[-1]
    paths: dict[str, list[str]] = {}
    # Bracket-depth scanned rather than matched to a closing line: the set mixes
    # one-line and multi-line entries, and a line-anchored pattern silently
    # swallows the entry after a one-liner.
    for match in re.finditer(r"^  (\w+): \[", block, re.MULTILINE):
        depth = 0
        for index in range(match.end() - 1, len(block)):
            if block[index] == "[":
                depth += 1
            elif block[index] == "]":
                depth -= 1
                if depth == 0:
                    paths[match.group(1)] = re.findall(
                        r'"([^"]+)"', block[match.end() : index]
                    )
                    break
    return paths


_ICON_PATHS = _read_icon_paths()


def _icon(key: str, size: int = _ICON_SIZE_FACT_ROW) -> str:
    """One glyph, in DESIGN.md §6's grammar. Decorative: it sits beside its word."""
    paths = _ICON_PATHS.get(key)
    if not paths:
        return ""
    drawn = "".join(f'<path d="{html.escape(d, quote=True)}" />' for d in paths)
    return (
        f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{drawn}</svg>'
    )


# =============================================================================
# 2. The MDX body
#
# A deliberately small subset: the constructs SCHEMA.md §7's sample body and the
# Architect's prompt actually produce. Anything else is passed through as a
# paragraph rather than swallowed, so an unexpected construct is visible to the
# reviewer instead of vanishing from the preview.
# =============================================================================

_INLINE = (
    # Images BEFORE links, because the link pattern matches the `[alt](url)`
    # inside `![alt](url)` and leaves a stray `!` in front of an anchor. That is
    # what it did until Gate 11 gave the toolbar an image button: the author
    # uploaded a photograph, the URL went into the body, and the preview showed
    # a link where the picture was going to be.
    (re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"), r'<img src="\2" alt="\1" />'),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<b>\1</b>"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"<i>\1</i>"),
)


def _inline(text: str) -> str:
    out = html.escape(text.strip())
    for pattern, replacement in _INLINE:
        out = pattern.sub(replacement, out)
    return out


#: Sentinels marking a block that is already HTML, so the paragraph splitter
#: below passes it through instead of wrapping it in a `<p>`. They wrap the
#: markup rather than overlapping it: `_raw` is the only thing that writes them
#: and these two constants are the only lengths the splitter trims, so a block
#: whose own tags start and end in angle brackets still trims back to exactly
#: what was emitted. Writing the sentinel inline is how the trim came to eat the
#: `<` off `<blockquote>` and the `>` off `</blockquote>`.
RAW_OPEN = "<<<"
RAW_CLOSE = ">>>"


def _raw(markup: str) -> str:
    """Wrap finished HTML so `render_body`'s splitter passes it through whole."""
    return f"\n\n{RAW_OPEN}{markup}{RAW_CLOSE}\n\n"


def render_body(body: str) -> str:
    """The MDX body as HTML, with the two components the entries use."""
    # JSX comments — `{/* … */}` — are not rendered by MDX and are not here.
    body = re.sub(r"\{/\*.*?\*/\}", "", body, flags=re.DOTALL)

    def pull(match: re.Match[str]) -> str:
        attribution = match.group("attribution")
        cite = (
            f'<cite class="pull__attribution">{html.escape(attribution)}</cite>'
            if attribution
            else ""
        )
        return _raw(
            f'<blockquote class="pull">{_inline(match.group("text"))}{cite}</blockquote>'
        )

    body = re.sub(
        r'<Pull(?:\s+attribution="(?P<attribution>[^"]*)")?\s*>(?P<text>.*?)</Pull>',
        pull,
        body,
        flags=re.DOTALL,
    )

    def tipped(match: re.Match[str]) -> str:
        attributes = dict(re.findall(r'(\w+)="([^"]*)"', match.group(0)))
        return _raw(
            '<figure class="tipped-photo"><div class="tipped-photo__mount">'
            f'<img src="{html.escape(attributes.get("src", ""), quote=True)}" alt="" />'
            '</div><figcaption class="tipped-photo__caption mono mono-caps">'
            f'{html.escape(attributes.get("caption", ""))}'
            "</figcaption></figure>"
        )

    body = re.sub(r"<TippedPhoto\b[^>]*/>", tipped, body)

    # `<Figure>` is INLINE — it sits inside a sentence — so it cannot use the
    # `_raw` block sentinels the way `<Pull>` and `<TippedPhoto>` do. Wrapping it
    # would split the sentence around it into three blocks.
    #
    # It cannot be substituted straight to markup either: the paragraph branch
    # below runs `html.escape` over the whole block, which would turn the emitted
    # `<span>` into visible `&lt;span&gt;`. Observed on the first post rendered
    # through this preview, and it is the same class of defect as the Gate 3
    # sentinel bug — a substitution that is correct until something downstream
    # treats its output as text.
    #
    # So the tags are lifted out to placeholders that survive escaping, and put
    # back after every block has been rendered. NUL cannot appear in an MDX file
    # the editor produced, and `render_body`'s inline patterns cannot match it.
    inline_figures: list[str] = []

    def figure(match: re.Match[str]) -> str:
        """`<Figure>` resolved for the preview. Gate 11.

        The build resolves this from the content collection; here it is resolved
        from `producers.json`, which is the same data one step downstream. An
        unresolvable query renders as the tag itself rather than as a number,
        because the author needs to see the thing that is about to fail the
        build, and a preview that silently rendered `0` would hide it until
        deploy.
        """
        attributes = dict(re.findall(r'(\w+)="([^"]*)"', match.group(0)))
        try:
            value = _figure_value(attributes.get("of", ""), attributes.get("member"))
        except (KeyError, ValueError):
            markup = (
                f'<span class="figure figure--unresolved">'
                f"{html.escape(match.group(0))}</span>"
            )
        else:
            markup = f'<span class="figure">{value:,}</span>'
        inline_figures.append(markup)
        return f"\x00F{len(inline_figures) - 1}\x00"

    body = re.sub(r"<Figure\b[^>]*/>", figure, body)

    rendered: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block:
            continue
        if block.startswith(RAW_OPEN) and block.endswith(RAW_CLOSE):
            rendered.append(block[len(RAW_OPEN) : -len(RAW_CLOSE)])
        elif block.startswith("## "):
            rendered.append(f"<h2>{_inline(block[3:])}</h2>")
        elif block.startswith("### "):
            rendered.append(f"<h3>{_inline(block[4:])}</h3>")
        else:
            rendered.append(f"<p>{_inline(block)}</p>")

    out = "\n".join(rendered)
    # The inline figures go back after escaping, never before it.
    return re.sub(
        r"\x00F(\d+)\x00", lambda m: inline_figures[int(m.group(1))], out
    )


def _figure_value(of: str, member: str | None) -> int:
    """One `<Figure>` query, resolved as the build resolves it.

    Delegates to `article_pipeline.figure_value` rather than reimplementing the
    nine counts. There are already two statements of this set — that one and
    `site/src/data/figures.ts` — and a third would be the one that disagrees.

    **This used to scan `available_figures` directly, and that was wrong.** That
    list is the set OFFERED to the drafting stage, which deliberately excludes
    members with no published producers so a model is not invited to write about
    a region this guide does not document. Resolution is a different question.
    A legal register member with zero producers builds fine and renders `0`, and
    the preview was painting it red and telling the author it was about to fail
    the build. Being told to delete a correct tag is worse than seeing no
    preview at all.
    """
    from admin.pipeline.article_pipeline import figure_value

    return figure_value(of, member)


def prose_word_count(body: str) -> int:
    """Words a reader sees: components and JSX comments removed first."""
    text = re.sub(r"\{/\*.*?\*/\}", "", body, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(text.split())


# =============================================================================
# 3. The structured fields, in DESIGN.md §7's order
# =============================================================================


def _fact_row(data: dict[str, Any], cid: str) -> str:
    """The present-only glyph row, mirroring `FactRow.astro`.

    PRESENT-ONLY, and practices render only the true ones. There is no row
    reading "not unfined": an absent practice is absence of evidence and this
    page does not assert it either way.
    """
    facts: list[tuple[str, str]] = []

    for key in PRACTICE_KEYS:
        if (data.get("practices") or {}).get(key) is True:
            facts.append((f"practice_{key}", schema.label_for("practice", key)))

    for subject in ("organic", "biodynamic"):
        state = data.get(subject)
        if not state or state == "none":
            continue
        certifier = data.get(f"{subject}_certifier")
        if state == "certified" and not certifier:
            continue
        label = (
            f"Certified {subject} ({certifier})"
            if state == "certified"
            else f"{schema.label_for('certification', state)} {subject}"
        )
        facts.append((subject, label))

    if data.get("fruit_source"):
        facts.append(("fruit_source", schema.label_for("fruit-source", data["fruit_source"])))

    band = data.get("production_band")
    if band and band != "unknown":
        facts.append(("production", schema.label_for("production-band", band)))

    for style in data.get("wine_styles") or []:
        facts.append((f"style_{style}", schema.label_for("wine-style", style)))
    for vessel in data.get("vessels") or []:
        facts.append((f"vessel_{vessel}", schema.label_for("vessel", vessel)))

    if not facts:
        return ""
    items = "".join(
        f'<li class="fact">{_icon(key)}<span>{html.escape(label)}</span></li>'
        for key, label in facts
    )
    return f'<ul class="fact-row"{cid}>{items}</ul>'


def _dateline(data: dict[str, Any]) -> str:
    location = data.get("location") or {}
    parts: list[str] = []
    if location.get("suburb"):
        parts.append(str(location["suburb"]))
    if location.get("state"):
        parts.append(schema.label_for("state", location["state"]))
    if data.get("primary_region"):
        parts.append(schema.region_name(data["primary_region"]))
    for slug in data.get("subregions") or []:
        parts.append(schema.subregion_name(slug))
    if data.get("category"):
        parts.append(schema.label_for("category", data["category"]))
    if data.get("founded_year"):
        parts.append(f"Founded {data['founded_year']}")
    return " · ".join(html.escape(str(part)) for part in parts)


def _appendix(data: dict[str, Any], cid: str) -> str:
    location = data.get("location") or {}
    rows: list[str] = []

    where = [
        location.get("address"),
        location.get("suburb"),
        schema.label_for("state", location["state"]) if location.get("state") else None,
    ]
    where = [str(part) for part in where if part]
    if where:
        rows.append(f"<dt>Where</dt><dd>{html.escape(', '.join(where))}</dd>")

    cellar_door = data.get("cellar_door")
    sentence = {
        "none": "No cellar door. Wine is sold direct rather than on site.",
        "by_appointment": "Open by appointment.",
        "open": "Open during published hours.",
    }.get(cellar_door or "", "")
    if sentence:
        hours = data.get("cellar_door_hours")
        extra = f"<br />{html.escape(str(hours))}" if hours else ""
        rows.append(f"<dt>Cellar door</dt><dd>{sentence}{extra}</dd>")

    if data.get("cost"):
        rows.append(f"<dt>Cost</dt><dd>{html.escape(str(data['cost']))}</dd>")
    if data.get("minimum_age"):
        rows.append(f"<dt>Minimum age</dt><dd>{html.escape(str(data['minimum_age']))}</dd>")
    if data.get("ships_nationally"):
        rows.append("<dt>Delivery</dt><dd>Ships nationally.</dd>")

    actions = ""
    if data.get("website"):
        actions += (
            f'<a class="visit-btn" href="{html.escape(str(data["website"]), quote=True)}" '
            f'rel="noopener">Producer\'s own site</a>'
        )
    if data.get("buy_online") and data.get("shop_url"):
        actions += (
            f'<a class="visit-btn" href="{html.escape(str(data["shop_url"]), quote=True)}" '
            f'rel="noopener">Buy direct</a>'
        )

    return (
        f'<section class="appendix"{cid}><dl>{"".join(rows)}</dl>'
        f'<p class="appendix__actions"{cid}>{actions}</p></section>'
    )


def _provenance(data: dict[str, Any], cid: str) -> str:
    """The provenance close — always present, set in words and dates.

    DESIGN.md §7: never a badge, tick, shield, seal, meter, score or percentage.
    It must read as a citation. Its absence would be read as "unknown", and an
    undetermined producer is not publishable, so it renders even while a field
    it cites is still empty in the draft.
    """
    ownership = data.get("ownership_source") or {}
    source = str(ownership.get("source") or "")
    ownership_date = schema.as_date(ownership.get("date"))
    method = ownership.get("method")
    source_html = (
        f'<a href="{html.escape(source, quote=True)}" rel="noopener">{html.escape(source)}</a>'
        if source.startswith("http")
        else html.escape(source)
    )

    # Amended 2026-08-09 (SCHEMA.md §1.15). The preview is the reviewer's only
    # sight of what the page will actually say, so it must branch exactly as
    # `producer/[slug].astro` does. Showing the independence claim over an
    # unconfirmed draft would put the reviewer's approval behind a sentence the
    # published page is not going to print.
    #
    # `unconfirmed` is a finished state, so it is NOT `preview-missing` — that
    # class means "a reviewer still owes this field", and dressing a valid
    # determination as an outstanding task is how a reviewer learns to ignore
    # the marker. The genuinely missing case is a `confirmed` draft with no
    # source, which keeps the class and the blocking sentence.
    status = str(data.get("ownership_status") or "")
    lines: list[str] = []
    if status == "unconfirmed":
        lines.append(
            "<p>No published source names who owns this producer, so the "
            'directory makes no claim about its independence. '
            '<a href="/methodology/">How ownership is checked</a>.</p>'
        )
    else:
        lines.append('<p><a href="/methodology/">Independent</a>. No parent company.</p>')
        if source and ownership_date and method:
            lines.append(
                f"<p>Ownership checked on {ownership_date.isoformat()} against {source_html} "
                f"({html.escape(schema.label_for('ownership-evidence', method).lower())}).</p>"
            )
        else:
            lines.append(
                '<p class="preview-missing">No ownership source recorded yet. '
                "This draft cannot be approved as confirmed without one. Set "
                "ownership_status to unconfirmed if no source names the owner.</p>"
            )

    drafted = schema.as_date(data.get("drafted"))
    verified = schema.as_date(data.get("verified"))
    source_url = str(data.get("source_url") or "")
    if drafted and verified and source_url:
        lines.append(
            f"<p>Entry drafted {drafted.isoformat()}. Verified {verified.isoformat()}. "
            f'Source: <a href="{html.escape(source_url, quote=True)}" rel="noopener">'
            f"{html.escape(source_url)}</a>.</p>"
        )

    records = data.get("verification") or {}
    if records:
        items = ""
        for field, record in records.items():
            if not isinstance(record, dict):
                continue
            record_date = schema.as_date(record.get("date"))
            items += (
                f"<li>{html.escape(field.replace('_', ' '))} · "
                f'<a href="{html.escape(str(record.get("source", "")), quote=True)}" '
                f'rel="noopener">{html.escape(str(record.get("source", "")))}</a> · '
                f"{html.escape(schema.label_for('confidence-tier', str(record.get('tier'))).lower())} · "
                f"{record_date.isoformat() if record_date else ''}</li>"
            )
        lines.append(f'<ul class="provenance__fields"{cid}>{items}</ul>')

    return f'<footer class="provenance mono"{cid}>{"".join(lines)}</footer>'


# =============================================================================
# 4. The document
# =============================================================================


def render_document(data: dict[str, Any], body: str) -> str:
    """A complete HTML document for the preview iframe.

    No `data-theme` attribute: DESIGN.md §8 gives the admin automatic theming
    only, so `tokens.css`'s `prefers-color-scheme` block is what decides, and the
    preview follows the hub around it.
    """
    built = _built_producer_page()
    page = _cid_for_class(built, "reading-spine")
    # `FactRow.astro` carries no `<style>` block — `.fact-row` and `.fact` are
    # global — so its elements carry no scoped attribute and must not be given
    # one.
    fact_row_cid = ""

    styles = "".join(
        f'<link rel="stylesheet" href="{href}" />' for href in stylesheet_hrefs()
    )
    unbuilt = (
        ""
        if styles
        else (
            '<p class="preview-missing">The site has not been built, so the real '
            "stylesheet is not available. Run npm run build in site/ to preview "
            "this draft in the styles it will ship with.</p>"
        )
    )

    varieties = data.get("varieties") or []
    varieties_html = ""
    if varieties:
        listed = " · ".join(
            f'<a href="/variety/{html.escape(str(slug), quote=True)}/">'
            f"{html.escape(schema.label_for('variety', str(slug)))}</a>"
            for slug in varieties
        )
        varieties_html = f'<p class="varieties mono"{page}>{_icon("variety")}{listed}</p>'

    faq_html = ""
    pairs = data.get("faq") or []
    if pairs:
        blocks = "".join(
            f'<div class="faq__pair"{page}><h3>{html.escape(str(pair.get("question", "")))}</h3>'
            f'<p>{html.escape(str(pair.get("answer", "")))}</p></div>'
            for pair in pairs
            if isinstance(pair, dict)
        )
        faq_html = (
            f'<section class="faq section-gap"{page}>'
            f'<p class="section-opener">Questions</p>{blocks}</section>'
        )

    plate = ""
    if data.get("image") and data.get("image_caption"):
        plate = (
            '<figure class="tipped-photo"><div class="tipped-photo__mount">'
            f'<img src="{html.escape(str(data["image"]), quote=True)}" alt="" />'
            '</div><figcaption class="tipped-photo__caption mono mono-caps">'
            f'{html.escape(str(data["image_caption"]))}</figcaption></figure>'
        )

    return f"""<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(str(data.get("name") or "Untitled draft"))}</title>
{styles}
<style>
  /* The preview's own two rules, and no more. Everything else on this page is
     the site's shipped CSS. */
  body {{ padding: 1.5rem 0 4rem; }}
  .preview-missing {{ color: var(--warn, #8a5a00); font-style: italic; }}
</style>
</head>
<body>
<div class="page-frame">
<main id="main">
{unbuilt}
<article class="reading-spine"{page}>
  <header{page}>
    <h1{page}>{html.escape(str(data.get("name") or "Untitled draft"))}</h1>
    <p class="dateline mono mono-caps"{page}>{_dateline(data)}</p>
  </header>
  <div class="fact-row-wrap"{page}>{_fact_row(data, fact_row_cid)}</div>
  {varieties_html}
  <div class="prose"{page}>{render_body(body)}</div>
  {plate}
  {faq_html}
  {_appendix(data, page)}
  {_provenance(data, page)}
</article>
</main>
</div>
</body>
</html>
"""


# =============================================================================
# 5. The post document — Gate 11, UX.md §6
#
# The blog editor's preview pane. Same posture as `render_document`: the public
# site's real shipped CSS, no site JavaScript, and this module's own two rules.
#
# It renders the shape of `/blog/[slug].astro` — dateline row, cover, body,
# sources — rather than the producer page's. A preview that showed the wrong
# page furniture would be reviewing a layout the post will never have.
# =============================================================================


def render_post(data: dict[str, Any], body: str) -> str:
    """A complete HTML document previewing one post."""
    built = _built_producer_page()
    page = _cid_for_class(built, "reading-spine")

    styles = "".join(
        f'<link rel="stylesheet" href="{href}" />' for href in stylesheet_hrefs()
    )
    unbuilt = (
        ""
        if styles
        else (
            '<p class="preview-missing">The site has not been built, so the real '
            "stylesheet is not available. Run npm run build in site/ to preview "
            "this post in the styles it will ship with.</p>"
        )
    )

    title = str(data.get("title") or "Untitled post")

    published = schema.as_date(data.get("published"))
    updated = schema.as_date(data.get("updated"))
    dateline_parts = [str(data.get("dateline") or "").strip()]
    if published:
        dateline_parts.append(published.strftime("%-d %B %Y"))
    dateline = " · ".join(part for part in dateline_parts if part)

    amended = (
        f'<p class="post-head__amended mono mono-caps"{page}>'
        f'Amended {updated.strftime("%-d %B %Y")}</p>'
        if updated
        else ""
    )

    cover = ""
    if data.get("cover"):
        cover = (
            f'<figure class="post-cover"{page}>'
            f'<img src="{html.escape(str(data["cover"]), quote=True)}" '
            f'alt="{html.escape(str(data.get("cover_caption") or ""), quote=True)}" />'
            f'<figcaption class="post-cover__source mono"{page}>Image: '
            f'<a href="{html.escape(str(data.get("cover_source") or ""), quote=True)}" '
            f'rel="noopener">{html.escape(str(data.get("cover_source") or ""))}</a>'
            f"</figcaption></figure>"
        )

    sources = data.get("sources") or []
    if sources:
        items = "".join(
            f'<li><a href="{html.escape(str(source.get("url", "")), quote=True)}" '
            f'rel="noopener">{html.escape(str(source.get("title", "")))}</a></li>'
            for source in sources
            if isinstance(source, dict)
        )
    else:
        # Stated rather than left blank. `sources` is required (SCHEMA.md §9.2)
        # and an empty block in the preview reads as a styling gap rather than
        # as the publish blocker it is.
        items = '<li class="preview-missing">No sources recorded. This post cannot publish.</li>'

    return f"""<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)}</title>
{styles}
<style>
  body {{ padding: 1.5rem 0 4rem; }}
  .preview-missing {{ color: var(--warn, #8a5a00); font-style: italic; }}
  /* The three post rules the public stylesheet carries as scoped styles, which
     a scoped-attribute lookup cannot reach from here. Kept to exactly what
     DESIGN.md §505 specifies: a plain mount border, and no plate signature. */
  .post-cover {{ margin: 0 0 2rem; padding: 4px; background: var(--paper-raised);
                 border: 1px solid var(--hairline); }}
  .post-cover img {{ display: block; width: 100%; height: auto; }}
  .post-cover__source {{ color: var(--ink-faded); margin: .6rem 0 0; font-size: .75rem;
                         overflow-wrap: anywhere; }}
  .post-head__title {{ font-size: clamp(2rem, 5vw, 3.25rem); margin: 0 0 .6rem; }}
  .post-head__dateline, .post-head__amended {{ color: var(--ink-faded); margin: 0; }}
  .post-sources__list {{ margin: 0; padding: 0; list-style: none; max-width: 60ch; }}
  .post-sources__list li {{ padding: .5rem 0; border-bottom: 1px solid var(--hairline);
                            overflow-wrap: anywhere; }}
  /* Section headings. `.prose` carries no heading rules sitewide — a producer
     entry is flowing prose with no `##` in it — so these are scoped to the post
     page and unreachable from here. Restated for the same reason the three
     rules above are: a preview in different spacing from the shipped page is a
     preview of a page nobody is reviewing (UX.md §1.4). */
  .prose h2 {{ margin-top: clamp(2.75rem, 5vw, 4rem); margin-bottom: 1rem; }}
  .prose h3 {{ margin-top: clamp(2rem, 3.5vw, 2.75rem); margin-bottom: .75rem; }}
  /* An unresolvable <Figure> shows as the tag it is, so the author sees the
     thing that is about to fail the build. */
  .figure--unresolved {{ color: var(--claret, #8a2a2a); font-family: var(--font-mono); }}
</style>
</head>
<body>
<div class="page-frame">
<main id="main">
{unbuilt}
<article class="reading-spine"{page}>
  <header class="post-head"{page}>
    <h1 class="post-head__title"{page}>{html.escape(title)}</h1>
    <p class="post-head__dateline mono mono-caps"{page}>{html.escape(dateline)}</p>
    {amended}
  </header>
  {cover}
  <div class="prose"{page}>{render_body(body)}</div>
  <section class="post-sources section-gap"{page}>
    <p class="section-opener"{page}>Written from</p>
    <ul class="post-sources__list mono"{page}>{items}</ul>
  </section>
</article>
</main>
</div>
</body>
</html>
"""
