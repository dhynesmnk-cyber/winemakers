"""ownership.py — the independence determination. Gate 4.

SCHEMA.md §4 is the contract; this module carries it out. It has no analogue in
the reference build, and it is the reason the site exists: the word doing the
work in "a field guide to independent Australian winemakers" is *independent*,
and this is the only place that word is decided.

── The first principle ───────────────────────────────────────────────────────

**Independence is an ownership fact. It is never inferred from prose**
(CLAUDE.md rule 8, SCHEMA.md §4). Corporate portfolio brands are engineered to
read as small and independent — that is their design brief and they are good at
it — while a genuinely independent producer with a thin website may read as
corporate. Any test based on tone fails systematically in both directions.

Nothing in this module reads marketing copy. It compares names, domains and
ABNs against a hand-maintained register, and it counts the ownership signals the
Harvester extracted. Signals are *weighed*, never *judged*: an escalating signal
moves the verdict to `check`, which is a request for a human, not a finding.

**Amended 2026-08-07 (Gate 5), signed off.** Until this date *any* populated
signal escalated to `check`. That made `clear` structurally unreachable, because
`PROMPTS/harvester.md` instructs the `statements` key to capture ownership
claims *in either direction* — so a page that positively named its owning family
populated `statements` and was escalated for it. The evidence a reviewer is told
to look for (SCHEMA.md §4.2 route 2, "it must positively state ownership") was
the same thing that forced the review. Basket Range Wine was the case that
exposed it: three clean deny-list rows, no ABN, and one quoted sentence naming
the Brodericks. `SEED.md` row 4 had predicted `clear` before the code existed.

The five keys are now partitioned by `ESCALATING_SIGNAL_KEYS`. Four of them are
signals of a *concealed* relationship and still escalate alone. `statements` is
bidirectional, so it escalates only when `statements_name_a_group` finds group
phrasing in it. All five are still extracted, still rendered and still written
to the sidecar — nothing stops being evidence, and a reviewer sees every row.

Three things keep the old rule's protection. The Harvester's own `check` still
tightens and never relaxes, and its prompt already routes silence and a family
claim naming nobody to `check`. `ownership_source` is still required before
approval on a `clear` (UX.md §1.4.5 rule 3). And `statements_name_a_group` is a
fixed lexicon in code, so the guard against a misfiled "part of the X group" is
deterministic — CLAUDE.md rule 8 holds, because no agent judges anything here.

`SEED.md` row 1 is the proof the deny-list has to exist. The Wolf Blass site
names no parent company anywhere — not in the footer, not in the copyright line.
Its only corporate trace is the trading entity in the terms of sale. A
tone-based test passes that site comfortably. Only the deny-list rejects it, and
Gate 4 requires it to do so three ways independently: by name, by domain, and by
the ABN in `data/ownership.json`.

── The three checks are independent, always ──────────────────────────────────

`deny_list_check` always returns exactly three rows — name, domain and ABN —
whether they hit or not (UX.md §1.4.2). They are never collapsed into one
combined test: Gate 4's done-condition requires each path to work on its own,
and a reviewer has to be able to see which one fired.

── Exact versus contained name matches ───────────────────────────────────────

An **exact** normalised name match carries the record's own verdict. A
**contained** match — the deny-list label appears as a whole-word run inside a
longer producer name — is floored to `check` and never rejects.

That asymmetry is deliberate, and it is SCHEMA.md §4.3's own reasoning applied
one level down: a false positive here silently blocks a genuinely independent
producer and nobody ever finds out. `check` still cannot auto-publish, so a
contained match costs a reviewer thirty seconds rather than costing a real
business its entry.

Containment is disabled for short single-word labels (see
`_MIN_CONTAINED_CHARS`), and — the register's own standing instruction — a
contained match is suppressed when the matched label is a **place name carried
in `regions.ts`**. `Tatachilla` is both a Vinarchy label and a McLaren Vale
locality; `Stanley` is a Vinarchy label and a Beechworth town. "Name matching
must not fire on the place", so it does not. An *exact* match still fires,
because a producer trading under exactly that name is the label, not the place.

Matching is on the producer's `name` field, never on free text, so a place name
in a body paragraph cannot fire anything either way.

── What this module will not do ──────────────────────────────────────────────

It never edits `data/ownership.json` (UX.md §1.4.5 rule 7). It never sets a
verdict of `clear` on the strength of silence — absence from the register means
unchecked, not cleared, and the register's own header says so. It never decides
alone: `determine` produces a verdict and the evidence behind it, and a person
records the source and approves (SCHEMA.md §4.5).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    BLOCKED_DIR,
    DETERMINATIONS_DIR,
    OWNERSHIP_JSON_PATH,
    STAGING_DIR,
)

# =============================================================================
# 1. Vocabulary
# =============================================================================

#: SCHEMA.md §4.5. The only three verdicts, weakest block to strongest.
VERDICTS = ("clear", "check", "reject")

#: Ordering so a combination of hits resolves to the strongest block present.
_VERDICT_RANK = {verdict: index for index, verdict in enumerate(VERDICTS)}

#: SCHEMA.md §5's `ownership_signals` keys, in the order UX.md §1.4.2 tables
#: them. Every row renders, including the empty ones: the absence of signals is
#: itself a finding the reviewer needs to see, and it is explicitly NOT evidence
#: of independence (UX.md §1.4.5).
SIGNAL_KEYS = (
    "parent_company_mentions",
    "abn",
    "shared_address",
    "shared_contact_domain",
    "statements",
)

#: Which of the five escalate to `check` on their own. Amended 2026-08-07, see
#: the module docstring for why and for what still holds the line.
#:
#: Each of these four is a signal of a relationship the page is not stating
#: plainly: a named group, an address shared with another label, a contact
#: address on someone else's domain, an ABN that will not parse. None of them
#: has an innocent reading that a reviewer should not see.
#:
#: `statements` is deliberately absent. It is the one bidirectional key —
#: "part of the X group" and "owned by the Broderick family since 1980" both
#: land in it — so escalating on its mere presence penalises exactly the
#: evidence SCHEMA.md §4.2 asks for. It escalates via `statements_name_a_group`
#: instead, and it is still rendered, resolvable and retained either way.
ESCALATING_SIGNAL_KEYS = (
    "parent_company_mentions",
    "abn",
    "shared_address",
    "shared_contact_domain",
)

#: The nouns that make a relationship corporate rather than familial. Used to
#: qualify the ambiguous stems below.
_GROUP_TERM = (
    r"(?:group|portfolio|holdings?|compan(?:y|ies)|corporation|conglomerate|"
    r"pty\.?\s*l(?:td|imited)|proprietary|brands|estates|partners|"
    r"investors?|investment|capital|equity|consortium)"
)

#: The deterministic guard on `statements`. Fixed patterns, matched
#: case-insensitively against each extracted statement.
#:
#: This is not a tone test and it is not an agent reading prose (CLAUDE.md rule
#: 8). It is a fixed list of the phrasings by which a corporate relationship is
#: actually written down, and it exists for one failure: a Harvester that files
#: "part of the Treasury portfolio" under `statements` rather than under
#: `parent_company_mentions`. Before the 2026-08-07 amendment the any-signal
#: rule caught that misfiling by accident. This catches it on purpose.
#:
#: The ambiguous stems are **qualified, never bare**. "Owned by" and "part of"
#: are the two commonest openings of a positive family-ownership statement —
#: "owned by the Broderick family" — so matching them on their own would
#: reintroduce the very penalty this amendment removes. They fire only when a
#: `_GROUP_TERM` follows within the same clause. "Family" is deliberately not a
#: group term: a family is who the strict rule is trying to publish, and a
#: family *group* is caught by the register, which is where an ownership fact
#: belongs (SCHEMA.md §4.1).
PARENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # Unambiguous on their own — no innocent reading in a producer's own copy.
        r"\bsubsidiar(?:y|ies)\b",
        r"\bparent\s+(?:company|group|entity)\b",
        r"\bdivision\s+of\b",
        r"\bacquir(?:ed|ition)\s+by\b",
        r"\b(?:majority|minority)\s+(?:stake|shareholding|interest|owner)",
        r"\bshareholding\b",
        r"\bjoint\s+venture\b",
        r"\bunder\s+the\s+umbrella\b",
        r"\bwholly[\s-]owned\b",
        r"\bgroup\s+of\s+companies\b",
        # Qualified stems — the group term must follow within the clause.
        rf"\bpart\s+of\s+(?:the\s+)?[\w'’&.\s-]{{0,40}}?{_GROUP_TERM}\b",
        rf"\bowned\s+by\s+(?:the\s+)?[\w'’&.\s-]{{0,40}}?{_GROUP_TERM}\b",
        rf"\bmember\s+of\s+(?:the\s+)?[\w'’&.\s-]{{0,40}}?{_GROUP_TERM}\b",
        rf"\bbelongs\s+to\s+(?:the\s+)?[\w'’&.\s-]{{0,40}}?{_GROUP_TERM}\b",
        rf"\bbacked\s+by\s+(?:the\s+)?[\w'’&.\s-]{{0,40}}?{_GROUP_TERM}\b",
        rf"\bportfolio\s+of\s+[\w'’&.\s-]{{0,40}}?(?:wines?|brands|labels|estates)\b",
    )
)

#: How each signal is named in copy. Lives here beside the keys rather than
#: being derived at the template, so the approval-block message and the panel
#: heading call the same row the same thing.
SIGNAL_LABELS = {
    "parent_company_mentions": "parent company mentions",
    "abn": "ABN",
    "shared_address": "shared address",
    "shared_contact_domain": "shared contact domain",
    "statements": "statements",
}

#: UX.md §1.4.3's three resolutions. `Explained` and `Confirms a parent` require
#: a note; `Not relevant` may be recorded without one.
RESOLUTIONS = ("explained", "confirms_parent", "not_relevant")
RESOLUTION_LABELS = {
    "explained": "Explained",
    "confirms_parent": "Confirms a parent",
    "not_relevant": "Not relevant",
}
RESOLUTIONS_REQUIRING_NOTE = ("explained", "confirms_parent")

#: Which of a record's list fields a match came from. Ordered strongest first,
#: because `check_name` reports the first list that hits.
_NAME_FIELDS = ("labels", "aliases", "parent")

#: How each check is named on screen. `ABN` is an initialism and is never
#: lower-cased in copy (UX.md §1.4.2's own deny-list block spells it `ABN`).
CHECK_LABELS = {"name": "name", "domain": "domain", "abn": "ABN"}

#: A contained name match needs this many characters before it is allowed to
#: fire, unless the label is more than one word. `Stanley` (7) is below it and
#: can only ever match exactly; `Wolf Blass` is two words and matches either
#: way. Tuned against the register's own two named traps, not guessed.
_MIN_CONTAINED_CHARS = 8

#: `site/src/data/regions.ts` is the site's taxonomy and the only home of the
#: region, subregion and town vocabulary. It is parsed rather than mirrored, so
#: there is no fourth hand-kept copy to drift — the same posture
#: `validate_content.py` takes.
_REGIONS_TS = Path(__file__).resolve().parents[2] / "site" / "src" / "data" / "regions.ts"

_TS_NAME = re.compile(r'\bname:\s*"([^"]+)"')
_TS_TOWNS = re.compile(r"\btowns:\s*\[([^\]]*)\]", re.DOTALL)
_TS_STRING = re.compile(r'"([^"]+)"')


def _place_names() -> frozenset[str]:
    """Every region, subregion and town name in `regions.ts`, normalised.

    The register's standing instruction, verbatim: "Name matching must not fire
    on the place." This is the data that makes that enforceable rather than a
    comment — a locality is a locality because the taxonomy says so, not because
    someone remembered to special-case it.
    """
    try:
        text = _REGIONS_TS.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    names = set(_TS_NAME.findall(text))
    for block in _TS_TOWNS.findall(text):
        names.update(_TS_STRING.findall(block))
    return frozenset(filter(None, (normalise_name(name) for name in names)))


_PLACES: frozenset[str] | None = None


def place_names() -> frozenset[str]:
    """`_place_names`, read once. Cached because `check_name` calls it per label."""
    global _PLACES
    if _PLACES is None:
        _PLACES = _place_names()
    return _PLACES


# =============================================================================
# 2. Normalisation
#
# All three checks compare normalised values. The normalisers are deliberately
# blunt — they fold case, strip punctuation and drop the legal-entity tail — and
# they never stem, never fuzzy-match and never compute an edit distance. A
# near-miss is a reviewer's job, not a threshold's.
# =============================================================================

#: Trading-entity tails. `Brown Family Wine Group` keeps `group`, which is part
#: of the trading name; only the incorporation suffix is dropped.
_LEGAL_TAIL = re.compile(
    r"\b(pty\.?\s*ltd\.?|pty\.?|ltd\.?|limited|inc\.?|incorporated|"
    r"llc|plc|nl|no liability)\b",
    re.IGNORECASE,
)

_PUNCTUATION = re.compile(r"[^a-z0-9]+")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")
_DIGITS = re.compile(r"\D+")


def normalise_name(value: Any) -> str:
    """Fold a business name to its comparable core.

    Case, accents, punctuation and the incorporation suffix all go; word order
    and the words themselves do not. `Moët Hennessy` and `Moet Hennessy Pty Ltd`
    both fold to `moet hennessy`; `Hennessy Moet` does not, and should not.
    """
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("&", " and ")
    text = _LEGAL_TAIL.sub(" ", text.lower())
    text = _PUNCTUATION.sub(" ", text)
    return " ".join(text.split())


def normalise_domain(value: Any) -> str:
    """A bare lower-case host: no scheme, no `www.`, no port, no path."""
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    if not text:
        return ""
    text = _SCHEME.sub("", text)
    text = text.split("/")[0].split("?")[0].split("#")[0]
    text = text.split("@")[-1]  # a contact email's domain half
    text = text.split(":")[0]
    while text.startswith("www."):
        text = text[4:]
    return text.strip(".")


def normalise_abn(value: Any) -> str:
    """An ABN as its eleven digits, or `""` when it is not eleven digits.

    Returning `""` for a malformed value is what makes the "ABN could not be
    read from the page" state distinguishable from "no ABN was on the page"
    (UX.md §1.4.2). The caller knows which it has; this function does not guess.
    """
    if not isinstance(value, (str, int)):
        return ""
    digits = _DIGITS.sub("", str(value))
    return digits if len(digits) == 11 else ""


def format_abn(value: Any) -> str:
    """`55 004 094 599` — the ABR's own grouping. Display only."""
    digits = normalise_abn(value)
    if not digits:
        return str(value or "")
    return f"{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:]}"


def abr_lookup_url(value: Any) -> str:
    """The ABR lookup for an ABN, for the signals table's link (UX.md §1.4.2)."""
    digits = normalise_abn(value)
    if not digits:
        return ""
    return f"https://abr.business.gov.au/ABN/View?abn={digits}"


def slugify(value: Any) -> str:
    """Kebab-case slug, matching the filename convention (SCHEMA.md §2)."""
    return "-".join(normalise_name(value).split()) or "unnamed"


# =============================================================================
# 3. The register
#
# Read-only, cached on mtime. The hub reads this file, displays it, links to it
# and reports its `updated` date; it never writes it (UX.md §1.4.5 rule 7).
# =============================================================================

_CACHE: dict[str, Any] = {"mtime": None, "data": None}


def load_register(path: Path = OWNERSHIP_JSON_PATH) -> dict[str, Any]:
    """`data/ownership.json`, parsed. A missing file is empty, never fatal.

    A missing register does NOT mean everything is clear. It means nothing has
    been checked, and `determine` says so in the basis line rather than
    returning a `clear` it has not earned.
    """
    if not path.is_file():
        return {"updated": "", "owners": [], "_missing": True}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    if _CACHE["mtime"] == mtime and _CACHE["data"] is not None and mtime is not None:
        return _CACHE["data"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"updated": "", "owners": [], "_error": str(exc)}
    if not isinstance(data, dict):
        return {"updated": "", "owners": [], "_error": "register is not an object"}
    data.setdefault("owners", [])
    _CACHE.update(mtime=mtime, data=data)
    return data


def register_updated(path: Path = OWNERSHIP_JSON_PATH) -> str:
    return str(load_register(path).get("updated") or "")


# =============================================================================
# 4. The three checks
# =============================================================================


@dataclass(frozen=True)
class Match:
    """One deny-list hit, carrying everything the review pane must show.

    UX.md §1.4.2: "The panel never says only 'matched'. A reviewer must be able
    to see the evidence behind a block without opening a JSON file." Every field
    a hit row expands to is on this object.
    """

    check: str  # "name" | "domain" | "abn"
    value: str  # the normalised value that was checked
    matched: str  # the register value it matched
    matched_in: str  # "labels" | "aliases" | "parent" | "domains" | "abns"
    parent: str
    category: str
    verdict: str  # after the containment floor, never the raw record verdict
    record_verdict: str  # what the record itself says, for the audit trail
    exact: bool
    source: str
    updated: str
    note: str = ""
    abn_evidence: dict[str, Any] | None = None

    def line(self) -> str:
        """The one-line reason a blocked row shows (UX.md §1.4.4)."""
        where = "name" if self.check == "name" else self.check
        return f"deny-list: {where} matches {self.parent}"


def _record_verdict(record: dict[str, Any]) -> str:
    """A record's verdict, defaulting to the blocking side of an omission.

    A record with no `verdict` key predates the Wave 2 amendment (SCHEMA.md
    §4.3). Defaulting it to `reject` rather than `check` keeps an old record
    blocking, which is the safe direction for a deny-list.
    """
    verdict = str(record.get("verdict") or "").strip().lower()
    return verdict if verdict in VERDICTS else "reject"


def _build_match(
    record: dict[str, Any],
    *,
    check: str,
    value: str,
    matched: str,
    matched_in: str,
    exact: bool,
    abn_evidence: dict[str, Any] | None = None,
) -> Match:
    record_verdict = _record_verdict(record)
    # The containment floor. A partial name match never rejects; see the module
    # docstring for why the asymmetry is deliberate.
    verdict = record_verdict if exact else _weaker(record_verdict, "check")
    return Match(
        check=check,
        value=value,
        matched=matched,
        matched_in=matched_in,
        parent=str(record.get("parent") or ""),
        category=str(record.get("category") or ""),
        verdict=verdict,
        record_verdict=record_verdict,
        exact=exact,
        source=str(record.get("source") or ""),
        updated=str(record.get("updated") or ""),
        note=str(record.get("note") or ""),
        abn_evidence=abn_evidence,
    )


def _weaker(left: str, right: str) -> str:
    """The less-blocking of two verdicts."""
    return left if _VERDICT_RANK[left] <= _VERDICT_RANK[right] else right


def _stronger(left: str, right: str) -> str:
    """The more-blocking of two verdicts."""
    return left if _VERDICT_RANK[left] >= _VERDICT_RANK[right] else right


def _contains_words(haystack: str, needle: str) -> bool:
    """Whole-word containment on already-normalised strings.

    Both sides are space-separated normalised tokens, so a plain substring test
    with space padding is exact about word boundaries without a regex per call.
    """
    return f" {needle} " in f" {haystack} "


def check_name(name: Any, register: dict[str, Any] | None = None) -> Match | None:
    """Check a producer's trading name against every record's names.

    Matches on the `name` field only, never on free text (the register's own
    rule: `Tatachilla` is a Vinarchy label and a McLaren Vale locality, and the
    place must not fire the label).

    Exact matches are preferred over contained ones across the whole register,
    so a producer whose name exactly matches one record is not first captured by
    a longer containment against another.
    """
    register = register or load_register()
    candidate = normalise_name(name)
    if not candidate:
        return None

    contained: Match | None = None
    for record in register.get("owners", []):
        if not isinstance(record, dict):
            continue
        for source_field in _NAME_FIELDS:
            raw = record.get(source_field)
            values = [raw] if isinstance(raw, str) else (raw or [])
            for entry in values:
                listed = normalise_name(entry)
                if not listed:
                    continue
                if listed == candidate:
                    return _build_match(
                        record,
                        check="name",
                        value=candidate,
                        matched=str(entry),
                        matched_in=source_field,
                        exact=True,
                    )
                if contained is not None:
                    continue
                words = listed.split()
                if len(words) < 2 and len(listed) < _MIN_CONTAINED_CHARS:
                    continue  # too short to fire on its own; see the docstring
                if listed in place_names():
                    # The register's standing instruction. `Tatachilla` inside a
                    # longer name is the McLaren Vale locality, not the Vinarchy
                    # label; the label is caught by the exact match above.
                    continue
                if _contains_words(candidate, listed):
                    contained = _build_match(
                        record,
                        check="name",
                        value=candidate,
                        matched=str(entry),
                        matched_in=source_field,
                        exact=False,
                    )
    return contained


def check_domain(website: Any, register: dict[str, Any] | None = None) -> Match | None:
    """Check a producer's own domain against every record's domains.

    A subdomain of a listed domain hits: `shop.penfolds.com` is Penfolds. The
    reverse does not — a listed `penfolds.com` must not match `notpenfolds.com`,
    which is what the leading-dot test enforces.
    """
    register = register or load_register()
    host = normalise_domain(website)
    if not host:
        return None
    for record in register.get("owners", []):
        if not isinstance(record, dict):
            continue
        for entry in record.get("domains") or []:
            listed = normalise_domain(entry)
            if not listed:
                continue
            if host == listed or host.endswith(f".{listed}"):
                return _build_match(
                    record,
                    check="domain",
                    value=host,
                    matched=str(entry),
                    matched_in="domains",
                    exact=host == listed,
                )
    return None


def check_abn(abn: Any, register: dict[str, Any] | None = None) -> Match | None:
    """Check an extracted ABN against every recorded ABN.

    An ABN match is always exact — eleven digits either are or are not the same
    number — so it always carries the record's own verdict. The matched record's
    ABN evidence (its entity, source, quote and verified date) rides along,
    because an ABN block that a reviewer cannot audit is a number nobody thinks
    to question.
    """
    register = register or load_register()
    digits = normalise_abn(abn)
    if not digits:
        return None
    for record in register.get("owners", []):
        if not isinstance(record, dict):
            continue
        for entry in record.get("abns") or []:
            if not isinstance(entry, dict):
                continue
            if normalise_abn(entry.get("abn")) == digits:
                return _build_match(
                    record,
                    check="abn",
                    value=digits,
                    matched=str(entry.get("abn") or ""),
                    matched_in="abns",
                    exact=True,
                    abn_evidence=entry,
                )
    return None


# =============================================================================
# 5. The three rows, always all three
# =============================================================================

#: A row's `state` is what the reviewer reads in the deny-list block.
#: `not checked` is not a pass. It says the input was not available, which is
#: different from a check that ran and found nothing.
ROW_STATES = ("no match", "match", "not checked", "unreadable")


@dataclass
class Row:
    check: str
    value: str
    state: str
    match: Match | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "value": self.value,
            "state": self.state,
            "match": asdict(self.match) if self.match else None,
        }


def deny_list_check(
    name: Any = None,
    website: Any = None,
    abn: Any = None,
    *,
    register: dict[str, Any] | None = None,
) -> list[Row]:
    """The three named checks, always all three, whether they hit or not.

    UX.md §1.4.2 requires all three rows to render every time. Returning them as
    a fixed-length list rather than a list of hits is what makes that the
    default rather than something the template has to remember.
    """
    register = register or load_register()

    name_value = normalise_name(name)
    name_match = check_name(name, register) if name_value else None
    rows = [
        Row(
            check="name",
            value=str(name or ""),
            state="match" if name_match else ("no match" if name_value else "not checked"),
            match=name_match,
        )
    ]

    host = normalise_domain(website)
    domain_match = check_domain(website, register) if host else None
    rows.append(
        Row(
            check="domain",
            value=host,
            state="match" if domain_match else ("no match" if host else "not checked"),
            match=domain_match,
        )
    )

    # The ABN row has a fourth state. An ABN that was never on the page is `not
    # checked`; one that was on the page and does not parse to eleven digits is
    # `unreadable`, and that is the state UX.md §1.4.2's third example basis
    # line refers to. Distinguishing them is what stops every draft on a site
    # without an ABN from being forced to `check`, which would make `clear`
    # unreachable and the common path slow (UX.md §1.4.3).
    supplied = abn not in (None, "")
    digits = normalise_abn(abn)
    abn_match = check_abn(abn, register) if digits else None
    if not supplied:
        state = "not checked"
    elif not digits:
        state = "unreadable"
    else:
        state = "match" if abn_match else "no match"
    rows.append(
        Row(
            check="abn",
            value=format_abn(abn) if digits else str(abn or ""),
            state=state,
            match=abn_match,
        )
    )
    return rows


# =============================================================================
# 6. The signals
# =============================================================================


def signal_rows(signals: Any) -> list[dict[str, Any]]:
    """One row per SCHEMA.md §5 key, always all five, empties included.

    Extraction only. Nothing here judges a signal — `parent_company_mentions`
    being empty means nothing at all, because that is the normal state of a
    corporate portfolio site (the ownership-check skill's standing warning).
    """
    signals = signals if isinstance(signals, dict) else {}
    rows: list[dict[str, Any]] = []
    for key in SIGNAL_KEYS:
        raw = signals.get(key)
        if raw in (None, "", [], {}):
            items: list[str] = []
        elif isinstance(raw, list):
            items = [str(item).strip() for item in raw if str(item).strip()]
        else:
            items = [str(raw).strip()]
        rows.append(
            {
                "key": key,
                "items": items,
                "populated": bool(items),
                # UX.md §1.4.3: a `check` cannot be approved while any populated
                # row is unresolved. An empty row needs no resolution.
                "resolution": None,
                "note": "",
            }
        )
    return rows


def hit_rows(rows: list[Row]) -> list[dict[str, Any]]:
    """A resolution row for every deny-list hit that returned `check`.

    *Extends UX.md §1.4.3, flagged for sign-off.* The spec requires every
    extracted **signal** to be resolved before a `check` can be approved, and
    says nothing about a deny-list hit that produced a `check` — a hit carries
    no signal rows, so such a draft could be approved on a recorded source alone
    with nothing making the reviewer engage with the match.

    That is the wrong way round. A named deny-list record is the strongest
    evidence on the screen, stronger than any extracted phrase, and the one
    thing §1.4.5 exists to stop is a `check` sliding through. So a `check` hit
    gets the same three resolutions and the same note rule the signal rows use.
    Nothing new is invented; §1.4.3's mechanism is applied to §1.4.2's evidence.

    A `reject` hit gets no row. There is no resolution for a reject and offering
    one would be an override, which UX.md §1.4.4 forbids outright.
    """
    return [
        {
            "key": f"deny_list:{row.match.check}",
            "check": row.match.check,
            "parent": row.match.parent,
            "matched": row.match.matched,
            "resolution": None,
            "note": "",
        }
        for row in rows
        if row.match and row.match.verdict == "check"
    ]


def unresolved_hits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deny-list hit rows with no resolution, or one that still needs a note."""
    pending = []
    for row in rows or []:
        resolution = str(row.get("resolution") or "")
        if resolution not in RESOLUTIONS:
            pending.append(row)
        elif resolution in RESOLUTIONS_REQUIRING_NOTE and not str(row.get("note") or "").strip():
            pending.append(row)
    return pending


def populated_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("populated")]


def statements_name_a_group(rows: list[dict[str, Any]]) -> list[str]:
    """The `statements` items that match `PARENT_PATTERNS`, verbatim.

    Returns the offending statements rather than a bool so the basis line and
    the review pane can quote what fired. A reviewer must be able to see the
    sentence that escalated the verdict without opening a JSON file (UX.md
    §1.4.2, "the panel never says only 'matched'").
    """
    hits: list[str] = []
    for row in rows:
        if row.get("key") != "statements":
            continue
        for item in row.get("items") or []:
            text = str(item)
            if any(pattern.search(text) for pattern in PARENT_PATTERNS):
                hits.append(text)
    return hits


def escalating_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Populated rows that move the verdict on their own. Amended 2026-08-07.

    The four `ESCALATING_SIGNAL_KEYS`, plus `statements` when and only when
    `statements_name_a_group` found group phrasing in it. A `statements` row
    that names an owning family is evidence *for* independence and is recorded
    without escalating (module docstring; SCHEMA.md §4.2 route 2).
    """
    flagged = bool(statements_name_a_group(rows))
    return [
        row
        for row in populated_signals(rows)
        if row.get("key") in ESCALATING_SIGNAL_KEYS
        or (row.get("key") == "statements" and flagged)
    ]


def unresolved_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Escalating rows with no resolution, or with one that still needs a note.

    Amended 2026-08-07 alongside `escalating_signals`: a non-escalating
    `statements` row is rendered and may be resolved, but never blocks approval.
    Blocking on it was the cost this amendment exists to remove. A `statements`
    row that *did* escalate blocks exactly like any other, so a false positive
    in `PARENT_PATTERNS` costs a reviewer one `Not relevant` click.
    """
    pending = []
    for row in escalating_signals(rows):
        resolution = str(row.get("resolution") or "")
        if resolution not in RESOLUTIONS:
            pending.append(row)
        elif resolution in RESOLUTIONS_REQUIRING_NOTE and not str(row.get("note") or "").strip():
            pending.append(row)
    return pending


# =============================================================================
# 7. The determination
# =============================================================================


@dataclass
class Determination:
    verdict: str
    basis: str
    rows: list[Row] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    hits_to_resolve: list[dict[str, Any]] = field(default_factory=list)
    register_updated: str = ""
    checked_at: str = ""
    machine_verdict: str = ""
    verdict_overridden_from: str = ""
    confidence_notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "basis": self.basis,
            "deny_list": {
                "updated": self.register_updated,
                "rows": [row.as_dict() for row in self.rows],
            },
            "signals": self.signals,
            "hits_to_resolve": self.hits_to_resolve,
            "checked_at": self.checked_at,
            "machine_verdict": self.machine_verdict,
            "verdict_overridden_from": self.verdict_overridden_from,
            "confidence_notes": list(self.confidence_notes),
        }

    def hits(self) -> list[Match]:
        return [row.match for row in self.rows if row.match]


def _basis_line(verdict: str, rows: list[Row], signals: list[dict[str, Any]]) -> str:
    """UX.md §1.4.2's one-line basis, naming which check produced the verdict."""
    hits = [row.match for row in rows if row.match]
    if hits:
        strongest = max(hits, key=lambda match: _VERDICT_RANK[match.verdict])
        # Ordered by the row order, not alphabetically: the basis line reads in
        # the same order as the three rows beneath it.
        order = {"name": 0, "domain": 1, "abn": 2}
        checks = ", ".join(
            CHECK_LABELS[check]
            for check in sorted({match.check for match in hits}, key=order.get)
        )
        qualifier = "" if strongest.exact else " on a partial name match"
        return (
            f"{verdict.capitalize()}: deny-list match on {checks}"
            f"{qualifier} — {strongest.parent}."
        )

    abn_row = next((row for row in rows if row.check == "abn"), None)
    if abn_row is not None and abn_row.state == "unreadable":
        return "Check: ABN could not be read from the page."

    # Amended 2026-08-07. The basis is the durable public record: it is written
    # to `ownership_source` and it is what answers a producer who disputes the
    # determination (UX.md §1.4.6). It must therefore never claim "no ownership
    # signals extracted" over a determination that extracted one, which is what
    # a `clear` carrying a family-ownership statement would have said.
    flagged = statements_name_a_group(signals)
    if flagged:
        return (
            f"Check: an extracted statement names a group or a corporate "
            f'owner — "{flagged[0]}".'
        )

    count = len(escalating_signals(signals))
    if count:
        return f"Check: {count} ownership signal{'s' if count != 1 else ''} extracted."

    if verdict == "clear":
        recorded = len(populated_signals(signals))
        if recorded == 1:
            return (
                "Clear: no deny-list match on name, domain or ABN, and the "
                "extracted statement names no parent."
            )
        if recorded:
            return (
                "Clear: no deny-list match on name, domain or ABN, and the "
                f"{recorded} extracted statements name no parent."
            )
        return (
            "Clear: no deny-list match on name, domain or ABN, and no ownership "
            "signals extracted."
        )
    return f"{verdict.capitalize()}: see the signals below."


def determine(
    name: Any = None,
    website: Any = None,
    signals: Any = None,
    *,
    harvester_verdict: str | None = None,
    floor: str | None = None,
    register: dict[str, Any] | None = None,
) -> Determination:
    """The verdict, and every piece of evidence behind it.

    `harvester_verdict` is the `independence` value the Harvester emits
    (SCHEMA.md §5). It is **one input, never the decision** (SCHEMA.md §4.5):
    it can only make the verdict more blocking, never less, so a Harvester that
    says `clear` about a deny-listed label changes nothing. That asymmetry is
    what "it never decides alone" means in code.

    `floor` caps how blocking the verdict may be, and exists for exactly one
    caller: UX.md §1.4.4's `Re-harvest as check`, which re-runs a URL with the
    machine verdict floored at `check` so a machine abort becomes a human
    decision. It downgrades a machine verdict; it never skips the human.

    The ABN checked is the one the Harvester extracted into
    `ownership_signals.abn`. This module does not fetch, parse or guess one.
    """
    register = register if register is not None else load_register()
    signals = signals if isinstance(signals, dict) else {}

    rows = deny_list_check(name, website, signals.get("abn"), register=register)
    signal_table = signal_rows(signals)

    verdict = "clear"
    for row in rows:
        if row.match:
            verdict = _stronger(verdict, row.match.verdict)

    if verdict == "clear":
        abn_row = next((row for row in rows if row.check == "abn"), None)
        if abn_row is not None and abn_row.state == "unreadable":
            verdict = "check"
        elif escalating_signals(signal_table):
            # Amended 2026-08-07: escalating, not merely populated. A statement
            # naming an owning family is the evidence SCHEMA.md §4.2 asks for
            # and no longer forces the review it is supposed to satisfy.
            verdict = "check"

    # The Harvester's own verdict can only tighten. It never relaxes one the
    # deny-list or the signals produced (SCHEMA.md §4.5).
    if harvester_verdict in VERDICTS:
        verdict = _stronger(verdict, harvester_verdict)

    notes: list[str] = []
    if register.get("_missing"):
        # Absence of a register is not a clean bill of health. Say so, and do
        # not hand back a `clear` that nothing verified.
        verdict = _stronger(verdict, "check")
        notes.append(
            "data/ownership.json is not present, so no deny-list check ran. "
            "Absence from the register means unchecked, never cleared."
        )
    elif register.get("_error"):
        verdict = _stronger(verdict, "check")
        notes.append(f"data/ownership.json could not be read: {register['_error']}")

    machine_verdict = verdict
    overridden_from = ""
    if floor in VERDICTS and _VERDICT_RANK[verdict] > _VERDICT_RANK[floor]:
        overridden_from = verdict
        verdict = floor

    return Determination(
        verdict=verdict,
        basis=_basis_line(verdict, rows, signal_table),
        rows=rows,
        signals=signal_table,
        hits_to_resolve=hit_rows(rows) if verdict == "check" else [],
        register_updated=str(register.get("updated") or ""),
        checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        machine_verdict=machine_verdict,
        verdict_overridden_from=overridden_from,
        confidence_notes=notes,
    )


# =============================================================================
# 8. The sidecar
#
# UX.md §1.4.6. The published frontmatter carries the durable public record;
# the sidecar carries the working evidence, including signals resolved as `Not
# relevant` that would otherwise vanish. When a producer argues with the
# determination, the sidecar is the file that answers them.
# =============================================================================


def sidecar_path(slug: str, directory: Path = STAGING_DIR) -> Path:
    """`<slug>.ownership.json` beside an MDX, `<slug>.json` once retained.

    UX.md §1.4.6 names both: the sidecar sits next to the draft in `_staging/`
    and next to the rejected file in `_rejected/`, where the suffix keeps it
    distinguishable from the MDX it belongs to; in `DETERMINATIONS_DIR` it is
    the only thing there, so it is plainly `<slug>.json`. The approve action
    renames it on the way through, and this function is the one place that
    knows which name applies where.
    """
    if directory == DETERMINATIONS_DIR:
        return directory / f"{slug}.json"
    return directory / f"{slug}.ownership.json"


def read_sidecar(slug: str, directory: Path = STAGING_DIR) -> dict[str, Any] | None:
    path = sidecar_path(slug, directory)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_sidecar(
    slug: str, determination: Determination | dict[str, Any], directory: Path = STAGING_DIR
) -> Path:
    payload = (
        determination.as_dict()
        if isinstance(determination, Determination)
        else dict(determination)
    )
    payload.setdefault("slug", slug)
    directory.mkdir(parents=True, exist_ok=True)
    path = sidecar_path(slug, directory)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def determination_for(slug: str) -> dict[str, Any] | None:
    """The determination wherever it currently lives: staging, then published."""
    return read_sidecar(slug, STAGING_DIR) or read_sidecar(slug, DETERMINATIONS_DIR)


def chip_for(sidecar: dict[str, Any] | None) -> str:
    """The queue chip: `CLEAR`, `CHECK`, `RESOLVED` or `NOT DETERMINED`.

    UX.md §1.4.3: resolving every signal row moves the chip from `CHECK` to
    `RESOLVED`. A missing sidecar is `NOT DETERMINED` and never `CLEAR` —
    `CLEAR` is a positive finding about checks that have actually run.
    """
    if not sidecar:
        return "NOT DETERMINED"
    verdict = str(sidecar.get("verdict") or "").lower()
    if verdict == "check":
        signals = sidecar.get("signals") or []
        hits = sidecar.get("hits_to_resolve") or []
        if unresolved_signals(signals) or unresolved_hits(hits):
            return "CHECK"
        # `RESOLVED` is a claim that a person worked through the evidence. With
        # nothing to work through, nobody has resolved anything and the chip
        # stays `CHECK` — reading `RESOLVED` there would credit a reviewer with
        # work they never did.
        return "RESOLVED" if (populated_signals(signals) or hits) else "CHECK"
    if verdict == "clear":
        return "CLEAR"
    if verdict == "reject":
        return "REJECT"
    return "NOT DETERMINED"


# =============================================================================
# 9. The approval gate
#
# UX.md §1.4.5's hard rules. These are requirements, not defaults, and they live
# here rather than in a template so that no route can publish without passing
# the same gate the UI enforces (rule 2).
# =============================================================================


def approval_blocks(data: dict[str, Any], sidecar: dict[str, Any] | None) -> list[str]:
    """What blocks approval on ownership grounds. Empty means the gate is open.

    Rule 5 first, because it is unconditional and has no override anywhere.
    """
    blocks: list[str] = []

    # Rule 5 — a non-null parent_company blocks approval unconditionally.
    if data.get("parent_company"):
        blocks.append(
            "parent_company is set. This producer cannot be published "
            "(SCHEMA.md §4.1). Reject it, or clear the field if it was entered "
            "in error."
        )

    # Rules 1 and 3 — `clear` and `check` alike require a recorded source, with
    # the missing element named. A `clear` verdict is an absence of *escalating*
    # signals, and absence is not evidence of a negative (SCHEMA.md §4.2). This
    # is the rule that carries the weight after the 2026-08-07 amendment: a
    # `clear` is now reachable on a producer whose page states its ownership, so
    # the recorded source is what stands behind that determination.
    ownership = data.get("ownership_source")
    if not isinstance(ownership, dict):
        blocks.append(
            "ownership_source is missing. Every producer publishes with a dated "
            "source that positively states who owns the business (SCHEMA.md §4.2)."
        )
    else:
        missing = [
            part
            for part in ("source", "method", "date")
            if not str(ownership.get(part) or "").strip()
        ]
        if missing:
            blocks.append(f"ownership_source is missing {', '.join(missing)}")

    verdict = str((sidecar or {}).get("verdict") or "").lower()

    # A `reject` never reaches the review pane (UX.md §1.4.3). If one is sitting
    # in the queue, something wrote a draft it should not have.
    if verdict == "reject":
        blocks.append(
            "the determination is reject. This draft should not have entered the "
            "queue; reject it and correct data/ownership.json if the deny-list is wrong."
        )

    # Rule 2's teeth — a `check` with unresolved signals cannot be approved, and
    # the count is stated in text beside the button, not only as a tooltip.
    if verdict == "check":
        pending = unresolved_signals((sidecar or {}).get("signals") or [])
        if pending:
            # Two different states reach here and they need different actions.
            # Saying "unresolved" for both sends a reviewer who HAS chosen a
            # resolution looking for a control they already used, with nothing
            # on screen naming the note they actually owe. Observed live on the
            # first real draft: `statements` resolved as `explained`, note
            # empty, and the only feedback was "1 ownership signal is
            # unresolved". UX.md §1.5 row 16 asks for the reason in text, and
            # the wrong reason does not satisfy it.
            unchosen = [
                row for row in pending if str(row.get("resolution") or "") not in RESOLUTIONS
            ]
            noteless = [row for row in pending if row not in unchosen]
            if unchosen:
                names = ", ".join(SIGNAL_LABELS.get(r["key"], r["key"]) for r in unchosen)
                blocks.append(
                    f"{len(unchosen)} ownership signal"
                    f"{'s are' if len(unchosen) != 1 else ' is'} unresolved ({names}). "
                    f"Choose a resolution for each."
                )
            if noteless:
                names = ", ".join(SIGNAL_LABELS.get(r["key"], r["key"]) for r in noteless)
                labels = ", ".join(
                    sorted({RESOLUTION_LABELS.get(r.get("resolution"), "") for r in noteless})
                )
                blocks.append(
                    f"{len(noteless)} ownership signal"
                    f"{'s need' if len(noteless) != 1 else ' needs'} a note ({names}). "
                    f"'{labels}' requires you to record why."
                )
        hits = unresolved_hits((sidecar or {}).get("hits_to_resolve") or [])
        if hits:
            named = ", ".join(sorted({hit.get("parent", "") for hit in hits if hit.get("parent")}))
            blocks.append(
                f"{len(hits)} deny-list match{'es are' if len(hits) != 1 else ' is'} "
                f"unresolved ({named})."
            )

    # Rule 2, the other half: no keyboard shortcut approves a draft whose
    # ownership panel has never been rendered. A missing sidecar is that case.
    if not sidecar:
        blocks.append(
            "no ownership determination exists for this draft. `check` never "
            "auto-publishes and neither does an undetermined draft (UX.md §1.4.5)."
        )

    return blocks


# =============================================================================
# 10. Blocked records
#
# UX.md §1.4.4. A `reject` aborts before a draft is written, and no file lands
# in `_staging/`. That is correct behaviour, and it still needs an on-screen
# state, because an abort a reviewer cannot see is a silent failure.
#
# Blocked records are never deleted. They are the record of what the site
# refused and why, and at 150 to 300 producers the same URL will be reached for
# twice.
# =============================================================================


def blocked_path(slug: str) -> Path:
    return BLOCKED_DIR / f"{slug}.json"


def reject_reason(determination: Determination) -> tuple[str, str]:
    """`(source_of_reject, one-line reason)` for the blocked row.

    `source_of_reject` decides which actions the row offers, and the two differ
    deliberately: a deny-list reject has no override in the UI, while a signal
    reject offers `Re-harvest as check` (UX.md §1.4.4).
    """
    hits = [match for match in determination.hits() if match.verdict == "reject"]
    if hits:
        return "deny-list", hits[0].line()
    populated = populated_signals(determination.signals)
    statements = next(
        (row for row in populated if row["key"] in ("statements", "parent_company_mentions")),
        None,
    )
    tail = ", statements name a parent group" if statements else ""
    return "harvester", f"harvester: {len(populated)} signals{tail}"


def write_blocked_record(
    url: str,
    name: Any,
    determination: Determination,
    *,
    slug: str | None = None,
) -> Path:
    """Write `<slug>.json` to `BLOCKED_DIR`. Never writes a draft.

    The slug comes from the producer's name where one was extracted, and from
    the host otherwise. A pre-fetch domain block has no name yet, and slugifying
    the whole URL would make `https-www-wolfblass-com-en-au`, which is unusable
    as the row a reviewer reads and as the filename they grep for.
    """
    if not slug:
        slug = slugify(name) if str(name or "").strip() else slugify(normalise_domain(url))
    source_of_reject, reason = reject_reason(determination)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # A URL that is blocked, re-harvested and blocked again keeps its history.
    # The re-harvest is the evidence that somebody looked twice, and losing it
    # would make the second block indistinguishable from the first.
    previous = read_blocked(slug) or {}
    payload = {
        "slug": slug,
        "url": url,
        "name": str(name or previous.get("name") or ""),
        "reason": reason,
        "source_of_reject": source_of_reject,
        "blocked_at": now,
        "first_blocked_at": str(
            previous.get("first_blocked_at") or previous.get("blocked_at") or now
        ),
        "reharvests": previous.get("reharvests") or [],
        **determination.as_dict(),
    }
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)
    path = blocked_path(slug)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_blocked(slug: str) -> dict[str, Any] | None:
    path = blocked_path(slug)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"slug": slug, "unreadable": str(exc)}
    return data if isinstance(data, dict) else None


def blocked_rows() -> list[dict[str, Any]]:
    """Every blocked record, newest first. Never raises on a bad file."""
    if not BLOCKED_DIR.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in BLOCKED_DIR.glob("*.json"):
        record = read_blocked(path.stem) or {}
        rows.append(
            {
                "slug": path.stem,
                "name": str(record.get("name") or path.stem),
                "url": str(record.get("url") or ""),
                "reason": str(record.get("reason") or record.get("unreadable") or ""),
                "source_of_reject": str(record.get("source_of_reject") or ""),
                "blocked_at": str(record.get("blocked_at") or ""),
                "reharvested": bool(record.get("reharvests")),
            }
        )
    rows.sort(key=lambda row: row["blocked_at"], reverse=True)
    return rows


def record_reharvest(slug: str, action: str) -> dict[str, Any] | None:
    """Stamp a re-harvest onto a blocked record. The record is never deleted."""
    record = read_blocked(slug)
    if not record or record.get("unreadable"):
        return None
    record.setdefault("reharvests", []).append(
        {"action": action, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    )
    blocked_path(slug).write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return record


# =============================================================================
# 11. The pre-queue screen
#
# SCHEMA.md §4.5 and TRD.md §7.5: deny-list checks on name, domain and ABN run
# BEFORE a draft enters the queue — before the Architect is called, so a
# portfolio-owned label costs one cheap call rather than three. A `reject`
# verdict aborts before any draft is written, with the reason logged.
# =============================================================================


def screen_url(url: str, *, floor: str | None = None) -> Determination:
    """The cheapest screen there is: the domain, before anything is fetched.

    A URL is all that exists at this point in a run, so this is a domain check
    only — the name and ABN rows report `not checked` rather than pretending.
    Gate 5's Harvester calls `screen_candidate` afterwards with what it read.
    """
    return determine(website=url, floor=floor)


def screen_candidate(
    url: str,
    name: Any = None,
    signals: Any = None,
    *,
    harvester_verdict: str | None = None,
    floor: str | None = None,
) -> Determination:
    """The full screen, once the Harvester has a name and ownership signals."""
    return determine(
        name=name,
        website=url,
        signals=signals,
        harvester_verdict=harvester_verdict,
        floor=floor,
    )
