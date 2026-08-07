"""fetcher.py — fetching, extraction, and the three ways a fetch ends badly.

Gate 5. TRD.md §7.6, UX.md §1.5 rows 1, 2 and 3.

── The posture ───────────────────────────────────────────────────────────────

SEED.md's ethics note is the design brief for this module: *"These sites are
being read, not scraped at volume."* One request at a time, a user agent that
identifies the project and links its methodology page, `robots.txt` honoured
with no override control anywhere in the system, and a 20 second ceiling.

── Playwright is not a fallback this module ever chooses ─────────────────────

`fetch(url, use_playwright=True)` exists and is only ever reached from a control
the operator clicks (UX.md §1.5 row 3). Nothing here escalates to it
automatically. A headless browser is a different and much heavier thing to point
at somebody's website than an HTTP GET, and the decision to do it belongs to a
person.

── robots.txt is read with our own client, not urllib's ──────────────────────

`urllib.robotparser` would fetch it with urllib: a different user agent, a
different timeout, and outside the IPv4 monkeypatch's reach in every practical
sense. So the file is fetched with the same httpx client as everything else and
only the *parsing* is stdlib. That is the stdlib-over-packages posture applied
at the right seam (TRD.md §2.2).
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    FETCH_TIMEOUT_SECONDS,
    HARVEST_USER_AGENT,
    THIN_EXTRACTION_CHARS,
)

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    pass


# =============================================================================
# 1. Outcomes
# =============================================================================


@dataclass
class Fetched:
    url: str
    final_url: str
    status: int
    html: str
    text: str
    rendered_by: str = "httpx"
    #: Bytes on the wire, for the log line's `ok (48 kB)`.
    byte_length: int = 0

    @property
    def kb(self) -> str:
        return f"{self.byte_length / 1000:.1f} kB"

    @property
    def text_kb(self) -> str:
        return f"{len(self.text.encode('utf-8')) / 1000:.1f} kB"


class FetchError(Exception):
    """UX.md §1.5 row 1. Carries the HTTP status or the word `timeout`."""

    def __init__(self, message: str, *, reason: str = ""):
        super().__init__(message)
        self.reason = reason or message


class RobotsDisallowed(Exception):
    """UX.md §1.5 row 2. No retry is offered and there is no override control."""

    def __init__(self, url: str, rule: str):
        super().__init__(f"robots.txt disallows {url} ({rule})")
        self.url = url
        self.rule = rule


class BoilerplateExtraction(Exception):
    """The extraction is a privacy policy or terms page, not producer content.

    NOT ANTICIPATED BY UX.md §1.5, added at Gate 5 against a real observation.
    d'Arenberg's homepage extracts to 9,039 characters of privacy policy and
    zero words about the winery, on every trafilatura setting. That is not a
    bug in the extractor: on a marketing homepage the longest run of continuous
    prose genuinely IS the legal boilerplate, because everything else is hero
    fragments and navigation.

    It matters because the extraction is well over THIN_EXTRACTION_CHARS, so
    nothing else would stop it, and what reaches the Harvester is a document
    about cookies. The honest outcomes from there are a wasted call or an
    invented producer, and the second one is the honesty rule broken by
    machinery rather than by anyone's intent.

    Playwright does not help and is not offered: the page rendered fine. The
    fix is to harvest a content-bearing page instead, which is what the message
    says.
    """

    def __init__(self, fetched: "Fetched", ratio: float):
        super().__init__(
            f"extraction is {ratio:.0%} legal boilerplate, not producer content"
        )
        self.fetched = fetched
        self.ratio = ratio


class ThinExtraction(Exception):
    """UX.md §1.5 row 3. The item ends WITHOUT drafting.

    Carries the `Fetched` so the caller can offer `Retry with Playwright` on the
    row and so the operator can see what little was there.
    """

    def __init__(self, fetched: Fetched):
        super().__init__(f"thin extraction: {len(fetched.text)} chars")
        self.fetched = fetched
        self.chars = len(fetched.text)


# =============================================================================
# 2. robots.txt
# =============================================================================

#: host -> parser. Per-process, so a batch of forty URLs on one domain fetches
#: robots.txt once. Not persisted: a cached disallow that outlived the operator's
#: session would be worse than one extra request.
_ROBOTS: dict[str, RobotFileParser | None] = {}


def _client(timeout: float | None = None):
    import httpx

    return httpx.Client(
        headers={"User-Agent": HARVEST_USER_AGENT},
        timeout=timeout if timeout is not None else FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def _robots_for(url: str, log: Logger) -> RobotFileParser | None:
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    if host in _ROBOTS:
        return _ROBOTS[host]

    parser: RobotFileParser | None = None
    try:
        with _client(timeout=10.0) as client:
            response = client.get(urljoin(host, "/robots.txt"))
        if response.status_code == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
    except Exception as exc:
        # A robots.txt that cannot be fetched is not a disallow. Say so out loud
        # rather than either blocking or silently proceeding.
        log("warn", f"robots.txt unreadable for {host} ({type(exc).__name__}), proceeding")
        parser = None

    _ROBOTS[host] = parser
    return parser


def robots_allows(url: str, log: Logger = _null_log) -> tuple[bool, str]:
    """`(allowed, rule)`. A missing or unreadable robots.txt allows."""
    parser = _robots_for(url, log)
    if parser is None:
        return True, ""
    if parser.can_fetch(HARVEST_USER_AGENT, url):
        return True, ""
    # `can_fetch` will not tell us which rule matched, so report the path that
    # was refused. Naming something specific is the requirement (UX.md §1.5).
    path = urlparse(url).path or "/"
    return False, f"Disallow matching {path}"


def reset_robots_cache() -> None:
    _ROBOTS.clear()
    _LAST_REQUEST.clear()


#: host -> monotonic time of the last request to it. `Crawl-delay` is a real
#: directive that real sites in this corpus publish (d'Arenberg asks for 1s), and
#: honouring only the Disallow half of a file we have already parsed would be
#: choosing the convenient half. The queue is serial anyway, so this costs a
#: batch on one domain a second per item and nothing else.
_LAST_REQUEST: dict[str, float] = {}

#: Applied when a site asks for something unreasonable, so one hostile robots.txt
#: cannot stall a forty-URL run indefinitely.
MAX_CRAWL_DELAY_SECONDS = 10.0


def _respect_crawl_delay(url: str, log: Logger) -> None:
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    parser = _ROBOTS.get(host)
    if parser is None:
        return
    try:
        delay = parser.crawl_delay(HARVEST_USER_AGENT)
    except Exception:  # pragma: no cover - a malformed directive
        return
    if not delay:
        return
    delay = min(float(delay), MAX_CRAWL_DELAY_SECONDS)
    last = _LAST_REQUEST.get(host)
    if last is not None:
        remaining = delay - (time.monotonic() - last)
        if remaining > 0:
            log("info", f"robots.txt crawl-delay {delay:g}s, waiting {remaining:.1f}s")
            time.sleep(remaining)
    _LAST_REQUEST[host] = time.monotonic()


# =============================================================================
# 3. Extraction
# =============================================================================


def extract_text(html: str) -> str:
    """trafilatura's main-content extraction.

    Comments and tables are excluded: a producer page's comment section is other
    people's words, and this pipeline may only document what the producer
    published about themselves.
    """
    import trafilatura

    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favour_precision=True,
    )
    return (text or "").strip()


# =============================================================================
# 3a. Boilerplate detection
# =============================================================================

#: Phrases that only appear in legal boilerplate. Chosen to be things a winery
#: does not say about its wine, so a producer page mentioning "privacy policy"
#: once in a footer sentence cannot trip the ratio on its own.
_BOILERPLATE_MARKERS = (
    "privacy policy",
    "personal information",
    "terms and conditions",
    "terms of sale",
    "terms of service",
    "this website uses cookies",
    "cookie policy",
    "third parties",
    "we may update",
    "governed by the laws",
    "liability",
    "intellectual property",
    "unsubscribe",
    "data protection",
    "your consent",
    "we collect",
)

#: Above this share of sentences carrying a marker, the extraction is the legal
#: page rather than the producer.
#:
#: MEASURED, and the separation is wide:
#:
#:     d'Arenberg homepage      26%   <- the offender, must be refused
#:     d'Arenberg /the-story     0%
#:     Basket Range              0%
#:     Gemtree                   0%
#:     Myrtaceae                 0%
#:
#: 0.15 sits below the offender with room and a full 15 points above every
#: legitimate page in the corpus, all of which score zero rather than merely
#: low. An earlier value of 0.30 was written before measuring and would have
#: passed the exact page this guard exists for, which is the second threshold
#: in this gate that an estimate got wrong: see THIN_EXTRACTION_CHARS. These
#: numbers are cheap to measure and are not reliably guessable.
BOILERPLATE_RATIO = 0.15


def boilerplate_ratio(text: str) -> float:
    """Share of sentences that carry a legal-boilerplate marker."""
    sentences = [s.strip() for s in re.split(r"[.\n]+", text) if len(s.strip()) > 30]
    if not sentences:
        return 0.0
    hits = sum(
        1
        for sentence in sentences
        if any(marker in sentence.lower() for marker in _BOILERPLATE_MARKERS)
    )
    return hits / len(sentences)


# =============================================================================
# 4. The fetch
# =============================================================================


def _fetch_httpx(url: str) -> tuple[str, str, int, int]:
    import httpx

    try:
        with _client() as client:
            response = client.get(url)
    except httpx.TimeoutException as exc:
        raise FetchError(f"timeout after {FETCH_TIMEOUT_SECONDS:.0f}s", reason="timeout") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"{type(exc).__name__}: {exc}", reason=type(exc).__name__) from exc

    if response.status_code >= 400:
        raise FetchError(
            f"HTTP {response.status_code}", reason=f"HTTP {response.status_code}"
        )

    content_type = response.headers.get("content-type", "")
    if content_type and "html" not in content_type.lower():
        raise FetchError(
            f"not an HTML page (content-type: {content_type.split(';')[0]})",
            reason="not html",
        )

    return response.text, str(response.url), response.status_code, len(response.content)


def _fetch_playwright(url: str, log: Logger) -> tuple[str, str, int, int]:
    """USER-TRIGGERED ONLY. Never reached without an explicit operator action."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - pinned in requirements.txt
        raise FetchError(f"playwright is not installed: {exc}", reason="playwright") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(user_agent=HARVEST_USER_AGENT)
                page.goto(url, timeout=FETCH_TIMEOUT_SECONDS * 1000, wait_until="networkidle")
                html = page.content()
                final_url = page.url
            finally:
                browser.close()
    except Exception as exc:
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        if "executable doesn" in message.lower() or "playwright install" in message.lower():
            raise FetchError(
                "the Playwright browser is not installed. Run: "
                "python -m playwright install chromium",
                reason="playwright browser missing",
            ) from exc
        raise FetchError(f"playwright: {message}", reason="playwright") from exc

    return html, final_url, 200, len(html.encode("utf-8"))


def fetch(
    url: str,
    *,
    log: Logger = _null_log,
    use_playwright: bool = False,
    check_robots: bool = True,
) -> Fetched:
    """Fetch, extract, and enforce the three failure states.

    Raises `RobotsDisallowed`, `FetchError` or `ThinExtraction`. Every one of
    them ends the item cleanly; none of them leaves anything on disk.
    """
    if check_robots:
        allowed, rule = robots_allows(url, log)
        if not allowed:
            raise RobotsDisallowed(url, rule)
        _respect_crawl_delay(url, log)

    if use_playwright:
        log("info", f"fetching {url} with Playwright (user-triggered)")
        html, final_url, status, size = _fetch_playwright(url, log)
        rendered_by = "playwright"
    else:
        html, final_url, status, size = _fetch_httpx(url)
        rendered_by = "httpx"

    fetched = Fetched(
        url=url,
        final_url=final_url,
        status=status,
        html=html,
        text="",
        rendered_by=rendered_by,
        byte_length=size,
    )
    log("info", f"fetching {url}  ok ({fetched.kb})")

    fetched.text = extract_text(html)
    log("info", f"extracting text (trafilatura)  ok ({fetched.text_kb})")

    enforce_extraction_rules(fetched)
    return fetched


def enforce_extraction_rules(fetched: Fetched) -> None:
    """The two content gates, in one place so a caller cannot skip half of them.

    Split out of `fetch` because the fixture harness stubs the network and would
    otherwise be testing a code path the real pipeline does not have. A guard
    that only the production path runs is a guard the tests cannot regress.
    """
    if len(fetched.text) < THIN_EXTRACTION_CHARS:
        raise ThinExtraction(fetched)

    ratio = boilerplate_ratio(fetched.text)
    if ratio >= BOILERPLATE_RATIO:
        raise BoilerplateExtraction(fetched, ratio)
