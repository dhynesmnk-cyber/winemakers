/**
 * paths.ts — the hand-authored inline SVG icon set. DESIGN.md §6.
 *
 * Wave 2 draws what §6's inventory specifies. 44 glyphs, no more.
 *
 * ── The grammar, restated because it is binding ───────────────────────────────
 * 24×24 viewBox. Stroke only. `stroke="currentColor"`, `fill="none"`,
 * `stroke-width: 1.4`, round caps and joins. No fill, ever. No colour beyond the
 * surrounding text colour, so a glyph stays tonal with the page instead of
 * becoming decoration.
 *
 * No icon package, no icon font, no runtime sprite fetch. Four repeating
 * primitives hold the set together: the bunch, the bottle, the barrel and the
 * glass. New glyphs are assembled from those and from plain geometry.
 *
 * No negation slashes. Every glyph states a positive fact a producer published.
 * No letterforms, with one inherited exception: `logistics_parking` carries a
 * stroke-drawn P, because that is what a parking symbol is.
 * No teardrop map pin. Locality is a survey triangle.
 *
 * Icons are never a badge, seal, shield, medal or ribbon, and never the only
 * carrier of meaning. SCHEMA.md §2 is explicit that there is no badge system and
 * that labels are words. This set gives a word a mark to sit beside. It never
 * replaces the word and it never encodes a rank, a score or a level of trust.
 *
 * ── Keys ──────────────────────────────────────────────────────────────────────
 * Namespaced by vocabulary: `practice_*`, `logistics_*`, `style_*`, `vessel_*`.
 * Namespacing is not cosmetic. `glass` is both a vessel and a drinking vessel,
 * and an un-namespaced set collides.
 *
 * This file does not import `site/src/config.ts`, because Gate 1 owns that file
 * and it does not exist yet. The namespacing helpers below take a raw enum value
 * and return the icon key, and `assertIconCoverage` is the build-time check that
 * a vocabulary value with no glyph FAILS THE BUILD rather than rendering blank.
 * Gate 1 wires it against the `as const` tuples. See CONSTANTS-REQUIRED.md.
 */

/* ─────────────────────────────────────────────────────────────────────────────
   Rendering constants. `Icon.astro` reads these; nothing else sets them.
   ───────────────────────────────────────────────────────────────────────── */

export const ICON_VIEWBOX = "0 0 24 24" as const;
export const ICON_STROKE_WIDTH = 1.4 as const;
export const ICON_LINECAP = "round" as const;
export const ICON_LINEJOIN = "round" as const;

/** DESIGN.md §6's size table. Nothing renders above 40px without a documented exception. */
export const ICON_SIZES = {
  /** Producer-page fact row, full context: glyph plus label text. */
  fact_row: 18,
  /** `ProducerEntry` list row, compact: glyph plus `title` and an `.sr-only` label. */
  list_entry: 16,
  /** Secondary chips: logistics, vessels. */
  chip: 14,
  /** Region, variety and practice page headers. */
  taxonomy_header: 16,
  /** Corner-menu "browse by" rows. */
  corner_menu: 20,
  footer: 20,
  glossary_index: 20,
  glossary_detail: 32,
  /** Homepage secondary "browse by practice / by style" block. */
  homepage_browse: 40,
} as const;

export type IconContext = keyof typeof ICON_SIZES;

/** The ceiling from §6. Anything above needs a dated DESIGN.md exception. */
export const ICON_MAX_SIZE = 40 as const;

/* ─────────────────────────────────────────────────────────────────────────────
   The inventory. Each value is a list of `d` strings, rendered one `<path>` each.
   ───────────────────────────────────────────────────────────────────────── */

export const ICON_PATHS = {
  /* ── Practices (4) — SCHEMA.md §1.6 ─────────────────────────────────── */

  /** An open-topped fermenter, contents doming above the rim, two short arcs rising off it. */
  practice_wild_ferment: [
    "M4.4 12 5.9 20h12.2L19.6 12",
    "M3 12h18",
    "M6.6 12c1.5-3.5 9.3-3.5 10.8 0",
    "M9 7.6c.8-1.1.2-1.9 1-2.9",
    "M14 7.9c.8-1.1.2-1.9 1-2.9",
  ],

  /** A tapered glass holding three particles in suspension. */
  practice_unfined: [
    "M7 5h10l-5 8z",
    "M12 13v6",
    "M9 19.4h6",
    "M10.05 8.8a.55.55 0 1 0 1.1 0 .55.55 0 1 0-1.1 0",
    "M12.65 9.2a.55.55 0 1 0 1.1 0 .55.55 0 1 0-1.1 0",
    "M11.35 10.9a.55.55 0 1 0 1.1 0 .55.55 0 1 0-1.1 0",
  ],

  /** A filter disc set aside from a pour line that bypasses it. The screen present, unused. */
  practice_unfiltered: [
    "M3 4.4h4.6c.6 0 .9.5.9 1.1",
    "M8.5 5.5c.5 4.6-.6 9.6.1 14.6",
    "M12.4 12a3.6 3.6 0 1 0 7.2 0 3.6 3.6 0 1 0-7.2 0",
    "M13.1 10.2h5.8",
    "M12.5 12h7",
    "M13.1 13.8h5.8",
  ],

  /** A single droplet suspended above a wide vessel mouth. One drop where a pour would be. */
  practice_minimal_so2: [
    "M12 4s2.5 3 2.5 4.8a2.5 2.5 0 0 1-5 0C9.5 7 12 4 12 4Z",
    "M4 13h16",
    "M5 13c.6 4.5 2.5 7 7 7s6.4-2.5 7-7",
  ],

  /* ── Wine styles (7) — SCHEMA.md §1.9. Built on the glass primitive. ──
     style_red, style_white and style_rose are the known compact-size
     ambiguity. Compact contexts render their labels, not these glyphs.
     ─────────────────────────────────────────────────────────────────── */

  /** Broad round bowl, short stem, foot. */
  style_red: [
    "M6.5 4h11c0 5.6-2.4 8.8-5.5 8.8S6.5 9.6 6.5 4Z",
    "M12 12.8v5.8",
    "M8.6 20h6.8",
  ],

  /** Narrower U-bowl, longer stem, foot. */
  style_white: [
    "M8 4h8c0 4.6-1.8 7-4 7s-4-2.4-4-7Z",
    "M12 11v8",
    "M9 20.2h6",
  ],

  /** The white bowl with a low level stroke and a single short arc at the rim. */
  style_rose: [
    "M8 4h8c0 4.6-1.8 7-4 7s-4-2.4-4-7Z",
    "M8.9 7.6h6.2",
    "M12 11v8",
    "M9 20.2h6",
    "M14.6 2.6c1-.9 2.2-.5 2.8.4",
  ],

  /** Tall narrow flute with three rising dots. */
  style_sparkling: [
    "M9.5 3h5l-.9 10h-3.2z",
    "M12 13v6",
    "M9.5 20.2h5",
    "M11.5 10.4a.5.5 0 1 0 1 0 .5.5 0 1 0-1 0",
    "M10.8 7.8a.5.5 0 1 0 1 0 .5.5 0 1 0-1 0",
    "M12.1 5.6a.5.5 0 1 0 1 0 .5.5 0 1 0-1 0",
  ],

  /** A shallow open vessel holding a half-berry, its skin drawn as a separate outer arc. */
  style_skin_contact: [
    "M4 11h16c-.8 5.6-3.8 8.5-8 8.5S4.8 16.6 4 11Z",
    "M8.6 11a3.4 3.4 0 0 1 6.8 0",
    "M7.2 11a4.8 4.8 0 0 1 9.6 0",
  ],

  /** A squat straight-sided stemmed glass with a low measure stroke. */
  style_fortified: [
    "M8 4v5.6c0 2 1.8 3 4 3s4-1 4-3V4",
    "M7.4 4h9.2",
    "M8.4 9.4h7.2",
    "M12 12.6v6",
    "M9 20.2h6",
  ],

  /** A single raisined berry, its contour puckered, on a short stem. */
  style_dessert: [
    "M12 3.4v2.8",
    "M12 6.2c2 0 3.2 1 3.4 2.2.2 1.2 1.2 1.6 1.4 2.8.2 1.2-.6 1.8-.4 3 .2 1.2-.6 2.4-1.6 3.2-1 .8-1.8 1.4-2.8 1.4s-1.8-.6-2.8-1.4c-1-.8-1.8-2-1.6-3.2.2-1.2-.6-1.8-.4-3 .2-1.2 1.2-1.6 1.4-2.8C8.8 7.2 10 6.2 12 6.2Z",
    "M10 11.6c1.3.7.9 2 2 2.7",
  ],

  /* ── Vessels (7) — SCHEMA.md §1.8. Built on the barrel primitive. ───── */

  /** Upright cylindrical tank, dished top, two short legs, a valve at the base. */
  vessel_stainless: [
    "M6.5 6.5V17h11V6.5",
    "M6.5 6.5c0-2.3 2.5-3.3 5.5-3.3s5.5 1 5.5 3.3",
    "M8.6 17v3.2",
    "M15.4 17v3.2",
    "M17.5 14h2.1",
    "M19.6 12.9v2.2",
  ],

  /** Barrel on its side, three hoop lines, bung at top centre. */
  vessel_oak_barrique: [
    "M6 5.6c3-1 9-1 12 0",
    "M6 18.4c3 1 9 1 12 0",
    "M6 5.6c-1.6 3.2-1.6 9.6 0 12.8",
    "M18 5.6c1.6 3.2 1.6 9.6 0 12.8",
    "M8.4 5.1c-.8 3.9-.8 9.9 0 13.8",
    "M12 4.9c-.5 4-.5 10.2 0 14.2",
    "M15.6 5.1c.8 3.9.8 9.9 0 13.8",
    "M11.1 5.3a.9.9 0 1 0 1.8 0 .9.9 0 1 0-1.8 0",
  ],

  /** A large upright staved cask, wider relative to its height than the barrique, with a front hatch. */
  vessel_oak_foudre: [
    "M6 5.6c1.6-1.2 10.4-1.2 12 0",
    "M6 5.6c-2 4.4-2 9.6 0 14",
    "M18 5.6c2 4.4 2 9.6 0 14",
    "M6 19.6c1.6 1.2 10.4 1.2 12 0",
    "M4.4 9.8h15.2",
    "M4.4 15.4h15.2",
    "M10 11.6h4v2.6h-4z",
  ],

  /** An egg: an ovoid on a low cradle, hatch line near the top. */
  vessel_concrete: [
    "M12 2.8c3.2 2.6 4.8 6.4 4.8 9.2 0 3.2-2.2 5.4-4.8 5.4s-4.8-2.2-4.8-5.4c0-2.8 1.6-6.6 4.8-9.2Z",
    "M6.4 14.8c.4 3.4 2.6 5 5.6 5s5.2-1.6 5.6-5",
    "M8 20h8",
    "M10.6 6.6a1.4 1.4 0 1 0 2.8 0 1.4 1.4 0 1 0-2.8 0",
  ],

  /** A two-handled tapering vessel with a pointed base. */
  vessel_amphora: [
    "M8.8 4h6.4",
    "M9.4 4c-2.4 2.6-3.4 5.6-2.4 8.4 1.1 3 3.4 5.4 5 8.4 1.6-3 3.9-5.4 5-8.4 1-2.8 0-5.8-2.4-8.4",
    "M9.4 5.2C7 5.6 6.2 7.6 7 9.4",
    "M14.6 5.2c2.4.4 3.2 2.4 2.4 4.2",
  ],

  /** A rounded jar with a rolled lip, no handles, one incised band. */
  vessel_ceramic: [
    "M8.4 4.2h7.2a1.1 1.1 0 0 1 0 2.2H8.4a1.1 1.1 0 0 1 0-2.2Z",
    "M9.4 6.4c-3.2 1.6-4.6 4.6-4 7.6.6 3.4 3.2 5.8 6.6 5.8s6-2.4 6.6-5.8c.6-3-.8-6-4-7.6",
    "M5.9 12.4c3.7 1.2 8.5 1.2 12.2 0",
  ],

  /** A demijohn: rounded body, narrow neck, stopper stroke. */
  vessel_glass: [
    "M10.6 2.6h2.8",
    "M10.6 3.4v3.2",
    "M13.4 3.4v3.2",
    "M10.6 6.6c-3.6 1.4-5.8 4.4-5.4 7.8.5 3.6 3.3 6 6.8 6s6.3-2.4 6.8-6c.4-3.4-1.8-6.4-5.4-7.8",
  ],

  /* ── Logistics (10) — SCHEMA.md §1.7 ────────────────────────────────── */

  /** An open door with a short swing arc. */
  logistics_walk_ins_welcome: [
    "M5.2 20.6V4.2h8.4v16.4",
    "M3.4 20.6h17.2",
    "M13.6 5.8 19.2 3.8v13.6l-5.6 2z",
    "M14.7 11.6a.45.45 0 1 0 .9 0 .45.45 0 1 0-.9 0",
    "M13.6 20.6a5.6 5.6 0 0 0 5.4-4",
  ],

  /** A diary page with a ticked date. */
  logistics_bookings_required: [
    "M4.6 5.4h14.8V20H4.6z",
    "M4.6 9.2h14.8",
    "M8.6 3v3.6",
    "M15.4 3v3.6",
    "M8.6 14.6 11.2 17l4.6-5.2",
  ],

  /** A plate circle with a fork left and a knife right. */
  logistics_restaurant: [
    "M7.8 12a4.2 4.2 0 1 0 8.4 0 4.2 4.2 0 1 0-8.4 0",
    "M2.6 3.6v3.8c0 1.8 1.4 3 1.4 3s1.4-1.2 1.4-3V3.6",
    "M4 3.6v6.8",
    "M4 10.4v10.2",
    "M20.2 3.6c1.2 2 1.2 6 0 7.8v9.2",
  ],

  /** A basket with a handle and one cloth fold over the rim. */
  logistics_picnic_provisions: [
    "M4.4 10.4h15.2L17.8 20H6.2z",
    "M3.8 10.4h16.4",
    "M7.6 10.4a4.4 4.4 0 0 1 8.8 0",
    "M5.4 15h13.2",
    "M13.6 10.4c1 2 2.8 2.8 4 2.2",
  ],

  /** A working dog's head in profile: muzzle and pricked ear. Not a paw print. */
  logistics_dog_friendly: [
    "M7 17.6c-1.8-3.4-1.4-7.6 1.1-9.6l.6-4.3 3.1 3c2.8.2 5 1.6 6 3.7l2.8 1.5-2.6 1.4c-.3 1.2-1.4 2.1-2.8 2.3h-1.8",
    "M7 17.6c1.6 1.8 4.4 2.4 6.4 1.8",
    "M12.1 10.2a.5.5 0 1 0 1 0 .5.5 0 1 0-1 0",
  ],

  /** Two figures, one tall, one short. */
  logistics_family_friendly: [
    "M6.6 5.6a1.8 1.8 0 1 0 3.6 0 1.8 1.8 0 1 0-3.6 0",
    "M8.4 7.6v7.8",
    "M8.4 15.4 6.4 20.6",
    "M8.4 15.4l2 5.2",
    "M5.6 11.2h5.6",
    "M14.4 10a1.4 1.4 0 1 0 2.8 0 1.4 1.4 0 1 0-2.8 0",
    "M15.8 11.6v5.6",
    "M15.8 17.2 14.2 20.6",
    "M15.8 17.2l1.6 3.4",
    "M13.6 14h4.4",
  ],

  /** The standard wheelchair figure: circle head, seated body stroke, wheel arc. */
  logistics_wheelchair_access: [
    "M8.9 4.4a1.5 1.5 0 1 0 3 0 1.5 1.5 0 1 0-3 0",
    "M10.4 6.6c-1.2 1.8-1.2 4.2-.2 5.8h4.6l2.4 4",
    "M15.6 16.8h3",
    "M6.4 14.6a5.2 5.2 0 1 0 10.4 0 5.2 5.2 0 1 0-10.4 0",
  ],

  /** Three overlapping circle heads in a row. */
  logistics_group_bookings: [
    "M4 12a3.4 3.4 0 1 0 6.8 0 3.4 3.4 0 1 0-6.8 0",
    "M8.6 12a3.4 3.4 0 1 0 6.8 0 3.4 3.4 0 1 0-6.8 0",
    "M13.2 12a3.4 3.4 0 1 0 6.8 0 3.4 3.4 0 1 0-6.8 0",
  ],

  /** Two vine rows converging toward a horizon, with a short path between them. */
  logistics_vineyard_tours: [
    "M3 9.4h18",
    "M2.8 20.6 9.4 9.6",
    "M8.4 20.6 11.2 9.6",
    "M15.6 20.6 12.8 9.6",
    "M21.2 20.6 14.6 9.6",
  ],

  /** A rect with a stroke-drawn P. The one letterform in the set. */
  logistics_parking: [
    "M4 4h16v16H4z",
    "M10 8v8",
    "M10 8h3.4a2.4 2.4 0 0 1 0 4.8H10",
  ],

  /* ── Cellar door (2) — SCHEMA.md §1.2. `none` renders nothing. ──────── */

  /** A door standing open beneath a lintel line. */
  cellar_door_open: [
    "M3.4 4.4h17.2",
    "M6.4 20.6V5.4h7.2v15.2",
    "M13.6 6.6 18.6 4.8v14.2l-5-1.8",
    "M11.95 13.4a.45.45 0 1 0 .9 0 .45.45 0 1 0-.9 0",
  ],

  /** The same door, closed, with a small hand-bell beside it. */
  cellar_door_by_appointment: [
    "M3.4 4.4h11",
    "M5.4 20.6V5.4H13v15.2z",
    "M10.95 13.4a.45.45 0 1 0 .9 0 .45.45 0 1 0-.9 0",
    "M16.4 15.4c0-3.2 1-4.8 2.2-4.8s2.2 1.6 2.2 4.8z",
    "M15.9 15.4h5.4",
    "M18.05 16.8a.55.55 0 1 0 1.1 0 .55.55 0 1 0-1.1 0",
    "M18.6 10.6V8.8",
  ],

  /* ── Certification (2) — SCHEMA.md §1.3. Shown when the state is not
     `none`. `practising` vs `certified` is carried in the label text and
     never by a glyph variant: a shape that changes with certification is a
     trust badge. ────────────────────────────────────────────────────── */

  /** A single leaf on a short stem with one midrib. */
  organic: [
    "M6 19c2.4-2.4 3.6-3.6 5-5",
    "M11 14c0-5.4 3.4-9 8.4-9.4-.4 5-4 9.2-8.4 9.4Z",
    "M11.6 13.4c2.2-2.6 4.6-5.2 7.2-7.8",
  ],

  /** A crescent with a small sprout at its inner edge. */
  biodynamic: [
    "M14.6 3.4a9 9 0 1 0 0 17.2 7.2 7.2 0 1 1 0-17.2Z",
    "M15.6 15.6v-4.2",
    "M15.6 12.8c-1.4 0-2.2-1-2.2-2 1.4 0 2.2.8 2.2 2",
    "M15.6 12c1.4 0 2.2-1 2.2-2-1.4 0-2.2.8-2.2 2",
  ],

  /* ── Vocabulary row markers (4) ─────────────────────────────────────── */

  /** The bunch: a triangular cluster of berries with stem and one leaf. Marks varieties. */
  variety: [
    "M12 5.4V3",
    "M12.2 4.4c1.2-1.6 3.6-1.8 4.8-.8-.6 1.8-3 2.4-4.8 1.2Z",
    "M8.2 8.4a1.9 1.9 0 1 0 3.8 0 1.9 1.9 0 1 0-3.8 0",
    "M12 8.4a1.9 1.9 0 1 0 3.8 0 1.9 1.9 0 1 0-3.8 0",
    "M6.3 12a1.9 1.9 0 1 0 3.8 0 1.9 1.9 0 1 0-3.8 0",
    "M10.1 12a1.9 1.9 0 1 0 3.8 0 1.9 1.9 0 1 0-3.8 0",
    "M13.9 12a1.9 1.9 0 1 0 3.8 0 1.9 1.9 0 1 0-3.8 0",
    "M10.1 15.6a1.9 1.9 0 1 0 3.8 0 1.9 1.9 0 1 0-3.8 0",
  ],

  /** A vine row: posts on a wire. */
  fruit_source: [
    "M2.6 9.4h18.8",
    "M2.6 13.4h18.8",
    "M6 5.6v13.8",
    "M12 5.6v13.8",
    "M18 5.6v13.8",
    "M2.6 19.4h18.8",
  ],

  /** Two stacked cases, front face braced. Never a chart. */
  production: [
    "M6.4 5.4h11.2v6.8H6.4z",
    "M4.2 12.6h15.6v7.4H4.2z",
    "M9.8 5.4v6.8",
    "M14.2 5.4v6.8",
    "M8.6 12.6v7.4",
    "M15.4 12.6v7.4",
  ],

  /** The bottle. Marks buy-direct links and the shop. */
  bottle: [
    "M9.4 2.8h5.2V7c0 1.6 1.8 2.8 1.8 5.4v7.2c0 .8-.7 1.4-1.5 1.4H9.1c-.8 0-1.5-.6-1.5-1.4v-7.2c0-2.6 1.8-3.8 1.8-5.4z",
    "M9.4 6.6h5.2",
  ],

  /* ── Utility and appendix (5) ───────────────────────────────────────── */

  /** Clock face with hands. */
  hours: [
    "M3.6 12a8.4 8.4 0 1 0 16.8 0 8.4 8.4 0 1 0-16.8 0",
    "M12 6.8V12h4",
  ],

  /** A price tag with its hole. */
  cost: [
    "M12.2 3h7.6a1 1 0 0 1 1 1v7.6l-9.2 9.2a1.4 1.4 0 0 1-2 0l-6.4-6.4a1.4 1.4 0 0 1 0-2Z",
    "M15.3 7.2a1.3 1.3 0 1 0 2.6 0 1.3 1.3 0 1 0-2.6 0",
  ],

  /** A survey triangle: an equilateral outline with a centre dot. Not a map pin. */
  location: [
    "M12 3.6 21 19.4H3Z",
    "M11.1 14.1a.9.9 0 1 0 1.8 0 .9.9 0 1 0-1.8 0",
  ],

  /** An arrow leaving a square. */
  website: [
    "M11.4 4.6H4.6v14.8h14.8v-6.8",
    "M13.4 10.6 20.4 3.6",
    "M15 3.6h5.4V9",
  ],

  /** A carton with a tie band. */
  ships_nationally: [
    "M3.6 7.4h16.8v12.2H3.6z",
    "M3.6 11h16.8",
    "M12 7.4v3.6",
    "M9 11v8.6",
  ],

  /* ── Footer (3) ─────────────────────────────────────────────────────── */

  /** Envelope: rect plus a flap V. */
  email: ["M3 5.6h18v12.8H3z", "M3 6.4 12 13.2l9-6.8"],

  /** A simplified two-wing mark. A simplification, not a traced brand asset. */
  bluesky: [
    "M12 10.6C10.4 7.4 7 4 4.6 4 2.8 4 2.6 6 3.2 8.6c.6 2.8 2.6 4.8 4.8 5.4-2.4.6-3.4 2.2-2.4 4.2 1.2 2.2 4.2.8 6.4-2.8",
    "M12 10.6C13.6 7.4 17 4 19.4 4c1.8 0 2 2 1.4 4.6-.6 2.8-2.6 4.8-4.8 5.4 2.4.6 3.4 2.2 2.4 4.2-1.2 2.2-4.2.8-6.4-2.8",
  ],

  /** Corner dot with two arcs. */
  rss: [
    "M3.9 18.6a1.5 1.5 0 1 0 3 0 1.5 1.5 0 1 0-3 0",
    "M4.4 12.6a7 7 0 0 1 7 7",
    "M4.4 6.6a13 13 0 0 1 13 13",
  ],
} as const satisfies Record<string, readonly string[]>;

export type IconKey = keyof typeof ICON_PATHS;

export const ICON_KEYS = Object.keys(ICON_PATHS) as readonly IconKey[];

/* ─────────────────────────────────────────────────────────────────────────────
   Namespacing helpers. §6: keys are derived mechanically from the SCHEMA.md §1
   tuples, never hand-listed a second time.
   ───────────────────────────────────────────────────────────────────────── */

export const practiceIcon = (key: string): string => `practice_${key}`;
export const logisticsIcon = (key: string): string => `logistics_${key}`;
export const styleIcon = (key: string): string => `style_${key}`;
export const vesselIcon = (key: string): string => `vessel_${key}`;
export const cellarDoorIcon = (key: string): string => `cellar_door_${key}`;

export function hasIcon(key: string): key is IconKey {
  return key in ICON_PATHS;
}

export function iconPaths(key: IconKey): readonly string[] {
  return ICON_PATHS[key];
}

/**
 * §6: "A vocabulary value with no glyph must fail the build, not render blank."
 * Gate 1 calls this once per glyph-rendering vocabulary, from `config.ts`'s
 * tuples, at module scope so the failure lands at build time and not on a page.
 *
 * `cellar_door: none` and `certification: none` render nothing by design
 * (present-only display), so their callers pass the reduced key list.
 */
export function assertIconCoverage(
  vocabulary: string,
  keys: readonly string[],
  namespacer: (key: string) => string,
): void {
  const missing = keys.map(namespacer).filter((k) => !hasIcon(k));
  if (missing.length > 0) {
    throw new Error(
      `Icon coverage: ${vocabulary} has no glyph for ${missing.join(", ")}. ` +
        `Draw it in site/src/icons/paths.ts or remove the value from the tuple. ` +
        `DESIGN.md §6 requires a missing glyph to fail the build rather than render blank.`,
    );
  }
}

/**
 * §6: where two glyphs cannot be told apart at compact size, the compact context
 * renders the label text instead of the glyph. An ambiguous glyph is worse than
 * no glyph. The still-wine glasses are the known case.
 */
export const COMPACT_AMBIGUOUS_ICONS: readonly IconKey[] = [
  "style_red",
  "style_white",
  "style_rose",
];

/** True where the context is compact and the glyph is one of the ambiguous set. */
export function rendersLabelInsteadOfGlyph(key: IconKey, context: IconContext): boolean {
  const compact: readonly IconContext[] = ["list_entry", "chip"];
  return compact.includes(context) && COMPACT_AMBIGUOUS_ICONS.includes(key);
}
