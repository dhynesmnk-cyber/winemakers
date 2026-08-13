"""validate_preview.py — `/validate` check 20. Engagement 2026-08-09.

The review pane's MDX preview renders well-formed HTML.

**Why this check exists.** `mdx_preview.render_body` wraps the two components an
entry may carry in `<<<`/`>>>` sentinels so the paragraph splitter passes them
through whole. The sentinel was written inline at each call site and trimmed by
a hardcoded three characters, which let the tag's own angle brackets stand in as
sentinel characters: the trim took the `<` off `<blockquote>` and the `>` off
`</blockquote>`, and every pull-quote in the review pane rendered as raw markup.
It shipped at Gate 3 and survived four gates because nothing in the suite ever
looked at the preview's output.

The renderer is the reviewer's only view of a draft before it publishes. A
component that renders as text there is a component nobody is actually reviewing.

Three properties, none of which the original defect could have satisfied:

1. **Balanced.** Every tag the renderer opens, it closes, in order.
2. **No sentinel leakage.** No `<<<` or `>>>` survives into the output, in any
   position, including inside prose that contains angle brackets of its own.
3. **Escaped.** Harvested prose is untrusted text rendered into the admin. A
   producer's page that contains a `<script>` tag, or an attribution carrying a
   quote mark, must not reach the reviewer's browser as live markup.
"""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin import mdx_preview  # noqa: E402

#: Tags that legitimately never close. The renderer emits `<img>` self-closed.
VOID_TAGS = {"img", "br", "hr", "input", "meta", "link"}


class _Balance(HTMLParser):
    """Tag balance, in order. `convert_charrefs` stays on so text is unchanged."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        pass

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"</{tag}> closes a tag that was never opened")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> closes out of order, expected </{self.stack[-1]}>")
            self.stack.pop()
        else:
            self.stack.pop()


def _balance_errors(markup: str) -> list[str]:
    parser = _Balance()
    parser.feed(markup)
    parser.close()
    return parser.errors + [f"<{tag}> is never closed" for tag in parser.stack]


PULL = """Opening paragraph.

<Pull attribution="Gemtree, on their website">
  Gifted the opportunity to work a unique patch of the earth.
</Pull>

Closing paragraph."""

PULL_NO_ATTRIBUTION = """<Pull>
  A quotation with no attribution at all.
</Pull>"""

TIPPED = '<TippedPhoto src="/images/x.jpg" caption="The cellar door" />'

BOTH = f"{PULL}\n\n{TIPPED}\n\nAnd a trailing paragraph."

#: Prose carrying angle brackets of its own, which is what made the original
#: defect possible: the sentinel and the payload were made of the same character.
ANGLED = """A paragraph mentioning <not a tag> and 3 > 2 and 1 < 2.

<Pull attribution="A source > another">
  The vineyard sits <somewhere> above the river.
</Pull>"""

HOSTILE = """<Pull attribution='He said "hello" &amp; left'>
  <script>alert(1)</script> and an <img src=x onerror=alert(2)> tag.
</Pull>"""

#: What the blog toolbar's image button writes, beside an ordinary link.
#:
#: Added at Gate 11 with the upload path. The link pattern matched the
#: `[alt](url)` inside `![alt](url)`, so an uploaded photograph rendered in the
#: preview as a stray `!` in front of an anchor. The author uploaded an image
#: and the preview showed a link where the picture was going to be — found by
#: driving the file picker in a browser rather than by calling the route.
IMAGE = """An opening paragraph.

![A vineyard block, looking west.](/blog-staging-images/a-post/vineyard.webp)

And a [methodology page](/methodology/) link, which must still be an anchor."""

#: A list, which the blog is the first body surface to use.
#:
#: The splitter had no list branch, so this rendered as one paragraph with the
#: hyphens literal while the shipped MDX page rendered a real `<ul>`. The last
#: block is the boundary: one line carrying a marker does not make a list, and
#: guessing at it would be worse than leaving it as prose.
LISTS = """Three kinds of source:

- **producer_statement**: the producer's own published page.
- **trade_source**: a regional association register.
- **registry**: the Australian Business Register.

1. First
2. Second

A paragraph - with a dash in it - that is not a list."""


#: Every body run through the three universal properties. Module-level so the
#: summary line can COUNT it rather than restate it: the count was hardcoded at
#: six, and adding the image case left the check reporting six while running
#: seven. Gate 9's carried-forward note in miniature — a number the code under
#: test already knows should never be typed out a second time.
CASES = {
    "pull with attribution": PULL,
    "pull without attribution": PULL_NO_ATTRIBUTION,
    "tipped photo": TIPPED,
    "both components in one body": BOTH,
    "prose containing angle brackets": ANGLED,
    "hostile source text": HOSTILE,
    "an inserted image beside a link": IMAGE,
    "bulleted and numbered lists": LISTS,
}


def check_20_preview() -> list[str]:
    errors: list[str] = []

    for name, body in CASES.items():
        out = mdx_preview.render_body(body)

        errors += [f"{name}: {message}" for message in _balance_errors(out)]

        for sentinel in (mdx_preview.RAW_OPEN, mdx_preview.RAW_CLOSE):
            if sentinel in out:
                errors.append(f"{name}: the sentinel {sentinel!r} survived into the output")

    # The components must actually render, not merely fail to unbalance.
    pull_out = mdx_preview.render_body(PULL)
    if '<blockquote class="pull">' not in pull_out or "</blockquote>" not in pull_out:
        errors.append("pull with attribution: no complete <blockquote> in the output")
    if "<cite" not in pull_out:
        errors.append("pull with attribution: the attribution did not render as a <cite>")
    if "Gifted the opportunity" not in pull_out:
        errors.append("pull with attribution: the quotation text is missing")

    bare = mdx_preview.render_body(PULL_NO_ATTRIBUTION)
    if "<cite" in bare:
        errors.append("pull without attribution: a <cite> was rendered with nothing to cite")

    tipped_out = mdx_preview.render_body(TIPPED)
    for fragment in ('<figure class="tipped-photo"', "</figure>", "<figcaption", "</figcaption>"):
        if fragment not in tipped_out:
            errors.append(f"tipped photo: {fragment} missing from the output")
    if 'src="/images/x.jpg"' not in tipped_out:
        errors.append("tipped photo: the src did not survive")
    if "The cellar door" not in tipped_out:
        errors.append("tipped photo: the caption did not survive")

    # An image the toolbar inserted must render AS an image, and must not take
    # the link pattern with it. A preview that shows an anchor where a
    # photograph is going is a preview of a page nobody is reviewing.
    image_out = mdx_preview.render_body(IMAGE)
    if '<img src="/blog-staging-images/a-post/vineyard.webp"' not in image_out:
        errors.append("inserted image: it did not render as an <img>")
    if 'alt="A vineyard block, looking west."' not in image_out:
        errors.append("inserted image: the alt text did not survive")
    if "!<a" in image_out or ">!<" in image_out:
        errors.append(
            "inserted image: a stray `!` is sitting in front of an anchor — the link "
            "pattern matched inside the image syntax"
        )
    if '<a href="/methodology/">' not in image_out:
        errors.append("inserted image: an ordinary link stopped rendering as an anchor")

    # Lists must be lists. The shipped page renders a real <ul>, and a preview
    # showing run-on prose with literal hyphens is a preview of a different page.
    list_out = mdx_preview.render_body(LISTS)
    if list_out.count("<li>") != 5:
        errors.append(
            f"lists: expected 5 <li>, got {list_out.count('<li>')} — three bulleted "
            f"and two numbered"
        )
    if "<ul>" not in list_out or "<ol>" not in list_out:
        errors.append("lists: a bulleted or numbered list did not render as a list")
    if "<li>- " in list_out or "<p>- " in list_out:
        errors.append("lists: a marker survived into the rendered text")
    if "<b>producer_statement</b>" not in list_out:
        errors.append("lists: inline formatting inside an item did not render")
    if "<li>A paragraph" in list_out:
        errors.append(
            "lists: a paragraph containing a dash was rendered as a list item. One "
            "line carrying a marker does not make a list."
        )

    # Untrusted prose must arrive as text, never as markup.
    hostile_out = mdx_preview.render_body(HOSTILE)
    if "<script>" in hostile_out:
        errors.append("hostile source text: a <script> tag reached the reviewer unescaped")
    if "onerror=" in hostile_out and "&lt;img" not in hostile_out:
        errors.append("hostile source text: an unescaped <img> carries an event handler")

    return errors


def main() -> int:
    errors = check_20_preview()
    if errors:
        print(f"VALIDATE 20 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    print(
        f"VALIDATE 20 PASS — {len(CASES)} preview bodies render balanced, sentinel-free "
        "and escaped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
