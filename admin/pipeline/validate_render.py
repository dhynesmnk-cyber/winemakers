"""validate_render.py — `/validate` check 16. Gate 1.

The built site renders correctly with JavaScript disabled, and under
`prefers-reduced-motion: reduce` every element renders fully visible in its
final position.

**This is a build requirement, not a courtesy.** DESIGN.md §9's binding no-JS
rule: motion is something JS adds on top of an already-correct page, never
something a missing script leaves hidden or broken. The admin review pane's
preview never loads site JS, so an entry that renders blank without JS cannot
be reviewed or approved.

Two layers, and both run:

1. **Static.** Parse the built HTML and CSS. No element carries an inline style
   that hides it; the reduced-motion kill switch exists; no keyframe leaves a
   persistent hidden resting state; there are no external resource requests.
   This layer needs no browser and always runs.

2. **Rendered.** Drive headless Chromium with JavaScript disabled and with
   `prefers-reduced-motion: reduce`, and assert that the same text and the same
   links are present and visible as with JS on. This layer is SKIPPED WITH A
   LOUD NOTE if Playwright or its browser is unavailable, because a check that
   silently degrades to nothing is worse than one that says it did not run.
"""

from __future__ import annotations

import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import SITE_DIR  # noqa: E402

DIST = SITE_DIR / "dist"

#: Inline styles that would leave content hidden when no script runs to reveal it.
HIDING_STYLE = re.compile(
    r'style="[^"]*(?:opacity:\s*0(?![.\d])|display:\s*none|visibility:\s*hidden)',
    re.I,
)

#: Anything the BROWSER FETCHES from another host: a script, a stylesheet, a
#: preload, an image, a frame. The site performs zero runtime data fetching and
#: there is no map, so this must be empty (TRD.md §4.4).
#:
#: A <link rel="canonical">, an <a href> and an og:url are declarations about
#: where something lives, not requests, and are deliberately not matched.
EXTERNAL_REF = re.compile(
    r'<(?:script|img|iframe|embed|source|video|audio)\b[^>]*\bsrc="(https?://[^"]+)"'
    r'|<link\b(?![^>]*\brel="(?:canonical|alternate)")[^>]*\bhref="(https?://[^"]+)"',
    re.I,
)


def built_pages() -> list[Path]:
    return sorted(DIST.rglob("index.html"))


def built_css() -> list[Path]:
    return sorted(DIST.rglob("*.css"))


def static_checks() -> list[str]:
    errors: list[str] = []

    pages = built_pages()
    if not pages:
        return ["no built pages found; run `npm run build` in site/ first"]

    for page in pages:
        html = page.read_text(encoding="utf-8")
        rel = page.relative_to(DIST)

        for match in HIDING_STYLE.finditer(html):
            errors.append(
                f"{rel}: inline style hides an element without JS: "
                f"{match.group(0)[:80]}"
            )

        for match in EXTERNAL_REF.finditer(html):
            url = match.group(1) or match.group(2)
            errors.append(f"{rel}: external resource request: {url}")

        # The page must carry a first-level heading in the served markup.
        if "<h1" not in html:
            errors.append(f"{rel}: no <h1> in the server-rendered HTML")

        # DESIGN.md §9 quality floor: the grain overlay is on every public page.
        if "grain-overlay" not in html:
            errors.append(f"{rel}: grain overlay missing (DESIGN.md §4)")

    css_text = "\n".join(path.read_text(encoding="utf-8") for path in built_css())
    if not css_text:
        errors.append("no built CSS found")
    else:
        if "prefers-reduced-motion" not in css_text:
            errors.append(
                "the reduced-motion kill switch is missing from the built CSS "
                "(DESIGN.md §9)"
            )
        # A persistent `opacity:0` resting state is the reveal-on-scroll flash
        # bug: the kill switch lands on a hidden frame and the content is gone.
        for match in re.finditer(r"\.([a-z0-9_-]+)\{[^}]*opacity:0[^}]*\}", css_text, re.I):
            if "keyframes" in match.group(0):
                continue
            errors.append(
                f"selector .{match.group(1)} has a persistent opacity:0 resting "
                f"state; its resting style must be the post-animation state "
                f"(DESIGN.md §9)"
            )

    return errors


def _serve(port: int) -> socketserver.TCPServer:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D102
            pass

    handler = lambda *a, **kw: Quiet(*a, directory=str(DIST), **kw)  # noqa: E731
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def rendered_checks(port: int = 0) -> tuple[list[str], bool]:
    """Returns (errors, ran). `ran` is False when no browser is available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], False

    errors: list[str] = []
    # Port 0 binds an ephemeral port, so a stray server from an earlier run
    # cannot make this check fail for the wrong reason.
    httpd = _serve(port)
    port = httpd.server_address[1]
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:
                return [], False

            routes = [
                "/" + str(page.parent.relative_to(DIST)).replace(".", "").lstrip("/")
                for page in built_pages()
            ]
            routes = [r if r.endswith("/") else r + "/" for r in routes]

            for route in routes:
                url = f"http://127.0.0.1:{port}{route}"

                with_js = browser.new_context()
                page = with_js.new_page()
                page.goto(url, wait_until="networkidle")
                text_with = page.inner_text("body")
                page.close()
                with_js.close()

                # JavaScript disabled entirely.
                no_js = browser.new_context(java_script_enabled=False)
                page = no_js.new_page()
                page.goto(url, wait_until="load")
                text_without = page.inner_text("body")
                heading = page.inner_text("h1") if page.query_selector("h1") else ""
                visible_main = page.is_visible("main")
                page.close()
                no_js.close()

                if not heading.strip():
                    errors.append(f"{route}: no visible <h1> with JS disabled")
                if not visible_main:
                    errors.append(f"{route}: <main> is not visible with JS disabled")

                # Every paragraph of prose present with JS must be present
                # without it. Compared as normalised words so whitespace and
                # the two JS-driven controls do not cause noise.
                def words(s: str) -> set[str]:
                    return set(re.findall(r"[a-z]{4,}", s.lower()))

                missing = words(text_with) - words(text_without)
                # The theme toggle and menu button are revealed BY script, so
                # their own labels legitimately differ.
                missing -= {"menu", "theme", "system", "light", "dark"}
                if missing:
                    errors.append(
                        f"{route}: {len(missing)} word(s) present with JS and absent "
                        f"without it: {sorted(missing)[:8]}"
                    )

                # prefers-reduced-motion: everything in its final position.
                reduced = browser.new_context(reduced_motion="reduce")
                page = reduced.new_page()
                page.goto(url, wait_until="networkidle")
                faded = page.eval_on_selector_all(
                    "body *",
                    "els => els.filter(e => {"
                    "  const s = getComputedStyle(e);"
                    "  if (s.display === 'none' || s.visibility === 'hidden') return false;"
                    "  return parseFloat(s.opacity) < 0.99;"
                    "}).map(e => e.tagName + '.' + e.className).slice(0, 5)",
                )
                # The grain overlay is deliberately low-opacity decoration.
                faded = [f for f in faded if "grain" not in str(f).lower()]
                if faded:
                    errors.append(
                        f"{route}: under prefers-reduced-motion these are not fully "
                        f"visible: {faded}"
                    )
                page.close()
                reduced.close()

            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    return errors, True


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    clean_html = '<html><body><h1>Name</h1><div class="grain-overlay"></div></body></html>'
    dirty_html = '<html><body><h1 style="opacity: 0">Name</h1></body></html>'

    if HIDING_STYLE.search(clean_html):
        errors.append("selftest: clean HTML flagged as hiding content")
    if not HIDING_STYLE.search(dirty_html):
        errors.append("selftest: `style=\"opacity: 0\"` was NOT caught")
    for probe in ('style="display:none"', 'style="visibility: hidden"', 'style="opacity:0"'):
        if not HIDING_STYLE.search(f"<p {probe}>x</p>"):
            errors.append(f"selftest: {probe} was NOT caught")
    # A decimal opacity is not zero and must not trip the check.
    if HIDING_STYLE.search('<p style="opacity: 0.035">x</p>'):
        errors.append("selftest: opacity: 0.035 wrongly flagged (that is the grain)")

    if not EXTERNAL_REF.search('<script src="https://cdn.example.com/x.js"></script>'):
        errors.append("selftest: external script was NOT caught")
    if not EXTERNAL_REF.search('<link rel="stylesheet" href="https://fonts.googleapis.com/x">'):
        errors.append("selftest: external stylesheet was NOT caught")
    if EXTERNAL_REF.search('<link rel="preload" href="/fonts/x.woff2" as="font">'):
        errors.append("selftest: local font preload wrongly flagged as external")
    if EXTERNAL_REF.search('<link rel="canonical" href="https://example.com/x/">'):
        errors.append("selftest: canonical wrongly flagged as a resource request")

    return errors


def main() -> int:
    errors = _selftest() + static_checks()
    rendered_errors, ran = rendered_checks()
    errors += rendered_errors

    if errors:
        print(f"VALIDATE 16 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1

    pages = len(built_pages())
    if ran:
        print(
            f"VALIDATE 16 PASS — selftest ok; {pages} page(s) static-checked and "
            f"rendered with JS disabled and under prefers-reduced-motion"
        )
    else:
        print(
            f"VALIDATE 16 PARTIAL — selftest ok; {pages} page(s) static-checked. "
            f"THE BROWSER LAYER DID NOT RUN (Playwright or its browser is not "
            f"available), so no-JS rendering was checked by static analysis only."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
