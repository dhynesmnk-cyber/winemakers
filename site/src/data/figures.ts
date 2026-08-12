/**
 * figures.ts — the closed query set behind `<Figure>`. SCHEMA.md §9.5, Gate 11.
 *
 * ── Why this exists ───────────────────────────────────────────────────────────
 *
 * UX.md §6: "A number in a post that ought to come from the data is a data
 * component, never typed prose." A typed figure is wrong the day after it is
 * typed and nothing tells anyone. A post claiming ninety-seven producers keeps
 * claiming it through every harvest that follows, and the only reader who can
 * tell is one who counts.
 *
 * ── Why the set is CLOSED ─────────────────────────────────────────────────────
 *
 * A component that evaluates an arbitrary expression is a component that can
 * assert an arbitrary figure, which is the problem restated one level down. Nine
 * named counts cover what a post about this guide has any business stating; a
 * tenth is a prompt to come back and add it deliberately, in this file, where
 * somebody has to say what it counts.
 *
 * ── It does not count anything itself ─────────────────────────────────────────
 *
 * Every query below delegates to `taxonomy.ts`, which is the module the PAGES
 * read. That is the whole design: a figure in a post and the count beside a
 * region's name on the homepage are the same number because they came from the
 * same function, not because two implementations agree today.
 *
 * ── Zero is an answer; an unknown member is not ───────────────────────────────
 *
 * A register member with no published producers answers `0`. That is a true
 * answer to a correctly asked question, and present-only generation is a rule
 * about listings rather than about arithmetic. A member the vocabulary has never
 * heard of is a typo and fails the build naming the file (SCHEMA.md §9.5).
 */

import {
  OWNERSHIP_STATES,
  PRACTICE_KEYS,
  STATES,
  VARIETY_KEYS,
  type OwnershipState,
  type PracticeKey,
  type State,
} from "../config.ts";
import { GLOSSARY } from "./glossary.ts";
import { REGION_SLUGS, SUBREGION_SLUGS } from "./regions.ts";
import { allProducers, list, regionsPresent } from "./taxonomy.ts";

/** The nine queries, in the order SCHEMA.md §9.5 tables them. */
export const FIGURE_QUERIES = [
  "published",
  "region",
  "subregion",
  "state",
  "variety",
  "practice",
  "ownership",
  "regions",
  "glossary",
] as const;

export type FigureQuery = (typeof FIGURE_QUERIES)[number];

/**
 * The vocabulary each keyed query draws its `member` from, and `null` for the
 * three that take none.
 *
 * The attribute is `member` rather than `key` because MDX compiles to JSX and the
 * automatic runtime lifts `key` out of props before the component is called — a
 * `<Figure of="region" key="adelaide-hills" />` would arrive with nothing and
 * fail as though the author had omitted it (SCHEMA.md §9.5).
 *
 * Read from the same tuples and registers everything else reads. A literal list
 * of region slugs here would be a second register, and the first symptom of its
 * drift would be a post that cannot name a region the site has pages for.
 */
const VOCABULARY: Record<FigureQuery, readonly string[] | null> = {
  published: null,
  region: REGION_SLUGS,
  subregion: SUBREGION_SLUGS,
  state: STATES,
  variety: VARIETY_KEYS,
  practice: PRACTICE_KEYS,
  ownership: OWNERSHIP_STATES,
  regions: null,
  glossary: null,
};

/** What each query counts, in one line, for the build error to quote back. */
const DESCRIPTION: Record<FigureQuery, string> = {
  published: "every published producer",
  region: "producers whose regions include this one",
  subregion: "producers whose subregions include this one",
  state: "producers located in this state",
  variety: "producers listing this variety",
  practice: "producers whose flag for this practice is true",
  ownership: "producers in this ownership state",
  regions: "regions with at least one published producer",
  glossary: "glossary terms",
};

function isQuery(value: string): value is FigureQuery {
  return (FIGURE_QUERIES as readonly string[]).includes(value);
}

/**
 * Resolve one `<Figure>`. Throws with an actionable message rather than
 * rendering something wrong.
 *
 * `where` is the file the tag sits in, so an error names the post rather than
 * this module — the same courtesy a zod field error extends.
 */
export async function figure(
  of: string,
  member: string | undefined,
  where: string,
): Promise<number> {
  if (!isQuery(of)) {
    throw new Error(
      `${where}: <Figure of="${of}"> is not a known query. ` +
        `SCHEMA.md §9.5 closes the set at: ${FIGURE_QUERIES.join(", ")}. ` +
        `Adding one is an edit to site/src/data/figures.ts, deliberately.`,
    );
  }

  const vocabulary = VOCABULARY[of];

  if (vocabulary === null && member !== undefined) {
    throw new Error(
      `${where}: <Figure of="${of}"> takes no member, and member="${member}" was given. ` +
        `It counts ${DESCRIPTION[of]}.`,
    );
  }

  if (vocabulary !== null) {
    if (member === undefined) {
      throw new Error(
        `${where}: <Figure of="${of}"> requires a member. It counts ${DESCRIPTION[of]}.`,
      );
    }
    if (!vocabulary.includes(member)) {
      // Not a listing question. A register member with zero producers is a
      // legitimate member answering 0; this fires only on a value the vocabulary
      // has never carried, which is a typo.
      throw new Error(
        `${where}: <Figure of="${of}" member="${member}"> — "${member}" is not a member ` +
          `of that vocabulary. ` +
          (vocabulary.length <= 12
            ? `Members: ${vocabulary.join(", ")}.`
            : `There are ${vocabulary.length} members; check the register for the slug.`),
      );
    }
  }

  const producers = await allProducers();

  switch (of) {
    case "published":
      return producers.length;
    case "region":
      return producers.filter((p) => p.data.regions.includes(member!)).length;
    case "subregion":
      return producers.filter((p) => list(p.data.subregions).includes(member!)).length;
    case "state":
      return producers.filter((p) => p.data.location.state === (member as State)).length;
    case "variety":
      return producers.filter((p) => list(p.data.varieties).includes(member!)).length;
    case "practice":
      return producers.filter((p) => p.data.practices[member as PracticeKey] === true)
        .length;
    case "ownership":
      return producers.filter(
        (p) => p.data.ownership_status === (member as OwnershipState),
      ).length;
    case "regions":
      return (await regionsPresent()).length;
    case "glossary":
      return GLOSSARY.length;
  }
}

/**
 * `1410` -> `1,410`, in en-AU.
 *
 * Separated at four digits and up, which is where a reader starts miscounting.
 * `Intl` is in the platform; no dependency (TRD.md §2.2).
 */
export function formatFigure(value: number): string {
  return value.toLocaleString("en-AU");
}
