/**
 * posts.ts — the blog collection's read side. SCHEMA.md §9, Gate 11.
 *
 * The counterpart to `taxonomy.ts`, and deliberately a separate file. That
 * module is "the one place the taxonomy meets the published set" and every
 * function in it is about producers; posts have no taxonomy, no present-only
 * membership and no foreword. Folding them in would make a module that answers
 * two unrelated questions, and the first cost would be a blog change touching
 * the file six producer route families read.
 *
 * ── Sort order, and why the tiebreak is here ──────────────────────────────────
 *
 * `published` descending, then `title` ascending. Same reasoning as
 * `byDraftedDesc` in `taxonomy.ts`: two posts published on one day would
 * otherwise order on nothing but sort stability, and `/blog/`, `/rss.xml` and
 * the sitemap would disagree with each other between builds for no reason a
 * reader could see.
 */

import { getCollection, type CollectionEntry } from "astro:content";

import { PRODUCERS_PER_PAGE } from "../config.ts";
import type { Crumb } from "./taxonomy.ts";

export type Post = CollectionEntry<"blog">;

export const postHref = (slug: string) => `/blog/${slug}/`;

/** Newest first, then title. See the module note on the tiebreak. */
export function byPublishedDesc(a: Post, b: Post): number {
  const delta = b.data.published.getTime() - a.data.published.getTime();
  return delta !== 0
    ? delta
    : a.data.title.localeCompare(b.data.title, "en-AU");
}

let cached: Post[] | null = null;

/** Every published post, newest first. Read once per build. */
export async function allPosts(): Promise<Post[]> {
  if (cached === null) {
    cached = (await getCollection("blog")).sort(byPublishedDesc);
  }
  return cached;
}

/**
 * `/blog/` paginates at the same page size as every other listing.
 *
 * UX.md §2.2 says "page size is `PRODUCERS_PER_PAGE` on every listing" and means
 * it sitewide. The constant's name is about producers and the rule is not; a
 * second constant holding the same number would be two numbers to keep equal
 * for no gain. At the current post count no pager ever renders, which is
 * UX.md §2.2's own instruction for a listing under one page.
 */
export const POSTS_PER_PAGE = PRODUCERS_PER_PAGE;

/**
 * The trail for a post. Two deep plus the post, with `/blog/` as the hub.
 *
 * The hub is labelled **Journal**, which is what DESIGN.md §193 and §219 call it
 * in the corner menu and the footer. The route is `/blog/` because TRD.md §4.2's
 * route table says so, and the two do not have to agree: the reader sees the
 * word, the URL is an identifier.
 */
export function postCrumbs(title: string): Crumb[] {
  return [
    { label: "Home", href: "/" },
    { label: "Journal", href: "/blog/" },
    { label: title, href: null },
  ];
}

/**
 * `2026-08-14` -> `14 August 2026`.
 *
 * Written out in words in en-AU order, because a numeric date is ambiguous
 * across the two conventions and the whole site sets dates in words already
 * (DESIGN.md §457's dateline row, the provenance block, the methodology page).
 */
export function longDate(date: Date): string {
  return date.toLocaleDateString("en-AU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** `2026-08-14`, for a `datetime` attribute and for JSON-LD. */
export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}
