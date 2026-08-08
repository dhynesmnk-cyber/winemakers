/**
 * regions.ts — the Australian Geographical Indication register.
 *
 * Hand-authored (Wave 2). Verified against the Wine Australia Register of
 * Protected GIs on 2026-08-07. Three hierarchy errors present in secondary
 * sources were corrected against the individual GI pages on that date:
 *   - The Peninsulas is a ZONE in South Australia, not a region of Mount Lofty Ranges.
 *   - Upper Hunter Valley is a SUB-REGION of the Hunter region, not a region.
 *   - Henty is a REGION of the Western Victoria zone, not a sub-region of Grampians.
 *
 * This file owns the region and subregion taxonomy and nothing else. It does not
 * import from `site/src/config.ts` — Gate 1 owns that file and it does not exist
 * yet. See `CONSTANTS-REQUIRED.md` for the assertions Gate 1 must wire once it does.
 *
 * Consumers: `/region/[region]/`, `/region/[region]/[subregion]/`, `/[state]/`,
 * `/validate` check 12, and SCHEMA.md §2's `regions`, `primary_region` and
 * `subregions` fields.
 *
 * ── Two editorial rules, both deliberate ──────────────────────────────────────
 *
 * 1. NOT EVERY ENTRY HERE IS A REGISTERED "REGION" GI, AND `registered_as`
 *    RECORDS THE TRUTH. Wine Australia registers GIs at four levels — state,
 *    zone, region, sub-region — and a producer may lawfully label with the
 *    narrowest GI covering their fruit. Gippsland and Tasmania have no registered
 *    regions beneath them, so a Gippsland or Tasmanian producer's GI *is* the
 *    zone or the state. Those are carried here as routable entries so the
 *    producer has a region slug to use, tagged with what they actually are.
 *    Never render `registered_as` as a rank or a quality signal; it is a
 *    registry fact, and the glossary explains it in words.
 *
 * 2. UNREGISTERED SUB-REGIONS ARE CARRIED ONLY WHERE THEY EARN IT. A sub-region
 *    with `registered: false` is a district in common trade use that Wine
 *    Australia has not registered. They are included only where (a) SCHEMA.md §2
 *    names them — Blewitt Springs, Whitlands, Moppity — or (b) they are in
 *    routine use in one of the four Gate 8 coverage regions. Everything else
 *    waits until a producer needs it. Adding one is a data change, not a schema
 *    change: append it here, no other surface moves.
 *
 * `towns` is complete for the four Gate 8 coverage regions. Elsewhere it lists
 * principal towns only and is extended as producers arrive. It is a display and
 * disambiguation aid, never a boundary definition — the GI boundary is the
 * registry's, not this file's.
 */

/** Mirrors SCHEMA.md §1.14 `STATES`. Gate 1 asserts this equals `(typeof STATES)[number]`. */
export type StateCode = "VIC" | "NSW" | "QLD" | "SA" | "WA" | "TAS" | "NT" | "ACT";

/**
 * The level at which this entry is registered with Wine Australia.
 * `none` means no GI exists and the entry is an administrative placeholder.
 */
export type RegistrationLevel = "region" | "zone" | "state" | "none";

export interface Zone {
  slug: string;
  name: string;
  states: readonly StateCode[];
  /** Zones grouped under the Adelaide Super Zone (SA only). */
  super_zone?: "Adelaide";
}

export interface Region {
  slug: string;
  name: string;
  /** The GI zone this region sits in. `null` where the entry is itself a zone or a state GI. */
  zone: string | null;
  /** Usually one. Murray Darling, Swan Hill and Canberra District genuinely span two. */
  states: readonly StateCode[];
  registered_as: RegistrationLevel;
  /**
   * `"the"` where Australian usage puts a definite article in front of the
   * region name: "the Adelaide Hills", "the Yarra Valley", but "McLaren Vale"
   * and "Coonawarra" bare. Absent means no article, which is the safe default.
   *
   * It exists because UX.md §2.4's page-title register is "Independent
   * winemakers of the Adelaide Hills" and there is no way to reach that from
   * the name alone. POPULATED AS A REGION GAINS ITS FIRST PUBLISHED PRODUCER,
   * not speculatively: a region with none generates no page (Gate 6,
   * present-only), so an unpopulated article on the other sixty is invisible
   * and guessing at them would be inventing copy nobody can check.
   */
  article?: "the";
  /** Subregion slugs. Order is display order: registered first, then alphabetical. */
  subregions: readonly string[];
  towns: readonly string[];
  /** Shown on the region page where the entry needs explaining. Plain prose, no hedging. */
  note?: string;
}

export interface Subregion {
  slug: string;
  name: string;
  /** Parent region slug. Exactly one, always. */
  region: string;
  /** `false` = in common trade use, not on the register. Stated plainly wherever it is shown. */
  registered: boolean;
  towns?: readonly string[];
  note?: string;
}

/* ─────────────────────────────────────────────────────────────────────────────
   ZONES — every registered zone GI, including those containing no regions.
   Carried for completeness of the register. Zones are not routed.
   ───────────────────────────────────────────────────────────────────────── */

export const ZONES: readonly Zone[] = [
  // South Australia
  { slug: "barossa", name: "Barossa", states: ["SA"], super_zone: "Adelaide" },
  { slug: "far-north", name: "Far North", states: ["SA"] },
  { slug: "fleurieu", name: "Fleurieu", states: ["SA"], super_zone: "Adelaide" },
  { slug: "limestone-coast", name: "Limestone Coast", states: ["SA"] },
  { slug: "lower-murray", name: "Lower Murray", states: ["SA"] },
  { slug: "mount-lofty-ranges", name: "Mount Lofty Ranges", states: ["SA"], super_zone: "Adelaide" },
  { slug: "the-peninsulas", name: "The Peninsulas", states: ["SA"] },
  // New South Wales
  { slug: "big-rivers", name: "Big Rivers", states: ["NSW"] },
  { slug: "central-ranges", name: "Central Ranges", states: ["NSW"] },
  { slug: "hunter-valley", name: "Hunter Valley", states: ["NSW"] },
  { slug: "northern-rivers", name: "Northern Rivers", states: ["NSW"] },
  { slug: "northern-slopes", name: "Northern Slopes", states: ["NSW"] },
  { slug: "south-coast", name: "South Coast", states: ["NSW"] },
  { slug: "southern-new-south-wales", name: "Southern New South Wales", states: ["NSW", "ACT"] },
  { slug: "western-plains", name: "Western Plains", states: ["NSW"] },
  // Victoria
  { slug: "central-victoria", name: "Central Victoria", states: ["VIC"] },
  { slug: "gippsland", name: "Gippsland", states: ["VIC"] },
  { slug: "north-east-victoria", name: "North East Victoria", states: ["VIC"] },
  { slug: "north-west-victoria", name: "North West Victoria", states: ["VIC"] },
  { slug: "port-phillip", name: "Port Phillip", states: ["VIC"] },
  { slug: "western-victoria", name: "Western Victoria", states: ["VIC"] },
  // Western Australia
  { slug: "central-western-australia", name: "Central Western Australia", states: ["WA"] },
  {
    slug: "eastern-plains-inland-and-north-of-western-australia",
    name: "Eastern Plains, Inland and North of Western Australia",
    states: ["WA"],
  },
  { slug: "greater-perth", name: "Greater Perth", states: ["WA"] },
  { slug: "south-west-australia", name: "South West Australia", states: ["WA"] },
  {
    slug: "west-australian-south-east-coastal",
    name: "West Australian South East Coastal",
    states: ["WA"],
  },
  // Queensland
  { slug: "queensland", name: "Queensland", states: ["QLD"] },
  // Tasmania — registered as a state GI; also functions as the zone.
  { slug: "tasmania", name: "Tasmania", states: ["TAS"] },
] as const;

/* ─────────────────────────────────────────────────────────────────────────────
   SUBREGIONS
   Slugs are globally unique. Where a natural slug would be nationally ambiguous
   it is qualified — `east-coast-tasmania`, not `east-coast`.
   ───────────────────────────────────────────────────────────────────────── */

export const SUBREGIONS: readonly Subregion[] = [
  /* ── South Australia ─────────────────────────────────────────────────── */
  { slug: "high-eden", name: "High Eden", region: "eden-valley", registered: true },
  {
    slug: "lenswood",
    name: "Lenswood",
    region: "adelaide-hills",
    registered: true,
    towns: ["Lenswood", "Forest Range"],
  },
  {
    slug: "piccadilly-valley",
    name: "Piccadilly Valley",
    region: "adelaide-hills",
    registered: true,
    towns: ["Piccadilly", "Summertown", "Carey Gully", "Uraidla"],
  },

  // McLaren Vale districts — in routine trade use, none registered.
  {
    slug: "blewitt-springs",
    name: "Blewitt Springs",
    region: "mclaren-vale",
    registered: false,
    towns: ["Blewitt Springs"],
    note: "Deep sand over clay on the region's northern rise. Named in SCHEMA.md §2 as a worked example.",
  },
  { slug: "blanche-point", name: "Blanche Point", region: "mclaren-vale", registered: false },
  { slug: "clarendon", name: "Clarendon", region: "mclaren-vale", registered: false, towns: ["Clarendon"] },
  { slug: "kangarilla", name: "Kangarilla", region: "mclaren-vale", registered: false, towns: ["Kangarilla"] },
  { slug: "mclaren-flat", name: "McLaren Flat", region: "mclaren-vale", registered: false, towns: ["McLaren Flat"] },
  { slug: "seaview", name: "Seaview", region: "mclaren-vale", registered: false },
  {
    slug: "sellicks-foothills",
    name: "Sellicks Foothills",
    region: "mclaren-vale",
    registered: false,
    towns: ["Sellicks Hill", "Sellicks Beach"],
  },
  { slug: "tatachilla", name: "Tatachilla", region: "mclaren-vale", registered: false },
  { slug: "whites-valley", name: "Whites Valley", region: "mclaren-vale", registered: false },
  {
    slug: "willunga-foothills",
    name: "Willunga Foothills",
    region: "mclaren-vale",
    registered: false,
    towns: ["Willunga", "Willunga South"],
  },

  /* ── New South Wales ─────────────────────────────────────────────────── */
  { slug: "broke-fordwich", name: "Broke Fordwich", region: "hunter", registered: true, towns: ["Broke", "Fordwich"] },
  { slug: "pokolbin", name: "Pokolbin", region: "hunter", registered: true, towns: ["Pokolbin"] },
  {
    slug: "upper-hunter-valley",
    name: "Upper Hunter Valley",
    region: "hunter",
    registered: true,
    towns: ["Denman", "Muswellbrook"],
  },
  {
    slug: "moppity",
    name: "Moppity",
    region: "hilltops",
    registered: false,
    note: "A locality west of Young. Named in SCHEMA.md §2 as a worked example.",
  },

  /* ── Victoria ────────────────────────────────────────────────────────── */
  { slug: "nagambie-lakes", name: "Nagambie Lakes", region: "goulburn-valley", registered: true, towns: ["Nagambie"] },
  { slug: "great-western", name: "Great Western", region: "grampians", registered: true, towns: ["Great Western"] },
  {
    slug: "whitlands",
    name: "Whitlands",
    region: "king-valley",
    registered: false,
    note: "The high plateau at the head of the King Valley. Named in SCHEMA.md §2 as a worked example.",
  },
  {
    slug: "upper-yarra",
    name: "Upper Yarra",
    region: "yarra-valley",
    registered: false,
    towns: ["Hoddles Creek", "Gladysdale", "Yarra Junction", "Woori Yallock", "Warburton", "Wesburn", "Don Valley"],
    note: "The cooler, higher southern and eastern reach of the valley.",
  },
  {
    slug: "lower-yarra",
    name: "Lower Yarra",
    region: "yarra-valley",
    registered: false,
    towns: ["Yering", "Coldstream", "Yarra Glen", "Dixons Creek", "Steels Creek", "Gruyere"],
    note: "The warmer valley floor either side of the Yarra.",
  },
  // Mornington Peninsula districts — in routine use by the region's own vignerons, none registered.
  { slug: "dromana", name: "Dromana", region: "mornington-peninsula", registered: false, towns: ["Dromana", "Safety Beach"] },
  { slug: "main-ridge", name: "Main Ridge", region: "mornington-peninsula", registered: false, towns: ["Main Ridge"] },
  { slug: "merricks", name: "Merricks", region: "mornington-peninsula", registered: false, towns: ["Merricks", "Merricks North"] },
  { slug: "moorooduc", name: "Moorooduc", region: "mornington-peninsula", registered: false, towns: ["Moorooduc"] },
  { slug: "red-hill", name: "Red Hill", region: "mornington-peninsula", registered: false, towns: ["Red Hill", "Red Hill South"] },
  { slug: "shoreham", name: "Shoreham", region: "mornington-peninsula", registered: false, towns: ["Shoreham", "Point Leo", "Flinders"] },
  { slug: "tuerong", name: "Tuerong", region: "mornington-peninsula", registered: false, towns: ["Tuerong"] },

  /* ── Western Australia ───────────────────────────────────────────────── */
  { slug: "swan-valley", name: "Swan Valley", region: "swan-district", registered: true, towns: ["Herne Hill", "Middle Swan", "Baskerville", "Henley Brook"] },
  { slug: "albany", name: "Albany", region: "great-southern", registered: true, towns: ["Albany"] },
  { slug: "denmark", name: "Denmark", region: "great-southern", registered: true, towns: ["Denmark"] },
  { slug: "frankland-river", name: "Frankland River", region: "great-southern", registered: true, towns: ["Frankland River"] },
  { slug: "mount-barker", name: "Mount Barker", region: "great-southern", registered: true, towns: ["Mount Barker"] },
  { slug: "porongurup", name: "Porongurup", region: "great-southern", registered: true, towns: ["Porongurup"] },

  /* ── Tasmania — no registered regions or sub-regions. Districts in common use. ── */
  { slug: "tamar-valley", name: "Tamar Valley", region: "tasmania", registered: false, towns: ["Rowella", "Kayena", "Exeter", "Legana"] },
  { slug: "pipers-river", name: "Pipers River", region: "tasmania", registered: false, towns: ["Pipers River", "Pipers Brook"] },
  { slug: "east-coast-tasmania", name: "East Coast", region: "tasmania", registered: false, towns: ["Swansea", "Bicheno"] },
  { slug: "coal-river-valley", name: "Coal River Valley", region: "tasmania", registered: false, towns: ["Richmond", "Cambridge", "Campania"] },
  { slug: "derwent-valley", name: "Derwent Valley", region: "tasmania", registered: false, towns: ["New Norfolk", "Granton"] },
  { slug: "huon-valley", name: "Huon Valley", region: "tasmania", registered: false, towns: ["Huonville", "Cygnet"] },
  { slug: "north-west-tasmania", name: "North West", region: "tasmania", registered: false, towns: ["Devonport", "Ulverstone"] },
] as const;

/* ─────────────────────────────────────────────────────────────────────────────
   REGIONS
   ───────────────────────────────────────────────────────────────────────── */

export const REGIONS: readonly Region[] = [
  /* ═══ South Australia ═══════════════════════════════════════════════════ */
  {
    slug: "barossa-valley",
    name: "Barossa Valley",
    zone: "Barossa",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Tanunda", "Nuriootpa", "Angaston", "Lyndoch", "Rowland Flat", "Marananga", "Greenock", "Seppeltsfield", "Bethany", "Williamstown"],
  },
  {
    slug: "eden-valley",
    name: "Eden Valley",
    zone: "Barossa",
    states: ["SA"],
    registered_as: "region",
    subregions: ["high-eden"],
    towns: ["Eden Valley", "Springton", "Mount Pleasant", "Keyneton", "Flaxman Valley"],
  },
  {
    slug: "southern-flinders-ranges",
    name: "Southern Flinders Ranges",
    zone: "Far North",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Melrose", "Wirrabara", "Laura"],
  },
  {
    slug: "currency-creek",
    name: "Currency Creek",
    zone: "Fleurieu",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Currency Creek", "Goolwa"],
  },
  {
    slug: "kangaroo-island",
    name: "Kangaroo Island",
    zone: "Fleurieu",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Kingscote", "Penneshaw", "Parndana"],
  },
  {
    slug: "langhorne-creek",
    name: "Langhorne Creek",
    zone: "Fleurieu",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Langhorne Creek", "Strathalbyn", "Belvidere"],
  },
  {
    slug: "mclaren-vale",
    name: "McLaren Vale",
    zone: "Fleurieu",
    states: ["SA"],
    registered_as: "region",
    subregions: [
      "blanche-point",
      "blewitt-springs",
      "clarendon",
      "kangarilla",
      "mclaren-flat",
      "seaview",
      "sellicks-foothills",
      "tatachilla",
      "whites-valley",
      "willunga-foothills",
    ],
    towns: [
      "McLaren Vale",
      "McLaren Flat",
      "Willunga",
      "Willunga South",
      "Blewitt Springs",
      "Kangarilla",
      "Clarendon",
      "Aldinga",
      "Aldinga Beach",
      "Port Willunga",
      "Maslin Beach",
      "Moana",
      "Sellicks Hill",
      "Sellicks Beach",
      "Old Noarlunga",
      "Seaford Heights",
      "Pedler Creek",
      "Tatachilla",
      "Whites Valley",
      "Onkaparinga Hills",
      "Chandlers Hill",
      "Morphett Vale",
    ],
    note: "A Gate 8 coverage region. None of its ten districts is a registered GI sub-region; all are in routine trade use.",
  },
  {
    slug: "southern-fleurieu",
    name: "Southern Fleurieu",
    zone: "Fleurieu",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Victor Harbor", "Port Elliot", "Yankalilla", "Normanville", "Mount Compass"],
  },
  {
    slug: "coonawarra",
    name: "Coonawarra",
    zone: "Limestone Coast",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Coonawarra", "Penola"],
  },
  {
    slug: "mount-benson",
    name: "Mount Benson",
    zone: "Limestone Coast",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Mount Benson", "Kingston SE"],
  },
  {
    slug: "mount-gambier",
    name: "Mount Gambier",
    zone: "Limestone Coast",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Mount Gambier"],
  },
  {
    slug: "padthaway",
    name: "Padthaway",
    zone: "Limestone Coast",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Padthaway"],
  },
  {
    slug: "robe",
    name: "Robe",
    zone: "Limestone Coast",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Robe"],
  },
  {
    slug: "wrattonbully",
    name: "Wrattonbully",
    zone: "Limestone Coast",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Wrattonbully", "Naracoorte"],
  },
  {
    slug: "riverland",
    name: "Riverland",
    zone: "Lower Murray",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Renmark", "Berri", "Loxton", "Waikerie", "Barmera"],
  },
  {
    slug: "adelaide-hills",
    name: "Adelaide Hills",
    zone: "Mount Lofty Ranges",
    states: ["SA"],
    registered_as: "region",
    article: "the",
    subregions: ["lenswood", "piccadilly-valley"],
    towns: [
      "Aldgate",
      "Ashton",
      "Balhannah",
      "Basket Range",
      "Birdwood",
      "Bradbury",
      "Bridgewater",
      "Carey Gully",
      "Chain of Ponds",
      "Charleston",
      "Crafers",
      "Cudlee Creek",
      "Echunga",
      "Forest Range",
      "Forreston",
      "Gumeracha",
      "Hahndorf",
      "Harrogate",
      "Hay Valley",
      "Inglewood",
      "Ironbank",
      "Kersbrook",
      "Kuitpo",
      "Lenswood",
      "Littlehampton",
      "Lobethal",
      "Longwood",
      "Macclesfield",
      "Meadows",
      "Mount Barker",
      "Mount Torrens",
      "Mylor",
      "Nairne",
      "Norton Summit",
      "Oakbank",
      "Paracombe",
      "Paris Creek",
      "Piccadilly",
      "Scott Creek",
      "Stirling",
      "Summertown",
      "Uraidla",
      "Verdun",
      "Woodside",
    ],
    note: "A Gate 8 coverage region. Its town of Mount Barker shares a name with the registered Great Southern sub-region in Western Australia; they are unrelated.",
  },
  {
    slug: "adelaide-plains",
    name: "Adelaide Plains",
    zone: "Mount Lofty Ranges",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Virginia", "Angle Vale", "Two Wells"],
  },
  {
    slug: "clare-valley",
    name: "Clare Valley",
    zone: "Mount Lofty Ranges",
    states: ["SA"],
    registered_as: "region",
    subregions: [],
    towns: ["Clare", "Auburn", "Watervale", "Sevenhill", "Penwortham", "Mintaro", "Leasingham"],
  },
  {
    slug: "the-peninsulas",
    name: "The Peninsulas",
    zone: null,
    states: ["SA"],
    registered_as: "zone",
    subregions: [],
    towns: ["Port Lincoln", "Coffin Bay", "Minlaton"],
    note: "A registered zone with no registered regions beneath it. Producers on the Yorke and southern Eyre Peninsulas label with the zone.",
  },

  /* ═══ New South Wales ═══════════════════════════════════════════════════ */
  {
    slug: "murray-darling",
    name: "Murray Darling",
    zone: "Big Rivers / North West Victoria",
    states: ["NSW", "VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Mildura", "Merbein", "Red Cliffs", "Wentworth", "Robinvale"],
    note: "One region spanning two states. It sits in the Big Rivers zone in New South Wales and the North West Victoria zone in Victoria.",
  },
  {
    slug: "perricoota",
    name: "Perricoota",
    zone: "Big Rivers",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Moama", "Echuca Village"],
  },
  {
    slug: "riverina",
    name: "Riverina",
    zone: "Big Rivers",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Griffith", "Leeton", "Yenda", "Hanwood", "Bilbul"],
  },
  {
    slug: "swan-hill",
    name: "Swan Hill",
    zone: "Big Rivers / North West Victoria",
    states: ["NSW", "VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Swan Hill", "Nyah", "Woorinen"],
    note: "One region spanning two states, on the same footing as Murray Darling.",
  },
  {
    slug: "cowra",
    name: "Cowra",
    zone: "Central Ranges",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Cowra", "Canowindra"],
  },
  {
    slug: "mudgee",
    name: "Mudgee",
    zone: "Central Ranges",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Mudgee", "Gulgong", "Rylstone"],
  },
  {
    slug: "orange",
    name: "Orange",
    zone: "Central Ranges",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Orange", "Molong", "Nashdale", "Borenore"],
  },
  {
    slug: "hunter",
    name: "Hunter",
    zone: "Hunter Valley",
    states: ["NSW"],
    registered_as: "region",
    subregions: ["broke-fordwich", "pokolbin", "upper-hunter-valley"],
    towns: ["Pokolbin", "Cessnock", "Broke", "Rothbury", "Lovedale", "Denman", "Muswellbrook", "Singleton"],
    note: "The registered region is Hunter. Hunter Valley is the zone above it.",
  },
  {
    slug: "hastings-river",
    name: "Hastings River",
    zone: "Northern Rivers",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Port Macquarie", "Wauchope"],
  },
  {
    slug: "new-england-australia",
    name: "New England Australia",
    zone: "Northern Slopes",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Armidale", "Glen Innes", "Tenterfield", "Inverell"],
  },
  {
    slug: "shoalhaven-coast",
    name: "Shoalhaven Coast",
    zone: "South Coast",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Nowra", "Berry", "Kangaroo Valley"],
  },
  {
    slug: "southern-highlands",
    name: "Southern Highlands",
    zone: "South Coast",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Bowral", "Mittagong", "Moss Vale", "Sutton Forest"],
  },
  {
    slug: "canberra-district",
    name: "Canberra District",
    zone: "Southern New South Wales",
    states: ["NSW", "ACT"],
    registered_as: "region",
    subregions: [],
    towns: ["Murrumbateman", "Hall", "Bungendore", "Yass", "Gundaroo", "Lake George", "Pialligo"],
    note: "The registered boundary lies partly in New South Wales and partly in the Australian Capital Territory. It is the only GI reaching into the ACT.",
  },
  {
    slug: "gundagai",
    name: "Gundagai",
    zone: "Southern New South Wales",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Gundagai", "Tumblong"],
  },
  {
    slug: "hilltops",
    name: "Hilltops",
    zone: "Southern New South Wales",
    states: ["NSW"],
    registered_as: "region",
    subregions: ["moppity"],
    towns: ["Young", "Boorowa", "Harden", "Murrumburrah"],
  },
  {
    slug: "tumbarumba",
    name: "Tumbarumba",
    zone: "Southern New South Wales",
    states: ["NSW"],
    registered_as: "region",
    subregions: [],
    towns: ["Tumbarumba", "Rosewood"],
  },
  {
    slug: "western-plains",
    name: "Western Plains",
    zone: null,
    states: ["NSW"],
    registered_as: "zone",
    subregions: [],
    towns: ["Dubbo", "Wellington"],
    note: "A registered zone with no registered regions beneath it.",
  },

  /* ═══ Victoria ══════════════════════════════════════════════════════════ */
  {
    slug: "bendigo",
    name: "Bendigo",
    zone: "Central Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Bendigo", "Harcourt", "Heathcote Junction", "Bridgewater on Loddon"],
  },
  {
    slug: "goulburn-valley",
    name: "Goulburn Valley",
    zone: "Central Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: ["nagambie-lakes"],
    towns: ["Nagambie", "Shepparton", "Tabilk", "Murchison"],
  },
  {
    slug: "heathcote",
    name: "Heathcote",
    zone: "Central Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Heathcote", "Colbinabbin", "Toolleen"],
  },
  {
    slug: "strathbogie-ranges",
    name: "Strathbogie Ranges",
    zone: "Central Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Strathbogie", "Euroa", "Avenel"],
  },
  {
    slug: "upper-goulburn",
    name: "Upper Goulburn",
    zone: "Central Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Yea", "Alexandra", "Mansfield", "Eildon"],
  },
  {
    slug: "gippsland",
    name: "Gippsland",
    zone: null,
    states: ["VIC"],
    registered_as: "zone",
    subregions: [],
    towns: ["Leongatha", "Bairnsdale", "Warragul", "Foster", "Maffra", "Traralgon"],
    note: "A registered zone with no registered regions beneath it. A Gippsland producer's narrowest available GI is the zone, which is why it is routed here as a region.",
  },
  {
    slug: "alpine-valleys",
    name: "Alpine Valleys",
    zone: "North East Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Myrtleford", "Bright", "Porepunkah", "Wandiligong"],
  },
  {
    slug: "beechworth",
    name: "Beechworth",
    zone: "North East Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Beechworth", "Everton", "Stanley"],
  },
  {
    slug: "glenrowan",
    name: "Glenrowan",
    zone: "North East Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Glenrowan", "Taminick"],
  },
  {
    slug: "king-valley",
    name: "King Valley",
    zone: "North East Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: ["whitlands"],
    towns: ["Whitfield", "Cheshunt", "Moyhu", "Milawa", "Oxley", "Meadow Creek"],
  },
  {
    slug: "rutherglen",
    name: "Rutherglen",
    zone: "North East Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Rutherglen", "Wahgunyah", "Chiltern"],
  },
  {
    slug: "geelong",
    name: "Geelong",
    zone: "Port Phillip",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Geelong", "Bannockburn", "Waurn Ponds", "Moriac", "Sutherlands Creek", "Drysdale", "Portarlington"],
  },
  {
    slug: "macedon-ranges",
    name: "Macedon Ranges",
    zone: "Port Phillip",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Kyneton", "Macedon", "Woodend", "Romsey", "Lancefield", "Gisborne"],
  },
  {
    slug: "mornington-peninsula",
    name: "Mornington Peninsula",
    zone: "Port Phillip",
    states: ["VIC"],
    registered_as: "region",
    article: "the",
    subregions: ["dromana", "main-ridge", "merricks", "moorooduc", "red-hill", "shoreham", "tuerong"],
    towns: [
      "Arthurs Seat",
      "Balnarring",
      "Baxter",
      "Bittern",
      "Blairgowrie",
      "Boneo",
      "Cape Schanck",
      "Crib Point",
      "Dromana",
      "Fingal",
      "Flinders",
      "Hastings",
      "Main Ridge",
      "McCrae",
      "Merricks",
      "Merricks North",
      "Moorooduc",
      "Mornington",
      "Mount Eliza",
      "Mount Martha",
      "Point Leo",
      "Portsea",
      "Red Hill",
      "Red Hill South",
      "Rosebud",
      "Rye",
      "Safety Beach",
      "Shoreham",
      "Somers",
      "Somerville",
      "Sorrento",
      "Tootgarook",
      "Tuerong",
      "Tyabb",
    ],
    note: "A Gate 8 coverage region. Its seven districts are in routine use by the region's own vignerons; none is a registered GI sub-region.",
  },
  {
    slug: "sunbury",
    name: "Sunbury",
    zone: "Port Phillip",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Sunbury", "Bulla", "Diggers Rest"],
  },
  {
    slug: "yarra-valley",
    name: "Yarra Valley",
    zone: "Port Phillip",
    states: ["VIC"],
    registered_as: "region",
    article: "the",
    subregions: ["lower-yarra", "upper-yarra"],
    towns: [
      "Badger Creek",
      "Chirnside Park",
      "Christmas Hills",
      "Coldstream",
      "Dixons Creek",
      "Don Valley",
      "Gladysdale",
      "Gruyere",
      "Healesville",
      "Hoddles Creek",
      "Kangaroo Ground",
      "Launching Place",
      "Lilydale",
      "Monbulk",
      "Panton Hill",
      "Seville",
      "Seville East",
      "Silvan",
      "Steels Creek",
      "St Andrews",
      "Tarrawarra",
      "Toolangi",
      "Wandin East",
      "Wandin North",
      "Warburton",
      "Wesburn",
      "Woori Yallock",
      "Yarra Glen",
      "Yarra Junction",
      "Yellingbo",
      "Yering",
    ],
    note: "A Gate 8 coverage region. Upper Yarra and Lower Yarra are in common use and are not registered GI sub-regions.",
  },
  {
    slug: "grampians",
    name: "Grampians",
    zone: "Western Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: ["great-western"],
    towns: ["Great Western", "Ararat", "Halls Gap", "Stawell", "Moyston"],
  },
  {
    slug: "henty",
    name: "Henty",
    zone: "Western Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Hamilton", "Drumborg", "Coleraine", "Condah"],
  },
  {
    slug: "pyrenees",
    name: "Pyrenees",
    zone: "Western Victoria",
    states: ["VIC"],
    registered_as: "region",
    subregions: [],
    towns: ["Avoca", "Moonambel", "Redbank", "Landsborough"],
  },

  /* ═══ Western Australia ═════════════════════════════════════════════════ */
  {
    slug: "peel",
    name: "Peel",
    zone: "Greater Perth",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Mandurah", "Pinjarra", "Waroona"],
  },
  {
    slug: "perth-hills",
    name: "Perth Hills",
    zone: "Greater Perth",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Bickley", "Carmel", "Chittering", "Gidgegannup", "Mundaring"],
  },
  {
    slug: "swan-district",
    name: "Swan District",
    zone: "Greater Perth",
    states: ["WA"],
    registered_as: "region",
    subregions: ["swan-valley"],
    towns: ["Herne Hill", "Middle Swan", "Baskerville", "Henley Brook", "Bullsbrook", "Gingin"],
  },
  {
    slug: "blackwood-valley",
    name: "Blackwood Valley",
    zone: "South West Australia",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Bridgetown", "Boyup Brook", "Nannup"],
  },
  {
    slug: "geographe",
    name: "Geographe",
    zone: "South West Australia",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Donnybrook", "Capel", "Ferguson Valley", "Harvey", "Dardanup"],
  },
  {
    slug: "great-southern",
    name: "Great Southern",
    zone: "South West Australia",
    states: ["WA"],
    registered_as: "region",
    subregions: ["albany", "denmark", "frankland-river", "mount-barker", "porongurup"],
    towns: ["Albany", "Denmark", "Mount Barker", "Frankland River", "Porongurup", "Kendenup"],
    note: "The most sub-divided region on the register: five registered sub-regions.",
  },
  {
    slug: "manjimup",
    name: "Manjimup",
    zone: "South West Australia",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Manjimup"],
  },
  {
    slug: "margaret-river",
    name: "Margaret River",
    zone: "South West Australia",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Margaret River", "Cowaramup", "Wilyabrup", "Yallingup", "Dunsborough", "Karridale", "Witchcliffe"],
  },
  {
    slug: "pemberton",
    name: "Pemberton",
    zone: "South West Australia",
    states: ["WA"],
    registered_as: "region",
    subregions: [],
    towns: ["Pemberton", "Northcliffe"],
  },
  {
    slug: "central-western-australia",
    name: "Central Western Australia",
    zone: null,
    states: ["WA"],
    registered_as: "zone",
    subregions: [],
    towns: [],
    note: "A registered zone with no registered regions beneath it.",
  },
  {
    slug: "eastern-plains-inland-and-north-of-western-australia",
    name: "Eastern Plains, Inland and North of Western Australia",
    zone: null,
    states: ["WA"],
    registered_as: "zone",
    subregions: [],
    towns: [],
    note: "A registered zone with no registered regions beneath it.",
  },
  {
    slug: "west-australian-south-east-coastal",
    name: "West Australian South East Coastal",
    zone: null,
    states: ["WA"],
    registered_as: "zone",
    subregions: [],
    towns: ["Esperance"],
    note: "A registered zone with no registered regions beneath it.",
  },

  /* ═══ Queensland ════════════════════════════════════════════════════════ */
  {
    slug: "granite-belt",
    name: "Granite Belt",
    zone: "Queensland",
    states: ["QLD"],
    registered_as: "region",
    subregions: [],
    towns: ["Stanthorpe", "Ballandean", "Glen Aplin", "Severnlea", "Wyberba"],
  },
  {
    slug: "south-burnett",
    name: "South Burnett",
    zone: "Queensland",
    states: ["QLD"],
    registered_as: "region",
    subregions: [],
    towns: ["Kingaroy", "Murgon", "Nanango", "Wondai"],
  },

  /* ═══ Tasmania ══════════════════════════════════════════════════════════ */
  {
    slug: "tasmania",
    name: "Tasmania",
    zone: null,
    states: ["TAS"],
    registered_as: "state",
    subregions: [
      "coal-river-valley",
      "derwent-valley",
      "east-coast-tasmania",
      "huon-valley",
      "north-west-tasmania",
      "pipers-river",
      "tamar-valley",
    ],
    towns: ["Launceston", "Hobart", "Richmond", "Pipers River", "Rowella", "Swansea", "New Norfolk", "Huonville", "Devonport"],
    note: "Tasmania is registered as a state GI with no regions or sub-regions beneath it. Every Tasmanian wine is labelled Tasmania, which is why the state is routed here as a single region. Its seven districts are in common use and none is registered.",
  },

  /* ═══ Northern Territory ════════════════════════════════════════════════ */
  {
    slug: "northern-territory",
    name: "Northern Territory",
    zone: null,
    states: ["NT"],
    registered_as: "none",
    subregions: [],
    towns: ["Alice Springs"],
    note: "The Northern Territory has no registered wine GI of any kind. This entry exists so a Territory producer has somewhere to sit and so every state resolves to at least one region. It is not a Geographical Indication and must never be presented as one.",
  },
] as const;

/* ─────────────────────────────────────────────────────────────────────────────
   Derived lookups and helpers
   ───────────────────────────────────────────────────────────────────────── */

export const REGION_SLUGS: readonly string[] = REGIONS.map((r) => r.slug);
export const SUBREGION_SLUGS: readonly string[] = SUBREGIONS.map((s) => s.slug);

export const REGION_BY_SLUG: ReadonlyMap<string, Region> = new Map(
  REGIONS.map((r) => [r.slug, r]),
);
export const SUBREGION_BY_SLUG: ReadonlyMap<string, Subregion> = new Map(
  SUBREGIONS.map((s) => [s.slug, s]),
);

/** Display name for a region slug, or the slug itself if unknown. Never throws in a template. */
export function regionName(slug: string): string {
  return REGION_BY_SLUG.get(slug)?.name ?? slug;
}

/** Display name for a subregion slug, or the slug itself if unknown. */
export function subregionName(slug: string): string {
  return SUBREGION_BY_SLUG.get(slug)?.name ?? slug;
}

/**
 * The region name as it appears mid-sentence: "the Adelaide Hills", "McLaren
 * Vale". For page titles and prose, never for a heading or a link label, both
 * of which take the bare name.
 */
export function regionWithArticle(slug: string): string {
  const region = REGION_BY_SLUG.get(slug);
  if (!region) return slug;
  return region.article ? `${region.article} ${region.name}` : region.name;
}

export function isRegionSlug(slug: string): boolean {
  return REGION_BY_SLUG.has(slug);
}

export function isSubregionSlug(slug: string): boolean {
  return SUBREGION_BY_SLUG.has(slug);
}

/** Every region touching a state, in register order. */
export function regionsForState(state: StateCode): readonly Region[] {
  return REGIONS.filter((r) => r.states.includes(state));
}

/** Every subregion of a region, in the region's declared display order. */
export function subregionsForRegion(regionSlug: string): readonly Subregion[] {
  const region = REGION_BY_SLUG.get(regionSlug);
  if (!region) return [];
  return region.subregions
    .map((slug) => SUBREGION_BY_SLUG.get(slug))
    .filter((s): s is Subregion => s !== undefined);
}

/**
 * SCHEMA.md §2a rule 5: every `subregions` entry must belong to a region the
 * producer lists. Returns the offending subregion slugs, empty when valid.
 * `/validate` check 12 calls this; so does the admin editor.
 */
export function orphanSubregions(
  regionSlugs: readonly string[],
  subregionSlugs: readonly string[],
): string[] {
  const allowed = new Set(regionSlugs);
  return subregionSlugs.filter((slug) => {
    const sub = SUBREGION_BY_SLUG.get(slug);
    return sub === undefined || !allowed.has(sub.region);
  });
}
