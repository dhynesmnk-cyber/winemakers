/**
 * animals.ts — the margin fauna registry. DESIGN.md §6a.
 *
 * ── THE ARTWORK DOES NOT EXIST YET, AND THIS FILE DOES NOT CREATE IT ─────────
 *
 * DESIGN.md §6a is a brief for an illustrator and says plainly: do not generate
 * the artwork from that document. Wave 2 delivers the registry, the keys and the
 * served paths. `Icons and logos/FAUNA-BRIEF.md` is the commissioning document.
 *
 * `MarginAnimal.astro` must therefore render nothing when a key's file is
 * absent, rather than emitting a broken image. `availableAnimals()` below reads
 * the manifest; until artwork lands it returns an empty list and every margin
 * slot renders nothing. That is the correct homepage: DESIGN.md §7's zero-image
 * default requires every page to look complete and intentional with no images at
 * all, and the fauna are decoration.
 *
 * ── What these are ───────────────────────────────────────────────────────────
 *
 * Sparse decorative illustration in the reading spine's wide right margin, where
 * §6's glyphs are strictly functional. Homepage only. One per section-opener
 * slot, never inline with copy, never more than one per section break.
 *
 * Sized 40 to 64px, larger than any §6 glyph, because they carry no label.
 * `aria-hidden="true"`, never linked, never captioned. Collapses out of the
 * layout below 1024px rather than being squeezed into the single-column spine.
 *
 * Recoloured at runtime by a CSS mask that reads only the PNG's alpha channel.
 * Light mode paints `--ink-faded`. Dark mode is forced to pure white, a
 * deliberate narrow exception to §2's six tokens, scoped to this one decorative
 * element, because the silhouettes read better at full contrast against
 * near-black paper than the warm ink tones do.
 *
 * NO COLOUR-CODING BY SPECIES OR MEANING. Decoration, not notation. A reader
 * must never be able to infer a fact about a producer, a region or a category
 * from which animal is in the margin. The rotation is positional, not semantic.
 */

/** The nine subjects from DESIGN.md §6a, one per section-opener slot. */
export const ANIMAL_KEYS = [
  "silvereye",
  "willie-wagtail",
  "australian-raven",
  "echidna",
  "blue-tongue-lizard",
  "kelpie",
  "guinea-fowl",
  "ewe",
  "blue-banded-bee",
] as const;

export type AnimalKey = (typeof ANIMAL_KEYS)[number];

/** Served copies. `site/public/animals/` maps to `/animals/` at the site root. */
export const ANIMAL_SRC: Record<AnimalKey, string> = {
  silvereye: "/animals/silvereye.png",
  "willie-wagtail": "/animals/willie-wagtail.png",
  "australian-raven": "/animals/australian-raven.png",
  echidna: "/animals/echidna.png",
  "blue-tongue-lizard": "/animals/blue-tongue-lizard.png",
  kelpie: "/animals/kelpie.png",
  "guinea-fowl": "/animals/guinea-fowl.png",
  ewe: "/animals/ewe.png",
  "blue-banded-bee": "/animals/blue-banded-bee.png",
};

/**
 * Species names, for the commissioning brief and for the asset pipeline. Not
 * rendered: these motifs are never captioned and never labelled.
 */
export const ANIMAL_SUBJECTS: Record<AnimalKey, string> = {
  silvereye: "Silvereye (Zosterops lateralis), the grape-eating bird every vineyard net is up against",
  "willie-wagtail": "Willie wagtail, tail fanned",
  "australian-raven": "Australian raven or grey currawong, perched, in profile",
  echidna: "Short-beaked echidna, mid-amble",
  "blue-tongue-lizard": "Eastern blue-tongue lizard, flattened, basking",
  kelpie: "Working kelpie, sitting, ears up",
  "guinea-fowl": "Guinea fowl, upright, used for vineyard pest control",
  ewe: "Merino or Wiltipoll ewe, head down grazing, under-vine grazing being a real practice",
  "blue-banded-bee": "Blue-banded bee (Amegilla), in flight, at a scale that reads",
};

/**
 * DESIGN.md §5c recommends the silvereye as the site mascot: small, instantly
 * drawable, endemic, and a thief, which suits the register. Recorded here so
 * `SiteLogo.astro` has one place to read it from rather than hardcoding a key.
 */
export const MASCOT: AnimalKey = "silvereye";

/** DESIGN.md §6a. Larger than any §6 glyph because these carry no label. */
export const ANIMAL_SIZE_MIN = 40 as const;
export const ANIMAL_SIZE_MAX = 64 as const;

/**
 * Artwork actually present in `site/public/animals/`, as a build-time manifest.
 *
 * Gate 1 populates this by globbing the directory. Until then it is empty, and
 * `MarginAnimal.astro` renders nothing for every key, which is the intended
 * behaviour for a homepage whose decoration has not been commissioned yet.
 *
 * Keep this a manifest rather than a runtime existence check. Astro builds
 * static output; a file that is missing at build time must produce no markup,
 * not a 404 at read time.
 */
export const ANIMALS_AVAILABLE: readonly AnimalKey[] = [];

export function availableAnimals(): readonly AnimalKey[] {
  return ANIMALS_AVAILABLE;
}

export function hasAnimal(key: AnimalKey): boolean {
  return ANIMALS_AVAILABLE.includes(key);
}

/**
 * The animal for a section-opener slot, cycling through whatever artwork exists.
 * Returns `undefined` when there is none, and the caller renders nothing.
 *
 * Positional, never semantic. Do not pass a region, a category or any other
 * fact into this function; §6a forbids a reader being able to infer meaning
 * from which animal appears.
 */
export function animalForSlot(slotIndex: number): AnimalKey | undefined {
  const pool = availableAnimals();
  if (pool.length === 0) return undefined;
  return pool[slotIndex % pool.length];
}
