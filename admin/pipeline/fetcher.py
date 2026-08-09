"""fetcher.py — fetching, extraction, and the three ways a fetch ends badly.

Gate 5. TRD.md §7.6, UX.md §1.5 rows 1, 1a, 2 and 3.

── The posture ───────────────────────────────────────────────────────────────

SEED.md's ethics note is the design brief for this module: *"These sites are
being read, not scraped at volume."* One request at a time, a user agent that
identifies the project and links its methodology page, `robots.txt` honoured
with no override control anywhere in the system, and a 20 second ceiling.

── Playwright is not a fallback this module ever chooses ─────────────────────

`fetch(url, use_playwright=True)` exists and is only ever reached from a control
the operator clicks (UX.md §1.5 rows 3 and 1a). Nothing here escalates to it
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


#: UX.md §1.5 row 1a: the statuses a WAF returns to a plain HTTP client that a
#: real browser fetch can clear. Deliberately short. A timeout, a 404 and a 500
#: are absent because Playwright cannot reach a page that is unreachable, fix one
#: that is missing, or repair one that is broken, and a retry control that cannot
#: work costs a reviewer a browser launch to learn nothing.
PLAYWRIGHT_CLEARABLE_STATUSES = frozenset({403, 503})

#: How long to keep waiting for the network to fall quiet after the document has
#: parsed. A ceiling, not a target: whatever has rendered when it expires is what
#: gets extracted.
PLAYWRIGHT_SETTLE_MS = 3_000


class FetchError(Exception):
    """UX.md §1.5 row 1. Carries the HTTP status or the word `timeout`."""

    def __init__(self, message: str, *, reason: str = "", status: int | None = None):
        super().__init__(message)
        self.reason = reason or message
        #: The HTTP status when the failure carried one, else None. Row 1a reads
        #: this to decide whether the row may offer the Playwright retry.
        self.status = status


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


class OffSiteRedirect(Exception):
    """The URL asked for and the URL served are different businesses.

    FOUND LIVE, and it is the most dangerous thing in this module.
    `citywinery.com.au` — an urban winery considered as a SEED fixture — now
    301s to `dietpills.com.au`. httpx followed it, the fetch reported success,
    and the extraction was a weight-loss article. Nothing downstream would have
    known: the Harvester would have been handed that text and told it came from
    citywinery.com.au.

    A lapsed domain that has been resold is exactly the case this catches, and
    the failure mode it prevents is the worst one available to this project:
    publishing another party's content as a named producer's own.

    Redirects WITHIN a registrable domain are normal and are followed silently
    (http to https, apex to www, a moved path). Only a change of business is an
    error.
    """

    def __init__(self, url: str, final_url: str):
        super().__init__(
            f"redirected off-site: {urlparse(url).netloc} -> {urlparse(final_url).netloc}"
        )
        self.url = url
        self.final_url = final_url


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


def registrable(host: str) -> str:
    """`shop.example.com.au` -> `example.com.au`. Enough to compare businesses."""
    parts = [part for part in host.lower().split(".") if part]
    if len(parts) <= 2:
        return ".".join(parts)
    if parts[-1] == "au" and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_business(url: str, final_url: str) -> bool:
    left = registrable(urlparse(url).netloc)
    right = registrable(urlparse(final_url).netloc)
    return not left or not right or left == right


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


#: An `ABN` label, then eleven digits that may be spaced or hyphenated in any of
#: the groupings operators actually use (`12 345 678 901`, `12-345-678-901`).
#: Anchored on the label because a bare eleven-digit run is as likely to be a
#: phone number or a liquor licence.
_ABN_LABELLED = re.compile(r"\bA\.?B\.?N\.?\b[^0-9]{0,12}((?:\d[\s\-]{0,2}){11})", re.I)

#: `PROMPTS/harvester.md` tells the Harvester to read the ABN off "the footer,
#: the copyright line, the terms of sale". `extract_text` deletes all three:
#: boilerplate removal is trafilatura's whole job and `favour_precision=True`
#: makes it keener. The model was being asked for something already thrown away,
#: and across 97 staged drafts it returned an ABN zero times while producers
#: publish them in plain sight.
#:
#: So the ABN is read here, from the raw HTML, by rule rather than by model. It
#: is a checksummed identifier, not prose — a regex plus the ABR's own modulus
#: test cannot hallucinate one, which is the ownership-check skill's "never
#: guess an ABN" honoured rather than merely hoped for.
_ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)

_TAGS = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.I | re.S)


def valid_abn(digits: str) -> bool:
    """The ABR's published modulus-89 check.

    Subtract one from the leading digit, weight all eleven, and the sum is
    divisible by 89. It rejects roughly 98% of arbitrary eleven-digit runs, so
    it is what lets a page's phone number and its ABN be told apart.
    """
    if len(digits) != 11 or not digits.isdigit():
        return False
    weighted = (int(digits[0]) - 1) * _ABN_WEIGHTS[0]
    weighted += sum(int(d) * w for d, w in zip(digits[1:], _ABN_WEIGHTS[1:]))
    return weighted % 89 == 0


def find_abns(html: str) -> list[str]:
    """Every checksum-valid ABN printed in the page, in order, deduplicated.

    Reads the raw HTML rather than the extraction, because the footer and the
    terms of sale are exactly what the extraction removes. Tags are stripped
    first so that an ABN split across `<span>`s still reads as one number.
    """
    if not html:
        return []
    plain = _TAGS.sub(" ", html)
    found: list[str] = []
    for match in _ABN_LABELLED.finditer(plain):
        digits = re.sub(r"\D", "", match.group(1))
        if valid_abn(digits) and digits not in found:
            found.append(digits)
    return found


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
            f"HTTP {response.status_code}",
            reason=f"HTTP {response.status_code}",
            status=response.status_code,
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
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - pinned in requirements.txt
        raise FetchError(f"playwright is not installed: {exc}", reason="playwright") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(user_agent=HARVEST_USER_AGENT)
                page.goto(
                    url,
                    timeout=FETCH_TIMEOUT_SECONDS * 1000,
                    wait_until="domcontentloaded",
                )
                # `networkidle` is the best case here and never a requirement.
                # It cannot fire on a page that holds a connection open, which
                # covers anything streaming server-sent events, and it stalls
                # behind slow third-party embeds. Give it a bounded budget and
                # take whatever has rendered when that budget runs out: the
                # alternative is failing a page that had already loaded.
                try:
                    page.wait_for_load_state("networkidle", timeout=PLAYWRIGHT_SETTLE_MS)
                except PlaywrightTimeout:
                    log("info", "playwright: network still open, taking the rendered page")
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

    if not same_business(url, final_url):
        raise OffSiteRedirect(url, final_url)

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
