"""config.py — the Python half of the hand-mirrored config pair.

GATE 1 OWNS THIS FILE. Its TypeScript twin is ``site/src/config.ts``.

Nothing generates one of these files from the other. They are hand-mirrored,
which means they drift, which is why ``/validate`` check 13 diffs them and why
the ``schema-guardian`` agent exists. Any vocabulary change lands in BOTH, in
the same commit, name-matched (CLAUDE.md rule 7).

SCHEMA.md §1 is the source of truth for every tuple below. Adding a value here
is a schema change, not a config edit. Load the ``schema-change`` skill first.

Every cross-cutting path in the Python half is defined here and imported
everywhere else (CLAUDE.md rule 4). All paths are ``pathlib`` and are anchored
to the repo root, so every module is safe to run from the repo root regardless
of the caller's working directory.
"""

from __future__ import annotations

# =============================================================================
# 0. The two load-bearing config quirks — TRD.md §2.3
#
# BOTH ARE PORTED VERBATIM IN INTENT AND NEITHER IS OPTIONAL OR DECORATIVE.
# They sit at the very top of this module, before anything else, because the
# first of them must be installed before any httpx client exists anywhere in
# the process.
# =============================================================================

import socket

_ORIGINAL_GETADDRINFO = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Force DNS resolution to IPv4, process-wide, once.

    Some sandboxed environments advertise an IPv6 route that is a black hole:
    packets vanish with no RST and no ICMP unreachable. curl falls back to IPv4
    per RFC 8305; Python's socket stack does not, and hangs inside ``connect()``
    past any per-call timeout, so a 20-second httpx timeout does not save you.

    Every external call this project makes goes through httpx, so the fix
    belongs here rather than at each call site. Harmless where IPv6 works, and
    this project has no IPv6-only dependency.
    """
    return _ORIGINAL_GETADDRINFO(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo  # type: ignore[assignment]


import os  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> dict[str, str]:
    """Minimal ``KEY=VALUE`` reader. No python-dotenv (TRD.md §2.2).

    Deliberately does NOT strip quotes, expand variables, or handle ``export``.
    ``.env.example`` documents that contract for whoever writes the file. A
    parser that silently accepted ``export FOO="bar"`` and stored ``"bar"`` with
    the quotes would be worse than one that refuses to guess.

    A missing ``.env`` is not an error: the site build, the data layer and the
    review queue all work without one. Only the pipeline needs a key.
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


_ENV_FILE = _load_env(ROOT / ".env")


def env(key: str, default: str = "") -> str:
    """Real environment first, then ``.env``, then the default.

    The real environment wins because ``docker-entrypoint.sh`` injects Fly
    secrets as ordinary environment variables (TRD.md §2.4).
    """
    return os.environ.get(key) or _ENV_FILE.get(key) or default


# =============================================================================
# 1. Paths — every cross-cutting path, defined once (CLAUDE.md rule 4)
# =============================================================================

SITE_DIR = ROOT / "site"
ADMIN_DIR = ROOT / "admin"

# Producer content. `_published` is the ONLY producer content Astro builds from,
# and the approve action is the only thing that writes there (CLAUDE.md rule 5).
CONTENT_DIR = SITE_DIR / "src" / "content"
PUBLISHED_DIR = CONTENT_DIR / "producers" / "_published"

# Staging sits OUTSIDE site/src/content so Astro never builds a draft.
CONTENT_STAGING_DIR = ROOT / "content-staging"
STAGING_DIR = CONTENT_STAGING_DIR / "_staging"
REJECTED_DIR = CONTENT_STAGING_DIR / "_rejected"
DELETED_DIR = CONTENT_STAGING_DIR / "_deleted"

DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "directory.db"
OWNERSHIP_JSON_PATH = DATA_DIR / "ownership.json"

SITE_DATA_DIR = SITE_DIR / "src" / "data"
PRODUCERS_JSON_PATH = SITE_DATA_DIR / "producers.json"
FOREWORDS_JSON_PATH = SITE_DATA_DIR / "forewords.json"

PROMPTS_DIR = ROOT / "PROMPTS"

# GITIGNORED. Never edited by hand, never committed (CLAUDE.md rule 5).
TEMP_DATA_DIR = ROOT / "temp_data"
IMAGES_DIR = TEMP_DATA_DIR / "images"
FAILED_DIR = TEMP_DATA_DIR / "failed"
HARVEST_QUEUE_PATH = TEMP_DATA_DIR / "harvest_queue.json"
GEOCODE_CACHE_PATH = TEMP_DATA_DIR / "geocode_cache.json"

# Published producer photographs. Committed (TRD.md §3).
PUBLIC_IMAGES_DIR = SITE_DIR / "public" / "images"

# Gate 11. Named now so the key set is stable; unused until then.
BLOG_PUBLISHED_DIR = CONTENT_DIR / "blog" / "_published"
BLOG_STAGING_DIR = CONTENT_STAGING_DIR / "_blog_staging"
ARTICLE_STAGING_DIR = CONTENT_STAGING_DIR / "_article_staging"
FACTCHECKS_DIR = DATA_DIR / "factchecks"


# =============================================================================
# 2. Environment — TRD.md §3, mirroring .env.example's key set exactly
# =============================================================================

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")

# Model IDs come from .env and are NEVER hardcoded (TRD.md §2.1).
#
# Defaults CASCADE rather than falling back to a literal, so a real .env that
# overrides only MODEL_ARCHITECT still yields a valid id for every downstream
# role. The order below is the cascade and is load-bearing.
MODEL_HARVESTER = env("MODEL_HARVESTER", "claude-haiku-4-5-20251001")
MODEL_ARCHITECT = env("MODEL_ARCHITECT", "claude-opus-5")
MODEL_GATEKEEPER = env("MODEL_GATEKEEPER", MODEL_HARVESTER)

# Gate 6. Aggregation-page forewords: short editorial prose about a region, a
# grape or a practice. It is drafting work rather than extraction, so it
# cascades from the Architect, which is the drafting role.
MODEL_FOREWORD = env("MODEL_FOREWORD", MODEL_ARCHITECT)

# Gate 11 editorial roles.
MODEL_ARTICLE = env("MODEL_ARTICLE", MODEL_ARCHITECT)
MODEL_BRIEF = env("MODEL_BRIEF", MODEL_ARTICLE)
MODEL_FACTCHECK = env("MODEL_FACTCHECK", MODEL_GATEKEEPER)

#: MODEL_FACTCHECK must differ from MODEL_ARTICLE. The fact-check stage is
#: deliberately adversarial: a drafting model is a poor judge of its own
#: confabulation. The pipeline warns rather than failing, because the cascade
#: above can legitimately collapse them in a bare-bones local setup.
FACTCHECK_IS_SELF_REVIEW = MODEL_FACTCHECK == MODEL_ARTICLE

ADMIN_PORT = int(env("ADMIN_PORT", "8787"))
ADMIN_USERNAME = env("ADMIN_USERNAME")
ADMIN_PASSWORD = env("ADMIN_PASSWORD")

SITE_URL = env("SITE_URL", "https://example.com").rstrip("/")

NETLIFY_AUTH_TOKEN = env("NETLIFY_AUTH_TOKEN")
NETLIFY_SITE_ID = env("NETLIFY_SITE_ID")
INDEXNOW_KEY = env("INDEXNOW_KEY")
GITHUB_PAT = env("GITHUB_PAT")

GEOCODER = env("GEOCODER", "nominatim")
GEOCODER_USER_AGENT = env(
    "GEOCODER_USER_AGENT", "winemakers-directory/1.0 (you@example.com)"
)

#: One outbound HTTP timeout for everything (TRD.md §2.1).
HTTP_TIMEOUT_SECONDS = 20.0

#: UX.md §1.5 row 1 names the harvest fetch's timeout separately. It is the
#: same number, aliased rather than restated, so there is one value to change.
FETCH_TIMEOUT_SECONDS = HTTP_TIMEOUT_SECONDS

#: TRD.md §7.6: a descriptive user agent, because these are real businesses
#: being read one page at a time and an operator who wants to block us should be
#: able to identify us to do it (SEED.md, "Ethics").
HARVEST_USER_AGENT = (
    f"winemakers-directory/1.0 (+{SITE_URL}/methodology; "
    f"independent Australian winemaker directory)"
)


# =============================================================================
# 3. Closed vocabularies — SCHEMA.md §1
#
# MIRROR OF site/src/config.ts. Same names, same order, same members.
# `/validate` check 13 compares these as strings; a near-synonym is a failure.
# =============================================================================

# SCHEMA.md §1.1
CATEGORIES = (
    "estate_winery",
    "urban_winery",
    "negociant",
    "garagiste",
    "cooperative",
    "other",
)

# SCHEMA.md §1.2
CELLAR_DOOR_STATES = ("none", "by_appointment", "open")

# SCHEMA.md §1.3
CERTIFICATION_STATES = ("none", "practising", "certified")

# SCHEMA.md §1.4
FRUIT_SOURCE = ("estate", "purchased", "mixed")

# SCHEMA.md §1.5
PRODUCTION_BANDS = (
    "under_1000",
    "1000_5000",
    "5000_20000",
    "over_20000",
    "unknown",
)

# SCHEMA.md §1.6 — canonical order. There is no `low_intervention` key.
PRACTICE_KEYS = ("wild_ferment", "unfined", "unfiltered", "minimal_so2")

# SCHEMA.md §1.7
LOGISTICS_KEYS = (
    "walk_ins_welcome",
    "bookings_required",
    "restaurant",
    "picnic_provisions",
    "dog_friendly",
    "family_friendly",
    "wheelchair_access",
    "group_bookings",
    "vineyard_tours",
    "parking",
)

# SCHEMA.md §1.8
VESSEL_KEYS = (
    "stainless",
    "oak_barrique",
    "oak_foudre",
    "concrete",
    "amphora",
    "ceramic",
    "glass",
)

# SCHEMA.md §1.9
WINE_STYLE_KEYS = (
    "red",
    "white",
    "rose",
    "sparkling",
    "skin_contact",
    "fortified",
    "dessert",
)

# SCHEMA.md §1.10 — the Wave 2 seed set, 58 varieties.
#
# THIS IS THE COPY THAT DRIFTS. `site/src/config.ts` derives its tuple from
# `glossary.ts`, so the TypeScript side cannot fall out of step with the
# glossary. Python cannot import a TypeScript module, so this list is literal
# and is exactly what `/validate` check 13 exists to compare. Order matches
# glossary.ts: reds first, then whites, each in authored order.
VARIETY_KEYS = (
    # Red
    "shiraz",
    "cabernet-sauvignon",
    "merlot",
    "grenache",
    "mataro",
    "pinot-noir",
    "cabernet-franc",
    "malbec",
    "petit-verdot",
    "sangiovese",
    "nebbiolo",
    "barbera",
    "tempranillo",
    "touriga-nacional",
    "montepulciano",
    "aglianico",
    "nero-davola",
    "negroamaro",
    "lagrein",
    "dolcetto",
    "gamay",
    "zinfandel",
    "durif",
    "cinsault",
    "carignan",
    "tannat",
    "saperavi",
    "pinot-meunier",
    "graciano",
    "sagrantino",
    "blaufrankisch",
    # White
    "chardonnay",
    "sauvignon-blanc",
    "semillon",
    "riesling",
    "pinot-gris",
    "viognier",
    "marsanne",
    "roussanne",
    "verdelho",
    "vermentino",
    "fiano",
    "arneis",
    "gruner-veltliner",
    "chenin-blanc",
    "muscadelle",
    "colombard",
    "trebbiano",
    "garganega",
    "savagnin",
    "albarino",
    "gewurztraminer",
    "prosecco",
    "muscat-blanc",
    "pedro-ximenez",
    "palomino",
    "assyrtiko",
    "greco-di-tufo",
)

# SCHEMA.md §1.11, weakest → strongest.
CONFIDENCE_TIERS = (
    "unverified",
    "published_by_producer",
    "observed_on_visit",
    "operator_confirmed",
)

#: SCHEMA.md §2b: a re-harvest UPGRADES, never silently downgrades.
CONFIDENCE_TIER_RANK = {tier: index for index, tier in enumerate(CONFIDENCE_TIERS)}

# SCHEMA.md §1.12. A list of field names, not a vocabulary of values. Not glossed.
VERIFIABLE_FIELDS = (
    "parent_company",
    "organic",
    "organic_certifier",
    "biodynamic",
    "biodynamic_certifier",
    "fruit_source",
    "production_band",
    "annual_production_cases",
    "founded_year",
    "tasting_fee",
    "cellar_door_hours",
    "varieties",
    "wine_styles",
)

# SCHEMA.md §1.13
OWNERSHIP_EVIDENCE_METHODS = ("registry", "producer_statement", "trade_source")

# SCHEMA.md §1.14
STATES = ("VIC", "NSW", "QLD", "SA", "WA", "TAS", "NT", "ACT")


# =============================================================================
# 4. Bounds, ranges and thresholds
# =============================================================================

# SCHEMA.md §2 coordinate bounds.
AU_LATITUDE_BOUNDS = (-44.0, -9.0)
AU_LONGITUDE_BOUNDS = (112.0, 154.0)

#: The numeric ranges behind PRODUCTION_BANDS, for SCHEMA.md §2a rule 9.
#: ``None`` as the upper bound means unbounded above; ``unknown`` has no range
#: and never corroborates or contradicts a case figure.
PRODUCTION_BAND_RANGES = {
    "under_1000": (0, 999),
    "1000_5000": (1000, 5000),
    "5000_20000": (5001, 20000),
    "over_20000": (20001, None),
    "unknown": None,
}

#: The four Gate 8 coverage regions, so "which regions are populated" is data
#: rather than prose. Slugs must exist in ``site/src/data/regions.ts``.
COVERAGE_REGIONS = (
    "adelaide-hills",
    "mclaren-vale",
    "yarra-valley",
    "mornington-peninsula",
)

#: TRD.md §4.6 / §4.7. Mirrored so the admin's preview paginates as the site does.
PRODUCERS_PER_PAGE = 24
SEARCH_INDEX_INLINE_MAX = 500

#: Gate 9 thresholds.
MIN_COMPARISON_PRODUCERS = 4
MIN_AGGREGATION_LINKS = 3


# =============================================================================
# 5. The admin hub — UX.md §1
#
# Admin-only, so these live in the Python half alone. `site/src/config.ts` has
# no use for them and mirroring them there would create a drift surface with no
# consumer. `/validate` check 13's config-pair diff walks the SCHEMA.md §1
# vocabularies, which is the pair that has to agree.
# =============================================================================

#: UX.md §1.1. One URL per line in the batch textarea. UX.md's own worked
#: example is a forty-URL run surviving a page reload, so the cap sits above it.
BATCH_MAX_URLS = 50

#: UX.md §1.2. The log pane holds this many lines and drops from the top.
MAX_LOG_LINES = 500

#: UX.md §1.5 row 3. Extracted text below this is a thin page: the item ends
#: WITHOUT drafting and offers the user-triggered Playwright retry.
#:
#: MEASURED, not estimated. Every SEED.md URL was fetched on 2026-08-07 and the
#: trafilatura extraction counted, because this threshold decides which fixture
#: rows draft and which do not, and SEED.md states the expected outcome for each:
#:
#:     Wolf Blass      365 chars   must not draft (blocked earlier anyway)
#:     Myrtaceae       457 chars   SEED row 5: must trip this threshold
#:     Gemtree       1,225 chars   SEED row 3: must draft, needing reviewer work
#:     Basket Range  2,018 chars   SEED row 4: must draft on the first pass
#:
#: So the value has to sit above 457 and at or below 1,225. 1,000 characters is
#: roughly 170 words, which is comfortably less raw material than the 350-word
#: minimum of a body (MIN_PROSE_WORDS) and therefore cannot source one without
#: padding. Padding is how the honesty rule (CLAUDE.md rule 6) gets broken
#: quietly, so no draft is the correct output and the reviewer is told why.
#:
#: An earlier value of 2,000 was authored from a word-count estimate of SEED
#: row 5's prose. It would have put Basket Range, the clean baseline that is
#: meant to be the least reviewer work in the corpus, 18 characters from being
#: refused. Estimating this constant rather than measuring it does not work.
THIN_EXTRACTION_CHARS = 1000

#: UX.md §4 step 1. Candidates land in `temp_data/images/<slug>/` with a
#: manifest recording each source URL, and are never auto-published.
MAX_CANDIDATE_IMAGES = 6

#: UX.md §4 step 3. Long edge, webp, for the one image a reviewer may publish.
PUBLISHED_IMAGE_MAX_PX = 1600

#: UX.md §1.3. A queue row older than this shows its age in the warn colour and
#: the word `stale`. An unresolved ownership check left sitting is the thing
#: this is watching for.
STALE_DRAFT_DAYS = 7

#: SCHEMA.md §2. Mirrors the zod schema's `summary: z.string().min(1).max(160)`.
#: `/validate` check 13 diffs the two, so this cannot drift silently.
SUMMARY_MAX_CHARS = 160

#: SCHEMA.md §2 / §7 and DESIGN.md §4: body copy is 350 to 700 words. Outside
#: that range the draft is chipped FLAGGED rather than blocked (UX.md §1.3).
MIN_PROSE_WORDS = 350
MAX_PROSE_WORDS = 700

#: SCHEMA.md §2: 3 to 6 pairs recommended, hard cap 8. The cap is the zod one.
FAQ_MAX_ITEMS = 8

#: UX.md §1.4, "undo, not confirmation". The SERVER window is deliberately wider
#: than the client's 3-second offer, so a click at the boundary succeeds rather
#: than racing the timer it is trying to beat.
UNDO_WINDOW_SECONDS = 10
UNDO_CLIENT_SECONDS = 3

#: The admin's own assets. Hand-written, no build step, no CDN (TRD.md §3).
TEMPLATES_DIR = ADMIN_DIR / "templates"
STATIC_DIR = ADMIN_DIR / "static"

#: The built public site. The review pane's preview links the real shipped CSS
#: from here rather than restating it (UX.md §1.4): reviewing in a different
#: skin from what ships is how errors slip through.
SITE_DIST_DIR = SITE_DIR / "dist"

#: UX.md §1.4.4 and §1.4.6. Both are Gate 4's to fill: the blocked record is
#: written by the pipeline's ownership abort, and the determination sidecar is
#: what the approve action retains. Gate 3 defines the paths and moves the
#: sidecar when one is present, so the approve action does not have to change
#: shape later.
#:
#: FLAGGED FOR THE RECORD (2026-08-07): TRD.md §3's repository tree names
#: neither directory, while UX.md §1.4.4 and §1.4.6 both require them by name.
#: They are placed under `content-staging/` because that is gitignored volume
#: state and because the deploy allow-list (TRD.md §6.5) does not carry either
#: one, which settles that they are working files rather than published record.
BLOCKED_DIR = CONTENT_STAGING_DIR / "_blocked"
DETERMINATIONS_DIR = CONTENT_STAGING_DIR / "_determinations"
