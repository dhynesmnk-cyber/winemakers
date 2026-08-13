# CONSTANTS-REQUIRED — Wave 2 → Gate 1 handoff

Wave 2 delivered four standalone data and asset files. **None of them creates or
edits `site/src/config.ts` or `admin/config.py`** — Gate 1 owns that hand-mirrored
pair exclusively (HANDOVER, "the one rule that makes parallel work safe").

This document is the written list of what those files need to exist, so the Gate 1
agent has a checklist. It is modelled on DESIGN.md's "Constants required" section
and, like that section, **it does not set any of these values** except where a
value is itself a Wave 2 decision, marked below.

Dated 2026-08-07. Amended the same day at the Wave 2 close, when the six flagged conflicts were resolved and the deny-list was extended across the four coverage regions.

---

## 1. What Wave 2 delivered

| File | What it owns |
|---|---|
| `site/src/data/regions.ts` | The Australian GI register. 28 zones, 71 regions, 42 subregions |
| `site/src/data/glossary.ts` | 121 entries across 13 vocabularies, zero orphans either direction |
| `data/ownership.json` | The ownership deny-list. 22 owners, 164 labels, 103 domains, 1 verified ABN |
| `site/src/icons/paths.ts` | The 44-glyph icon set, plus sizes and the coverage assertion |
| `site/src/styles/tokens.css` | The dual-mode token machinery, declared four times per DESIGN.md §2 |
| `site/src/icons/animals.ts` | The nine fauna keys and served paths. Artwork not yet commissioned |
| `Icons and logos/FAUNA-BRIEF.md` | The illustrator's commissioning brief |
| `.claude/skills/ownership-check/` | The §4 determination procedure |
| `.claude/agents/data-curator.md` | Maintains the three data files |

All four TypeScript files load under `node --experimental-strip-types` with no
build step and no Astro imports. **Keep them that way.** A data file that needs
the build in order to be readable cannot be checked in isolation, and every
invariant check in this wave depends on that.

---

## 2. Constants Gate 1 must create

### 2.1 The vocabulary tuples

All of SCHEMA.md §1, as `as const` tuples in both `config.ts` and `config.py`.
Two of them are settled by Wave 2 and are reproduced here so Gate 1 does not have
to re-derive them.

**`VARIETY_KEYS` — the seed set, authored in Wave 2 per SCHEMA.md §1.10.**
58 slugs. Read the authoritative list straight out of the glossary rather than
retyping it:

```ts
import { VARIETY_SLUGS } from "./data/glossary";
```

`VARIETY_SLUGS` is exported from `glossary.ts` and is derived from the entries
themselves, so the two cannot drift. Mirror it into `config.py` by hand as usual,
and add both to the `schema_surfaces` diff.

Reds (31): `shiraz` `cabernet-sauvignon` `merlot` `grenache` `mataro` `pinot-noir`
`cabernet-franc` `malbec` `petit-verdot` `sangiovese` `nebbiolo` `barbera`
`tempranillo` `touriga-nacional` `montepulciano` `aglianico` `nero-davola`
`negroamaro` `lagrein` `dolcetto` `gamay` `zinfandel` `durif` `cinsault`
`carignan` `tannat` `saperavi` `pinot-meunier` `graciano` `sagrantino`
`blaufrankisch`

Whites (27): `chardonnay` `sauvignon-blanc` `semillon` `riesling` `pinot-gris`
`viognier` `marsanne` `roussanne` `verdelho` `vermentino` `fiano` `arneis`
`gruner-veltliner` `chenin-blanc` `muscadelle` `colombard` `trebbiano`
`garganega` `savagnin` `albarino` `gewurztraminer` `prosecco` `muscat-blanc`
`pedro-ximenez` `palomino` `assyrtiko` `greco-di-tufo`

**`OWNERSHIP_EVIDENCE_METHODS`** — `registry` · `producer_statement` ·
`trade_source`. It is easy to miss: DESIGN.md §6's vocabulary table omitted it
entirely until 2026-08-07. It is glossed like the other words-only vocabularies
and `/validate` check 11 must walk it.

### 2.2 The type assertion regions.ts needs

`regions.ts` declares its own local `StateCode` because it cannot import a file
that does not exist yet. Gate 1 must assert the two agree, at module scope, so a
divergence fails the build:

```ts
import type { StateCode } from "./data/regions";
// fails to compile if regions.ts and config.ts disagree about the state set
const _stateCheck: StateCode = "" as (typeof STATES)[number];
const _stateCheckBack: (typeof STATES)[number] = "" as StateCode;
```

### 2.3 The icon coverage assertions

DESIGN.md §6: *a vocabulary value with no glyph must fail the build, not render
blank.* `paths.ts` exports `assertIconCoverage`; Gate 1 calls it once per
glyph-rendering vocabulary, at module scope, from the tuples:

```ts
import {
  assertIconCoverage, practiceIcon, logisticsIcon, styleIcon, vesselIcon, cellarDoorIcon,
} from "./icons/paths";

assertIconCoverage("PRACTICE_KEYS",   PRACTICE_KEYS,   practiceIcon);
assertIconCoverage("LOGISTICS_KEYS",  LOGISTICS_KEYS,  logisticsIcon);
assertIconCoverage("WINE_STYLE_KEYS", WINE_STYLE_KEYS, styleIcon);
assertIconCoverage("VESSEL_KEYS",     VESSEL_KEYS,     vesselIcon);
// present-only: `none` renders nothing, so it is not passed
assertIconCoverage("CELLAR_DOOR_STATES", ["open", "by_appointment"], cellarDoorIcon);
```

### 2.4 Everything else, per TRD.md §3 and DESIGN.md's own list

Unchanged by Wave 2 and reproduced only as a checklist:

**Identity** — `SITE_NAME` (~~still a placeholder; the brand name is undecided and
must never be guessed~~ — **decided 2026-08-12: `winelister`**, signed off and set
in `config.ts`. The never-guess rule is discharged, not relaxed; it governed every
gate from Wave 2 to Gate 8 and stands as history), `SITE_TAGLINE`, `SITE_URL`,
`SITE_CONTACT_EMAIL` (~~placeholder~~ — **decided 2026-08-13**, supplied by the
user, replacing `hello@example.invalid`. The last placeholder constant in the
build; from this date no constant in `config.ts` is a stand-in for a decision
nobody has taken), `THEME_STORAGE_KEY`.

**Display labels** — one map per vocabulary: `CATEGORY_LABELS`,
`CELLAR_DOOR_LABELS`, `CERTIFICATION_LABELS`, `FRUIT_SOURCE_LABELS`,
`PRODUCTION_BAND_LABELS`, `PRACTICE_LABELS`, `LOGISTICS_LABELS`, `VESSEL_LABELS`,
`WINE_STYLE_LABELS`, `VARIETY_LABELS`, `CONFIDENCE_TIER_LABELS`, `STATE_NAMES`.

> Every one of these has a `term` already written in `glossary.ts`. Derive the
> label maps from `glossaryFor(vocabulary, value).term` rather than typing a
> second copy. A hand-typed second copy of 121 display strings is a drift surface
> nobody will ever check.

**Bounds and ranges** — `AU_LATITUDE_BOUNDS`, `AU_LONGITUDE_BOUNDS`,
`PRODUCTION_BAND_RANGES`, `CONFIDENCE_TIER_RANK`, `VERIFIABLE_FIELDS`.

**Pagination and scale** — `PRODUCERS_PER_PAGE` (24 unless UX.md says otherwise),
`SEARCH_INDEX_INLINE_MAX` (500), `MIN_COMPARISON_PRODUCERS`,
`MIN_AGGREGATION_LINKS` (3).

**Coverage** — `COVERAGE_REGIONS` / `SEED_REGIONS`, the four Gate 8 regions, as
slugs that exist in `regions.ts`:

```ts
["adelaide-hills", "mclaren-vale", "yarra-valley", "mornington-peninsula"]
```

**Paths** (`config.py`) — including `OWNERSHIP_JSON_PATH`, which now points at a
file that exists.

---

## 3. Wave 2 decisions Gate 1 inherits

These were decided in Wave 2 because a file had to be written, and all five were
put to the user and confirmed at the Wave 2 close on 2026-08-07.

1. **Glossary URLs are namespaced.** `/glossary/practice-wild-ferment/`, not
   `/glossary/wild-ferment/`. Raw enum values collide across vocabularies
   (`none` is both a cellar-door and a certification state) and DESIGN.md §6
   already namespaces the icon keys for the same reason. Namespacing all of them
   rather than only the colliding pair means a future enum value cannot silently
   take over a URL. **Gate 6 owns the route and may override this**; if it does,
   `slug` is the only field that changes. **Confirmed 2026-08-07.**

2. **`regions.ts` carries zone-level and state-level GIs as routable regions**,
   tagged with `registered_as`. Gippsland and Tasmania have no registered regions
   beneath them, so a producer there has no narrower GI to use; without this a
   Gippsland producer cannot satisfy `regions` min 1. `registered_as` records the
   registry truth and must never be rendered as a rank. **Confirmed 2026-08-07**,
   including the Northern Territory placeholder; `/validate` check 12 is unchanged.

3. **Unregistered subregions are carried only where they earn it** — named in
   SCHEMA.md §2, or in routine use in a Gate 8 coverage region. SCHEMA.md's own
   examples forced this: Blewitt Springs, Whitlands and Moppity are all in common
   trade use and none is on the register. **Confirmed 2026-08-07.**

4. **`ownership.json` records carry `abns`, `category` and a `verdict`.** All three
   were additions to SCHEMA.md §4.3's example shape. **Signed off 2026-08-07 and
   §4.3 amended to match**, with the reasoning recorded there rather than only here.

5. **The starter colour hexes are unchanged and now verified arithmetically.**
   Every text token clears 4.5:1 against both `--paper` and `--paper-raised` in
   both modes, and the computed figures reproduce DESIGN.md §2's table exactly.
   **The arithmetic is not the test.** DESIGN.md §2 requires someone to look at
   these on a real display before Gate 1 closes and record the result as a dated
   note in `tokens.css`. Light `--ink-faded` clears the floor on `--paper-raised`
   by 0.18 and is the value most likely to move.

---

## 4. Flagged conflicts

CLAUDE.md rule 3: flag the conflict either way, even when precedence resolves it.
A conflict that gets silently resolved is a spec bug that comes back.

**All six were resolved on 2026-08-07.** Four were fixed by amending the spec docs
in place with dated notes, per CLAUDE.md's amendment discipline.

| # | Conflict | Resolved |
|---|---|---|
| 1 | **SCHEMA.md §2** cited `OWNERSHIP_EVIDENCE_METHODS` as §1.14. It is §1.13; §1.14 is `STATES`. | **Fixed in SCHEMA.md**, dated, old cross-reference noted in place |
| 2 | **DESIGN.md §6**'s glyph table claimed "every SCHEMA.md §1 vocabulary is accounted for here" while omitting `OWNERSHIP_EVIDENCE_METHODS`, and labelled `STATES` as §1.13. | **Fixed in DESIGN.md**, dated. The missing row added as words-only, `STATES` renumbered, and `VERIFIABLE_FIELDS` annotated as not glossed so check 11 skips it. Following the old table would have made check 11 report three false orphans |
| 3 | **SCHEMA.md §4.3**'s example record omitted `abns`, while its own prose requires deny-list checks on ABN and Gate 4's done-condition requires rejection by ABN to work independently. | **Fixed in SCHEMA.md §4.3**, dated. `abns` is a list of `{abn, entity, source, verified}` objects so an ABN carries its provenance and is never guessed |
| 4 | **`verdict` on an ownership record was not in the spec at all.** | **Signed off and added to SCHEMA.md §4.3**, dated, alongside `category`. `reject` blocks outright; `check` routes to human review and never auto-publishes, which §4.5 already provided for. Without it, attributions resting on trade reporting rather than a registry sit in a hard-reject list and silently block real independent producers |
| 5 | **`/validate` check 12 requires every state in `STATES` to have ≥1 region. The Northern Territory has no wine GI of any kind.** | **Placeholder kept.** `northern-territory`, `registered_as: "none"`, stated in the data as not a Geographical Indication and never to be presented as one. Check 12 unchanged. Tasmania and the empty zones are genuine GIs and are covered by decision 2 above |
| 6 | **HANDOVER open item 1 — `au-places.ts`.** TRD.md §2.5 declines the gazetteer and the 50 km near-me feature; the approved plan listed it as a Wave 2 deliverable. | **Dropped, open item closed.** TRD.md §2.5's reasoning stands: region, not distance, is how anyone chooses a winery to visit, and this build has no map and no runtime tile fetch. The plan file remains deliberately unedited, so it and TRD.md now disagree on the record |

---

## 5. Known gaps, stated rather than papered over

1. **`ownership.json` is deepest in the four coverage regions and thin elsewhere.**
   Adelaide Hills, McLaren Vale, Yarra Valley and Mornington Peninsula were swept
   on 2026-08-07, because that is where Gate 8 publishes first and where a gap
   actually bites. A national sweep was deferred deliberately.

   **Genuine minority stakes remain uncovered.** A 20% outside investor blocks
   publication and is almost never on a producer's website. What is seeded is
   outright and controlling stakes plus co-ownerships whose proportions are
   unpublished. Finding the rest needs ASIC and ABN registry lookups, not web
   reading.

   **Absence from the file means unchecked, not cleared.** It is not a whitelist.
   The file carries a `checked_and_not_listed` section recording what was looked
   at and deliberately left out, so the work is not repeated.

   **Ownership moves, and three records already did.** Stonier left Accolade in
   2022 and Knappstein left in 2025; both were in the file as portfolio brands on
   the first pass and both would have been wrong rejections. Vinarchy is cutting
   roughly 40 per cent of its brands. `/validate` check 8 re-checks every
   published producer against the file for exactly this reason, and that re-check
   matters as much as the first pass.

2. **One ABN is recorded.** The Wolf Blass ABN from SEED.md, which passes the ATO
   checksum. Every other record carries an empty `abns` array. That is the honest
   state of the register and not a gap to be filled by estimation.

3. **Coles Liquor's exclusive-label list is unpopulated.** Domains match; label
   names do not. A guessed label name in a deny-list blocks a real business.

4. **Endeavour Group announced a Pinnacle restructure and winery sales in May
   2026.** That record will move. Re-verify before Gate 4 runs.

5. **The fauna artwork does not exist yet, and will be commissioned** (confirmed
   2026-08-07). `animals.ts` carries the keys; `ANIMALS_AVAILABLE` is empty and
   `MarginAnimal.astro` must render nothing for every key until artwork lands.
   DESIGN.md §7's zero-image default already requires the homepage to look
   complete without it, so this is not a Gate 1 blocker. The brief is ready to
   send.

6. **`logistics_vineyard_tours` is the weakest glyph in the set.** It reads as
   converging rows at 32px and gets busy at 14px. DESIGN.md §10's rule applies:
   if you are unsure whether something meets the document, it doesn't. Put it in
   front of the Gate 1 design review rather than shipping it unexamined.

7. **Town lists are complete for the four Gate 8 coverage regions only.**
   Elsewhere they list principal towns and are extended as producers arrive. They
   are a display and disambiguation aid, never a boundary definition.

---

## 6. How the three data files were verified

No test framework exists yet (`/validate`'s self-test pattern lands with the
validators at Gate 6). These ran as standalone scripts on 2026-08-07 and all
passed. Gate 6 folds them into checks 11 and 12; Gate 4 folds the ownership one
into check 8.

| Check | Result |
|---|---|
| GI hierarchy verified against the Wine Australia register | 3 mis-nestings in secondary sources corrected against the individual GI pages |
| regions: unique slugs, one parent per subregion, both directions agree, every state ≥1 region, zone names resolve | pass |
| glossary: coverage both directions against all 13 vocabularies, slug derivation, `see_also` targets resolve | pass, 121 entries |
| glossary: em dashes, hedge words, banned words, tasting descriptors, US spellings | pass |
| ownership: required fields, no label/domain/ABN under two parents, bare-host domains, ABN checksum | pass, 22 owners |
| ownership: every cited source URL resolves | pass |
| ownership: coverage-region sweep | 8 records added, 1 corrected. Stonier and Knappstein removed from portfolio records they had left |
| icons: 44 glyphs, key set matches the §6 inventory exactly | pass |
| icons: every path parses, starts with a moveto, stays inside the 24×24 field at stroke 1.4 | pass |
| icons: rendered as a contact sheet at display size and at 16px, and reviewed | 9 glyphs redrawn after the first pass |
| tokens: 4.5:1 against `--paper` and `--paper-raised`, both modes | pass, reproduces DESIGN.md §2's table |
