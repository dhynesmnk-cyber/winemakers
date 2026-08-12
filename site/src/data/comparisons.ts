/**
 * comparisons.ts — the comparison registry and its minimum-producer threshold.
 *
 * GATE 9 OWNS THIS FILE.
 *
 * ── The registry is derived, not hand-listed ──────────────────────────────────
 *
 * TRD.md §3 calls this a "comparison registry", and `regions.ts` and
 * `glossary.ts` — the other two hand-authored registers — set the expectation
 * that a register is a literal list. This one is not, deliberately.
 *
 * The comparison family chosen for Gate 9 is VARIETY WITHIN A REGION, which is
 * combinatorial: 106 pairs exist across the current corpus and the set moves
 * every time a producer is published. A hand-listed register would need an
 * entry added on most approvals, would silently rot when a variety fell below
 * the threshold, and would be a fourth surface to keep name-matched against a
 * vocabulary that already has four (CLAUDE.md rule 7). What is authored here is
 * the FAMILY and its rule; the members are read from the published set, exactly
 * as `taxonomy.ts` reads its five present-only taxonomies.
 *
 * ── Skip and log, never fail ──────────────────────────────────────────────────
 *
 * CLAUDE.md Gate 9 and DESIGN.md §501: below `MIN_COMPARISON_PRODUCERS` the
 * page is skipped and logged, "never rendered thin and never failed". A thin
 * comparison is worse than no comparison — a table of two producers invites a
 * reader to draw a conclusion the sample cannot carry — but a build that dies
 * because a grape lost its fourth producer is worse still. At the current
 * corpus 16 pairs clear and 90 skip, so the skipping branch is the common one
 * and is exercised on every build rather than only by a fixture.
 *
 * ── Ordering is stated, because unstated ordering reads as a ranking ──────────
 *
 * UX.md §5: "no 'best of' ordering that is not explicitly defined ... Ordering
 * on every listing is stated in words where it is not obvious". Rows are A to Z
 * by producer name and the page says so above the table. There is no column the
 * table can be sorted by, no default sort that implies quality, and no score.
 */
import {
  MIN_COMPARISON_PRODUCERS,
  VARIETY_KEYS,
  VARIETY_LABELS,
} from "../config.ts";
import { REGION_SLUGS, regionName, regionWithArticle } from "./regions.ts";
import { allProducers, byName, list, varietyHref } from "./taxonomy.ts";
import type { Producer } from "./taxonomy.ts";

/** A comparison that cleared the threshold and therefore gets a page. */
export interface Comparison {
  /** `chardonnay-in-adelaide-hills`. */
  slug: string;
  varietySlug: string;
  varietyName: string;
  regionSlug: string;
  /** Bare name, for link labels and table cells (`regions.ts` on the article). */
  regionName: string;
  /** Mid-sentence form: "the Adelaide Hills", "McLaren Vale". Prose only. */
  regionInWords: string;
  href: string;
  /** The `<h1>` and the table's `<caption>`, in words. */
  heading: string;
  /** The `<title>`, in the house register. */
  title: string;
  count: number;
  /** A to Z by name. The ordering is stated on the page. */
  producers: Producer[];
}

export const comparisonHref = (slug: string) => `/compare/${slug}/`;

/** The hub. Named once here so no call site types the string. */
export const COMPARE_HUB = "/compare/";

/**
 * Logged once per build, not once per `getStaticPaths` that asks.
 *
 * `taxonomy.ts` carries the same guard and the same reasoning: Astro evaluates
 * each route's `getStaticPaths` separately, and the hub and the detail route
 * both want this list. Without the guard the ninety skips print twice and the
 * log stops being read.
 */
let logged = false;

function logSkips(kept: number, skipped: string[]): void {
  if (logged) return;
  logged = true;

  console.log(
    `[compare]  ${kept} present, ${skipped.length} skipped (under ${MIN_COMPARISON_PRODUCERS} producers)`,
  );
  if (skipped.length > 0) {
    console.log(`[compare]  skipped: ${skipped.join(", ")}`);
  }
}

let cache: Comparison[] | null = null;

/**
 * Every variety-within-region pair carrying at least `MIN_COMPARISON_PRODUCERS`
 * published producers, in variety-register order then region-register order.
 *
 * A producer counts for a region if that region appears anywhere in `regions`,
 * not only as `primary_region` — a producer working fruit across two regions is
 * genuinely comparable in both, and the region pages already list them that way.
 */
export async function comparisonsPresent(): Promise<Comparison[]> {
  if (cache) return cache;

  const producers = await allProducers();
  const kept: Comparison[] = [];
  const skipped: string[] = [];

  for (const varietySlug of VARIETY_KEYS) {
    for (const regionSlug of REGION_SLUGS) {
      const matched = producers
        .filter(
          (p) =>
            list(p.data.varieties).includes(varietySlug) &&
            list(p.data.regions).includes(regionSlug),
        )
        .sort(byName);

      // Zero is not a skip worth naming. The taxonomy is 71 regions by 60-odd
      // varieties, so logging every empty pair would print thousands of lines
      // and bury the ones that are genuinely close to the threshold.
      if (matched.length === 0) continue;

      const slug = `${varietySlug}-in-${regionSlug}`;
      if (matched.length < MIN_COMPARISON_PRODUCERS) {
        skipped.push(`${slug} (${matched.length})`);
        continue;
      }

      const varietyName = VARIETY_LABELS[varietySlug];
      kept.push({
        slug,
        varietySlug,
        varietyName,
        regionSlug,
        regionName: regionName(regionSlug),
        regionInWords: regionWithArticle(regionSlug),
        href: comparisonHref(slug),
        heading: `${varietyName} in ${regionWithArticle(regionSlug)}`,
        title: `${varietyName} producers in ${regionWithArticle(regionSlug)}`,
        count: matched.length,
        producers: matched,
      });
    }
  }

  logSkips(kept.length, skipped);
  cache = kept;
  return kept;
}

/** One comparison by slug, or undefined. */
export async function comparisonBySlug(
  slug: string,
): Promise<Comparison | undefined> {
  return (await comparisonsPresent()).find((c) => c.slug === slug);
}

/**
 * The comparisons a given producer appears in.
 *
 * This is what makes a producer page link SIDEWAYS into the comparison surface
 * (UX.md §2.4), and it is counted by `/validate` check 17 towards the three
 * aggregation pages every producer must be reachable from.
 */
export async function comparisonsForProducer(
  producerSlug: string,
): Promise<Comparison[]> {
  return (await comparisonsPresent()).filter((c) =>
    c.producers.some((p) => p.id === producerSlug),
  );
}

/** The comparisons drawn from one variety, for the variety page's sideways links. */
export async function comparisonsForVariety(
  varietySlug: string,
): Promise<Comparison[]> {
  return (await comparisonsPresent()).filter((c) => c.varietySlug === varietySlug);
}

/** The comparisons drawn from one region, for the region page's sideways links. */
export async function comparisonsForRegion(
  regionSlug: string,
): Promise<Comparison[]> {
  return (await comparisonsPresent()).filter((c) => c.regionSlug === regionSlug);
}

/** Grouped by variety for the hub, in variety-register order. */
export async function comparisonsByVariety(): Promise<
  { slug: string; name: string; href: string; comparisons: Comparison[] }[]
> {
  const all = await comparisonsPresent();
  const groups: {
    slug: string;
    name: string;
    href: string;
    comparisons: Comparison[];
  }[] = [];

  for (const varietySlug of VARIETY_KEYS) {
    const comparisons = all.filter((c) => c.varietySlug === varietySlug);
    if (comparisons.length === 0) continue;
    groups.push({
      slug: varietySlug,
      name: VARIETY_LABELS[varietySlug],
      href: varietyHref(varietySlug),
      comparisons,
    });
  }

  return groups;
}

/**
 * The regions a comparison's siblings sit in, for the "sideways" links UX.md
 * §2.4 requires of every programmatic page: the same grape in another region.
 */
export async function siblingComparisons(
  current: Comparison,
): Promise<Comparison[]> {
  return (await comparisonsForVariety(current.varietySlug)).filter(
    (c) => c.slug !== current.slug,
  );
}
