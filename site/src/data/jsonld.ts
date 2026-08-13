/**
 * jsonld.ts — the structured-data graph. Gate 10, TRD.md §3, `/validate` 18.
 *
 * ONE HOME FOR EVERY NODE. Pages call a builder; no page hand-writes a
 * schema.org object. The alternative was a `@type` literal in each of nine page
 * files, which is nine places for `LocalBusiness` to quietly become `Winery`.
 *
 * ══ The rules this file is written to ═════════════════════════════════════
 *
 * 1. **Nothing is asserted here that the page does not show.** Structured data
 *    is the machine-readable copy of the page, and a field a reader cannot see
 *    is a claim nobody proofreads. Every builder takes its values from the same
 *    data the component renders.
 *
 * 2. **The honesty rule reaches here too** (CLAUDE.md rule 6). No invented
 *    `aggregateRating`, no `review`, no `priceRange` guessed from a tasting fee,
 *    no `openingHours` parsed out of a freeform string. A producer with no
 *    published photograph gets no `image` rather than a stock one.
 *
 * 3. **Absent is absent.** `omitEmpty` strips keys whose value is null or
 *    undefined rather than emitting `"foundingDate": null`, which reads as a
 *    statement that the founding date is known to be nothing. This is the
 *    present-only rule of DESIGN.md §6, in JSON.
 *
 * 4. **`LocalBusiness`, deliberately, never `Winery`** — TRD.md §2, decided
 *    2026-08-06 and declined for v1 with sign-off. `Winery` reads as a cellar
 *    door with a tasting room, and a large share of this dataset is garagiste,
 *    negociant and label-only producers with no premises a reader can visit.
 *    CLAUDE.md Gate 10 requires any move beyond `LocalBusiness` to be a dated
 *    TRD.md exception. Do not widen the type here; widen it there first.
 */

import {
  SITE_CONTACT_EMAIL,
  SITE_NAME,
  SITE_TAGLINE,
  SITE_URL,
} from "../config.ts";
import type { GlossaryEntry } from "./glossary.ts";
import type { Post } from "./posts.ts";
import { postHref } from "./posts.ts";
import type { Crumb, Producer } from "./taxonomy.ts";
import { glossaryHref, producerHref } from "./taxonomy.ts";

/** A schema.org node. Loose by design: the shapes differ per type. */
export type JsonLdNode = Record<string, unknown>;

/**
 * Stable `@id`s, so nodes reference each other instead of restating each other.
 * A producer node pointing at `#organization` is one publisher on the site; ten
 * inline copies of the publisher are ten things to keep in step.
 */
export const ORG_ID = `${SITE_URL}/#organization`;
export const WEBSITE_ID = `${SITE_URL}/#website`;

/** Absolute URL for a site-relative path. Every `url` in the graph is absolute. */
export function absolute(path: string): string {
  return new URL(path, SITE_URL).href;
}

/**
 * Drop keys with no value. See rule 3 above: a null in structured data is a
 * claim, and the claim is usually wrong.
 */
function omitEmpty(node: JsonLdNode): JsonLdNode {
  const out: JsonLdNode = {};
  for (const [key, value] of Object.entries(node)) {
    if (value === null || value === undefined) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    out[key] = value;
  }
  return out;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Sitewide — emitted by BaseLayout on every page
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * The publisher. `SITE_NAME` is lowercase by decision (2026-08-12) and is not
 * re-cased here: TRD.md's rule is that the casing is decided in `config.ts`
 * alone and no call site re-cases it.
 *
 * No `logo`. The site's mark is set in type by `SiteLogo.astro` and there is no
 * image file to point at; an `Organization` claiming a logo URL that 404s is
 * worse than one that claims none.
 *
 * `email` is emitted only when `SITE_CONTACT_EMAIL` is a real address.
 *
 * ~~It is still the Wave 2 placeholder at `example.invalid`~~ — **resolved
 * 2026-08-13**: `config.ts` carries a real address and this line now publishes
 * it, exactly as it said it would.
 *
 * The guard stays rather than being deleted. It was written because a machine-
 * readable contact address that cannot receive mail is a worse claim than no
 * contact address at all: the footer's `mailto:` shows a placeholder to a
 * reader, who can see what it is, and a crawler cannot. That reasoning is not
 * spent — it applies again to any `.invalid` address a future edit introduces,
 * and the cost of keeping it is one string comparison per build.
 */
const CONTACT_IS_PLACEHOLDER = SITE_CONTACT_EMAIL.endsWith(".invalid");

export function organization(): JsonLdNode {
  return omitEmpty({
    "@type": "Organization",
    "@id": ORG_ID,
    name: SITE_NAME,
    url: `${SITE_URL}/`,
    description: SITE_TAGLINE,
    email: CONTACT_IS_PLACEHOLDER ? undefined : SITE_CONTACT_EMAIL,
  });
}

/**
 * The site itself.
 *
 * **No `potentialAction`/`SearchAction`, deliberately.** Search here is
 * client-side over an index embedded at build time (TRD.md §4.7); there is no
 * `/search?q=` route to declare, and declaring one would send crawlers to a URL
 * that does not exist. A `SearchAction` is a promise about a route.
 */
export function website(): JsonLdNode {
  return {
    "@type": "WebSite",
    "@id": WEBSITE_ID,
    name: SITE_NAME,
    url: `${SITE_URL}/`,
    description: SITE_TAGLINE,
    inLanguage: "en-AU",
    publisher: { "@id": ORG_ID },
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   Breadcrumbs — emitted by Breadcrumbs.astro, from the crumb array it renders
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Built from the SAME `Crumb[]` the visible trail renders, which is why this
 * lives beside that component's call rather than in each page: the two cannot
 * describe different paths if there is only one array.
 *
 * The last crumb has a null `href` because it is the current page and is not a
 * link. It still needs an `item`, so the page's own URL is used.
 */
export function breadcrumbList(crumbs: Crumb[], currentPath: string): JsonLdNode {
  return {
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.label,
      item: absolute(crumb.href ?? currentPath),
    })),
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   Listings
   ═══════════════════════════════════════════════════════════════════════════ */

interface ItemListInput {
  name: string;
  description?: string;
  /** Absolute or site-relative; both are normalised. */
  items: { name: string; href: string }[];
  /** Total across a paginated series, when it exceeds the items on this page. */
  totalItems?: number;
  /** 1-based position of the FIRST item, for page 2 and up. */
  startPosition?: number;
}

/**
 * A listing of producers, in the order the page renders them.
 *
 * `itemListOrder` is spelled out rather than left to default. An unordered
 * `ItemList` over a page that IS ordered would be the structured-data version
 * of the unstated ranking UX.md §5 bans; the order here is the page's stated
 * one, and saying so is what keeps it from reading as a ranking.
 *
 * On a paginated series each page describes its own slice, with positions
 * continuing across the series so a crawler can reconstruct the whole listing.
 */
export function itemList(input: ItemListInput): JsonLdNode {
  const start = input.startPosition ?? 1;
  return omitEmpty({
    "@type": "ItemList",
    name: input.name,
    description: input.description,
    numberOfItems: input.totalItems ?? input.items.length,
    itemListOrder: "https://schema.org/ItemListOrderAscending",
    itemListElement: input.items.map((item, index) => ({
      "@type": "ListItem",
      position: start + index,
      name: item.name,
      url: absolute(item.href),
    })),
  });
}

/** The producer slice of a listing page, in render order. */
export function producerItems(
  producers: Producer[],
): { name: string; href: string }[] {
  return producers.map((producer) => ({
    name: producer.data.name,
    href: producerHref(producer.id),
  }));
}

/* ═══════════════════════════════════════════════════════════════════════════
   Producers
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * A producer entry as `LocalBusiness`. See rule 4 in the header before changing
 * the type.
 *
 * What is deliberately NOT here:
 *
 * - `openingHours`. `cellar_door_hours` is a freeform display string by schema
 *   design (SCHEMA.md §2, "never reformatted into a grid"). Parsing it into
 *   schema.org's opening-hours grammar would invent structure the source does
 *   not have, and would do it silently on the entries it got wrong.
 * - `priceRange`. A tasting fee is not a price range for the wine, and the
 *   guide does not publish bottle prices.
 * - `aggregateRating` and `review`. Nobody here has tasted anything
 *   (CLAUDE.md rule 6). There are no ratings on this site to report.
 *
 * `sameAs` carries the producer's own website and shop, which is what it is
 * for: other web pages about the same entity.
 */
export function localBusiness(producer: Producer): JsonLdNode {
  const data = producer.data;
  const url = absolute(producerHref(producer.id));
  const location = data.location;

  const address = omitEmpty({
    "@type": "PostalAddress",
    streetAddress: location.address,
    addressLocality: location.suburb,
    addressRegion: location.state,
    addressCountry: "AU",
  });

  // Both or neither: a half-coordinate is not a place.
  const hasCoordinates =
    typeof location.latitude === "number" &&
    typeof location.longitude === "number";

  return omitEmpty({
    "@type": "LocalBusiness",
    "@id": `${url}#business`,
    name: data.name,
    description: data.summary,
    url,
    address,
    geo: hasCoordinates
      ? {
          "@type": "GeoCoordinates",
          latitude: location.latitude,
          longitude: location.longitude,
        }
      : undefined,
    // A four-digit year, which is a valid ISO 8601 date for schema.org's
    // purposes and is all the guide knows. A fabricated month would be a
    // fabricated fact.
    foundingDate: data.founded_year ? String(data.founded_year) : undefined,
    image: data.image ? absolute(data.image) : undefined,
    sameAs: [data.website, data.shop_url].filter(
      (href): href is string => typeof href === "string" && href.length > 0,
    ),
    isPartOf: { "@id": WEBSITE_ID },
  });
}

/**
 * The producer page's FAQ, when it has one.
 *
 * Answers are drafted strictly from the Harvester's facts (UX.md §1 panel 9)
 * and are the same strings the page renders. `FAQPage` is emitted only where
 * the page actually shows the questions; structured data for a section that is
 * not on the page is the thing this markup gets penalised for.
 */
export function faqPage(
  faq: { question: string; answer: string }[],
  currentPath: string,
): JsonLdNode {
  return {
    "@type": "FAQPage",
    "@id": `${absolute(currentPath)}#faq`,
    mainEntity: faq.map((pair) => ({
      "@type": "Question",
      name: pair.question,
      acceptedAnswer: { "@type": "Answer", text: pair.answer },
    })),
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   Glossary — DefinedTermSet and DefinedTerm
   ═══════════════════════════════════════════════════════════════════════════ */

export const TERM_SET_ID = `${SITE_URL}/glossary/#termset`;

/**
 * The glossary as a set. Every enum value across every SCHEMA.md §1 vocabulary
 * has an entry, unconditionally, which is what `/validate` check 11 enforces in
 * both directions, so the set is the whole vocabulary rather than the terms
 * that happen to be in use.
 */
export function definedTermSet(entries: GlossaryEntry[]): JsonLdNode {
  return {
    "@type": "DefinedTermSet",
    "@id": TERM_SET_ID,
    name: `${SITE_NAME} glossary`,
    description:
      "Every term this guide uses about how wine is grown, made and sold, " +
      "defined plainly, including what each one does not mean.",
    url: absolute("/glossary/"),
    inLanguage: "en-AU",
    hasDefinedTerm: entries.map((entry) => ({
      "@type": "DefinedTerm",
      "@id": `${absolute(glossaryHref(entry.slug))}#term`,
      name: entry.term,
      description: entry.short,
      url: absolute(glossaryHref(entry.slug)),
    })),
  };
}

/**
 * One term, on its own page.
 *
 * `description` is the full definition plus what the term excludes, because the
 * exclusion is half of what the definition means here (DESIGN.md §7: "say what
 * the term excludes"). A definition quoted without its exclusion is the reading
 * the glossary exists to prevent.
 */
export function definedTerm(entry: GlossaryEntry): JsonLdNode {
  const description = entry.excludes
    ? `${entry.definition} ${entry.excludes}`
    : entry.definition;

  return omitEmpty({
    "@type": "DefinedTerm",
    "@id": `${absolute(glossaryHref(entry.slug))}#term`,
    name: entry.term,
    description,
    termCode: entry.value,
    url: absolute(glossaryHref(entry.slug)),
    inDefinedTermSet: { "@id": TERM_SET_ID },
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   Blog — BlogPosting. Gate 11, TRD.md §2.5 exception 2026-08-13
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * One post.
 *
 * **This type is the first widening of the allowed set since Gate 10 closed
 * it**, and it exists because §2.5 carries a dated exception with sign-off, not
 * because a rich-results guide recommends it. Rule 4 in this file's header still
 * stands for producers: widen the type in TRD.md first, here second.
 *
 * `Blog` on the index is deliberately NOT taken. The index is a listing and it
 * carries `ItemList`, like every other listing on this site.
 *
 * `author` is the Organization, not a person. This guide carries no bylines,
 * and inventing one to fill a recommended field is the same defect as claiming
 * a logo URL that 404s.
 *
 * `citation` is the machine-readable half of SCHEMA.md §9.2's required
 * `sources`. Check 18 asserts its length against the source count the page
 * prints, so a post cannot cite one thing to a reader and three to a crawler.
 *
 * `dateModified` is emitted only where `updated` is set. Defaulting it to
 * `datePublished` would assert that an unamended post was checked on the day it
 * shipped and never since, which is a claim about editorial process that
 * nothing here has made.
 */
export function blogPosting(post: Post): JsonLdNode {
  const url = absolute(postHref(post.id));
  const day = (date: Date) => date.toISOString().slice(0, 10);

  return omitEmpty({
    "@type": "BlogPosting",
    "@id": `${url}#post`,
    headline: post.data.title,
    description: post.data.summary,
    url,
    datePublished: day(post.data.published),
    dateModified: post.data.updated ? day(post.data.updated) : undefined,
    inLanguage: "en-AU",
    author: { "@id": ORG_ID },
    publisher: { "@id": ORG_ID },
    isPartOf: { "@id": WEBSITE_ID },
    image: post.data.cover ? absolute(post.data.cover) : undefined,
    citation: post.data.sources.map((source) => ({
      "@type": "CreativeWork",
      name: source.title,
      url: source.url,
    })),
  });
}

/** The post slice of the journal index, in render order. */
export function postItems(posts: Post[]): { name: string; href: string }[] {
  return posts.map((post) => ({
    name: post.data.title,
    href: postHref(post.id),
  }));
}

/* ═══════════════════════════════════════════════════════════════════════════
   Emission
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * One `<script>` per page holding one `@graph`, rather than a scatter of
 * separate scripts. The graph is what lets `@id` references work: a producer
 * node can point at the publisher instead of carrying a copy of it.
 *
 * Serialised with `JSON.stringify`, and `</` is escaped because a `</script>`
 * inside a JSON string would close the element early. That is the one way an
 * inline JSON-LD block can break the page around it.
 */
export function graph(nodes: JsonLdNode[]): string {
  const payload = {
    "@context": "https://schema.org",
    "@graph": nodes,
  };
  return JSON.stringify(payload).replace(/</g, "\\u003c");
}
