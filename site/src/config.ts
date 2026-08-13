/**
 * config.ts — the TypeScript half of the hand-mirrored config pair.
 *
 * GATE 1 OWNS THIS FILE. Its Python twin is `admin/config.py`.
 *
 * ── The mirror is held by discipline and nothing else ────────────────────────
 *
 * Nothing generates one of these files from the other. They are hand-mirrored,
 * which means they drift, which is why `/validate` check 13 diffs them and why
 * the `schema-guardian` agent exists. Any vocabulary change lands in BOTH, in
 * the same commit, name-matched (CLAUDE.md rule 7).
 *
 * SCHEMA.md §1 is the source of truth for every tuple below. Adding a value here
 * is a schema change, not a config edit: it moves the zod schema, the SQLite
 * DDL, the Harvester validator and the admin frontmatter editor with it. Load
 * the `schema-change` skill before touching one.
 *
 * **Never write an enum literal inline anywhere else in the codebase.** The zod
 * sub-schemas are built programmatically from these tuples (SCHEMA.md §8), so
 * adding a key to a tuple carries the schema with it.
 */

import { VARIETY_SLUGS } from "./data/glossary.ts";
import type { StateCode } from "./data/regions.ts";

/* ═══════════════════════════════════════════════════════════════════════════
   1. Identity
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * The brand name, chosen and signed off 2026-08-12. It was a placeholder
 * (`SITE_NAME_PENDING`) from Wave 2 until then, on the rule that the name must
 * never be guessed; that rule is discharged, not relaxed.
 *
 * Recorded verbatim as given, lowercase included. Every surface that shows a
 * name reads this constant, so the casing is decided here and nowhere else —
 * do not re-case it at a call site.
 *
 * Explicitly ruled out: "Where We Pour".
 */
export const SITE_NAME = "winelister";

/** PLACEHOLDER, same rule as SITE_NAME. DESIGN.md §5c. */
export const SITE_TAGLINE = "A field guide to independent Australian winemakers";

/**
 * The public host. **Interim, and deliberately not the brand domain** — see
 * TRD.md §2.4's 2026-08-09 amendment.
 *
 * This was `https://example.invalid` until 2026-08-09, which put 156 dead
 * `<loc>` entries in the production sitemap: Astro feeds this constant to
 * `astro.config.mjs`'s `site:`, so every absolute URL the build emits was
 * pointing at a host that does not resolve.
 *
 * The Netlify subdomain is not a guess at the brand. TRD.md §2.4 already
 * treats it as the public host until a custom domain exists, and 301s it to
 * the apex afterwards. `SITE_NAME` stays pending: the domain switch and the
 * brand name are separate decisions and only one of them has been made.
 *
 * `admin/config.py` mirrors this, and `.env`'s `SITE_URL` overrides that
 * mirror at runtime, so the value has to match in all three.
 */
export const SITE_URL = "https://winemakers.netlify.app";

/**
 * The address a producer writes to when they think this guide has them wrong.
 *
 * **Decided 2026-08-13**, supplied by the user, replacing the Wave 2 placeholder
 * `hello@example.invalid`. The last placeholder in the build, and it carried
 * further than it looked: the footer publishes it as a working `mailto:` on
 * every page, and the methodology page tells producers to "write to us at the
 * contact address on this site" — which is the one page whose entire job is to
 * be answerable, on a site whose whole claim is that it can be corrected.
 *
 * `Organization.email` in `data/jsonld.ts` is emitted conditionally and starts
 * publishing on this change, so the address is now machine-readable as well as
 * reader-facing. That is the intended state; the condition existed only to keep
 * a crawler from being told an address that could not receive mail.
 *
 * Not mirrored into `admin/config.py`, and deliberately: the site is its sole
 * consumer, exactly as with `SITE_NAME`. Check 13 does not diff it.
 */
export const SITE_CONTACT_EMAIL = "d.hynes.mnk@gmail.com";

/** DESIGN.md §2. Read by the FOUC-avoiding head script and the theme toggle. */
export const THEME_STORAGE_KEY = "wm-theme";

/* ═══════════════════════════════════════════════════════════════════════════
   2. Closed vocabularies — SCHEMA.md §1
   ═══════════════════════════════════════════════════════════════════════════ */

/** SCHEMA.md §1.1 */
export const CATEGORIES = [
  "estate_winery",
  "urban_winery",
  "negociant",
  "garagiste",
  "cooperative",
  "other",
] as const;

/** SCHEMA.md §1.2 */
export const CELLAR_DOOR_STATES = ["none", "by_appointment", "open"] as const;

/** SCHEMA.md §1.3 */
export const CERTIFICATION_STATES = ["none", "practising", "certified"] as const;

/** SCHEMA.md §1.4 */
export const FRUIT_SOURCE = ["estate", "purchased", "mixed"] as const;

/** SCHEMA.md §1.5 */
export const PRODUCTION_BANDS = [
  "under_1000",
  "1000_5000",
  "5000_20000",
  "over_20000",
  "unknown",
] as const;

/** SCHEMA.md §1.6 — canonical order. There is no `low_intervention` key and there never will be. */
export const PRACTICE_KEYS = [
  "wild_ferment",
  "unfined",
  "unfiltered",
  "minimal_so2",
] as const;

/** SCHEMA.md §1.7 */
export const LOGISTICS_KEYS = [
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
] as const;

/** SCHEMA.md §1.8 */
export const VESSEL_KEYS = [
  "stainless",
  "oak_barrique",
  "oak_foudre",
  "concrete",
  "amphora",
  "ceramic",
  "glass",
] as const;

/** SCHEMA.md §1.9 */
export const WINE_STYLE_KEYS = [
  "red",
  "white",
  "rose",
  "sparkling",
  "skin_contact",
  "fortified",
  "dessert",
] as const;

/**
 * SCHEMA.md §1.10 — the seed set, authored in Wave 2.
 *
 * Derived from `glossary.ts` rather than retyped, because the glossary must
 * carry an entry for every variety (`/validate` check 11) and two hand-kept
 * copies of 58 slugs would drift on the first addition. `glossary.ts` is the
 * authority; this is the projection of it.
 *
 * `admin/config.py` cannot import a TypeScript module, so it carries the list
 * literally. That copy is the one that drifts — check 13 diffs it.
 */
export const VARIETY_KEYS = VARIETY_SLUGS as readonly string[];

/** SCHEMA.md §1.11, weakest → strongest. */
export const CONFIDENCE_TIERS = [
  "unverified",
  "published_by_producer",
  "observed_on_visit",
  "operator_confirmed",
] as const;

/**
 * Rank for SCHEMA.md §2b: a re-harvest UPGRADES, never silently downgrades.
 * Index into `CONFIDENCE_TIERS`, so the order above is load-bearing.
 */
export const CONFIDENCE_TIER_RANK: Record<ConfidenceTier, number> =
  Object.fromEntries(
    CONFIDENCE_TIERS.map((tier, index) => [tier, index]),
  ) as Record<ConfidenceTier, number>;

/** SCHEMA.md §1.12. Not a vocabulary of values — a list of field names. Not glossed. */
export const VERIFIABLE_FIELDS = [
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
] as const;

/** SCHEMA.md §1.13 */
export const OWNERSHIP_EVIDENCE_METHODS = [
  "registry",
  "producer_statement",
  "trade_source",
] as const;

/**
 * SCHEMA.md §1.15 — added 2026-08-09.
 *
 * Whether a dated source positively states who owns the business. `unconfirmed`
 * publishes with a visible notice and the site makes no independence claim for
 * the entry. It is the absence of evidence, never a fourth evidence route.
 *
 * Mirrored by hand in `admin/config.py`. Nothing generates one from the other.
 */
export const OWNERSHIP_STATES = ["confirmed", "unconfirmed"] as const;

/**
 * SCHEMA.md §1.16 — added 2026-08-10.
 *
 * The three independent paths the deny-list runs against `data/ownership.json`.
 * `audit_exemptions` records which one a judged false positive answers, and
 * only `name` is ever exemptable (SCHEMA.md §2a rule 15).
 *
 * Mirrored by hand in `admin/config.py`. Nothing generates one from the other.
 */
export const DENY_LIST_CHECKS = ["name", "domain", "abn"] as const;

/** SCHEMA.md §1.14 */
export const STATES = ["VIC", "NSW", "QLD", "SA", "WA", "TAS", "NT", "ACT"] as const;

export type Category = (typeof CATEGORIES)[number];
export type CellarDoorState = (typeof CELLAR_DOOR_STATES)[number];
export type CertificationState = (typeof CERTIFICATION_STATES)[number];
export type FruitSource = (typeof FRUIT_SOURCE)[number];
export type ProductionBand = (typeof PRODUCTION_BANDS)[number];
export type PracticeKey = (typeof PRACTICE_KEYS)[number];
export type LogisticsKey = (typeof LOGISTICS_KEYS)[number];
export type VesselKey = (typeof VESSEL_KEYS)[number];
export type WineStyleKey = (typeof WINE_STYLE_KEYS)[number];
export type ConfidenceTier = (typeof CONFIDENCE_TIERS)[number];
export type VerifiableField = (typeof VERIFIABLE_FIELDS)[number];
export type OwnershipEvidenceMethod = (typeof OWNERSHIP_EVIDENCE_METHODS)[number];
export type OwnershipState = (typeof OWNERSHIP_STATES)[number];
export type State = (typeof STATES)[number];

/**
 * `regions.ts` declares its own `StateCode` because Wave 2 could not import a
 * file Gate 1 had not written yet. These two assignments fail to compile if the
 * two ever disagree about the state set, in either direction.
 * (CONSTANTS-REQUIRED.md §2.2.)
 */
const _stateForward: StateCode = "VIC" as State;
const _stateBackward: State = "VIC" as StateCode;
void _stateForward;
void _stateBackward;

/* ═══════════════════════════════════════════════════════════════════════════
   3. Bounds and ranges
   ═══════════════════════════════════════════════════════════════════════════ */

/** SCHEMA.md §2. Australia's mainland-plus-Tasmania envelope. */
export const AU_LATITUDE_BOUNDS = { min: -44.0, max: -9.0 } as const;
export const AU_LONGITUDE_BOUNDS = { min: 112.0, max: 154.0 } as const;

/**
 * The numeric ranges behind `PRODUCTION_BANDS`, for SCHEMA.md §2a rule 9.
 * `max: null` means unbounded above. `unknown` has no range and never
 * corroborates or contradicts a case figure.
 */
export const PRODUCTION_BAND_RANGES: Record<
  ProductionBand,
  { min: number; max: number | null } | null
> = {
  under_1000: { min: 0, max: 999 },
  "1000_5000": { min: 1000, max: 5000 },
  "5000_20000": { min: 5001, max: 20000 },
  over_20000: { min: 20001, max: null },
  unknown: null,
};

/* ═══════════════════════════════════════════════════════════════════════════
   4. Scale and coverage
   ═══════════════════════════════════════════════════════════════════════════ */

/** TRD.md §4.6. Page size for every server-paginated list. */
export const PRODUCERS_PER_PAGE = 24;

/**
 * UX.md §2.1 item 5. The homepage renders this many `ProducerEntry` rows —
 * the most recently `drafted` — then one link to `/producers/`, and never
 * more. It is a fixed-length slice, not a page-one of anything: the homepage
 * has no pager and mints no `/page/[n]/` route at the site root.
 *
 * VALUE SET AT GATE 6, 2026-08-08. UX.md names the constant and never gives it
 * a number, and TRD.md §3's checklist does not carry it at all. See the dated
 * TRD.md amendment for the reasoning: eight is long enough to show the guide is
 * being added to and short enough that it cannot compete with the region
 * chooser above it, which UX.md calls the main content of the page.
 */
export const HOMEPAGE_LATEST_COUNT = 8;

/**
 * UX.md §2.1 item 3. The most results the search field offers at once.
 *
 * VALUE SET AT GATE 6, 2026-08-08, same footing as `HOMEPAGE_LATEST_COUNT`.
 * Eight is a keyboard-navigable list: `↑`/`↓` reaches the last result without
 * the list running off the viewport on a phone. Search is an accelerator and
 * never the only route to anything, so truncation is not a loss of access.
 */
export const SEARCH_MAX_RESULTS = 8;

/**
 * TRD.md §4.7. Above this published-producer count the embedded search index
 * becomes a fetched one. NOT IN FORCE AT v1 and not to be built pre-emptively.
 */
export const SEARCH_INDEX_INLINE_MAX = 500;

/**
 * The four Gate 8 coverage regions, so "which regions are populated" is data
 * rather than prose. Slugs must exist in `regions.ts`; the check below is what
 * catches a typo, at build time.
 */
export const COVERAGE_REGIONS = [
  "adelaide-hills",
  "mclaren-vale",
  "yarra-valley",
  "mornington-peninsula",
] as const;

/** DESIGN.md §7 promotes these on the homepage. Same four; one name for one thing. */
export const SEED_REGIONS = COVERAGE_REGIONS;

/** Gate 9 thresholds. `MIN_AGGREGATION_LINKS` is 3 per `/validate` check 17. */
export const MIN_COMPARISON_PRODUCERS = 4;
export const MIN_AGGREGATION_LINKS = 3;

/* ═══════════════════════════════════════════════════════════════════════════
   5. Display labels — DESIGN.md § Constants
   ═══════════════════════════════════════════════════════════════════════════

   DESIGN.md §6 renders most §1 vocabularies as words, so every value needs a
   display string. Every one of them is already written as a `term` in
   `glossary.ts`, so these maps are DERIVED rather than retyped. A second
   hand-kept copy of 121 display strings is a drift surface nobody would ever
   check, and check 11 already guarantees the glossary is complete.
   ═══════════════════════════════════════════════════════════════════════════ */

import { glossaryFor, type VocabularyId } from "./data/glossary.ts";

function labelsFor<T extends string>(
  vocabulary: VocabularyId,
  keys: readonly T[],
): Record<T, string> {
  return Object.fromEntries(
    keys.map((key) => {
      const entry = glossaryFor(vocabulary, key);
      if (!entry) {
        // DESIGN.md §9: a vocabulary value with no glossary entry fails the
        // build rather than rendering blank. This is the same posture as the
        // icon coverage assertion below.
        throw new Error(
          `Glossary coverage: ${vocabulary}/${key} has no entry in glossary.ts. ` +
            `Add one, or remove the value from the tuple in config.ts. ` +
            `/validate check 11 enforces this in both directions.`,
        );
      }
      return [key, entry.term];
    }),
  ) as Record<T, string>;
}

export const CATEGORY_LABELS = labelsFor("category", CATEGORIES);
export const CELLAR_DOOR_LABELS = labelsFor("cellar-door", CELLAR_DOOR_STATES);
export const CERTIFICATION_LABELS = labelsFor("certification", CERTIFICATION_STATES);
export const FRUIT_SOURCE_LABELS = labelsFor("fruit-source", FRUIT_SOURCE);
export const PRODUCTION_BAND_LABELS = labelsFor("production-band", PRODUCTION_BANDS);
export const PRACTICE_LABELS = labelsFor("practice", PRACTICE_KEYS);
export const LOGISTICS_LABELS = labelsFor("logistics", LOGISTICS_KEYS);
export const VESSEL_LABELS = labelsFor("vessel", VESSEL_KEYS);
export const WINE_STYLE_LABELS = labelsFor("wine-style", WINE_STYLE_KEYS);
export const VARIETY_LABELS = labelsFor("variety", VARIETY_KEYS);
export const CONFIDENCE_TIER_LABELS = labelsFor("confidence-tier", CONFIDENCE_TIERS);
export const OWNERSHIP_EVIDENCE_LABELS = labelsFor(
  "ownership-evidence",
  OWNERSHIP_EVIDENCE_METHODS,
);
export const OWNERSHIP_STATE_LABELS = labelsFor("ownership-state", OWNERSHIP_STATES);
export const STATE_NAMES = labelsFor("state", STATES);

/* ═══════════════════════════════════════════════════════════════════════════
   6. Build-time coverage assertions
   ═══════════════════════════════════════════════════════════════════════════

   DESIGN.md §6 and §9: a vocabulary value with no glyph must FAIL THE BUILD,
   not render blank. These run at module scope, so the failure lands during
   `astro build` with a named key, not on a page as an empty span.
   ═══════════════════════════════════════════════════════════════════════════ */

import {
  assertIconCoverage,
  cellarDoorIcon,
  logisticsIcon,
  practiceIcon,
  styleIcon,
  vesselIcon,
} from "./icons/paths.ts";
import { isRegionSlug } from "./data/regions.ts";

assertIconCoverage("PRACTICE_KEYS", PRACTICE_KEYS, practiceIcon);
assertIconCoverage("LOGISTICS_KEYS", LOGISTICS_KEYS, logisticsIcon);
assertIconCoverage("WINE_STYLE_KEYS", WINE_STYLE_KEYS, styleIcon);
assertIconCoverage("VESSEL_KEYS", VESSEL_KEYS, vesselIcon);
// Present-only display: `cellar_door: none` renders nothing, so it is not passed.
assertIconCoverage(
  "CELLAR_DOOR_STATES",
  CELLAR_DOOR_STATES.filter((s) => s !== "none"),
  cellarDoorIcon,
);

// A coverage-region slug that does not exist in regions.ts would silently
// produce a homepage promoting a region with no page behind it.
for (const slug of COVERAGE_REGIONS) {
  if (!isRegionSlug(slug)) {
    throw new Error(
      `COVERAGE_REGIONS names "${slug}", which is not a region slug in regions.ts.`,
    );
  }
}
