/**
 * `/sitemap.xml` — AN ENDPOINT, NOT A STATIC FILE (TRD.md §4.2).
 *
 * The route table is explicit that this is generated rather than committed, for
 * the same reason `llms.txt` is at Gate 10: a static file drifts from the
 * routes that exist, and the drift is invisible until a crawler follows a URL
 * that 404s.
 *
 * It is built from the SAME present-only functions the pages are built from, so
 * a region that generated no page cannot appear here. That is the half of Gate
 * 6's done-condition that a link check alone would not catch: check 5 proves
 * every link resolves, and this proves the sitemap lists nothing that was never
 * built.
 *
 * Pagination: every page in every series is listed (UX.md §2.2), because a
 * crawler that only reaches page 1 of a region never reaches the producers on
 * page 3.
 */

import type { APIRoute } from "astro";

import { SITE_URL } from "../config.ts";
import { GLOSSARY } from "../data/glossary.ts";
import {
  allProducers,
  allSubregionsPresent,
  glossaryHref,
  pageHref,
  pageCount,
  practicesPresent,
  producerHref,
  regionHref,
  regionsPresent,
  stateFromSlug,
  stateHref,
  statesPresent,
  subregionHref,
  varietiesPresent,
  varietyHref,
  practiceHref,
} from "../data/taxonomy.ts";
import type { State } from "../config.ts";

/** Every page in a paginated series, page 1 first. */
function series(base: string, total: number): string[] {
  return Array.from({ length: pageCount(total) }, (_, i) =>
    pageHref(base, i + 1),
  );
}

export const GET: APIRoute = async () => {
  const paths: string[] = ["/", "/region/", "/glossary/"];

  const producers = await allProducers();
  paths.push(...series("/producers/", producers.length));
  paths.push(...producers.map((p) => producerHref(p.id)));

  for (const region of await regionsPresent()) {
    paths.push(...series(regionHref(region.slug), region.count));
  }

  for (const { region, sub } of await allSubregionsPresent()) {
    paths.push(...series(subregionHref(region, sub.slug), sub.count));
  }

  for (const state of await statesPresent()) {
    paths.push(...series(stateHref(stateFromSlug(state.slug) as State), state.count));
  }

  for (const variety of await varietiesPresent()) {
    paths.push(...series(varietyHref(variety.slug), variety.count));
  }

  for (const practice of await practicesPresent()) {
    paths.push(...series(practiceHref(practice.slug), practice.count));
  }

  // Unconditional, exactly as the pages are.
  paths.push(...GLOSSARY.map((entry) => glossaryHref(entry.slug)));

  // Sorted and de-duplicated so the output is byte-stable between builds. A
  // sitemap that reorders on every build makes every deploy diff unreadable.
  const urls = [...new Set(paths)].sort();

  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urls.map((path) => `  <url><loc>${new URL(path, SITE_URL).href}</loc></url>`),
    "</urlset>",
    "",
  ].join("\n");

  return new Response(body, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
};
