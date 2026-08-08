"""validate_pipeline.py — the Gate 5 failure-table harness.

CLAUDE.md's Gate 5 done-conditions name four things that can only be shown with
deliberately broken fixtures: a bad URL and a malformed-JSON simulation failing
per the failure table, a batch of ten completing with per-URL failures isolated,
and the Harvester's `independence: reject` aborting before a draft is written.

validate.md's self-test pattern is how this project mechanises exactly that:
"the regression fails the same command that runs the real check". This module is
that harness, so those conditions are re-proved on every run rather than
demonstrated once at a gate exit and then trusted forever.

── Fully offline, and deliberately so ────────────────────────────────────────

No API key, no network, no real producer website. The agent client is a scripted
fake and the fetch is stubbed, because a harness that needs the internet is one
that gets skipped the first time a run is slow. The live SEED.md corpus is a
separate exercise; this is the part that must work in a bare clone.

Every fixture writes into a temporary directory. Nothing here touches the real
`_staging`, `_blocked` or `_determinations`, and nothing accumulates.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.pipeline import (  # noqa: E402
    agents,
    fetcher,
    geocode,
    harvest,
    images,
    orchestrator,
    ownership,
)

TODAY = date(2026, 8, 7)


# =============================================================================
# Fakes
# =============================================================================


class _Block:
    def __init__(self, text: str):
        self.text = text


class _Usage:
    def __init__(self, i: int, o: int):
        self.input_tokens = i
        self.output_tokens = o


class _Message:
    def __init__(self, text: str):
        self.content = [_Block(text)]
        self.usage = _Usage(1200, 800)


class FakeClient:
    """Returns scripted responses in order. An exception in the script raises."""

    def __init__(self, script: list[Any]):
        self.script = list(script)
        self.calls = 0
        self.messages = self

    def create(self, **kwargs: Any) -> _Message:
        self.calls += 1
        if not self.script:
            raise AssertionError("fake client ran out of scripted responses")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Message(item)


def harvester_json(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "name": "Fixture Wines",
        "website": "https://fixture.test/",
        "location": {"address": "1 Fixture Road", "suburb": "Basket Range",
                     "state": "SA", "latitude": None, "longitude": None},
        "regions": ["Adelaide Hills"],
        "category": "garagiste",
        "founded_year": 2014,
        "ownership_signals": {"parent_company_mentions": [], "abn": None,
                              "shared_address": None, "shared_contact_domain": None,
                              "statements": ["Owned by the Fixture family since 2014"]},
        "independence": "clear",
        "determinations": {"organic": "practising", "organic_certifier": None,
                           "biodynamic": "none", "biodynamic_certifier": None,
                           "fruit_source": "mixed",
                           "practices": {"wild_ferment": True, "unfined": True,
                                         "unfiltered": False, "minimal_so2": False},
                           "varieties": ["Chardonnay", "Pinot Noir"]},
        "facts": {k: [] for k in orchestrator.HARVESTER_FACT_KEYS},
        "confidence_notes": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


DRAFT_MDX = """---
name: Fixture Wines
category: garagiste
website: https://fixture.test/
location:
  address: 1 Fixture Road
  suburb: Basket Range
  state: SA
regions:
  - adelaide-hills
primary_region: adelaide-hills
cellar_door: by_appointment
organic: practising
biodynamic: none
fruit_source: mixed
practices:
  wild_ferment: true
  unfined: true
  unfiltered: false
  minimal_so2: false
production_band: under_1000
buy_online: false
ships_nationally: false
summary: A garagiste operation at Basket Range working Adelaide Hills fruit.
---

The operation began in 2014 with fruit bought from two growers. The estate block
is a little over a hectare, planted in the 1990s.

Everything else is purchased. Production sits under a thousand cases.
"""


#: What the Architect actually returns: its prompt asks for an
#: `ownership_source` with a `method`, so the model supplies one — on a page
#: stating no ownership at all it still chose `producer_statement`. The field
#: is a PIPELINE_OWNED_FIELD and that value must not survive the stamp.
DRAFT_MDX_CLAIMING_STATEMENT = DRAFT_MDX.replace(
    "name: Fixture Wines\n",
    "name: Fixture Wines\n"
    "ownership_source:\n"
    "  source: https://fixture.test/\n"
    "  method: producer_statement\n"
    "  date: 2026-08-08\n",
)


#: The Architect's real failure on SEED.md row 2, reduced: an unquoted FAQ
#: answer whose own text contains a colon. YAML reads the first `: ` as a key
#: separator, and the document stops parsing there. Kept faithful to what the
#: model actually emitted rather than invented, because the point of the
#: fixture is that this shape occurs unprompted — PROMPTS/architect.md tells
#: the model to use a colon in place of an em dash.
UNPARSEABLE_MDX = DRAFT_MDX.replace(
    "---\n\nThe operation began",
    "faq:\n"
    "  - question: Where does the fruit come from?\n"
    "    answer: Two growers, with one exception: the sparkling fruit is bought in.\n"
    "---\n\nThe operation began",
)


def _stub_fetch(text: str = "x" * 4000, html: str = "<html></html>"):
    """Stub the network, but NOT the content gates.

    The thin and boilerplate rules run here exactly as they do in production,
    via the same function, so a fixture cannot pass by taking a code path the
    real pipeline does not have.
    """

    def fake(url: str, **kwargs: Any) -> fetcher.Fetched:
        fetched = fetcher.Fetched(url=url, final_url=url, status=200, html=html,
                                  text=text, byte_length=len(html))
        fetcher.enforce_extraction_rules(fetched)
        return fetched

    return fake


class Harness:
    """A temporary tree, with every write path redirected into it."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="winemakers-pipeline-"))
        self.staging = self.root / "_staging"
        self.published = self.root / "_published"
        self.blocked = self.root / "_blocked"
        for directory in (self.staging, self.published, self.blocked):
            directory.mkdir(parents=True)
        self._saved: dict[str, Any] = {}

    def __enter__(self) -> "Harness":
        self._saved = {
            "h_staging": harvest.STAGING_DIR,
            "h_published": harvest.PUBLISHED_DIR,
            "o_blocked": ownership.BLOCKED_DIR,
            "fetch": fetcher.fetch,
            "geocode": geocode.geocode,
            "images": images.download_candidates,
        }
        harvest.STAGING_DIR = self.staging
        harvest.PUBLISHED_DIR = self.published
        ownership.BLOCKED_DIR = self.blocked
        fetcher.fetch = _stub_fetch()
        # Neither of these may be reached over the network in a fixture run.
        geocode.geocode = lambda location, **kw: (None, None)
        images.download_candidates = lambda *a, **kw: []
        return self

    def __exit__(self, *exc: Any) -> None:
        harvest.STAGING_DIR = self._saved["h_staging"]
        harvest.PUBLISHED_DIR = self._saved["h_published"]
        ownership.BLOCKED_DIR = self._saved["o_blocked"]
        fetcher.fetch = self._saved["fetch"]
        geocode.geocode = self._saved["geocode"]
        images.download_candidates = self._saved["images"]
        shutil.rmtree(self.root, ignore_errors=True)

    @property
    def drafts(self) -> list[str]:
        return sorted(p.name for p in self.staging.glob("*.mdx"))


# =============================================================================
# The fixtures
# =============================================================================


def _harvest(script: list[Any], url: str = "https://fixture.test/", **kwargs: Any):
    """Run one harvest against a scripted client, capturing the log."""
    lines: list[tuple[str, str]] = []
    agents.set_client(FakeClient(script))
    result = harvest.harvest_one(
        url, log=lambda lvl, msg: lines.append((lvl, msg)), today=TODAY, **kwargs
    )
    return result, lines


def _text(lines: list[tuple[str, str]]) -> str:
    return "\n".join(message for _, message in lines)


def _selftest() -> list[str]:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    # ── Row 1: a bad or unreachable URL ───────────────────────────────────
    with Harness() as h:
        def boom(url: str, **kw: Any):
            raise fetcher.FetchError("timeout after 20s", reason="timeout")
        fetcher.fetch = boom
        result, lines = _harvest([])
        check(result.state == harvest.FAILED, "row 1: a failed fetch did not FAIL")
        check("timeout" in result.detail, "row 1: the reason is not carried on the row")
        check(any(lvl == "error" for lvl, _ in lines), "row 1: no error-level log line")
        check(h.drafts == [], "row 1: a draft was written despite a failed fetch")
        check(not result.offer_playwright,
              "row 1: a timeout offered the Playwright retry, but a browser "
              "cannot reach a host that did not answer")

    # ── Row 1a: a WAF status offers the retry, and only a WAF status ──────
    #    Added 2026-08-09. The narrowness is the point: this row exists so a
    #    Cloudflare 403 is reachable from the hub, not so every fetch failure
    #    grows a button.
    for status, offered in ((403, True), (503, True), (404, False), (500, False)):
        with Harness() as h:
            def refused(url: str, _status: int = status, **kw: Any):
                raise fetcher.FetchError(
                    f"HTTP {_status}", reason=f"HTTP {_status}", status=_status
                )
            fetcher.fetch = refused
            result, lines = _harvest([])
            check(result.state == harvest.FAILED, f"row 1a: HTTP {status} did not FAIL")
            check(h.drafts == [], f"row 1a: a draft was written on HTTP {status}")
            check(
                result.offer_playwright is offered,
                f"row 1a: HTTP {status} "
                + ("did not offer" if offered else "offered")
                + " the Playwright retry",
            )

    # A block that survived Playwright must not offer Playwright again.
    with Harness() as h:
        def still_refused(url: str, **kw: Any):
            raise fetcher.FetchError("HTTP 403", reason="HTTP 403", status=403)
        fetcher.fetch = still_refused
        result, _ = _harvest([], use_playwright=True)
        check(not result.offer_playwright,
              "row 1a: a 403 through Playwright offered Playwright again")

    # ── Row 2: robots.txt disallows ───────────────────────────────────────
    with Harness() as h:
        def disallowed(url: str, **kw: Any):
            raise fetcher.RobotsDisallowed(url, "Disallow matching /")
        fetcher.fetch = disallowed
        result, lines = _harvest([])
        check(result.state == harvest.FAILED, "row 2: a robots disallow did not FAIL")
        check("robots.txt" in _text(lines), "row 2: robots.txt is not named in the log")
        check(not result.offer_playwright,
              "row 2: a robots disallow must offer NO retry path")
        check(h.drafts == [], "row 2: a draft was written despite a disallow")

    # ── Row 3: thin page offers the user-triggered Playwright retry ───────
    with Harness() as h:
        def thin(url: str, **kw: Any):
            raise fetcher.ThinExtraction(
                fetcher.Fetched(url=url, final_url=url, status=200, html="", text="x" * 220)
            )
        fetcher.fetch = thin
        result, lines = _harvest([])
        check(result.state == harvest.FAILED, "row 3: a thin page did not end the item")
        check(result.offer_playwright, "row 3: Playwright retry was not offered")
        check("thin extraction: 220 chars" in _text(lines),
              "row 3: the log does not state the character count")
        check(h.drafts == [], "row 3: a draft was written from a thin page")

    # ── Off-site redirect: never publish one business as another ──────────
    #    Found live: citywinery.com.au now 301s to dietpills.com.au.
    with Harness() as h:
        def redirected(url: str, **kw: Any):
            raise fetcher.OffSiteRedirect(url, "https://www.dietpills.com.au/post/x")
        fetcher.fetch = redirected
        result, lines = _harvest([harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check(result.state == harvest.FAILED, "off-site redirect: did not FAIL")
        check(h.drafts == [],
              "off-site redirect: A DRAFT WAS WRITTEN FROM ANOTHER BUSINESS'S SITE")
        check("dietpills" in _text(lines), "off-site redirect: the log does not name where it went")

    # A same-site redirect must still be followed without complaint.
    check(fetcher.same_business("https://example.com.au/", "https://www.example.com.au/about"),
          "off-site redirect: an apex-to-www redirect was treated as off-site")
    check(not fetcher.same_business("https://a.com.au/", "https://b.com.au/"),
          "off-site redirect: a genuine change of domain was allowed")

    # ── Boilerplate: a privacy policy must never become a producer ────────
    #    Not a UX.md §1.5 row. Added at Gate 5 against d'Arenberg's homepage,
    #    which extracts to 9,039 characters of privacy policy and no winery.
    with Harness() as h:
        legal = (
            "This privacy policy sets out how we use and protect any personal "
            "information that you give us when you use this website. "
            "We may update our Privacy Policy from time to time. "
            "We collect personal information in accordance with data protection law. "
            "We do not sell your personal information to third parties. "
            "These terms and conditions are governed by the laws of South Australia. "
        ) * 6
        fetcher.fetch = _stub_fetch(text=legal)
        result, lines = _harvest([harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check(result.state == harvest.FAILED,
              "boilerplate: a privacy-policy extraction did not FAIL")
        check(h.drafts == [], "boilerplate: A DRAFT WAS WRITTEN FROM A PRIVACY POLICY")
        check("boilerplate" in _text(lines).lower(),
              "boilerplate: the log does not say why")
        check(not result.offer_playwright,
              "boilerplate: Playwright was offered, but the page rendered fine "
              "and the fix is a different URL")

    # Producer prose that merely mentions a privacy policy must NOT trip it.
    with Harness() as h:
        prose = (
            "The estate block is a little over a hectare of chardonnay, planted in "
            "the 1990s on ironstone over clay. Everything else is purchased fruit. "
            "Fermentation is spontaneous and the wines are bottled without fining. "
            "Production sits under a thousand cases a year. "
        ) * 8 + "See our privacy policy for how we handle your personal information."
        fetcher.fetch = _stub_fetch(text=prose)
        result, _ = _harvest([harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check(result.state == harvest.STAGED,
              "boilerplate: a false positive on producer prose mentioning a privacy policy")

    # ── Row 4: malformed agent JSON, one re-ask, then saved and reported ──
    with Harness() as h:
        result, lines = _harvest(["this is not json", "still not json"])
        check(result.state == harvest.FAILED, "row 4: malformed JSON did not FAIL")
        check("re-asking once" in _text(lines), "row 4: no re-ask was logged")
        check("failed/" in _text(lines), "row 4: the raw output path was not logged")
        check(h.drafts == [], "row 4: a draft was written from malformed JSON")

    # A malformed FIRST response that parses on the re-ask must recover.
    with Harness() as h:
        result, lines = _harvest(["not json", harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check(result.state == harvest.STAGED,
              "row 4: a recovered re-ask did not produce a draft")

    # Row 4 again, for the ARCHITECT's MDX rather than the Harvester's JSON.
    #
    # These were separate paths until 2026-08-08: the Architect was called with
    # an identity `validate` and its output parsed afterwards, so the content
    # tier never saw the error and the re-ask never fired. The stage that emits
    # the most text was the one stage with no second chance. SEED.md row 2 hit
    # it on a real page and failed the whole URL on one unquoted colon, which
    # is the exact shape of the fixture below.
    with Harness() as h:
        result, lines = _harvest([harvester_json(), UNPARSEABLE_MDX, UNPARSEABLE_MDX])
        check(result.state == harvest.FAILED, "row 4: unparseable MDX did not FAIL")
        check("re-asking once" in _text(lines),
              "row 4: THE ARCHITECT DID NOT RE-ASK on unparseable MDX")
        check("failed/" in _text(lines), "row 4: the raw MDX path was not logged")
        check(h.drafts == [], "row 4: a draft was written from unparseable MDX")

    with Harness() as h:
        result, lines = _harvest([harvester_json(), UNPARSEABLE_MDX, DRAFT_MDX, DRAFT_MDX])
        check(result.state == harvest.STAGED,
              "row 4: an Architect re-ask that parsed did not produce a draft")

    # ── Row 5: name null is not an error state ────────────────────────────
    with Harness() as h:
        result, lines = _harvest([harvester_json(name=None,
                                                 confidence_notes=["This is a retailer."])])
        check(result.state == harvest.FAILED, "row 5: a non-producer page did not end")
        check("could not identify a wine producer" in _text(lines),
              "row 5: the log does not use the documented wording")
        check("This is a retailer." in _text(lines),
              "row 5: confidence_notes were not surfaced")
        check(h.drafts == [], "row 5: a draft was written for a non-producer page")

    # ── Row 7: the Harvester's reject aborts BEFORE a draft is written ────
    #    This is a named Gate 5 done-condition.
    with Harness() as h:
        # The Architect and Gatekeeper responses are scripted DELIBERATELY, even
        # though a correct pipeline never reaches them. If the abort regresses,
        # the run must get far enough to write a draft so the assertion that
        # fires is "a draft was written" and not "the fake ran out of script".
        # A harness whose failure message names the wrong thing costs an hour.
        result, lines = _harvest([
            harvester_json(
                independence="reject",
                ownership_signals={"parent_company_mentions": ["A division of Example Group"],
                                   "abn": None, "shared_address": None,
                                   "shared_contact_domain": None,
                                   "statements": ["Part of the Example Group"]},
            ),
            DRAFT_MDX,
            DRAFT_MDX,
        ])
        check(result.state == harvest.BLOCKED, "row 7: a Harvester reject did not BLOCK")
        check(h.drafts == [], "row 7: A DRAFT WAS WRITTEN DESPITE independence: reject")
        check(list(h.blocked.glob("*.json")), "row 7: no blocked record was written")
        check(any(lvl == "error" for lvl, _ in lines), "row 7: no error-level log line")
        # UX.md §1.5 row 7 asks for the first statement quoted, not just counted.
        # The reader of that log is deciding whether the reject was right, and a
        # count tells them nothing. This assertion is here because the line read
        # `row.get("values")` where signal_rows emits `items`, so it silently
        # printed nothing at all from the day it was written.
        check(
            any('first signal: "A division of Example Group"' in msg for _, msg in lines),
            "row 7: the first extracted signal was not quoted in the log",
        )

    # ── Row 8: an ownership check writes the draft and flags it ───────────
    with Harness() as h:
        result, lines = _harvest([
            harvester_json(independence="check"), DRAFT_MDX, DRAFT_MDX
        ])
        check(result.state == harvest.STAGED, "row 8: a check verdict did not stage a draft")
        check("OWNERSHIP: CHECK" in _text(lines),
              "row 8: the save line does not carry OWNERSHIP: CHECK")
        # `<slug>.ownership.json` beside the draft; `<slug>.json` only once the
        # approve action retains it into DETERMINATIONS_DIR (Gate 4 convention).
        check((h.staging / "fixture-wines.ownership.json").is_file(),
              "row 8: no determination sidecar was written beside the draft")

    # ── Silence is not independence ───────────────────────────────────────
    #
    # A page that says nothing about who owns it. Every deny-list row is clean
    # and no signal escalates, which until 2026-08-08 returned `clear` — a
    # positive finding resting on nothing, and the reading SCHEMA.md §4.2, this
    # module's docstring and the ownership-check skill all forbid: "a source
    # that merely fails to mention a parent is not evidence of absence".
    #
    # This is the Wolf Blass shape without the deny-list entry. SEED.md row 1
    # is caught by the register; a portfolio label not yet in it, on an equally
    # silent site, was publishable as independent. SEED.md row 3 found it.
    with Harness() as h:
        silent = {"parent_company_mentions": [], "abn": None, "shared_address": None,
                  "shared_contact_domain": None, "statements": []}
        result, lines = _harvest([
            harvester_json(ownership_signals=silent),
            DRAFT_MDX_CLAIMING_STATEMENT, DRAFT_MDX_CLAIMING_STATEMENT,
        ])
        check(result.state == harvest.STAGED,
              "silence: the draft was not written for a human to complete")
        check(result.determination.verdict == "check",
              "SILENCE WAS READ AS INDEPENDENCE: a source stating no ownership "
              f"returned {result.determination.verdict!r}, not 'check'")
        # And the provenance must not claim evidence that was never extracted.
        # DRAFT_MDX carries an `ownership_source` naming `producer_statement`,
        # because the Architect's prompt asks it for a method and the model
        # supplies one. `ownership_source` is a PIPELINE_OWNED_FIELD, so that
        # value must be overwritten, not deferred to. Observed on SEED.md row 3,
        # where the first fix left the Architect's invented method standing.
        staged = (h.staging / "fixture-wines.mdx").read_text(encoding="utf-8")
        check("producer_statement" not in staged,
              "SILENCE: the draft claims a producer_statement that does not "
              "exist. An agent's ownership_source survived the pipeline stamp.")
        blocks = ownership.approval_blocks(
            {"parent_company": None}, {"verdict": "check"}
        )
        check(any("ownership_source" in block for block in blocks),
              "silence: approval is not blocked on the missing ownership_source")

    # The positive case the 2026-08-07 amendment exists to protect must still
    # reach `clear`, or the fix above has simply re-broken it the other way.
    with Harness() as h:
        result, lines = _harvest([harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check(result.determination.verdict == "clear",
              "a statement naming the owners no longer reaches 'clear'")

    # ── Row 9: slug collision halts before drafting ───────────────────────
    with Harness() as h:
        (h.published / "fixture-wines.mdx").write_text("---\nname: x\n---\n", encoding="utf-8")
        result, lines = _harvest([harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check(result.state == harvest.SKIPPED, "row 9: a slug collision did not SKIP")
        check("_published" in _text(lines), "row 9: the log does not say where it exists")
        check(h.drafts == [], "row 9: a draft was written over a collision")

    # ── Row 11: an unmatched variety is reported, never silently dropped ──
    with Harness() as h:
        result, lines = _harvest([
            harvester_json(determinations={
                "organic": "none", "organic_certifier": None,
                "biodynamic": "none", "biodynamic_certifier": None,
                "fruit_source": "estate",
                "practices": {k: False for k in orchestrator.PRACTICE_KEYS},
                "varieties": ["Chardonnay", "Invented Grape"],
            }),
            DRAFT_MDX, DRAFT_MDX,
        ])
        check(result.state == harvest.STAGED, "row 11: the draft was not written")
        check('unmatched variety: "Invented Grape"' in _text(lines),
              "row 11: the unmatched variety was not logged")
        check(result.unmatched.get("varieties") == ["Invented Grape"],
              "row 11: the unmatched value is not carried to the review pane")

    # Row 11 must fire for a grape that is genuinely absent, and must NOT fire
    # for one whose only difference from its key is a diacritic. The §1 slugs
    # are ASCII, so an accented spelling has to fold to the same key. Until
    # 2026-08-08 `slugify` swept accents into hyphens, so `Albariño` became
    # `albari-o` and five varieties already in the vocabulary were unreachable
    # by their correct names — reported as unmatched and dropped from the
    # field, which is how a producer's actual varieties disappear.
    for spelling, key in (
        ("Albariño", "albarino"),
        ("Gewürztraminer", "gewurztraminer"),
        ("Grüner Veltliner", "gruner-veltliner"),
        ("Pedro Ximénez", "pedro-ximenez"),
        ("Blaufränkisch", "blaufrankisch"),
        # Already ASCII, and must stay working.
        ("Nero d'Avola", "nero-davola"),
    ):
        got = orchestrator.slugify(spelling)
        check(got == key, f"slugify({spelling!r}) is {got!r}, not the vocabulary key {key!r}")
        check(key in orchestrator.VARIETY_KEYS,
              f"fixture is stale: {key!r} is no longer a variety key")

    # ── Certification integrity: certified with no certifier is downgraded ─
    with Harness() as h:
        result, lines = _harvest([
            harvester_json(determinations={
                "organic": "certified", "organic_certifier": None,
                "biodynamic": "none", "biodynamic_certifier": None,
                "fruit_source": "estate",
                "practices": {k: False for k in orchestrator.PRACTICE_KEYS},
                "varieties": [],
            }),
            DRAFT_MDX, DRAFT_MDX,
        ])
        check(result.state == harvest.STAGED, "certification: the draft was not written")
        text = (h.staging / "fixture-wines.mdx").read_text(encoding="utf-8")
        check("organic: practising" in text,
              "certification: `certified` with no named certifier was NOT downgraded")
        check("no named certifier" in _text(lines),
              "certification: the downgrade was not logged")

    # ── Token usage appears in the log (a named done-condition) ───────────
    with Harness() as h:
        result, lines = _harvest([harvester_json(), DRAFT_MDX, DRAFT_MDX])
        check("tokens in/out:" in _text(lines), "token usage did not appear in the log")
        check(result.ledger is not None and result.ledger.total().input_tokens > 0,
              "the ledger recorded no input tokens")

    # ── The Gatekeeper failing must not cost the producer ─────────────────
    with Harness() as h:
        result, lines = _harvest([harvester_json(), DRAFT_MDX, "not mdx at all", "still not"])
        check(result.state == harvest.STAGED,
              "a Gatekeeper failure lost the draft; the Architect's copy was usable")
        check("staging the unpolished draft" in _text(lines),
              "the Gatekeeper fallback was not logged")

    return errors


def _batch_selftest() -> list[str]:
    """Ten URLs, mixed outcomes, per-URL isolation (Gate 5 done-condition)."""
    from admin.pipeline import queue as queue_module

    errors: list[str] = []
    with Harness() as h:
        urls = [f"https://fixture{i}.test/" for i in range(10)]

        # Two bad ones: index 3 fetch-fails, index 7 returns unusable JSON.
        real_stub = _stub_fetch()

        def selective(url: str, **kw: Any):
            if url == urls[3]:
                raise fetcher.FetchError("HTTP 404", reason="HTTP 404")
            return real_stub(url, **kw)

        fetcher.fetch = selective

        script: list[Any] = []
        for index in range(10):
            if index == 3:
                continue  # never reaches an agent
            if index == 7:
                script += ["not json", "still not json"]
            else:
                script += [harvester_json(name=f"Fixture {index} Wines"), DRAFT_MDX, DRAFT_MDX]
        agents.set_client(FakeClient(script))

        lines: list[str] = []
        q = queue_module.HarvestQueue(path=h.root / "queue.json")
        q.add(urls)
        q.run_sync(log=lambda lvl, msg: lines.append(msg), today=TODAY)

        states = [item["state"] for item in q.items]
        staged = states.count("STAGED")
        failed = states.count("FAILED")

        if staged != 8:
            errors.append(f"batch: expected 8 staged from 10 with 2 bad URLs, got {staged}")
        if failed != 2:
            errors.append(f"batch: expected 2 failed, got {failed}")
        if len(h.drafts) != 8:
            errors.append(f"batch: {len(h.drafts)} draft files on disk, expected 8")
        if q.items[3]["state"] != "FAILED":
            errors.append("batch: the fetch-failing URL did not fail on its own row")
        if q.items[7]["state"] != "FAILED":
            errors.append("batch: the malformed-JSON URL did not fail on its own row")
        if any(item["state"] == "QUEUED" for item in q.items):
            errors.append("batch: a failure stopped the run; items were left QUEUED")

        # Durability: the queue must survive being reloaded from disk.
        reloaded = queue_module.HarvestQueue(path=h.root / "queue.json")
        reloaded.load()
        if [i["state"] for i in reloaded.items] != states:
            errors.append("batch: queue state did not survive a reload from disk")

    return errors


def main() -> int:
    try:
        errors = _selftest() + _batch_selftest()
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        errors = [f"harness raised {exc!r}"]

    if errors:
        print(f"PIPELINE FIXTURES FAIL — {len(errors)} issue(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    print(
        "PIPELINE FIXTURES PASS — failure table rows 1, 1a, 2, 3, 4, 5, 7, 8, 9 and 11, "
        "boilerplate refusal both ways, off-site redirect refusal, certification "
        "downgrade, token ledger, "
        "Gatekeeper fallback, and a ten-URL batch with two isolated failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
