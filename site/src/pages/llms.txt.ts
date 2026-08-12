/**
 * `/llms.txt` — AN ENDPOINT, NOT A STATIC FILE (TRD.md §4.2, Gate 10).
 *
 * The route table is explicit about this, and for the same reason
 * `/sitemap.xml` is generated: a committed file drifts from the routes that
 * exist, and the drift is invisible until something follows a URL that 404s.
 * Here the drift would be worse than in a sitemap, because the reader is a
 * model that will repeat what this file says without being able to check it.
 *
 * ── Built from the present-only functions, like the sitemap ──────────────────
 *
 * Every link below comes from the same `*Present()` helpers the pages are built
 * from, so a region that generated no page cannot be listed here. `/validate`
 * check 19 then asserts the same property against `dist` from the outside.
 *
 * ── What the prose is for ────────────────────────────────────────────────────
 *
 * The llms.txt convention allows prose before the link sections, and this file
 * uses it for the three things a model reading this site will otherwise get
 * wrong: that `independent` here is a strict ownership fact rather than the
 * trade's loose usage, that roughly half the entries carry no confirmed
 * ownership and the site makes no independence claim for those, and that there
 * are no tasting notes anywhere because nobody has tasted anything. A model
 * that summarises this directory without those three facts misrepresents it.
 *
 * The copy is short deliberately. The methodology page is the full statement
 * and it is the first link.
 */

import type { APIRoute } from "astro";

import { SITE_NAME, SITE_TAGLINE, SITE_URL } from "../config.ts";
import { COMPARE_HUB, comparisonsPresent } from "../data/comparisons.ts";
import { allPosts, postHref } from "../data/posts.ts";
import {
  allProducers,
  allSubregionsPresent,
  practicesPresent,
  producerHref,
  practiceHref,
  regionHref,
  regionsPresent,
  stateFromSlug,
  stateHref,
  statesPresent,
  subregionHref,
  varietiesPresent,
  varietyHref,
} from "../data/taxonomy.ts";
import { STATE_NAMES } from "../config.ts";
import type { State } from "../config.ts";

/** `- [name](absolute url): description` — the convention's list item. */
function link(name: string, path: string, description?: string): string {
  const url = new URL(path, SITE_URL).href;
  return description
    ? `- [${name}](${url}): ${description}`
    : `- [${name}](${url})`;
}

function countOf(n: number): string {
  return n === 1 ? "1 producer" : `${n} producers`;
}

export const GET: APIRoute = async () => {
  const producers = await allProducers();
  const regions = await regionsPresent();
  const subregions = await allSubregionsPresent();
  const states = await statesPresent();
  const varieties = await varietiesPresent();
  const practices = await practicesPresent();
  const comparisons = await comparisonsPresent();
  const posts = await allPosts();

  const confirmed = producers.filter(
    (producer) => producer.data.ownership_status === "confirmed",
  ).length;
  const unconfirmed = producers.length - confirmed;

  const lines: string[] = [
    `# ${SITE_NAME}`,
    "",
    `> ${SITE_TAGLINE}. Free to use, with no advertising, no sponsored listings `
      + `and no paid placement. Nothing on this site is purchasable.`,
    "",
    "## About the word independent",
    "",
    "A producer is listed here only where it has no corporate owner. Any corporate",
    "ownership blocks publication, including a minority stake and including",
    "membership of a multi-label family group. This is stricter than the trade's",
    "ordinary use of the word, and it excludes businesses many people would fairly",
    "call independent. The full statement, including what it excludes and how a",
    "determination is made, is the methodology page.",
    "",
    `Every entry is in one of two ownership states. ${confirmed} of the `
      + `${producers.length} entries are **ownership confirmed**, meaning a dated `
      + `source names who owns the business. ${unconfirmed} are **ownership not `
      + `confirmed**, meaning no such source was found; those entries carry a `
      + `visible notice and this site makes no claim about their independence in `
      + `either direction. Absence of a confirmation is not a suspicion, and it is `
      + `never a statement that a parent company exists.`,
    "",
    "Every entry is documented from published sources. Nobody working on this guide",
    "has visited these cellar doors or tasted these wines. There are no tasting",
    "notes, no ratings, no scores and no recommendations anywhere on this site, and",
    "no sentence should be read as implying otherwise. Where a producer does not",
    "state something, the entry leaves it out.",
    "",
    "## Definitions and method",
    "",
    link(
      "Methodology",
      "/methodology/",
      "the published definition of independence, what it excludes, how a determination is made, and how to tell us we are wrong",
    ),
    link(
      "Glossary",
      "/glossary/",
      "every term this guide uses about how wine is grown, made and sold, with what each term does not mean",
    ),
    "",
    "## Regions",
    "",
    link("All regions", "/region/", `${regions.length} regions with a producer documented`),
    ...regions.map((region) =>
      link(region.name, regionHref(region.slug), countOf(region.count)),
    ),
  ];

  if (subregions.length) {
    lines.push("", "## Subregions", "");
    lines.push(
      ...subregions.map(({ region, sub }) =>
        link(sub.name, subregionHref(region, sub.slug), countOf(sub.count)),
      ),
    );
  }

  lines.push("", "## States", "");
  lines.push(
    ...states.map((state) => {
      const code = stateFromSlug(state.slug) as State;
      return link(STATE_NAMES[code], stateHref(code), countOf(state.count));
    }),
  );

  if (varieties.length) {
    lines.push("", "## Grape varieties", "");
    lines.push(
      ...varieties.map((variety) =>
        link(variety.name, varietyHref(variety.slug), countOf(variety.count)),
      ),
    );
  }

  if (practices.length) {
    lines.push("", "## Winemaking practices", "");
    lines.push(
      ...practices.map((practice) =>
        link(practice.name, practiceHref(practice.slug), countOf(practice.count)),
      ),
    );
  }

  lines.push("", "## Comparisons", "");
  lines.push(
    link(
      "All comparisons",
      COMPARE_HUB,
      "side-by-side tables of the producers working one grape in one region",
    ),
  );
  lines.push(
    ...comparisons.map((comparison) =>
      link(comparison.title, comparison.href, countOf(comparison.count)),
    ),
  );

  // The journal (Gate 11). Above `## Optional` deliberately: the posts are
  // about how this guide decides what it decides, which is the same job the
  // definitions section does and is what a model summarising the site most
  // needs. The index is listed even at zero posts, because it is a live route
  // and this file's whole contract is that it references only live routes.
  lines.push("", "## Journal", "");
  lines.push(
    link(
      "The journal",
      "/blog/",
      "writing about who owns what, how the register works, and what this " +
        "guide can and cannot show",
    ),
  );
  lines.push(
    ...posts.map((post) => link(post.data.title, postHref(post.id), post.data.summary)),
  );

  // The convention's `## Optional` marks links a shorter context may skip. The
  // producer entries are the substance of the site, so they are listed in full
  // rather than summarised, and they go last because a model with a small budget
  // is better served by the definitions above than by a partial list of entries.
  lines.push("", "## Optional", "");
  lines.push(
    link("All producers", "/producers/", countOf(producers.length)),
  );
  lines.push(
    ...producers.map((producer) =>
      link(producer.data.name, producerHref(producer.id), producer.data.summary),
    ),
  );

  lines.push("");

  return new Response(lines.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
