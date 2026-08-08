/**
 * taxonomy.ts — the one place the taxonomy meets the published set.
 *
 * GATE 6 OWNS THIS FILE.
 *
 * ── Why it exists ─────────────────────────────────────────────────────────────
 *
 * Six route families — region, subregion, state, variety, practice and the A to
 * Z index — need the same three things: which taxonomy values actually have
 * published producers, how many each has, and a slice of them for page N. Six
 * copies of that is six chances for one of them to emit a page for a region
 * with nothing in it.
 *
 * PRESENT-ONLY IS THE WHOLE POINT (CLAUDE.md Gate 6, UX.md §2.4, TRD.md §4.2
 * rule 2). Loop the taxonomy, `continue` on zero, log the skip, never render an
 * empty page. Every `*Present()` function below returns only members with at
 * least one published producer, and every `getStaticPaths` in `pages/` is built
 * from one of them. A route file that filters the collection itself has
 * reintroduced the bug this module exists to prevent.
 *
 * ── It sits in /data, and it is not data ──────────────────────────────────────
 *
 * TRD.md §3's tree describes `/data` as the register plus the generated
 * artefacts, and this is query logic. It lives here anyway, beside `regions.ts`
 * and `glossary.ts`, because those two files are what it spends its time
 * reading and the alternative was a new directory or 300 lines of async
 * collection queries inside the hand-mirrored `config.ts`. Recorded so the next
 * person does not read the placement as precedent for putting logic in `/data`
 * generally.
 *
 * ── The one thing NOT filtered ────────────────────────────────────────────────
 *
 * The glossary is generated UNCONDITIONALLY, for every value of every closed
 * vocabulary, whether or not a producer uses the term (UX.md §2.4). It does not
 * come through this module, and `/validate` check 11 enforces it in both
 * directions. Present-only is a rule about producer LISTINGS, never about
 * definitions: a reader who meets `amphora` on a producer page needs the word
 * explained even when that producer is the only one using it.
 */

import { getCollection, type CollectionEntry } from "astro:content";

import {
  PRACTICE_KEYS,
  PRACTICE_LABELS,
  PRODUCERS_PER_PAGE,
  STATES,
  STATE_NAMES,
  VARIETY_KEYS,
  VARIETY_LABELS,
  type PracticeKey,
  type State,
} from "../config.ts";
import {
  REGIONS,
  REGION_BY_SLUG,
  SUBREGION_BY_SLUG,
  regionName,
  subregionName,
  subregionsForRegion,
} from "./regions.ts";
import forewordsData from "./forewords.json";

export type Producer = CollectionEntry<"producers">;

/**
 * `subregions`, `varieties` and `wine_styles` are `.optional()` in the zod
 * schema, so they arrive as `undefined` rather than `[]` on a producer whose
 * source named none. SCHEMA.md §5 is why they are optional: a variety appears
 * only where the source named it, and an empty array would assert "we checked
 * and there are none" where the truth is "nobody said".
 */
const list = (value: readonly string[] | undefined): readonly string[] =>
  value ?? [];

/* ═══════════════════════════════════════════════════════════════════════════
   1. The published set
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Sort order for every producer listing on the site: name, A to Z, in en-AU.
 *
 * One order everywhere is deliberate. `/producers/` is the completeness route
 * (UX.md §2.2), and a reader who works through page 3 of a region and then page
 * 3 of the index should not have to work out that the two are sorted
 * differently.
 */
export function byName(a: Producer, b: Producer): number {
  return a.data.name.localeCompare(b.data.name, "en-AU");
}

/**
 * Most recently drafted first, then name. The homepage's fixed slice only
 * (UX.md §2.1 item 5).
 *
 * THE TIEBREAK IS LOAD-BEARING. A batch harvest stamps one `drafted` date
 * across a whole run, so without a second key the homepage's eight rows would
 * reorder between builds on nothing more than sort stability, and `/validate`
 * check 3 would see the derived artefacts churn.
 */
export function byDraftedDesc(a: Producer, b: Producer): number {
  const delta = b.data.drafted.getTime() - a.data.drafted.getTime();
  return delta !== 0 ? delta : byName(a, b);
}

let cached: Producer[] | null = null;

/** Every published producer, A to Z. Read once per build. */
export async function allProducers(): Promise<Producer[]> {
  if (cached === null) {
    cached = (await getCollection("producers")).sort(byName);
  }
  return cached;
}

/* ═══════════════════════════════════════════════════════════════════════════
   2. Slugs and paths
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * The eight state slugs (TRD.md §3 amendment, 2026-08-08): the slugified full
 * name, `/south-australia/`, never the two-letter code. Every other public
 * route slugifies a human name, and DESIGN.md §5 states the rule for states
 * specifically — words, not codes.
 */
export function stateSlug(code: State): string {
  return STATE_NAMES[code].toLowerCase().replace(/\s+/g, "-");
}

const STATE_BY_SLUG: ReadonlyMap<string, State> = new Map(
  STATES.map((code) => [stateSlug(code), code]),
);

export function stateFromSlug(slug: string): State | undefined {
  return STATE_BY_SLUG.get(slug);
}

export const regionHref = (slug: string) => `/region/${slug}/`;
export const subregionHref = (region: string, sub: string) =>
  `/region/${region}/${sub}/`;
export const stateHref = (code: State) => `/${stateSlug(code)}/`;
export const varietyHref = (slug: string) => `/variety/${slug}/`;
export const practiceHref = (key: string) => `/practice/${key}/`;
export const producerHref = (slug: string) => `/producer/${slug}/`;
export const glossaryHref = (slug: string) => `/glossary/${slug}/`;

/**
 * UX.md §2.2. Page 1 is the bare route and is never also available at a second
 * URL, so there is no duplicate content and no canonical juggling. Pages 2 and
 * up take a literal `page/` segment, which is what keeps
 * `/region/adelaide-hills/page/2/` from colliding with
 * `/region/adelaide-hills/[subregion]/` — a bare `/region/adelaide-hills/2/`
 * would. The same shape is used on every route, including those with no
 * collision risk, because one rule is easier to hold than two.
 */
export function pageHref(base: string, n: number): string {
  return n === 1 ? base : `${base}page/${n}/`;
}

/* ═══════════════════════════════════════════════════════════════════════════
   3. Present-only membership
   ═══════════════════════════════════════════════════════════════════════════ */

export type TaxonomyKind =
  | "region"
  | "subregion"
  | "state"
  | "variety"
  | "practice";

export interface TaxonomyMember {
  kind: TaxonomyKind;
  /** The taxonomy value's own slug, as it appears in frontmatter. */
  slug: string;
  /** Display name, in words. */
  name: string;
  /** Page-1 href. */
  href: string;
  count: number;
  producers: Producer[];
}

/**
 * Skips are logged ONCE PER BUILD, not once per route file that asks.
 *
 * Astro evaluates each `getStaticPaths` separately and several of them want the
 * same list, so without this the same sixty-odd skipped regions would print
 * five times over and the log would stop being read. The Gate 6 done-condition
 * asks that the skip be logged. It does not ask for it to be logged repeatedly.
 */
const logged = new Set<TaxonomyKind>();

function logSkips(kind: TaxonomyKind, present: number, skipped: string[]): void {
  if (logged.has(kind)) return;
  logged.add(kind);

  const label = kind.padEnd(9);
  console.log(
    `[taxonomy] ${label} ${present} present, ${skipped.length} skipped (no published producers)`,
  );
  if (skipped.length > 0) {
    console.log(`[taxonomy] ${" ".repeat(9)} skipped: ${skipped.join(", ")}`);
  }
}

/**
 * The shared shape of every present-only builder: walk the closed taxonomy in
 * its authored order, collect the producers matching each member, drop the
 * empties, log what was dropped.
 */
function present<K extends { slug: string; name: string; href: string }>(
  kind: TaxonomyKind,
  members: readonly K[],
  match: (member: K) => Producer[],
): TaxonomyMember[] {
  const kept: TaxonomyMember[] = [];
  const skipped: string[] = [];

  for (const member of members) {
    const producers = match(member);
    if (producers.length === 0) {
      skipped.push(member.slug);
      continue;
    }
    kept.push({
      kind,
      slug: member.slug,
      name: member.name,
      href: member.href,
      count: producers.length,
      producers,
    });
  }

  logSkips(kind, kept.length, skipped);
  return kept;
}

/** Every GI region with at least one published producer, in register order. */
export async function regionsPresent(): Promise<TaxonomyMember[]> {
  const producers = await allProducers();
  return present(
    "region",
    REGIONS.map((r) => ({ slug: r.slug, name: r.name, href: regionHref(r.slug) })),
    (r) => producers.filter((p) => p.data.regions.includes(r.slug)),
  );
}

/**
 * Every subregion of one region with at least one published producer.
 *
 * A producer in a subregion appears on BOTH its subregion page and its region
 * page (UX.md §2.4). The region page is the superset and never a remainder
 * list, so nothing here subtracts.
 */
export async function subregionsPresent(
  regionSlug: string,
): Promise<TaxonomyMember[]> {
  const producers = await allProducers();
  const inRegion = producers.filter((p) => p.data.regions.includes(regionSlug));

  const kept: TaxonomyMember[] = [];
  for (const sub of subregionsForRegion(regionSlug)) {
    const members = inRegion.filter((p) =>
      list(p.data.subregions).includes(sub.slug),
    );
    if (members.length === 0) continue;
    kept.push({
      kind: "subregion",
      slug: sub.slug,
      name: sub.name,
      href: subregionHref(regionSlug, sub.slug),
      count: members.length,
      producers: members,
    });
  }
  return kept;
}

/**
 * Every subregion, across every region, that has a published producer, paired
 * with its parent region slug. This is what the subregion route's
 * `getStaticPaths` walks.
 */
export async function allSubregionsPresent(): Promise<
  { region: string; sub: TaxonomyMember }[]
> {
  const regions = await regionsPresent();
  const out: { region: string; sub: TaxonomyMember }[] = [];
  const skipped: string[] = [];

  for (const region of regions) {
    const subs = await subregionsPresent(region.slug);
    const kept = new Set(subs.map((s) => s.slug));
    for (const sub of subregionsForRegion(region.slug)) {
      if (!kept.has(sub.slug)) skipped.push(sub.slug);
    }
    for (const sub of subs) out.push({ region: region.slug, sub });
  }

  logSkips("subregion", out.length, skipped);
  return out;
}

/**
 * Every state with at least one published producer.
 *
 * Membership is `location.state`, which is where the producer IS, not which GIs
 * they may label with. Murray Darling, Swan Hill and Canberra District
 * genuinely span two states; a producer still sits in exactly one.
 */
export async function statesPresent(): Promise<TaxonomyMember[]> {
  const producers = await allProducers();
  return present(
    "state",
    STATES.map((code) => ({
      slug: stateSlug(code),
      name: STATE_NAMES[code],
      href: stateHref(code),
      code,
    })),
    (s) => producers.filter((p) => p.data.location.state === s.code),
  );
}

/**
 * The regions of one state, with the count of producers in BOTH.
 *
 * The intersection matters for the three border-spanning regions. On the
 * Victoria page, Murray Darling's count is its Victorian producers and not its
 * total: a reader on a state page is asking what is in that state, and a count
 * that silently included New South Wales would not add up against the list
 * printed underneath it.
 */
export async function regionsForStatePresent(
  code: State,
): Promise<TaxonomyMember[]> {
  const producers = (await allProducers()).filter(
    (p) => p.data.location.state === code,
  );
  const kept: TaxonomyMember[] = [];

  for (const region of REGIONS) {
    if (!region.states.includes(code)) continue;
    const members = producers.filter((p) => p.data.regions.includes(region.slug));
    if (members.length === 0) continue;
    kept.push({
      kind: "region",
      slug: region.slug,
      name: region.name,
      href: regionHref(region.slug),
      count: members.length,
      producers: members,
    });
  }
  return kept;
}

/** Every variety at least one published producer lists. */
export async function varietiesPresent(): Promise<TaxonomyMember[]> {
  const producers = await allProducers();
  return present(
    "variety",
    VARIETY_KEYS.map((slug) => ({
      slug,
      name: VARIETY_LABELS[slug],
      href: varietyHref(slug),
    })),
    (v) => producers.filter((p) => list(p.data.varieties).includes(v.slug)),
  );
}

/**
 * Every practice at least one published producer declares TRUE.
 *
 * False is not the opposite of true here. SCHEMA.md §1.6 and UX.md §2.3: an
 * absent or false practice is absence of evidence, and no page asserts it
 * either way. There is no `/practice/not-unfined/` and there never will be.
 */
export async function practicesPresent(): Promise<TaxonomyMember[]> {
  const producers = await allProducers();
  return present(
    "practice",
    PRACTICE_KEYS.map((key) => ({
      slug: key,
      name: PRACTICE_LABELS[key],
      href: practiceHref(key),
    })),
    (k) =>
      producers.filter((p) => p.data.practices[k.slug as PracticeKey] === true),
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   4. Pagination — UX.md §2.2
   ═══════════════════════════════════════════════════════════════════════════ */

export interface PageLink {
  n: number;
  href: string;
  current: boolean;
}

export interface Paged {
  items: Producer[];
  current: number;
  totalPages: number;
  totalItems: number;
  /** Page-1 href, which is the bare route. */
  base: string;
  prev: string | null;
  next: string | null;
  links: PageLink[];
  /** UX.md §2.2: a single-page listing renders NO pager, not a pager reading `1`. */
  showPager: boolean;
}

export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / PRODUCERS_PER_PAGE));
}

/** Pages 2..N, for the `page/[page]` route files. Empty when there is one page. */
export function extraPages(total: number): number[] {
  return Array.from({ length: pageCount(total) - 1 }, (_, i) => i + 2);
}

export function paginate(items: Producer[], current: number, base: string): Paged {
  const totalPages = pageCount(items.length);
  const start = (current - 1) * PRODUCERS_PER_PAGE;

  return {
    items: items.slice(start, start + PRODUCERS_PER_PAGE),
    current,
    totalPages,
    totalItems: items.length,
    base,
    prev: current > 1 ? pageHref(base, current - 1) : null,
    next: current < totalPages ? pageHref(base, current + 1) : null,
    links: Array.from({ length: totalPages }, (_, i) => ({
      n: i + 1,
      href: pageHref(base, i + 1),
      current: i + 1 === current,
    })),
    showPager: totalPages > 1,
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   5. Forewords — UX.md §2.4
   ═══════════════════════════════════════════════════════════════════════════ */

type ForewordBuckets = Partial<Record<TaxonomyKind, Record<string, string>>>;
const forewords = forewordsData as ForewordBuckets;

/**
 * The foreword for one taxonomy member, or null.
 *
 * NULL IS A FIRST-CLASS ANSWER. UX.md §1.5 row 19: a foreword that failed to
 * generate is non-fatal, and the page renders without one rather than not
 * rendering. Forewords are drafted once into `forewords.json` by
 * `admin/pipeline/forewords.py`, are human-editable afterwards, and are never
 * regenerated on every build — copy that churns every build is copy nobody
 * trusts.
 */
export function foreword(kind: TaxonomyKind, key: string): string | null {
  const text = forewords[kind]?.[key];
  return typeof text === "string" && text.trim().length > 0 ? text.trim() : null;
}

/**
 * The meta description for a programmatic page: the foreword's first sentence
 * (UX.md §2.4), falling back to `fallback` where no foreword exists yet. Capped
 * at the 160 characters SCHEMA.md holds `summary` to.
 */
export function metaDescription(
  kind: TaxonomyKind,
  key: string,
  fallback: string,
): string {
  const text = foreword(kind, key);
  if (text === null) return fallback.slice(0, 160);
  const firstSentence = text.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? text;
  return firstSentence.trim().slice(0, 160);
}

/* ═══════════════════════════════════════════════════════════════════════════
   6. Breadcrumbs
   ═══════════════════════════════════════════════════════════════════════════ */

export interface Crumb {
  label: string;
  /** Null on the last crumb, which is the current page and is not a link. */
  href: string | null;
}

export function regionCrumbs(regionSlug: string): Crumb[] {
  return [
    { label: "Home", href: "/" },
    { label: "Regions", href: "/region/" },
    { label: regionName(regionSlug), href: null },
  ];
}

/** Four deep, per UX.md §2.4. */
export function subregionCrumbs(regionSlug: string, subSlug: string): Crumb[] {
  return [
    { label: "Home", href: "/" },
    { label: "Regions", href: "/region/" },
    { label: regionName(regionSlug), href: regionHref(regionSlug) },
    { label: subregionName(subSlug), href: null },
  ];
}

export function simpleCrumbs(hub: Crumb, current: string): Crumb[] {
  return [{ label: "Home", href: "/" }, hub, { label: current, href: null }];
}

/* ═══════════════════════════════════════════════════════════════════════════
   7. Build-time guards
   ═══════════════════════════════════════════════════════════════════════════

   Module scope, so a collision fails `astro build` with a named slug rather
   than showing up later as a mysteriously missing page.
   ═══════════════════════════════════════════════════════════════════════════ */

if (SUBREGION_BY_SLUG.has("page")) {
  throw new Error(
    `regions.ts has a subregion slugged "page", which collides with the ` +
      `pagination segment at /region/[region]/page/[n]/ (UX.md §2.2). Rename it.`,
  );
}

/**
 * UX.md §2.4: the eight state slugs are the only top-level dynamic paths, and
 * NO OTHER TOP-LEVEL ROUTE may take one of them.
 *
 * The check is against top-level segments only. `tasmania` and
 * `northern-territory` are deliberately both a state slug and a region slug,
 * and that is not a collision: the state page is `/tasmania/` and the region
 * page is `/region/tasmania/`. Different namespaces, both reachable, both
 * correct. An earlier version of this guard compared the two lists directly and
 * would have failed the build on a register that is right.
 */
const RESERVED_TOP_LEVEL: readonly string[] = [
  "region",
  "variety",
  "practice",
  "glossary",
  "producer",
  "producers",
  "compare",
  "methodology",
  "blog",
  "images",
  "fonts",
  "page",
];

for (const slug of STATE_BY_SLUG.keys()) {
  if (RESERVED_TOP_LEVEL.includes(slug)) {
    throw new Error(
      `The state slug "${slug}" collides with the top-level route /${slug}/.`,
    );
  }
}
