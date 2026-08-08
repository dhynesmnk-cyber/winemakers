/**
 * glossary.ts — one entry for every value of every closed vocabulary in SCHEMA.md §1.
 *
 * Hand-authored (Wave 2). Consumers: `/glossary/`, `/glossary/[key]/`, the
 * definition lines at the foot of `/variety/[grape]/` and `/practice/[key]/`,
 * `DefinedTermSet` / `DefinedTerm` JSON-LD at Gate 10, and `/validate` check 11,
 * which fails on an orphan in either direction.
 *
 * ── Keys ──────────────────────────────────────────────────────────────────────
 * Entries are keyed `<vocabulary>-<value>`, kebab-cased, because the raw enum
 * values collide across vocabularies: `none` is both a cellar-door state and a
 * certification state. DESIGN.md §6 namespaces the icon keys for the same
 * reason. Namespacing everything, rather than only the pair that currently
 * collides, means a future enum value cannot silently take over a URL.
 *
 * `value` is the raw enum member and is what joins back to SCHEMA.md §1.
 * `/validate` check 11 walks the tuples in config.ts and matches on `value`
 * within `vocabulary`, never on `slug`.
 *
 * ── Copy rules ────────────────────────────────────────────────────────────────
 * Every string in this file is read by a member of the public, so the editorial
 * guardrails apply in full: Australian English, no em dashes, no hedge words,
 * no banned-list words, no unsourced tasting descriptors. A variety entry says
 * what the grape is and where it is grown in Australia. It does not say what the
 * wine tastes like. Nobody on this project has tasted it.
 *
 * `excludes` carries what DESIGN.md §7 asks of a glossary definition: what the
 * term does not mean. It is present wherever a reader could reasonably get the
 * term wrong and absent where nothing needs heading off.
 */

export type VocabularyId =
  | "category"
  | "cellar-door"
  | "certification"
  | "fruit-source"
  | "production-band"
  | "practice"
  | "logistics"
  | "vessel"
  | "wine-style"
  | "variety"
  | "confidence-tier"
  | "ownership-evidence"
  | "state";

export interface GlossaryEntry {
  /** URL segment. Globally unique. `<vocabulary>-<value>`, kebab-cased. */
  slug: string;
  /** The SCHEMA.md §1 vocabulary this value belongs to. */
  vocabulary: VocabularyId;
  /** The raw enum member exactly as it appears in the config.ts tuple. */
  value: string;
  /** Display name. Title case for proper nouns, sentence case otherwise. */
  term: string;
  /** One line. Used inline on region, variety and practice pages. */
  short: string;
  /** Two to four plain sentences. The glossary detail page. */
  definition: string;
  /** What the term does not mean. */
  excludes?: string;
  /** Other names the same thing goes by. Searchable; never a separate entry. */
  aliases?: readonly string[];
  /** Other glossary slugs worth reading next. */
  see_also?: readonly string[];
}

export const GLOSSARY: readonly GlossaryEntry[] = [
  /* ═══ §1.1 CATEGORIES ═══════════════════════════════════════════════════ */
  {
    slug: "category-estate-winery",
    vocabulary: "category",
    value: "estate_winery",
    term: "Estate winery",
    short: "Grows its own fruit and makes the wine on the same site.",
    definition:
      "An estate winery farms vineyards and operates a winery on the same property. Fruit is picked and processed without leaving the site. It is the arrangement most people picture when they think of a winery, and it is a minority of the producers in this directory.",
    excludes:
      "It does not mean the producer uses only its own fruit. An estate winery that also buys fruit is recorded as fruit source mixed.",
    see_also: ["fruit-source-estate", "category-garagiste"],
  },
  {
    slug: "category-urban-winery",
    vocabulary: "category",
    value: "urban_winery",
    term: "Urban winery",
    short: "Makes wine in a city or town premises from fruit trucked in.",
    definition:
      "An urban winery operates its cellar in a built-up area and brings fruit in from growing regions. The winery is in one place and the vineyards are in another, which is why this directory records location and regions as separate fields.",
    excludes:
      "The city is not the wine's region. An urban winery in Sydney working Hilltops fruit is listed under Hilltops.",
    see_also: ["fruit-source-purchased", "category-negociant"],
  },
  {
    slug: "category-negociant",
    vocabulary: "category",
    value: "negociant",
    term: "Négociant",
    short: "Buys fruit or finished wine and blends it under their own label.",
    definition:
      "A négociant sources fruit, juice or finished wine from growers and makers, then blends, matures and bottles under their own name. The model is old and entirely legitimate. It is how a number of well-regarded Australian labels have always worked.",
    excludes:
      "A négociant is not a garagiste. The line this directory draws is what gets bought: a négociant buys fruit or wine, a garagiste buys space.",
    aliases: ["Negociant"],
    see_also: ["category-garagiste", "fruit-source-purchased"],
  },
  {
    slug: "category-garagiste",
    vocabulary: "category",
    value: "garagiste",
    term: "Garagiste",
    short: "Makes wine at small scale in shared, rented or borrowed space.",
    definition:
      "A garagiste makes wine without owning a winery, working in a corner of someone else's facility, a rented shed or a shared crush space. Volumes are usually small. Many of the producers this directory exists to document started this way and a good number have stayed there by choice.",
    excludes:
      "It says nothing about quality or scale of ambition, and it is not a synonym for new. Some garagistes have been making wine for twenty years.",
    see_also: ["category-negociant", "production-band-under-1000"],
  },
  {
    slug: "category-cooperative",
    vocabulary: "category",
    value: "cooperative",
    term: "Cooperative",
    short: "Growers or makers sharing one facility and one label.",
    definition:
      "A cooperative pools the fruit or the facilities of several members and sells under a shared name. It is common elsewhere in the world and uncommon in Australia, which is why the category is here and rarely used.",
    excludes:
      "A shared crush space used by separate labels is not a cooperative. Those makers are each recorded as garagiste under their own names.",
    see_also: ["category-garagiste"],
  },
  {
    slug: "category-other",
    vocabulary: "category",
    value: "other",
    term: "Other",
    short: "A business shape the five named categories do not describe.",
    definition:
      "Used where a producer genuinely does not fit the other five. It is rare and it is meant to stay rare.",
    excludes:
      "It is not a place to put a producer whose category has not been looked up. An entry reaching publication with other should have a reason a reader could follow.",
  },

  /* ═══ §1.2 CELLAR_DOOR_STATES ═══════════════════════════════════════════ */
  {
    slug: "cellar-door-none",
    vocabulary: "cellar-door",
    value: "none",
    term: "No cellar door",
    short: "There is nowhere to visit.",
    definition:
      "The producer has no premises open to the public. Wine is bought online, through retailers or through restaurants. A great many of the smallest and most interesting producers in Australia are in this state, and an entry with no cellar door is a complete entry, not a thin one.",
    excludes:
      "It does not mean the producer is closed, dormant or hard to buy from.",
    see_also: ["cellar-door-by-appointment"],
  },
  {
    slug: "cellar-door-by-appointment",
    vocabulary: "cellar-door",
    value: "by_appointment",
    term: "By appointment",
    short: "You can visit, once you have arranged it first.",
    definition:
      "The producer receives visitors on a booking. This covers everything from a formal reservation system to a phone number and a conversation. It is the most common state for small producers, which is why this directory records three states rather than a yes or no.",
    excludes:
      "Published opening hours do not make a cellar door open if a booking is still required. A producer listing weekend hours and asking for a reservation is by appointment.",
    see_also: ["cellar-door-open", "logistics-bookings-required"],
  },
  {
    slug: "cellar-door-open",
    vocabulary: "cellar-door",
    value: "open",
    term: "Open cellar door",
    short: "You can turn up during published hours.",
    definition:
      "The producer keeps regular hours and takes visitors without a booking. Hours are recorded as the producer publishes them, in their own words.",
    excludes:
      "Open does not mean open every day, and it does not promise a table for a group. Group bookings are a separate fact.",
    see_also: ["cellar-door-by-appointment", "logistics-walk-ins-welcome"],
  },

  /* ═══ §1.3 CERTIFICATION_STATES ═════════════════════════════════════════ */
  {
    slug: "certification-none",
    vocabulary: "certification",
    value: "none",
    term: "Not certified or practising",
    short: "The producer makes no organic or biodynamic claim.",
    definition:
      "Nothing the producer publishes claims organic or biodynamic farming. This is the correct record for the large majority of Australian producers and it carries no judgement.",
    excludes:
      "It is not a finding that the vineyard is farmed conventionally. It records the absence of a published claim, which is a different thing.",
    see_also: ["certification-practising"],
  },
  {
    slug: "certification-practising",
    vocabulary: "certification",
    value: "practising",
    term: "Practising",
    short: "Farms to the method and holds no certificate for it.",
    definition:
      "The producer states they farm organically or biodynamically without being certified. Certification costs money and takes years, and plenty of growers decide it is not worth either. Some are in conversion. Some have simply never applied.",
    excludes:
      "Practising is not a weaker grade of certified. It is a different fact, and this directory records the producer's own words rather than ranking them. A vineyard described only as sustainable is recorded as none, because sustainable is a third claim again.",
    see_also: ["certification-certified", "certification-none"],
  },
  {
    slug: "certification-certified",
    vocabulary: "certification",
    value: "certified",
    term: "Certified",
    short: "Audited and certified by a named certifying body.",
    definition:
      "An independent certifier has audited the operation and issued a certificate. Australian Certified Organic, NASAA and Demeter are the bodies most often named. This directory records certified only where the certifier is named, and the certifier is displayed with the claim.",
    excludes:
      "A header reading Certified Organic with no certifying body named anywhere is not enough. Publishing an unbacked certification claim about a real business is a labelling problem, so the entry is held rather than guessed at.",
    see_also: ["certification-practising", "confidence-tier-published-by-producer"],
  },

  /* ═══ §1.4 FRUIT_SOURCE ═════════════════════════════════════════════════ */
  {
    slug: "fruit-source-estate",
    vocabulary: "fruit-source",
    value: "estate",
    term: "Estate fruit",
    short: "All the fruit comes from vineyards the producer farms.",
    definition:
      "Every grape is grown on land the producer owns or manages. Recorded only where the producer states it.",
    excludes:
      "Estate fruit does not require an estate winery. A producer can farm their own vineyard and make the wine in rented space.",
    see_also: ["fruit-source-mixed", "category-estate-winery"],
  },
  {
    slug: "fruit-source-purchased",
    vocabulary: "fruit-source",
    value: "purchased",
    term: "Purchased fruit",
    short: "The fruit is bought from growers.",
    definition:
      "The producer buys grapes rather than farming them. Long grower relationships are common and are often the reason a wine is what it is. This directory records purchased fruit as a neutral fact.",
    excludes:
      "Purchased is not a demerit and it is not a mark of scale. Some of the smallest producers in Australia buy every kilogram they crush.",
    see_also: ["category-negociant", "fruit-source-mixed"],
  },
  {
    slug: "fruit-source-mixed",
    vocabulary: "fruit-source",
    value: "mixed",
    term: "Mixed fruit",
    short: "Some fruit is grown, some is bought.",
    definition:
      "The producer farms part of what they crush and buys the rest. This is the most common arrangement among the producers in this directory, and it is why the field has three values rather than being a yes or no.",
    see_also: ["fruit-source-estate", "fruit-source-purchased"],
  },

  /* ═══ §1.5 PRODUCTION_BANDS ═════════════════════════════════════════════ */
  {
    slug: "production-band-under-1000",
    vocabulary: "production-band",
    value: "under_1000",
    term: "Under 1,000 cases",
    short: "Fewer than 1,000 cases a year, which is around 12,000 bottles.",
    definition:
      "The smallest band. A single vineyard block or a few barrels. Producers at this scale usually sell direct and often sell out.",
    see_also: ["category-garagiste", "production-band-unknown"],
  },
  {
    slug: "production-band-1000-5000",
    vocabulary: "production-band",
    value: "1000_5000",
    term: "1,000 to 5,000 cases",
    short: "Between 1,000 and 5,000 cases a year.",
    definition:
      "A small producer with enough volume to supply restaurants and independent retailers as well as selling direct.",
  },
  {
    slug: "production-band-5000-20000",
    vocabulary: "production-band",
    value: "5000_20000",
    term: "5,000 to 20,000 cases",
    short: "Between 5,000 and 20,000 cases a year.",
    definition:
      "A mid-sized independent producer, usually with national distribution and often with export.",
  },
  {
    slug: "production-band-over-20000",
    vocabulary: "production-band",
    value: "over_20000",
    term: "Over 20,000 cases",
    short: "More than 20,000 cases a year.",
    definition:
      "The largest band this directory records. Independent producers of this size exist and are listed on the same terms as everyone else.",
    excludes: "Size is not a proxy for ownership. The two are recorded separately and only ownership decides inclusion.",
    see_also: ["ownership-evidence-registry"],
  },
  {
    slug: "production-band-unknown",
    vocabulary: "production-band",
    value: "unknown",
    term: "Production not published",
    short: "The producer does not publish how much they make.",
    definition:
      "Most producers do not publish case numbers. Unknown is the correct and honest record when they do not, and it appears on a great many entries.",
    excludes:
      "It is not a gap waiting to be estimated. A band inferred from vineyard area or from the look of a website would be a fabrication.",
    see_also: ["confidence-tier-unverified"],
  },

  /* ═══ §1.6 PRACTICE_KEYS ════════════════════════════════════════════════ */
  {
    slug: "practice-wild-ferment",
    vocabulary: "practice",
    value: "wild_ferment",
    term: "Wild ferment",
    short: "Fermented by the yeast already on the fruit and in the cellar, with none added.",
    definition:
      "Also called native, ambient, spontaneous or indigenous ferment. The winemaker does not inoculate with a cultured yeast strain and lets the population present on the grapes and in the winery start the fermentation. It is slower and less predictable than an inoculated ferment. This directory records it only where the producer states it in their own published material.",
    excludes:
      "Wild ferment is a single technical decision. It is not a guarantee about anything else in the cellar and it is not a certification.",
    aliases: ["Native ferment", "Wild yeast", "Spontaneous fermentation", "Indigenous yeast"],
    see_also: ["practice-minimal-so2", "practice-unfined"],
  },
  {
    slug: "practice-unfined",
    vocabulary: "practice",
    value: "unfined",
    term: "Unfined",
    short: "Bottled without fining agents, so the wine may be cloudy.",
    definition:
      "Fining clarifies and stabilises wine by adding an agent that binds to suspended matter and drops out. An unfined wine skips that step. Because several traditional fining agents come from animals, unfined wines are often, though not always, suitable for vegans.",
    excludes:
      "Unfined does not mean unfiltered, and the two are recorded separately. A wine can be one, both or neither.",
    see_also: ["practice-unfiltered"],
  },
  {
    slug: "practice-unfiltered",
    vocabulary: "practice",
    value: "unfiltered",
    term: "Unfiltered",
    short: "Bottled without passing the wine through a filter.",
    definition:
      "Filtration removes solids and can remove yeast and bacteria along with them. An unfiltered wine goes into bottle without it, which leaves more in suspension and leaves the wine less stabilised.",
    excludes:
      "Unfiltered does not mean unfined. It also does not mean a sediment in the bottle is a fault.",
    see_also: ["practice-unfined"],
  },
  {
    slug: "practice-minimal-so2",
    vocabulary: "practice",
    value: "minimal_so2",
    term: "Minimal sulphur",
    short: "Little or no sulphur dioxide added, usually only at bottling.",
    definition:
      "Sulphur dioxide is the standard preservative and antioxidant in winemaking. Producers working with minimal sulphur add very little, or add it only at bottling, or add none at all. Fermentation produces a small amount of sulphites on its own, so no wine is entirely free of them.",
    excludes:
      "There is no legal definition of minimal and no threshold behind it. This directory records the producer's own published statement and nothing more.",
    aliases: ["Low sulphur", "Minimal SO2", "No added sulphites"],
    see_also: ["practice-wild-ferment"],
  },

  /* ═══ §1.7 LOGISTICS_KEYS ═══════════════════════════════════════════════ */
  {
    slug: "logistics-walk-ins-welcome",
    vocabulary: "logistics",
    value: "walk_ins_welcome",
    term: "Walk-ins welcome",
    short: "You can arrive without booking.",
    definition: "The producer takes visitors who turn up during opening hours.",
    excludes: "It does not promise a seat, a table or a full tasting at a busy time.",
    see_also: ["cellar-door-open"],
  },
  {
    slug: "logistics-bookings-required",
    vocabulary: "logistics",
    value: "bookings_required",
    term: "Bookings required",
    short: "Arrange your visit before you go.",
    definition:
      "The producer asks visitors to book. For a small operation this is usually because one person is doing the tasting, the paperwork and the pruning.",
    see_also: ["cellar-door-by-appointment"],
  },
  {
    slug: "logistics-restaurant",
    vocabulary: "logistics",
    value: "restaurant",
    term: "Restaurant",
    short: "There is a restaurant on site.",
    definition:
      "The producer runs a restaurant or a kitchen serving full meals at the cellar door.",
    excludes:
      "A cheese plate, a share board or a coffee cart is not a restaurant. Those sit under picnic provisions where the producer supplies them.",
    see_also: ["logistics-picnic-provisions"],
  },
  {
    slug: "logistics-picnic-provisions",
    vocabulary: "logistics",
    value: "picnic_provisions",
    term: "Picnic provisions",
    short: "Food to take outside is sold on site.",
    definition:
      "The producer sells something to eat with the wine without running a restaurant. Boards, hampers, bread and cheese, or a table you may bring your own lunch to.",
    see_also: ["logistics-restaurant"],
  },
  {
    slug: "logistics-dog-friendly",
    vocabulary: "logistics",
    value: "dog_friendly",
    term: "Dog friendly",
    short: "Dogs are welcome, usually outdoors and on a lead.",
    definition:
      "The producer states that dogs are allowed. Conditions vary and the producer's own wording is worth reading before you drive.",
    excludes: "It is not a promise that dogs are allowed inside the tasting room.",
  },
  {
    slug: "logistics-family-friendly",
    vocabulary: "logistics",
    value: "family_friendly",
    term: "Family friendly",
    short: "Children are welcome.",
    definition:
      "The producer states that children are welcome on the premises. Cellar doors are licensed premises, so a minimum age may still apply to tasting.",
    see_also: ["logistics-wheelchair-access"],
  },
  {
    slug: "logistics-wheelchair-access",
    vocabulary: "logistics",
    value: "wheelchair_access",
    term: "Wheelchair access",
    short: "The producer states the cellar door is wheelchair accessible.",
    definition:
      "Recorded from the producer's own published statement about their premises.",
    excludes:
      "This directory has not inspected any of these buildings and this flag is not an accessibility audit. Ring ahead if access decides whether the trip is worth making.",
    see_also: ["confidence-tier-published-by-producer"],
  },
  {
    slug: "logistics-group-bookings",
    vocabulary: "logistics",
    value: "group_bookings",
    term: "Group bookings",
    short: "Groups are taken, usually by arrangement.",
    definition:
      "The producer accepts group visits. Minimum and maximum numbers are the producer's to set.",
  },
  {
    slug: "logistics-vineyard-tours",
    vocabulary: "logistics",
    value: "vineyard_tours",
    term: "Vineyard tours",
    short: "You can walk the vineyard or the winery with someone who works there.",
    definition:
      "The producer offers a tour of the vines, the winery or both. Often it is the winemaker doing the walking.",
  },
  {
    slug: "logistics-parking",
    vocabulary: "logistics",
    value: "parking",
    term: "Parking",
    short: "There is parking on site.",
    definition: "The producer has parking at the cellar door.",
  },

  /* ═══ §1.8 VESSEL_KEYS ══════════════════════════════════════════════════ */
  {
    slug: "vessel-stainless",
    vocabulary: "vessel",
    value: "stainless",
    term: "Stainless steel",
    short: "Temperature-controlled steel tanks. Inert, so nothing is added by the vessel.",
    definition:
      "The default vessel in modern winemaking. Steel is inert and airtight, holds temperature precisely and contributes nothing of its own. Almost every winery has some.",
  },
  {
    slug: "vessel-oak-barrique",
    vocabulary: "vessel",
    value: "oak_barrique",
    term: "Oak barrique",
    short: "A small oak barrel, around 225 litres.",
    definition:
      "The standard small barrel. At this size a large share of the wine touches wood, so a new barrique influences a wine considerably and an old one much less. French and American oak are both used in Australia.",
    excludes:
      "This directory records that a producer uses barriques. It does not record how new they are or infer anything about the wine from it.",
    aliases: ["Barrique", "Hogshead", "Puncheon"],
    see_also: ["vessel-oak-foudre"],
  },
  {
    slug: "vessel-oak-foudre",
    vocabulary: "vessel",
    value: "oak_foudre",
    term: "Oak foudre",
    short: "A large oak cask, often several thousand litres.",
    definition:
      "A big upright or horizontal cask. Because the volume is large relative to the surface of wood, a foudre lets a wine breathe through oak without taking on much oak character. Australian growers of Italian and Rhône varieties have taken to them.",
    aliases: ["Foudre", "Botte", "Large-format oak"],
    see_also: ["vessel-oak-barrique"],
  },
  {
    slug: "vessel-concrete",
    vocabulary: "vessel",
    value: "concrete",
    term: "Concrete",
    short: "Concrete tanks or eggs. Porous, thermally stable, adds no wood character.",
    definition:
      "Concrete holds a steady temperature and lets a small amount of air through the wall. Eggs are shaped so the wine moves on its own without stirring. Older Australian wineries often have square concrete tanks that predate stainless steel and are back in use.",
    aliases: ["Concrete egg", "Cement tank"],
  },
  {
    slug: "vessel-amphora",
    vocabulary: "vessel",
    value: "amphora",
    term: "Amphora",
    short: "A clay vessel, sometimes buried, in the Georgian and Italian manner.",
    definition:
      "Unglazed clay, often tapering to a point and sometimes set into the ground. Clay breathes more than concrete and adds no flavour of its own. Georgian qvevri and Italian tinaja are the usual references.",
    aliases: ["Qvevri", "Tinaja", "Clay pot"],
    see_also: ["vessel-ceramic", "wine-style-skin-contact"],
  },
  {
    slug: "vessel-ceramic",
    vocabulary: "vessel",
    value: "ceramic",
    term: "Ceramic",
    short: "A glazed or fired ceramic jar.",
    definition:
      "Fired ceramic, usually glazed, so it behaves closer to glass than to raw clay. Recorded separately from amphora because the porosity is the point of difference.",
    see_also: ["vessel-amphora"],
  },
  {
    slug: "vessel-glass",
    vocabulary: "vessel",
    value: "glass",
    term: "Glass",
    short: "Glass demijohns and carboys. Entirely inert.",
    definition:
      "Glass adds nothing and lets nothing through. Used for small parcels, for trials and for holding a wine unchanged.",
    excludes: "This is the fermentation and maturation vessel, not the bottle the wine is sold in.",
  },

  /* ═══ §1.9 WINE_STYLE_KEYS ══════════════════════════════════════════════ */
  {
    slug: "wine-style-red",
    vocabulary: "wine-style",
    value: "red",
    term: "Red",
    short: "Wine fermented on dark grape skins.",
    definition:
      "Colour and tannin come from time on the skins during fermentation. The single largest category in Australian wine.",
  },
  {
    slug: "wine-style-white",
    vocabulary: "wine-style",
    value: "white",
    term: "White",
    short: "Wine pressed off the skins before fermentation.",
    definition:
      "Juice is separated from the skins early, so the wine takes little colour or tannin from them. White wine can be made from dark-skinned grapes, and in sparkling wine it usually is.",
    see_also: ["wine-style-skin-contact"],
  },
  {
    slug: "wine-style-rose",
    vocabulary: "wine-style",
    value: "rose",
    term: "Rosé",
    short: "Dark grapes given brief skin contact, then finished as a white.",
    definition:
      "A few hours on the skins gives colour without much tannin, and the wine is then handled like a white. Some are made by drawing juice off a red ferment early.",
    excludes: "Rosé is not a blend of red and white wine. That method is not used for still rosé in Australia.",
    aliases: ["Rose"],
  },
  {
    slug: "wine-style-sparkling",
    vocabulary: "wine-style",
    value: "sparkling",
    term: "Sparkling",
    short: "Wine carrying dissolved carbon dioxide from a second fermentation.",
    definition:
      "A second fermentation traps carbon dioxide in the wine. It can happen in the bottle, in a tank, or in the same bottle the wine is sold in with the sediment left behind. Tasmania, the Adelaide Hills and Macedon are the cool sites Australian sparkling most often comes from.",
    aliases: ["Pét-nat", "Méthode traditionnelle", "Traditional method"],
  },
  {
    slug: "wine-style-skin-contact",
    vocabulary: "wine-style",
    value: "skin_contact",
    term: "Skin contact",
    short: "White grapes fermented on their skins, the way a red is made.",
    definition:
      "Leaving white grapes on their skins draws out colour, tannin and texture, giving a wine that is amber or orange rather than yellow. The method is ancient in Georgia and north-east Italy and has been taken up widely by small Australian producers.",
    excludes: "Skin contact is a white wine made like a red. It is not a rosé and it is not a fault.",
    aliases: ["Orange wine", "Amber wine", "Ramato"],
    see_also: ["vessel-amphora", "wine-style-white"],
  },
  {
    slug: "wine-style-fortified",
    vocabulary: "wine-style",
    value: "fortified",
    term: "Fortified",
    short: "Wine with grape spirit added, which stops fermentation and lifts the alcohol.",
    definition:
      "Spirit is added during or after fermentation. Australia has a long fortified tradition, most of it in Rutherglen and the Barossa, and the Rutherglen Muscat classification is its own graded system.",
    aliases: ["Muscat", "Topaque", "Apera", "Tawny"],
    see_also: ["variety-muscat-blanc", "wine-style-dessert"],
  },
  {
    slug: "wine-style-dessert",
    vocabulary: "wine-style",
    value: "dessert",
    term: "Dessert",
    short: "Sweet wine made from concentrated fruit, with no spirit added.",
    definition:
      "Sugar is concentrated in the grape before or during fermentation, by botrytis, by drying the fruit, by freezing it or by picking late. Riverina botrytis Semillon is Australia's best-known example.",
    excludes: "A dessert wine is not fortified. If spirit was added, the style is fortified.",
    aliases: ["Botrytis", "Late harvest", "Sticky"],
    see_also: ["wine-style-fortified", "variety-semillon"],
  },

  /* ═══ §1.10 VARIETY_KEYS ════════════════════════════════════════════════
     The seed set. Closed and curated, because it drives /variety/[grape]/ and a
     typo would mint a dead page. Every variety here is grown commercially in
     Australia. Extending the list is a schema change (CLAUDE.md rule 7).
     Entries say what the grape is and where it grows. They do not say what it
     tastes like.
     ═══════════════════════════════════════════════════════════════════════ */

  /* ── Red ─────────────────────────────────────────────────────────────── */
  {
    slug: "variety-shiraz",
    vocabulary: "variety",
    value: "shiraz",
    term: "Shiraz",
    short: "Australia's most planted grape. The same variety as Syrah.",
    definition:
      "Shiraz has been in Australia since the 1830s and is planted in every wine-growing state. The Barossa, McLaren Vale and the Hunter each have their own long history with it. Some producers label cooler-climate wines Syrah to signal a different intent; the grape is identical.",
    aliases: ["Syrah"],
    see_also: ["variety-grenache", "variety-mataro"],
  },
  {
    slug: "variety-cabernet-sauvignon",
    vocabulary: "variety",
    value: "cabernet-sauvignon",
    term: "Cabernet Sauvignon",
    short: "A late-ripening red variety, most closely associated in Australia with Coonawarra and Margaret River.",
    definition:
      "A cross of Cabernet Franc and Sauvignon Blanc. It ripens late and needs a long season, which is why the Australian regions best known for it are the cooler and more maritime ones.",
    aliases: ["Cabernet"],
    see_also: ["variety-cabernet-franc", "variety-merlot"],
  },
  {
    slug: "variety-merlot",
    vocabulary: "variety",
    value: "merlot",
    term: "Merlot",
    short: "An early-ripening Bordeaux red, grown widely and often blended.",
    definition:
      "Ripens earlier than Cabernet Sauvignon and is frequently blended with it. Planted across most Australian regions.",
    see_also: ["variety-cabernet-sauvignon"],
  },
  {
    slug: "variety-grenache",
    vocabulary: "variety",
    value: "grenache",
    term: "Grenache",
    short: "A drought-tolerant red with very old vines in McLaren Vale and the Barossa.",
    definition:
      "Grenache handles heat and dry seasons well and was widely planted in South Australia before the shift to Shiraz and Cabernet. Some of the oldest surviving plantings in the world are in McLaren Vale and the Barossa. It is grown as a single variety and blended with Shiraz and Mataro.",
    aliases: ["Garnacha", "Grenache Noir"],
    see_also: ["variety-mataro", "variety-shiraz"],
  },
  {
    slug: "variety-mataro",
    vocabulary: "variety",
    value: "mataro",
    term: "Mataro",
    short: "The Australian name for Mourvèdre, the third grape of the GSM blend.",
    definition:
      "Australia has called this grape Mataro since the nineteenth century, and both names are in current use on labels. Old plantings survive in the Barossa and McLaren Vale.",
    aliases: ["Mourvèdre", "Mourvedre", "Monastrell"],
    see_also: ["variety-grenache", "variety-shiraz"],
  },
  {
    slug: "variety-pinot-noir",
    vocabulary: "variety",
    value: "pinot-noir",
    term: "Pinot Noir",
    short: "A cool-climate red. In Australia that means Tasmania, the Yarra, Mornington and the Adelaide Hills.",
    definition:
      "Thin-skinned, early-budding and sensitive to site, which is why it is grown in Australia's coolest places and why single-vineyard bottlings are common. It is also a principal grape in traditional-method sparkling wine.",
    aliases: ["Pinot"],
    see_also: ["variety-chardonnay", "variety-pinot-meunier", "wine-style-sparkling"],
  },
  {
    slug: "variety-cabernet-franc",
    vocabulary: "variety",
    value: "cabernet-franc",
    term: "Cabernet Franc",
    short: "A parent of Cabernet Sauvignon, grown in small quantities and increasingly bottled alone.",
    definition:
      "Long used in Australia as a blending component in Bordeaux-style reds. A growing number of small producers bottle it as a single variety.",
    see_also: ["variety-cabernet-sauvignon", "variety-merlot"],
  },
  {
    slug: "variety-malbec",
    vocabulary: "variety",
    value: "malbec",
    term: "Malbec",
    short: "A Bordeaux red with a long history in Clare and Langhorne Creek.",
    definition:
      "Planted in Australia well before its Argentine fame, particularly in the Clare Valley and Langhorne Creek. Used both alone and in Cabernet blends.",
    aliases: ["Côt"],
  },
  {
    slug: "variety-petit-verdot",
    vocabulary: "variety",
    value: "petit-verdot",
    term: "Petit Verdot",
    short: "A very late-ripening Bordeaux red that suits Australia's warmer regions.",
    definition:
      "Struggles to ripen in Bordeaux and has no such trouble in the Riverina, the Riverland or Margaret River. Grown both for blending and as a single variety.",
  },
  {
    slug: "variety-sangiovese",
    vocabulary: "variety",
    value: "sangiovese",
    term: "Sangiovese",
    short: "The red grape of Tuscany, grown across central Victoria and the Adelaide Hills.",
    definition:
      "One of the earliest Italian varieties to be taken seriously in Australia. Plantings are spread across Heathcote, the King Valley, McLaren Vale and the Adelaide Hills.",
    see_also: ["variety-nebbiolo", "variety-barbera"],
  },
  {
    slug: "variety-nebbiolo",
    vocabulary: "variety",
    value: "nebbiolo",
    term: "Nebbiolo",
    short: "The red grape of Piedmont. Difficult, late-ripening and grown by a small and committed group.",
    definition:
      "Nebbiolo ripens very late and is fussy about site. The Australian plantings that work are mostly in the King Valley, the Adelaide Hills and Canberra District, and the producers who grow it tend to be small.",
    see_also: ["variety-barbera", "variety-dolcetto"],
  },
  {
    slug: "variety-barbera",
    vocabulary: "variety",
    value: "barbera",
    term: "Barbera",
    short: "A Piedmontese red that holds acidity in warm sites.",
    definition:
      "Keeps its acidity as it ripens, which makes it useful in warmer Australian regions. Grown in the King Valley, McLaren Vale and Mudgee among others.",
    see_also: ["variety-nebbiolo", "variety-dolcetto"],
  },
  {
    slug: "variety-tempranillo",
    vocabulary: "variety",
    value: "tempranillo",
    term: "Tempranillo",
    short: "The principal red of Rioja, now planted in most Australian regions.",
    definition:
      "One of the fastest-growing alternative varieties in Australia over the past two decades, with plantings from the Granite Belt to the Adelaide Hills.",
    aliases: ["Tinta Roriz", "Aragonez"],
    see_also: ["variety-graciano", "variety-touriga-nacional"],
  },
  {
    slug: "variety-touriga-nacional",
    vocabulary: "variety",
    value: "touriga-nacional",
    term: "Touriga Nacional",
    short: "A Portuguese red used in Australia for both table and fortified wine.",
    definition:
      "Came to Australia for fortified production and is now bottled as a dry red as well. Grown in the Riverland, McLaren Vale and the Rutherglen area.",
    aliases: ["Touriga"],
    see_also: ["wine-style-fortified"],
  },
  {
    slug: "variety-montepulciano",
    vocabulary: "variety",
    value: "montepulciano",
    term: "Montepulciano",
    short: "A central Italian red variety, not the Tuscan town of the same name.",
    definition:
      "Grown in the Riverland, McLaren Vale and the Adelaide Hills. The variety is from Abruzzo.",
    excludes:
      "Vino Nobile di Montepulciano is a Tuscan wine made from Sangiovese and has nothing to do with this grape. The shared name is a long-standing confusion.",
    see_also: ["variety-sangiovese", "variety-aglianico"],
  },
  {
    slug: "variety-aglianico",
    vocabulary: "variety",
    value: "aglianico",
    term: "Aglianico",
    short: "A late-ripening southern Italian red, grown in small quantities in Australia.",
    definition:
      "From Campania and Basilicata. Australian plantings are small and are concentrated in warmer regions including McLaren Vale and the Riverland.",
    see_also: ["variety-nero-davola", "variety-negroamaro"],
  },
  {
    slug: "variety-nero-davola",
    vocabulary: "variety",
    value: "nero-davola",
    term: "Nero d'Avola",
    short: "The main red grape of Sicily, suited to hot and dry Australian sites.",
    definition:
      "Handles heat and drought, which is why it has been planted in the Riverland, McLaren Vale and the Riverina.",
    aliases: ["Nero d Avola"],
    see_also: ["variety-aglianico", "variety-negroamaro"],
  },
  {
    slug: "variety-negroamaro",
    vocabulary: "variety",
    value: "negroamaro",
    term: "Negroamaro",
    short: "A red grape from Puglia, planted in Australia's warmer regions.",
    definition: "Grown in small quantities in the Riverland, McLaren Vale and the Riverina.",
    see_also: ["variety-nero-davola"],
  },
  {
    slug: "variety-lagrein",
    vocabulary: "variety",
    value: "lagrein",
    term: "Lagrein",
    short: "A deeply coloured red from Alto Adige in northern Italy.",
    definition: "A small Australian planting, mostly in the Adelaide Hills, McLaren Vale and central Victoria.",
    see_also: ["variety-dolcetto"],
  },
  {
    slug: "variety-dolcetto",
    vocabulary: "variety",
    value: "dolcetto",
    term: "Dolcetto",
    short: "An early-ripening Piedmontese red.",
    definition:
      "Ripens well ahead of Nebbiolo, which is why Piedmont grows both. Australian plantings are small and long-standing, with some of the oldest in the Adelaide Hills.",
    see_also: ["variety-nebbiolo", "variety-barbera"],
  },
  {
    slug: "variety-gamay",
    vocabulary: "variety",
    value: "gamay",
    term: "Gamay",
    short: "The red grape of Beaujolais, grown in Australia's cooler regions.",
    definition:
      "Plantings are small and are found in the Yarra Valley, the Adelaide Hills, Mornington Peninsula and Tasmania. Often made with whole bunches in the ferment.",
    aliases: ["Gamay Noir"],
    see_also: ["variety-pinot-noir"],
  },
  {
    slug: "variety-zinfandel",
    vocabulary: "variety",
    value: "zinfandel",
    term: "Zinfandel",
    short: "The same variety as Primitivo, grown in warm Australian regions.",
    definition:
      "Known as Primitivo in Puglia and as Zinfandel in California, and both names appear on Australian labels. Grown in McLaren Vale, the Riverland and Margaret River.",
    aliases: ["Primitivo"],
  },
  {
    slug: "variety-durif",
    vocabulary: "variety",
    value: "durif",
    term: "Durif",
    short: "A dark, thick-skinned red closely tied to Rutherglen.",
    definition:
      "A cross of Syrah and Peloursin, known as Petite Sirah in California. Rutherglen has grown it since the nineteenth century and remains its Australian home.",
    aliases: ["Petite Sirah"],
  },
  {
    slug: "variety-cinsault",
    vocabulary: "variety",
    value: "cinsault",
    term: "Cinsault",
    short: "A southern French red, present in Australia as old bush vines under the name Blue Imperial.",
    definition:
      "Long grown in Australia under local names including Blue Imperial and Oeillade. Old plantings survive in Great Western and the Barossa.",
    aliases: ["Blue Imperial", "Oeillade", "Cinsaut"],
  },
  {
    slug: "variety-carignan",
    vocabulary: "variety",
    value: "carignan",
    term: "Carignan",
    short: "A southern French red grown in small Australian quantities.",
    definition: "Plantings are small and are mostly in McLaren Vale and the Barossa.",
    aliases: ["Carignane", "Mazuelo"],
  },
  {
    slug: "variety-tannat",
    vocabulary: "variety",
    value: "tannat",
    term: "Tannat",
    short: "A tannic red from south-west France and Uruguay.",
    definition: "A small Australian planting, found in Gippsland, the Granite Belt and the Riverland.",
  },
  {
    slug: "variety-saperavi",
    vocabulary: "variety",
    value: "saperavi",
    term: "Saperavi",
    short: "A Georgian red whose flesh is coloured as well as its skin.",
    definition:
      "One of very few varieties with red pulp. Australian plantings are small and are concentrated in the Hunter, Mudgee and the Adelaide Hills.",
    see_also: ["vessel-amphora"],
  },
  {
    slug: "variety-pinot-meunier",
    vocabulary: "variety",
    value: "pinot-meunier",
    term: "Pinot Meunier",
    short: "A relative of Pinot Noir, used in sparkling wine and bottled alone in the Grampians.",
    definition:
      "One of the three principal Champagne varieties. Great Western in Victoria has some of the oldest Meunier vines anywhere and bottles it as a still red.",
    aliases: ["Meunier"],
    see_also: ["variety-pinot-noir", "wine-style-sparkling"],
  },
  {
    slug: "variety-graciano",
    vocabulary: "variety",
    value: "graciano",
    term: "Graciano",
    short: "A Rioja blending red, grown in small quantities in Australia.",
    definition: "Small plantings, mostly in the Riverland, McLaren Vale and the Barossa.",
    see_also: ["variety-tempranillo"],
  },
  {
    slug: "variety-sagrantino",
    vocabulary: "variety",
    value: "sagrantino",
    term: "Sagrantino",
    short: "A very tannic red from Umbria.",
    definition: "A small Australian planting, largely in McLaren Vale and central Victoria.",
  },
  {
    slug: "variety-blaufrankisch",
    vocabulary: "variety",
    value: "blaufrankisch",
    term: "Blaufränkisch",
    short: "An Austrian red, grown by a handful of cool-climate Australian producers.",
    definition: "Plantings are very small and are found in the Adelaide Hills, Tasmania and the Macedon Ranges.",
    aliases: ["Blaufrankisch", "Lemberger", "Kékfrankos"],
  },

  /* ── White ───────────────────────────────────────────────────────────── */
  {
    slug: "variety-chardonnay",
    vocabulary: "variety",
    value: "chardonnay",
    term: "Chardonnay",
    short: "Australia's most planted white variety, grown in every wine region.",
    definition:
      "Handled in many different ways, from unoaked and early-picked to barrel-fermented and matured on lees. Also a principal grape in traditional-method sparkling wine.",
    see_also: ["variety-pinot-noir", "wine-style-sparkling"],
  },
  {
    slug: "variety-sauvignon-blanc",
    vocabulary: "variety",
    value: "sauvignon-blanc",
    term: "Sauvignon Blanc",
    short: "A widely planted white, often blended with Semillon in Margaret River.",
    definition:
      "Grown across the cooler Australian regions and made both as a single variety and in the Margaret River blend with Semillon.",
    aliases: ["Sauvignon"],
    see_also: ["variety-semillon"],
  },
  {
    slug: "variety-semillon",
    vocabulary: "variety",
    value: "semillon",
    term: "Semillon",
    short: "The Hunter Valley's signature white, and the base of Riverina botrytis wine.",
    definition:
      "Hunter Semillon is picked early and bottled without oak, and it is one of very few Australian wine styles with no direct model overseas. Semillon is also blended with Sauvignon Blanc in Margaret River and made into botrytis dessert wine in the Riverina.",
    aliases: ["Sémillon"],
    see_also: ["variety-sauvignon-blanc", "wine-style-dessert"],
  },
  {
    slug: "variety-riesling",
    vocabulary: "variety",
    value: "riesling",
    term: "Riesling",
    short: "Dry Australian Riesling is centred on the Clare and Eden valleys.",
    definition:
      "Grown in Australia since the nineteenth century. Clare and Eden are its established homes; Great Southern, Tasmania and the Canberra District also grow it. Most Australian Riesling is bottled dry.",
    see_also: ["variety-gewurztraminer"],
  },
  {
    slug: "variety-pinot-gris",
    vocabulary: "variety",
    value: "pinot-gris",
    term: "Pinot Gris",
    short: "The same grape as Pinot Grigio. Both names are used in Australia.",
    definition:
      "A colour mutation of Pinot Noir with pinkish skins. Australian producers label it Gris or Grigio to signal the style they are after, and there is no rule governing which. It is grown widely in cooler regions, particularly Mornington Peninsula and the Adelaide Hills.",
    excludes: "Pinot Gris and Pinot Grigio are one variety. The two names do not describe two grapes.",
    aliases: ["Pinot Grigio", "Grauburgunder"],
    see_also: ["variety-pinot-noir", "wine-style-skin-contact"],
  },
  {
    slug: "variety-viognier",
    vocabulary: "variety",
    value: "viognier",
    term: "Viognier",
    short: "A northern Rhône white, sometimes co-fermented with Shiraz.",
    definition:
      "Grown as a single variety and also added in small proportion to Shiraz ferments, a practice borrowed from Côte-Rôtie and taken up in the Canberra District and elsewhere.",
    see_also: ["variety-marsanne", "variety-roussanne", "variety-shiraz"],
  },
  {
    slug: "variety-marsanne",
    vocabulary: "variety",
    value: "marsanne",
    term: "Marsanne",
    short: "A Rhône white with the world's oldest surviving plantings in Victoria.",
    definition:
      "The Goulburn Valley holds vines planted in the nineteenth century, which are understood to be the oldest Marsanne anywhere. Also grown in the Adelaide Hills and Great Western.",
    see_also: ["variety-roussanne", "variety-viognier"],
  },
  {
    slug: "variety-roussanne",
    vocabulary: "variety",
    value: "roussanne",
    term: "Roussanne",
    short: "A Rhône white, usually blended with Marsanne.",
    definition: "Small Australian plantings, in the Adelaide Hills, central Victoria and McLaren Vale.",
    see_also: ["variety-marsanne", "variety-viognier"],
  },
  {
    slug: "variety-verdelho",
    vocabulary: "variety",
    value: "verdelho",
    term: "Verdelho",
    short: "A Portuguese white with a long history in the Hunter and the Swan.",
    definition:
      "Came to Australia for fortified wine and is now made dry. The Hunter Valley and the Swan Valley are its established regions.",
  },
  {
    slug: "variety-vermentino",
    vocabulary: "variety",
    value: "vermentino",
    term: "Vermentino",
    short: "A Mediterranean white that handles heat and holds acidity.",
    definition:
      "Grown in Sardinia, Liguria and Corsica, and increasingly in the Riverland, McLaren Vale and the Riverina.",
    aliases: ["Rolle", "Pigato"],
    see_also: ["variety-fiano"],
  },
  {
    slug: "variety-fiano",
    vocabulary: "variety",
    value: "fiano",
    term: "Fiano",
    short: "A southern Italian white, one of the more successful alternative varieties in Australia.",
    definition:
      "From Campania. Planted through McLaren Vale, the Adelaide Hills and the Riverland since the early 2000s.",
    see_also: ["variety-vermentino", "variety-greco-di-tufo"],
  },
  {
    slug: "variety-arneis",
    vocabulary: "variety",
    value: "arneis",
    term: "Arneis",
    short: "A white grape from Piedmont.",
    definition: "Small Australian plantings, mostly in the King Valley, the Adelaide Hills and Gippsland.",
    see_also: ["variety-nebbiolo"],
  },
  {
    slug: "variety-gruner-veltliner",
    vocabulary: "variety",
    value: "gruner-veltliner",
    term: "Grüner Veltliner",
    short: "Austria's principal white, grown by a small group of Australian producers.",
    definition:
      "Plantings began in Australia in the late 2000s and are found in the Adelaide Hills, Canberra District and Tasmania.",
    aliases: ["Gruner Veltliner", "Grüner"],
  },
  {
    slug: "variety-chenin-blanc",
    vocabulary: "variety",
    value: "chenin-blanc",
    term: "Chenin Blanc",
    short: "A Loire white with old plantings in Western Australia.",
    definition:
      "Long grown in the Swan Valley and Margaret River, where some of the oldest Australian plantings are. Made dry, sparkling and sweet.",
    aliases: ["Steen"],
  },
  {
    slug: "variety-muscadelle",
    vocabulary: "variety",
    value: "muscadelle",
    term: "Muscadelle",
    short: "The grape behind Rutherglen Topaque.",
    definition:
      "A Bordeaux white variety that Australia uses chiefly for fortified wine in Rutherglen, where it was known for many years as Tokay.",
    excludes: "Muscadelle is not a Muscat variety, despite the name.",
    aliases: ["Topaque", "Tokay"],
    see_also: ["wine-style-fortified", "variety-muscat-blanc"],
  },
  {
    slug: "variety-colombard",
    vocabulary: "variety",
    value: "colombard",
    term: "Colombard",
    short: "A high-acid French white grown mainly in Australia's warm inland regions.",
    definition: "Planted in the Riverland, the Riverina and Murray Darling.",
  },
  {
    slug: "variety-trebbiano",
    vocabulary: "variety",
    value: "trebbiano",
    term: "Trebbiano",
    short: "A widely planted Italian white, known in France as Ugni Blanc.",
    definition: "Grown in Australia's inland regions and in small quantities in McLaren Vale and the Adelaide Hills.",
    aliases: ["Ugni Blanc", "Trebbiano Toscano"],
  },
  {
    slug: "variety-garganega",
    vocabulary: "variety",
    value: "garganega",
    term: "Garganega",
    short: "The white grape of Soave.",
    definition: "A very small Australian planting, in the King Valley and the Adelaide Hills.",
  },
  {
    slug: "variety-savagnin",
    vocabulary: "variety",
    value: "savagnin",
    term: "Savagnin",
    short: "A Jura white that arrived in Australia mislabelled as Albariño.",
    definition:
      "Vines imported as Albariño were identified in 2009 as Savagnin, and Australian growers relabelled accordingly. The variety is the one behind the Jura's vin jaune. Plantings are in the Adelaide Hills, McLaren Vale and central Victoria.",
    excludes: "Savagnin is not Sauvignon Blanc and it is not Albariño, which is a separate entry.",
    aliases: ["Traminer", "Savagnin Blanc"],
    see_also: ["variety-albarino", "variety-gewurztraminer"],
  },
  {
    slug: "variety-albarino",
    vocabulary: "variety",
    value: "albarino",
    term: "Albariño",
    short: "A Galician white, planted in Australia after the Savagnin mix-up was corrected.",
    definition:
      "Genuine Albariño material was imported after 2009. Plantings are small and are in Mornington Peninsula, the Adelaide Hills and the Riverland.",
    aliases: ["Albarino", "Alvarinho"],
    see_also: ["variety-savagnin"],
  },
  {
    slug: "variety-gewurztraminer",
    vocabulary: "variety",
    value: "gewurztraminer",
    term: "Gewürztraminer",
    short: "An aromatic pink-skinned white from Alsace.",
    definition:
      "A colour mutation of Savagnin. Australian plantings are in cooler regions including the Adelaide Hills, Tasmania and Great Southern.",
    aliases: ["Gewurztraminer", "Traminer"],
    see_also: ["variety-savagnin"],
  },
  {
    slug: "variety-prosecco",
    vocabulary: "variety",
    value: "prosecco",
    term: "Prosecco",
    short: "The variety also called Glera. In Australia the grape name is used on the label.",
    definition:
      "The King Valley planted it in the 1990s and built a sparkling category on it. In the European Union, Prosecco is a protected place name and the grape must be called Glera; Australian producers continue to use the variety name, and the difference is a live trade dispute rather than a settled matter.",
    aliases: ["Glera"],
    see_also: ["wine-style-sparkling"],
  },
  {
    slug: "variety-muscat-blanc",
    vocabulary: "variety",
    value: "muscat-blanc",
    term: "Muscat à Petits Grains",
    short: "The Muscat behind Rutherglen fortified wine, in its red-berried form.",
    definition:
      "Rutherglen Muscat is made from the Rouge form of this variety, sometimes called Brown Muscat. The same variety in its white form is used for table and sparkling wine. Rutherglen operates a graded classification for its Muscat that runs from Rutherglen through Classic and Grand to Rare.",
    aliases: ["Brown Muscat", "Muscat à Petits Grains Rouge", "Frontignac", "Moscato"],
    see_also: ["wine-style-fortified", "variety-muscadelle"],
  },
  {
    slug: "variety-pedro-ximenez",
    vocabulary: "variety",
    value: "pedro-ximenez",
    term: "Pedro Ximénez",
    short: "A Spanish white grown in Australia for fortified wine.",
    definition: "Planted in the Riverland and the Barossa, principally for Apera and other fortified styles.",
    aliases: ["Pedro Ximenez", "PX"],
    see_also: ["wine-style-fortified", "variety-palomino"],
  },
  {
    slug: "variety-palomino",
    vocabulary: "variety",
    value: "palomino",
    term: "Palomino",
    short: "The sherry grape of Jerez, grown in Australia for Apera.",
    definition:
      "Small plantings remain in the Barossa, the Riverland and the Hunter. Apera is the Australian name for the fortified style once sold as sherry.",
    aliases: ["Palomino Fino", "Listán"],
    see_also: ["wine-style-fortified", "variety-pedro-ximenez"],
  },
  {
    slug: "variety-assyrtiko",
    vocabulary: "variety",
    value: "assyrtiko",
    term: "Assyrtiko",
    short: "A Greek white from Santorini, newly planted in Australia.",
    definition:
      "Holds acidity in hot, dry conditions. Australian plantings are recent and small, in McLaren Vale, the Riverland and the Adelaide Hills.",
  },
  {
    slug: "variety-greco-di-tufo",
    vocabulary: "variety",
    value: "greco-di-tufo",
    term: "Greco",
    short: "A southern Italian white from Campania.",
    definition: "A small Australian planting, mostly in McLaren Vale and the Riverland.",
    aliases: ["Greco di Tufo"],
    see_also: ["variety-fiano"],
  },

  /* ═══ §1.11 CONFIDENCE_TIERS ════════════════════════════════════════════ */
  {
    slug: "confidence-tier-unverified",
    vocabulary: "confidence-tier",
    value: "unverified",
    term: "Unverified",
    short: "Recorded without a source behind it.",
    definition:
      "The weakest tier. A field at this tier has no citation, and this directory does not publish verifiable fields at this tier.",
    see_also: ["confidence-tier-published-by-producer"],
  },
  {
    slug: "confidence-tier-published-by-producer",
    vocabulary: "confidence-tier",
    value: "published_by_producer",
    term: "Published by producer",
    short: "Taken from the producer's own published material, with the page cited.",
    definition:
      "The producer states it on their own website. This is the tier almost every fact in this directory carries, and the source page is recorded alongside it so a reader can check.",
    excludes:
      "It does not mean anyone has confirmed the statement is true. It means the producer published it and this directory recorded where.",
    see_also: ["confidence-tier-operator-confirmed", "ownership-evidence-producer-statement"],
  },
  {
    slug: "confidence-tier-observed-on-visit",
    vocabulary: "confidence-tier",
    value: "observed_on_visit",
    term: "Observed on visit",
    short: "Seen in person by a named person who went there.",
    definition:
      "This tier exists for completeness and is never set by the pipeline. Nobody working on this directory has visited these cellar doors or tasted these wines, and nothing here is written as though they had. Only a reviewer who genuinely visited may set it.",
    see_also: ["confidence-tier-published-by-producer"],
  },
  {
    slug: "confidence-tier-operator-confirmed",
    vocabulary: "confidence-tier",
    value: "operator_confirmed",
    term: "Operator confirmed",
    short: "The producer has checked the entry and confirmed it.",
    definition: "The strongest tier. The business itself has reviewed the record and confirmed the detail.",
    see_also: ["confidence-tier-published-by-producer"],
  },

  /* ═══ §1.13 OWNERSHIP_EVIDENCE_METHODS ══════════════════════════════════ */
  {
    slug: "ownership-evidence-registry",
    vocabulary: "ownership-evidence",
    value: "registry",
    term: "Registry lookup",
    short: "An ASIC or ABN lookup identifying the operating entity.",
    definition:
      "A search of the public company or business register showing which entity operates the business and whether a corporate parent stands behind it. Where the three kinds of evidence disagree, the registry is the one this directory follows.",
    see_also: ["ownership-evidence-producer-statement", "ownership-evidence-trade-source"],
  },
  {
    slug: "ownership-evidence-producer-statement",
    vocabulary: "ownership-evidence",
    value: "producer_statement",
    term: "Producer statement",
    short: "The producer's own published statement of who owns the business.",
    definition:
      "An about page, an our-story page or similar that names who owns the business. It has to name them. A page that simply never mentions a parent company is not evidence that there is none.",
    excludes:
      "Silence is not evidence of absence. This is the single most important thing to understand about how this directory decides independence.",
    see_also: ["ownership-evidence-registry"],
  },
  {
    slug: "ownership-evidence-trade-source",
    vocabulary: "ownership-evidence",
    value: "trade_source",
    term: "Trade source",
    short: "A named independent source stating who owns the business.",
    definition:
      "Wine media, a regional association register, or an importer or distributor listing that states ownership. It must be named and dated, and it must state ownership rather than imply it.",
    see_also: ["ownership-evidence-registry", "ownership-evidence-producer-statement"],
  },

  /* ═══ §1.14 STATES ══════════════════════════════════════════════════════ */
  {
    slug: "state-vic",
    vocabulary: "state",
    value: "VIC",
    term: "Victoria",
    short: "Six wine zones, from Rutherglen in the north-east to Henty on the far west coast.",
    definition:
      "Victoria has more separate wine regions than any other state. Port Phillip alone holds the Yarra Valley, Mornington Peninsula, Geelong, Macedon Ranges and Sunbury, all within reach of Melbourne.",
  },
  {
    slug: "state-nsw",
    vocabulary: "state",
    value: "NSW",
    term: "New South Wales",
    short: "The oldest wine state, and the home of the Hunter.",
    definition:
      "Australian winemaking began here. The Hunter is its best-known region; Orange, Mudgee, Canberra District and Tumbarumba are the cooler and higher ones, and the Riverina is the largest by volume.",
  },
  {
    slug: "state-qld",
    vocabulary: "state",
    value: "QLD",
    term: "Queensland",
    short: "Two registered regions, both at altitude.",
    definition:
      "The Granite Belt sits around 800 metres up near the New South Wales border, which is what makes wine growing possible there. South Burnett is the other registered region.",
  },
  {
    slug: "state-sa",
    vocabulary: "state",
    value: "SA",
    term: "South Australia",
    short: "Around half of Australia's crush, and the country's oldest surviving vines.",
    definition:
      "The Barossa, McLaren Vale, Clare, Coonawarra and the Adelaide Hills are all here, along with the Riverland. Because phylloxera never reached the state, some vineyards hold vines planted in the nineteenth century.",
  },
  {
    slug: "state-wa",
    vocabulary: "state",
    value: "WA",
    term: "Western Australia",
    short: "A small share of the national crush and a large share of its bottled wine.",
    definition:
      "Margaret River and Great Southern dominate, with the Swan Valley the oldest region and Perth Hills, Geographe, Pemberton and Manjimup alongside them.",
  },
  {
    slug: "state-tas",
    vocabulary: "state",
    value: "TAS",
    term: "Tasmania",
    short: "One state-wide GI, no registered regions beneath it.",
    definition:
      "Every Tasmanian wine is labelled Tasmania, because the state is registered as a single Geographical Indication with nothing beneath it. Districts such as the Tamar Valley, Pipers River and the Coal River Valley are in everyday use and are not on the register.",
    see_also: ["state-nt"],
  },
  {
    slug: "state-nt",
    vocabulary: "state",
    value: "NT",
    term: "Northern Territory",
    short: "No registered wine GI of any kind.",
    definition:
      "The Territory has no Geographical Indication. It appears in this directory so that a Territory producer has somewhere to sit, and the entry is an administrative one rather than a wine region.",
    excludes: "Northern Territory is not a Geographical Indication and is never presented as one.",
    see_also: ["state-tas"],
  },
  {
    slug: "state-act",
    vocabulary: "state",
    value: "ACT",
    term: "Australian Capital Territory",
    short: "Reached by one GI, Canberra District, whose boundary crosses the border.",
    definition:
      "The Canberra District GI sits in the Southern New South Wales zone and its registered boundary lies partly in New South Wales and partly in the Australian Capital Territory. Most of the district's vineyards are on the New South Wales side, around Murrumbateman.",
  },
];

/* ─────────────────────────────────────────────────────────────────────────────
   Derived lookups and helpers
   ───────────────────────────────────────────────────────────────────────── */

export const GLOSSARY_BY_SLUG: ReadonlyMap<string, GlossaryEntry> = new Map(
  GLOSSARY.map((e) => [e.slug, e]),
);

/**
 * Keyed `<vocabulary>SEPARATOR<value>` so a lookup by enum member cannot
 * collide across vocabularies.
 *
 * The separator is U+0000, written as an ESCAPE and never as a literal NUL
 * byte. A literal one here made the whole file `data` rather than text, and
 * grep skips a binary file silently: no error, no match, just nothing. That
 * matters because `/validate` check 6 greps sources, the `schema-guardian`
 * agent greps this file specifically, and check 11 joins it against the
 * config.ts tuples. Keep it an escape.
 */
const BY_VALUE: ReadonlyMap<string, GlossaryEntry> = new Map(
  GLOSSARY.map((e) => [`${e.vocabulary}\u0000${e.value}`, e]),
);

/** The entry for a raw enum member. This is the join `/validate` check 11 walks. */
export function glossaryFor(
  vocabulary: VocabularyId,
  value: string,
): GlossaryEntry | undefined {
  return BY_VALUE.get(`${vocabulary}\u0000${value}`);
}

/** Every entry in one vocabulary, in authored order. */
export function glossaryVocabulary(vocabulary: VocabularyId): readonly GlossaryEntry[] {
  return GLOSSARY.filter((e) => e.vocabulary === vocabulary);
}

/** The seed variety slugs, in authored order. Gate 1 mirrors this as `VARIETY_KEYS`. */
export const VARIETY_SLUGS: readonly string[] = GLOSSARY.filter(
  (e) => e.vocabulary === "variety",
).map((e) => e.value);

/**
 * Section headings for `/glossary/`, in the order the index presents them
 * (Gate 6). Sentence-case plain words: a reader browsing the glossary is not
 * looking up the schema, and "SCHEMA.md §1.9 WINE_STYLE_KEYS" is not a heading.
 *
 * The order is editorial rather than the tuple order in config.ts. What a
 * producer IS comes first, then what they make, then how they make it, then the
 * apparatus this directory uses to say how sure it is about any of it.
 */
export const VOCABULARY_LABELS: Record<VocabularyId, string> = {
  category: "Kinds of producer",
  "wine-style": "Styles of wine",
  variety: "Grape varieties",
  practice: "Practices in the cellar",
  vessel: "Vessels",
  "fruit-source": "Where the fruit comes from",
  "production-band": "How much they make",
  certification: "Organic and biodynamic status",
  "cellar-door": "Cellar door",
  logistics: "Visiting",
  state: "States and territories",
  "confidence-tier": "How a fact was established",
  "ownership-evidence": "How ownership was established",
};

/** The index's display order. Every covered vocabulary appears exactly once. */
export const VOCABULARY_ORDER: readonly VocabularyId[] = Object.keys(
  VOCABULARY_LABELS,
) as readonly VocabularyId[];

/**
 * Every vocabulary that must have full glossary coverage.
 * SCHEMA.md §1.12 `VERIFIABLE_FIELDS` is deliberately absent: it is a list of
 * field names rather than a vocabulary of values, and DESIGN.md §6 records it as
 * not rendered as a set. Check 11 must skip it or it will report false orphans.
 */
export const COVERED_VOCABULARIES: readonly VocabularyId[] = [
  "category",
  "cellar-door",
  "certification",
  "fruit-source",
  "production-band",
  "practice",
  "logistics",
  "vessel",
  "wine-style",
  "variety",
  "confidence-tier",
  "ownership-evidence",
  "state",
];
