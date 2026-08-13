# SCHEMA.md — The Data Contract

This document is the single source of truth for the producer data model. It outranks TRD.md wherever the two disagree about data (CLAUDE.md rule 3).

**One contract, four consumers.** Every field named here exists in four places, and any change lands in all four *in the same commit* (CLAUDE.md rule 7):

1. the zod content schema — `site/src/content/config.ts`
2. the SQLite DDL — `admin/pipeline/data_store.py`
3. the Harvester JSON validator — `admin/pipeline/orchestrator.py`
4. the admin frontmatter editor — `admin/schema.py` (`KNOWN_FIELDS`)

`/validate` check 13 diffs these four surfaces and fails on any disagreement. The `schema-change` skill fires on any edit to a field, enum or validator.

Closed enums live once in `site/src/config.ts` (TypeScript) and `admin/config.py` (Python) as a hand-mirrored pair, and the zod sub-schemas are **built programmatically from those tuples** — add a key to the tuple and the schema follows. Never write an enum literal inline.

---

## 1. Closed vocabularies

Every list below is a closed `as const` tuple in `config.ts` / `config.py`. Adding a value is a schema change.

### 1.1 `CATEGORIES`

| Key | Meaning |
|---|---|
| `estate_winery` | Grows and makes on its own site. |
| `urban_winery` | Makes wine in a city or town premises, fruit trucked in. |
| `negociant` | Buys fruit or finished wine and blends under their own label. |
| `garagiste` | Makes wine in shared, rented or borrowed space, at small scale. |
| `cooperative` | Multiple growers/makers sharing a facility and a label. |
| `other` | Genuinely ambiguous. Not a dumping ground. |

`negociant` and `garagiste` are deliberately split — a garagiste makes wine in shared or rented space; a négociant buys fruit or finished wine. Different businesses.

### 1.2 `CELLAR_DOOR_STATES`

`none` · `by_appointment` · `open`

A boolean would lose `by_appointment`, which is the most common state for small producers.

### 1.3 `CERTIFICATION_STATES`

`none` · `practising` · `certified`

Applies to both `organic` and `biodynamic`. The distinction is load-bearing: certified and uncertified-but-in-practice are materially different, the difference is often a deliberate choice by the producer, and publishing a false certification claim about a real business is a labelling problem, not merely an accuracy one. `certified` without a named certifier fails the build (`/validate` check 9).

### 1.4 `FRUIT_SOURCE`

`estate` · `purchased` · `mixed`

Most small producers are `mixed`; a boolean forces a wrong answer. `purchased` is neutral, not a demerit.

### 1.5 `PRODUCTION_BANDS`

`under_1000` · `1000_5000` · `5000_20000` · `over_20000` · `unknown`

Bands are gettable from published sources; exact case numbers usually are not.

### 1.6 `PRACTICE_KEYS` (canonical order)

`wild_ferment` · `unfined` · `unfiltered` · `minimal_so2`

Four booleans, all required when the `practices` object is present, no extras (zod `.strict()`). Each is checkable against a producer's own tech sheets.

**There is no `low_intervention` key and there never will be.** The term has no agreed definition and no certification. Flagging it means arbitrating it, and the site would be argued with from both directions. A `/low-intervention/` editorial page composed from these four facts is fine; a field on anyone's entry is not.

### 1.7 `LOGISTICS_KEYS`

`walk_ins_welcome` · `bookings_required` · `restaurant` · `picnic_provisions` · `dog_friendly` · `family_friendly` · `wheelchair_access` · `group_bookings` · `vineyard_tours` · `parking`

Optional object; individual keys default `false`.

### 1.8 `VESSEL_KEYS`

`stainless` · `oak_barrique` · `oak_foudre` · `concrete` · `amphora` · `ceramic` · `glass`

### 1.9 `WINE_STYLE_KEYS`

`red` · `white` · `rose` · `sparkling` · `skin_contact` · `fortified` · `dessert`

### 1.10 `VARIETY_KEYS`

Grape slugs, closed and curated in `config.ts` (e.g. `shiraz`, `cabernet-sauvignon`, `chardonnay`, `pinot-noir`, `grenache`, `nebbiolo`, `fiano`, `vermentino`, `gamay`, `mataro`). Closed rather than freeform because it drives `/variety/[grape]/` routes and the glossary — a typo would otherwise mint a dead page. Extending the list is a schema change; the seed set is authored in Wave 2.

### 1.11 `CONFIDENCE_TIERS` (weakest → strongest)

`unverified` · `published_by_producer` · `observed_on_visit` · `operator_confirmed`

The pipeline only ever sets `published_by_producer`. `observed_on_visit` exists for completeness but is **never pipeline-set** — this project makes no first-hand visits and publishes no first-hand tasting notes (CLAUDE.md rule 6); only a reviewer who genuinely visited may set it. A re-harvest **upgrades, never silently downgrades** a field's tier (`CONFIDENCE_TIER_RANK`).

### 1.12 `VERIFIABLE_FIELDS`

`parent_company` · `organic` · `organic_certifier` · `biodynamic` · `biodynamic_certifier` · `fruit_source` · `production_band` · `annual_production_cases` · `founded_year` · `tasting_fee` · `cellar_door_hours` · `varieties` · `wine_styles`

Certification and ownership need provenance more than tasting fees do. Deliberately *not* on the list: `name`, `location`, `category` (self-evident or editorial), the practice and logistics booleans (covered by the producer-level `verified` date).

### 1.13 `OWNERSHIP_EVIDENCE_METHODS`

`registry` · `producer_statement` · `trade_source`

Which of §4.2's three routes established the ownership determination. Recorded on every entry so the evidence base is auditable in aggregate — "how many producers rest on the producer's own word?" is a question the methodology page should be able to answer, and it cannot be reconstructed from a bare source URL.

### 1.15 `OWNERSHIP_STATES`

`confirmed` · `unconfirmed`

*Added 2026-08-09, signed off (CLAUDE.md, Engagement 2026-08-09 second).* Whether a dated source positively states who owns the business. `confirmed` carries an `ownership_source` and the site's independence claim applies to the entry. `unconfirmed` carries none, publishes with a visible notice, and **the site makes no independence claim for it.**

Numbered 1.15 rather than inserted at 1.14, because `STATES` is referenced by number in code comments and in the §1.13 correction note above; renumbering it would silently invalidate both.

`unconfirmed` is ignorance, never tolerance. `parent_company` must still be null (§2a rule 10) and a deny-list hit is never publishable in this state (§2a rule 14).

### 1.14 `STATES`

`VIC` · `NSW` · `QLD` · `SA` · `WA` · `TAS` · `NT` · `ACT`

### 1.16 `DENY_LIST_CHECKS`

`name` · `domain` · `abn`

*Added 2026-08-10, signed off.* The three independent paths `ownership.deny_list_check` runs against `data/ownership.json` (§4.3, UX.md §1.4.2). Named as a vocabulary because `audit_exemptions` (§2) has to say *which* of the three a recorded exemption answers, and a free string there would let an exemption written against one path silently appear to cover another.

Only `name` is ever exemptable, and only on a contained match (§2a rule 15). The vocabulary carries all three so the recorded value is checked against the same closed set the audit iterates, rather than being the one place the three paths are spelled by hand.

---

## 2. MDX Frontmatter

Collection directory: `site/src/content/producers/_published/`. Entity: `producer`. Route: `/producer/[slug]/`.

Slug = filename (`jauma-wines.mdx`), kebab-case, unique across `_staging` + `_published`. Slug is **not** a frontmatter field — it is derived from the filename everywhere.

| Field | Type | Req | Rules |
|---|---|---|---|
| `name` | string | ✓ | The producer's actual trading name. |
| `parent_company` | string \| null | ✓ | **`null` = independent. Any non-null value blocks publication.** The key is always present — an absent key is an undetermined producer, which is not publishable. See §4. |
| `ownership_status` | enum | ✓ | One of `OWNERSHIP_STATES` (§1.15). `confirmed` requires `ownership_source`; `unconfirmed` requires its absence. *Added 2026-08-09.* |
| `ownership_source` | object \| null | ✓ | `{ source: string, method: enum, date: date }`, or `null`. `method` is one of `OWNERSHIP_EVIDENCE_METHODS` (§1.13 — *corrected 2026-08-07, previously cited as §1.14, which is `STATES`*) and records *which* of the three routes in §4.2 was used. Documents a *negative* (see §4.2). **Amended 2026-08-09:** this previously read "No producer publishes without an ownership determination and a source." A producer still publishes only with a determination — that clause is untouched and `ownership_status` is now its record — but the *source* is required on `confirmed` alone. The key is always present; `null` is a positive statement that no source was found, not an omission. |
| `audit_exemptions` | array | – | *Added 2026-08-10.* Deny-list hits judged false positives, each `{ check: enum, matched: string, parent: string, register_updated: date, date: date, note: string }`. `check` is one of `DENY_LIST_CHECKS` (§1.16). The **durable** record of a judgement that was previously only in the gitignored determination sidecar, which meant `/validate` check 8 could never be brought to green in a fresh clone. Absent or `[]` on almost every entry: an exemption is an exception, and §2a rules 15 to 17 keep it one. Rendered/metadata only; not stored in SQLite. |
| `category` | enum | ✓ | One of `CATEGORIES` (§1.1). Never a near-synonym. |
| `founded_year` | number \| null | – | Four-digit year. Null when not published. |
| `website` | string (url) | ✓ | The producer's own site. |
| `location` | object | ✓ | `{ address?, suburb?, state, latitude?, longitude? }`. **Only `state` is required.** Where a person can physically go. Latitude −44.0…−9.0, longitude 112.0…154.0 when present; null coordinates mean no map pin and **do not block publication** — a label-only producer is a first-class entry. |
| `regions` | array of region slugs | ✓ | Min 1. Where the **fruit** comes from. GI region slugs from `regions.ts`. |
| `primary_region` | region slug | ✓ | Canonical route and breadcrumb anchor. Must be a member of `regions`. |
| `subregions` | array of subregion slugs | – | Blewitt Springs, Piccadilly Valley, Whitlands, Moppity and similar. Each must belong to a region listed in `regions`. |
| `cellar_door` | enum | ✓ | One of `CELLAR_DOOR_STATES` (§1.2). |
| `cellar_door_hours` | string \| null | – | **Freeform display string**, e.g. `"Fri–Sun 11am–5pm, and by appointment midweek"`. Deliberately not a per-day structured object: most producers here are appointment-only or irregular ("first Sunday of the month, harvest permitting"), and a seven-day grid forces a null-heavy shape that misrepresents them. Drafted from `facts.hours`, never fabricated. Omitted entirely when `cellar_door: none`. |
| `cost` | string \| null | – | Freeform pricing display string, e.g. `"Tastings $15, waived on a six-bottle purchase"`. Drafted from `facts.pricing`, never fabricated. |
| `tasting_fee` | object | – | `{ fee_aud: number \| null, waived_on_purchase: boolean \| null }`. Structured numbers alongside the freeform `cost` string, never replacing it. Cross-validated against `cost` (§2a). Omitted entirely when there is no published tasting fee — never invented. |
| `minimum_age` | number \| null | – | Positive integer. Licensed premises. |
| `organic` | enum | ✓ | One of `CERTIFICATION_STATES` (§1.3). |
| `organic_certifier` | string \| null | –* | *Required when `organic: certified`. ACO, NASAA, AUS-QUAL. Must be null otherwise. |
| `biodynamic` | enum | ✓ | One of `CERTIFICATION_STATES`. |
| `biodynamic_certifier` | string \| null | –* | *Required when `biodynamic: certified`. Demeter. Must be null otherwise. |
| `fruit_source` | enum | ✓ | One of `FRUIT_SOURCE` (§1.4). |
| `practices` | object | ✓ | Exactly the four boolean keys from §1.6, all required, no extras (zod `.strict()`). |
| `vessels` | array of enum | – | Values from `VESSEL_KEYS` (§1.8). Unique, no duplicates. |
| `varieties` | array of variety slugs | – | Values from `VARIETY_KEYS` (§1.10). A variety is listed only if the source names it. Drives `/variety/[grape]/`. |
| `wine_styles` | array of enum | – | Values from `WINE_STYLE_KEYS` (§1.9). |
| `production_band` | enum | ✓ | One of `PRODUCTION_BANDS` (§1.5). `unknown` is a legitimate answer and the correct one when not published. |
| `annual_production_cases` | number \| null | – | Exact figure only when published. Must be consistent with `production_band` (§2a). |
| `buy_online` | boolean | ✓ | |
| `ships_nationally` | boolean | ✓ | |
| `shop_url` | string (url) \| null | – | Required in practice when `buy_online: true`; enforced as a zod refinement. |
| `logistics` | object | – | The ten boolean keys from §1.7. Optional — omit entirely where none are known; individual keys default `false`. |
| `verification` | object | – | Per-field `{source, tier, date}` provenance, keyed by field name (subset of `VERIFIABLE_FIELDS`, §1.12). Rendered/metadata only; not stored in SQLite. |
| `change_log` | array | – | Computed diff entries `{field, from, to, date, trigger}`, appended on re-harvest. Absent at first draft. Rendered/metadata only. |
| `summary` | string | ✓ | ≤160 chars. Index one-liner + meta description. In register. |
| `drafted` | date (YYYY-MM-DD) | ✓ | Date the draft was generated. Stays fixed. |
| `verified` | date (YYYY-MM-DD) | ✓ | Date of the most recent harvest/verification pass. Re-set on every re-harvest. |
| `source_url` | string (url) | ✓ | The URL harvested from. |
| `image` | string | – | Path to published image asset. Present only after the separate image-publish action. |
| `image_source` | string (url) | –* | *Required if `image` present (zod refinement). |
| `image_caption` | string | –* | *Required if `image` present. `LOT I. — THE HOME BLOCK, LOOKING WEST.` register. |
| `faq` | array of `{question, answer}` | – | 3–6 pairs recommended, hard cap 8. Drafted strictly from the Harvester's `facts`; never fabricated. Absent or empty → no FAQ section renders. |

### Fields deliberately absent

- **`status` / claim fields.** The claim flow and Stripe are deferred (handover §2). No `unclaimed`/`claimed` enum, no claim routes, no `noindex` claim pages.
- **`independence`.** The `clear | check | reject` verdict is a *pipeline and staging* artefact, not published frontmatter — a published producer is `clear` by definition. It lives in the Harvester JSON (§5) and the staging sidecar.
- **`low_intervention`.** See §1.6.
- **Notation/abbreviation codes.** No badge system. Labels are words.

### 2a. Cross-field rules

These are the refinements that cannot be expressed by a single field's type. Those that can see both fields live in zod `.superRefine()`; those that need the filesystem or the DB live in `/validate`.

| # | Rule | Enforced in |
|---|---|---|
| 1 | `image_source` and `image_caption` are required when `image` is present | zod `.refine()` |
| 2 | `organic: certified` requires a non-null `organic_certifier`; any other state requires it to be null | zod `.superRefine()` + `/validate` 9 |
| 3 | `biodynamic: certified` requires a non-null `biodynamic_certifier`; any other state requires it to be null | zod `.superRefine()` + `/validate` 9 |
| 4 | `primary_region` must be a member of `regions` | zod `.superRefine()` |
| 5 | Every `subregions` entry must belong to a region listed in `regions` | `/validate` 12 (needs `regions.ts`) |
| 6 | `buy_online: true` requires a non-null `shop_url` | zod `.superRefine()` |
| 7 | `cellar_door: none` forbids `cellar_door_hours` | zod `.superRefine()` |
| 8 | **`tasting_fee.fee_aud` must fall within the range of dollar amounts stated in the `cost` string.** A structured fee the cost string cannot corroborate is a failure — delete the whole `tasting_fee` object rather than leave an uncorroborated figure | `/validate` 10 |
| 9 | `annual_production_cases`, when present, must fall inside `production_band` | `/validate` 10 |
| 10 | **`parent_company` must be `null`** on every published file | `/validate` 8 |
| 11 | `ownership_status: confirmed` requires `ownership_source` present with a non-empty `source`, a `date` and a `method` in `OWNERSHIP_EVIDENCE_METHODS` | zod `.superRefine()` + `/validate` 8 |
| 12 | Every populated `VERIFIABLE_FIELDS` entry carries a `{source, tier, date}` record; no tier downgrades against the previous commit | `/validate` 14 |
| 13 | `ownership_status: unconfirmed` requires `ownership_source` to be `null` | zod `.superRefine()` + `/validate` 8 |
| 14 | **`ownership_status: unconfirmed` requires the deny-list to be silent on name, domain and ABN.** A register hit is never publishable as unconfirmed | `/validate` 8 + `ownership.approval_blocks` |
| 15 | An `audit_exemptions` entry is valid only against a **contained (non-exact) `name`** match. An exact name match, a domain match and an ABN match each identify the entity itself, and none is ever exemptable | zod `.superRefine()` + `/validate` 8 |
| 16 | An exemption does **not** relax rule 14. A producer carrying one must publish as `confirmed` | `/validate` 8 |
| 17 | An exemption is honoured only while `parent` and `register_updated` still match the live register record. If the record moves, the exemption is **stale** and the hit fails again | `/validate` 8 |

*Rules 15 to 17, added 2026-08-10, are one mechanism and are written as three because each closes a different way of abusing it.*

**Rule 15** is the whole basis for the feature existing. A contained name match is the only deny-list hit with an innocent reading: a surname or a place name appearing inside a longer trading name. `ownership.check_name` already floors those to `check` and never rejects on them, for exactly this reason. A domain match means the producer's website *is* the register's listed domain and an ABN match means the same legal entity, and neither has a false-positive story worth writing a schema field for.

**Rule 16** stops the exemption becoming a second route into `unconfirmed`. If the evidence is good enough to show the register matched the wrong business, it named the right owner on the way through, so `confirmed` is available. An exemption that let a producer publish with no ownership source *and* a suppressed register hit would be the one combination that defeats both halves of §4 at once.

**Rule 17** is what keeps check 8 a standing audit rather than a one-time gate. The register grows, and the case this whole mechanism was built for is the case that must not become permanent: `Riposte by Tim Knappstein and Son` is exempt from the `Knappstein` label under Australian Yinmore Wines *as that record stood on 2026-08-07*. If somebody later buys Riposte and the record is updated to say so, the exemption goes stale on its own and the producer fails the audit again. **An exemption is a judgement about a register state, never a permanent waiver on a name.**

Rules 11 and 13 are the same co-requirement read in both directions, and they are deliberately shaped like rules 2 and 3 (`organic`/`organic_certifier`): a state enum plus the evidence that state implies, each forbidden without the other. The asymmetry that matters is rule 14, which has no counterpart on `confirmed` — a register hit blocks in *either* state, and `unconfirmed` must never become the door a deny-listed label walks through because nobody found a source for it.

Rule 8 mirrors the reference's price↔cost cross-check, which lives in Python rather than zod because the regex that scrapes dollar amounts from the freeform string is shared with the display helper. Keep that split: one regex, one home.

### 2b. Provenance

**`verification`** is built by `admin/pipeline/verification.py::build_verification`, keyed by `VERIFIABLE_FIELDS`. Every currently-populated verifiable field carries a `{source, tier, date}` record; a field the producer doesn't state carries none. On re-harvest, a field already at an equal-or-stronger tier is **preserved, never downgraded** (`CONFIDENCE_TIER_RANK`).

**`change_log`** is *computed*, not hand-maintained (`compute_change_log`): on a re-harvest, one `{field, from, to, date, trigger}` entry per verifiable field whose value moved. This matches the "frontmatter is truth, DB is disposable" architecture — nobody edits a log by hand.

---

## 3. SQLite (`data/directory.db`)

The published MDX directory is the source of truth; `directory.db` is disposable and always fully rebuilt from `_published` frontmatter. Rebuilding twice must be byte-identical.

**Correction to the build handover (§3.10).** The handover says `varieties`, `wine_styles`, `vessels` and `subregions` become child tables "mirroring the facilities pattern". The reference's `facilities` table is a **1:1 wide table of fixed boolean columns**, not a child table. That shape is correct for `practices` and `logistics`, whose keys are a fixed closed set. It cannot hold an open-ended array. Those four therefore become **true `(slug, value)` row tables** — and so does `regions`, which the handover's list omits but which is equally an array.

```sql
CREATE TABLE producers (
  slug TEXT PRIMARY KEY,          -- matches MDX filename; no separate UUID
  name TEXT NOT NULL,
  parent_company TEXT,            -- always NULL on published rows; column kept so
                                  -- the invariant is queryable, not merely asserted
  ownership_status TEXT NOT NULL,  -- OWNERSHIP_STATES (§1.15); added 2026-08-09
  ownership_source TEXT,           -- NULL on `unconfirmed` rows, and only there.
  ownership_source_method TEXT,    -- The three dropped NOT NULL on the same date;
  ownership_source_date TEXT,      -- §2a rules 11 and 13 are what enforce the pairing
                                   -- now, because SQL cannot express "required when".
  category TEXT NOT NULL,
  founded_year INTEGER,
  website TEXT NOT NULL,
  -- location, flattened
  address TEXT,
  suburb TEXT,
  state TEXT NOT NULL,
  latitude REAL,
  longitude REAL,
  primary_region TEXT NOT NULL,
  -- visiting
  cellar_door TEXT NOT NULL,
  cellar_door_hours TEXT,
  cost TEXT,
  tasting_fee_aud REAL,           -- flattened from tasting_fee
  tasting_fee_waived_on_purchase INTEGER,
  minimum_age INTEGER,
  -- farming and winemaking
  organic TEXT NOT NULL,
  organic_certifier TEXT,
  biodynamic TEXT NOT NULL,
  biodynamic_certifier TEXT,
  fruit_source TEXT NOT NULL,
  -- scale
  production_band TEXT NOT NULL,
  annual_production_cases INTEGER,
  -- commerce
  buy_online INTEGER NOT NULL DEFAULT 0,
  ships_nationally INTEGER NOT NULL DEFAULT 0,
  shop_url TEXT,
  summary TEXT NOT NULL,
  has_image INTEGER NOT NULL DEFAULT 0
);

-- 1:1 wide boolean tables (fixed closed key sets)
CREATE TABLE practices (
  slug TEXT PRIMARY KEY REFERENCES producers(slug) ON DELETE CASCADE,
  wild_ferment INTEGER NOT NULL,
  unfined INTEGER NOT NULL,
  unfiltered INTEGER NOT NULL,
  minimal_so2 INTEGER NOT NULL
);
CREATE TABLE logistics (
  slug TEXT PRIMARY KEY REFERENCES producers(slug) ON DELETE CASCADE,
  walk_ins_welcome INTEGER NOT NULL DEFAULT 0,
  bookings_required INTEGER NOT NULL DEFAULT 0,
  restaurant INTEGER NOT NULL DEFAULT 0,
  picnic_provisions INTEGER NOT NULL DEFAULT 0,
  dog_friendly INTEGER NOT NULL DEFAULT 0,
  family_friendly INTEGER NOT NULL DEFAULT 0,
  wheelchair_access INTEGER NOT NULL DEFAULT 0,
  group_bookings INTEGER NOT NULL DEFAULT 0,
  vineyard_tours INTEGER NOT NULL DEFAULT 0,
  parking INTEGER NOT NULL DEFAULT 0
);

-- (slug, value) child row tables — one row per array member
CREATE TABLE producer_regions (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  region TEXT NOT NULL,
  PRIMARY KEY (slug, region)
);
CREATE TABLE producer_subregions (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  subregion TEXT NOT NULL,
  PRIMARY KEY (slug, subregion)
);
CREATE TABLE producer_varieties (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  variety TEXT NOT NULL,
  PRIMARY KEY (slug, variety)
);
CREATE TABLE producer_wine_styles (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  wine_style TEXT NOT NULL,
  PRIMARY KEY (slug, wine_style)
);
CREATE TABLE producer_vessels (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  vessel TEXT NOT NULL,
  PRIMARY KEY (slug, vessel)
);
```

`verification` and `change_log` are **not** stored in SQLite — rendered/metadata only, same posture as `verified`. Child-table rebuild is delete-then-insert per slug so a removed variety disappears rather than lingering.

---

## 4. The independence determination

The inclusion criterion, the editorial position, and the reason the site exists. **Independence is an ownership fact. It is not inferable from prose** — corporate portfolio brands are engineered to read as small and independent, and a genuinely independent producer with a thin website may read as corporate. Any test based on tone fails systematically in both directions.

### 4.1 The rule

**Strict.** Any corporate ownership blocks publication — including minority stakes and multi-label family groups. `parent_company: null` is the only publishable value.

This is stricter than the trade's ordinary use of "independent": it excludes a maker with a 20% outside investor, and it excludes one of four labels under a family group that is itself unowned. That is a deliberate editorial position, and the consequence is that **the methodology page must define the term as this site uses it** rather than relying on the reader's assumption. It also means `data/ownership.json` has to seed family groups and minority holdings, not only outright portfolio ownership — otherwise the deny-list silently under-enforces the rule.

### 4.2 Evidence of a negative

Because the rule is strict, `ownership_source` documents the *absence* of a corporate parent, which is harder evidence than documenting a presence. One of the following, recorded with a date:

1. An ASIC or ABN lookup identifying the operating entity and showing no corporate parent — `registry`;
2. The producer's own published ownership statement, an "about" or "our story" page that names who owns the business — `producer_statement`;
3. A named independent trade source (wine media, regional association register, importer or distributor listing) stating ownership — `trade_source`.

**Any one of the three is sufficient**, provided it is specific about who owns the business and is recorded with a date. A source that merely fails to mention a parent is not evidence of absence — it must positively state ownership. Where the three conflict, the registry lookup wins and the conflict is noted in `confidence_notes`.

**Amended 2026-08-09, signed off.** Everything above is unchanged and still governs `ownership_status: confirmed`. What changed is what happens when none of the three routes yields anything.

Until this date the answer was: the producer does not publish. Measured against a real corpus that turned out to mean 43 of 98 drafts were unpublishable not because anything was wrong with them but because nobody publishes who owns them — and the largest bucket in the queue was silence, which the contract had no state for. `clear` asserts a fact. `check` blocks indefinitely. Neither is honest about "we looked and found nothing."

`unconfirmed` is that third state, and its entire justification is that **it does not make the claim.** The entry is listed; the notice on it says the site has not confirmed who owns the business; the methodology page says the same thing in general terms and gives the count. A reader who wants only confirmed-independent producers can still get exactly that set, because the state is a field and not a caveat buried in prose.

What this is not: it is **not** a fourth evidence route, and it must never be written as one. `unconfirmed` records the absence of evidence. The moment it is used to publish a producer somebody had a bad feeling about, or to wave through a register hit that lacked a registry confirmation, it has become the thing §4.1 exists to prevent. Rules 10 and 14 in §2a are what hold that line: null `parent_company` always, deny-list silence always.

### 4.3 `data/ownership.json`

Hand-maintained. Shape:

```json
{
  "parent": "Treasury Wine Estates",
  "category": "corporate_portfolio",
  "verdict": "reject",
  "labels": ["…"],
  "domains": ["…"],
  "aliases": ["…"],
  "abns": [
    { "abn": "55 004 094 599", "entity": "Wolf Blass",
      "source": "https://…", "verified": "2026-08-07" }
  ],
  "source": "https://…",
  "updated": "2026-08-06"
}
```

Deny-list checks run on **name, domain and ABN** before a draft enters the queue. No label may appear under two parents. Every record carries a source and a date.

**Amended 2026-08-07, Wave 2.** The example above previously omitted `abns`, `category` and `verdict`. The first was an outright omission — this section's own prose requires ABN checks and Gate 4's done-condition requires rejection by ABN to work independently, so the field had to exist. The other two were added and signed off on the same date:

- **`abns`** is a list of objects, not bare strings, so an ABN carries its provenance. An ABN is recorded only from a registry lookup or the operator's own published trading terms, and **never guessed** — a wrong ABN in a deny-list rejects an innocent business by a number nobody thinks to question.
- **`category`** is drawn from the file's own `categories` map and records *why* a record is here, so the review pane can say so and so §4.4's categories are auditable in aggregate.
- **`verdict`** is `reject` or `check`. `reject` blocks the draft outright. **`check` routes it to human review and never auto-publishes**, which §4.5 already provides for. The distinction exists because a false positive here silently blocks a genuinely independent producer and nobody ever finds out; attributions resting on trade reporting rather than a registry carry `check` until a lookup upgrades them.

The file also carries a `checked_and_not_listed` section. **Absence from `ownership.json` means unchecked, not cleared.** It is not a whitelist and must never be read as one.

### 4.4 Explicit reject categories

Pure retailers · restaurants · large corporate portfolio brands · and the highest-volume false positive, **virtual brands and supermarket private labels**, which have plausible-looking standalone sites by design.

### 4.5 The verdict

The Harvester extracts `ownership_signals` and emits `independence: clear | check | reject`. **It never decides alone.** The admin review pane surfaces the flag and the underlying signals; `check` never auto-publishes.

**Amended 2026-08-07 (Gate 5), signed off.** Not every extracted signal escalates. `parent_company_mentions`, `abn`, `shared_address` and `shared_contact_domain` each move the verdict to `check` on their own — each is a sign of a relationship the page is not stating plainly. `statements` does not, because §5 instructs it to capture ownership claims *in either direction*, and escalating on its presence penalised the positive statement §4.2 route 2 asks for. It escalates only when a fixed lexicon (`ownership.PARENT_PATTERNS`) finds group phrasing in it — a deterministic list in code, not a judgement about prose, so §4's first principle and CLAUDE.md rule 8 both hold. All five keys are extracted, rendered and retained regardless. The Harvester's own verdict can still only tighten, never relax.

---

## 5. Harvester JSON output

One JSON object, no markdown fence (the orchestrator strips one anyway rather than burning the single re-ask on formatting). Validated by `_validate_harvester_json` for parseability, object-ness, and the presence of every required key.

```jsonc
{
  "name": "…",                       // null if the page is not an independent wine producer
  "website": "…",
  "location": { "address": null, "suburb": null, "state": null,
                "latitude": null, "longitude": null },   // lat/lng always null — geocoded downstream
  "regions": [],                     // GI region names as stated; slugified downstream
  "category": null,                  // one of CATEGORIES, or null
  "founded_year": null,

  "ownership_signals": {
    "parent_company_mentions": [],   // verbatim phrases naming a parent, group or holding company
    "abn": null,
    "shared_address": null,          // an address shared with another label
    "shared_contact_domain": null,   // a contact email on another label's domain
    "statements": []                 // "part of the X family", "a member of the Y group", etc.
  },
  "independence": "clear",           // clear | check | reject

  "determinations": {                // re-imposed on the frontmatter by the pipeline (§6)
    "organic": "none",
    "organic_certifier": null,
    "biodynamic": "none",
    "biodynamic_certifier": null,
    "fruit_source": null,
    "practices": { "wild_ferment": false, "unfined": false,
                   "unfiltered": false, "minimal_so2": false },
    "varieties": []
  },

  "facts": {
    "vineyard": [], "varieties": [], "winemaking": [], "tastings": [],
    "pricing": [], "hours": [], "setting": [], "history": [],
    "people": [], "other": []
  },
  "confidence_notes": []
}
```

`HARVESTER_REQUIRED_KEYS = ("name", "website", "location", "regions", "category", "ownership_signals", "independence", "determinations", "facts", "confidence_notes")`

### The Harvester's standing rules

Preserved verbatim in intent from the reference, vocabulary swapped:

- **Evidence or nothing.** A variety is listed only if the source names it. `fruit_source: estate` only if the source states the fruit is estate-grown. `organic: certified` only if a certifier is named — otherwise `practising` at most, and note it in `confidence_notes`.
- **Null over guess.** Unknown scalars are `null`. Do not infer state from a region name. Leave `latitude`/`longitude` null always.
- **Facts are specifics.** Preserve numbers and materials exactly as stated: *"2019 Syrah, 14 months in old oak"*. One fact per array item.
- **Strip the marketing.** A sentence with zero facts is discarded.
- **Ownership signals are extracted, not judged.** The Harvester reports what the page says about ownership. It does not decide independence from tone.

---

## 6. Pipeline-owned fields

The pipeline, not the agents, owns these — `_finalize_frontmatter()` stamps them after the Gatekeeper returns:

- `source_url` (the harvest URL); `website` defaults to it
- `drafted` and `verified` = today
- **`determinations` re-imposed from the Harvester** onto `organic`, `organic_certifier`, `biodynamic`, `biodynamic_certifier`, `fruit_source`, `practices` and `varieties` — these are the Harvester's finding, not the Architect's or Gatekeeper's, and that is enforced rather than trusted to survive two rewrite passes
- `location.latitude` / `location.longitude` from the geocoder
- **`location.address` / `location.suburb` dropped when the Harvester returns them null.** §5's standing rule is "null over guess" and §2 declares both as optional *strings* — absent when unknown, never null. Both are right for their own surface and they are not the same shape, so the conversion happens here. Coordinates are deliberately excluded: a null `latitude` is a published statement that there is no map pin (§2), so it stays a null and stays a key. *Added 2026-08-10 (Gate 8): the step was always required by the §2/§5 pairing but was never written down, and neither `_finalize_frontmatter` nor `admin/schema.py` performed it. Five drafts reached `_published` carrying nulls and the Astro build rejected them — a stage later than the surface that should have caught it.*
- `verification` stamped `published_by_producer` from the harvest URL
- `change_log` computed against the previous frontmatter on re-harvest

The Gatekeeper is instructed to leave `verification` and `change_log` untouched.

---

## 7. Sample MDX

Place in `_published` at G1. Every required field present; optional fields shown both populated and absent.

**Corrected 2026-08-07, Gate 4.** The `verification` block below carries records for `organic` and `tasting_fee` only, while §2a rule 12 and §2b require one for **every currently-populated `VERIFIABLE_FIELDS` entry** — which in this sample is eleven fields, not two. The normative rule wins over the illustration, and `/validate` check 14 enforces the rule. The shipped `example-wines.mdx` was completed to match; the block below is left as authored so the correction is visible rather than silent. `verification.parent_company` is required even though its value is `null`: the null is a positive assertion of independence, not an empty field, and UX.md §1.4.6 makes that block the durable public half of the ownership determination.

```mdx
---
name: Example Wines
parent_company: null
ownership_status: confirmed
ownership_source:
  source: https://example.com/about
  method: producer_statement
  date: 2026-08-06
category: garagiste
founded_year: 2014
website: https://example.com
location:
  address: 12 Example Road
  suburb: Basket Range
  state: SA
  latitude: -34.9285
  longitude: 138.7401
regions:
  - adelaide-hills
primary_region: adelaide-hills
subregions:
  - piccadilly-valley
cellar_door: by_appointment
cellar_door_hours: Saturdays 11am to 4pm, by appointment
cost: Tastings $15 per person, waived on a six-bottle purchase
tasting_fee:
  fee_aud: 15
  waived_on_purchase: true
minimum_age: 18
organic: practising
organic_certifier: null
biodynamic: none
biodynamic_certifier: null
fruit_source: mixed
practices:
  wild_ferment: true
  unfined: true
  unfiltered: true
  minimal_so2: false
vessels:
  - stainless
  - oak_barrique
  - amphora
varieties:
  - chardonnay
  - pinot-noir
  - gamay
wine_styles:
  - red
  - white
  - skin_contact
production_band: under_1000
annual_production_cases: 800
buy_online: true
ships_nationally: true
shop_url: https://example.com/shop
logistics:
  bookings_required: true
  dog_friendly: true
  parking: true
verification:
  organic:
    source: https://example.com/vineyard
    tier: published_by_producer
    date: 2026-08-06
  tasting_fee:
    source: https://example.com/visit
    tier: published_by_producer
    date: 2026-08-06
summary: A garagiste operation in Basket Range working Adelaide Hills fruit across three varieties.
drafted: 2026-08-06
verified: 2026-08-06
source_url: https://example.com/about
faq:
  - question: Do I need to book to visit?
    answer: Yes. The cellar door opens Saturdays by appointment only.
---

Body copy goes here, 350 to 700 words, with one or two <Pull> tags.
```

---

## 8. Astro build note

Sub-schemas are built programmatically from the `config.ts` tuples, following the reference's pattern:

```ts
const practicesSchema = z.object(
  Object.fromEntries(PRACTICE_KEYS.map((key) => [key, z.boolean()])) as Record<
    (typeof PRACTICE_KEYS)[number], z.ZodBoolean>,
).strict();

const logisticsSchema = z.object(
  Object.fromEntries(LOGISTICS_KEYS.map((key) => [key, z.boolean().default(false)])) as ...
).strict().optional();

const verificationEntrySchema = z.object({
  source: z.string(),
  tier: z.enum(CONFIDENCE_TIERS),
  date: z.coerce.date(),   // coerce, not z.date(): YAML writes both Date and "YYYY-MM-DD"
});
```

Use `z.coerce.date()` for every date field for the same reason. The collection loader points at `_published` only, so staging and rejected content sit outside the collection tree entirely.

---

## 9. The blog contract — Gate 11, authored 2026-08-13

This document was frozen at Wave 1 and said nothing about the blog. UX.md §6 names
four editor fields — title, summary, dateline, an optional cover — and TRD.md §3
places the collection at `site/src/content/blog/_published/` and the claim audits at
`data/factchecks/`. Nothing anywhere defined the frontmatter. It is defined here,
in the data document, rather than in a zod file where it would be a contract nobody
could read without opening TypeScript.

**This is not a §2 change and it does not touch the producer contract.** No field
below appears on a producer, no vocabulary below is shared with one, and
`/validate` check 13 does not diff these surfaces. Said plainly because CLAUDE.md
rule 7 fires on any vocabulary change, and the honest answer for this one is that
the blog has **two** consumers, not four.

### 9.1 Why two consumers and not four

Rule 7 exists because a producer field has to survive four independent readers: zod,
the SQLite DDL, the Harvester's JSON validator, and the admin frontmatter editor. A
post has neither of the middle two, and the omissions are decisions:

- **No SQLite table.** TRD.md §5 makes `directory.db` a derived artefact rebuilt from
  `_published` producers, feeding aggregation pages and the search index. A post is
  not an entity anything aggregates over: `/blog/` reads the collection directly, the
  search index covers producers, and there is no post taxonomy. A table would be a
  second copy of the frontmatter that nothing reads.
- **No Harvester validator.** Posts are hand-authored and editorially drafted, never
  harvested. There is no page to extract from and no JSON to validate.

So the blog contract lands in **two** surfaces, name-matched in the same commit:

1. the zod schema, `site/src/content/config.ts`
2. the admin post editor's field contract, `admin/pipeline/blog.py::POST_FIELDS`

Plus this section, which is where they are written down. `schema_surfaces` grew a
second, smaller comparison for the pair rather than folding posts into the producer
diff, so a blog field added to one surface and not the other fails check 13 exactly
as a producer field does.

### 9.2 Frontmatter

Collection directory: `site/src/content/blog/_published/`. Entity: `post`.
Route: `/blog/[slug]/`.

Slug = filename (`who-owns-the-adelaide-hills.mdx`), kebab-case, unique. Slug is
**not** a frontmatter field, exactly as for producers.

| Field | Type | Req | Rules |
|---|---|---|---|
| `title` | string | ✓ | The post's own title. Sentence case, in register. Never a question the post does not answer. |
| `summary` | string | ✓ | ≤160 chars. The `/blog/` list one-liner and the meta description. Same bound and same job as a producer's `summary`. |
| `dateline` | string | ✓ | The **journalistic** dateline: where the post is written *about*, in words. `Adelaide Hills, South Australia`. Freeform because the subject of a post is not always a GI region — it may be a state, the whole country, or the register itself. Rendered beside `published` in the mono dateline row, which is what makes DESIGN.md §15's "the collector's date and locality beside it" true of a post as well as an entry. |
| `published` | date (YYYY-MM-DD) | ✓ | The publication date. Stays fixed once the post is live; a correction sets `updated`, never this. Sorts `/blog/` and `/rss.xml`, descending. |
| `updated` | date (YYYY-MM-DD) | – | Set when a published post is edited in place (UX.md §6). Absent on a post never amended. Renders as `Amended 14 August 2026` beneath the dateline, because a silently rewritten post is the thing the site's own documentation habit exists to prevent. |
| `sources` | array of `{title, url}` | ✓ | **Min 1.** Every source the post's claims rest on, in citation order. Rendered as a list at the foot of the post. A post with no sources is an opinion, and this site publishes documented claims (CLAUDE.md rule 6). `title` is what the source calls itself, never a paraphrase; `url` must be absolute. |
| `factcheck` | string | ✓ | The slug of the committed claim audit at `data/factchecks/<factcheck>.json` (§9.4). Equal to the post's own slug in every ordinary case; a field rather than a convention so the audit is a *stated* dependency the validator resolves, not one it infers from a filename. |
| `cover` | string | – | Path to the cover image, `/blog-images/<slug>/<name>.webp` once published. *Amended 2026-08-13: the post's slug is a path segment.* A staged draft carries `/blog-staging-images/<slug>/…` until the publish move rewrites it. Without the slug, two posts each carrying a `photo` overwrote one another on publish. |
| `cover_source` | string (url) | –* | *Required if `cover` present. |
| `cover_caption` | string | –* | *Required if `cover` present. Same attribution rule as a producer's `image_caption`, and for the same reason: a photograph of somebody's vineyard carries visible attribution or it does not publish. **Not** the `LOT I. —` plate register, which is the producer page's specimen signature (DESIGN.md §505). |

`.strict()`, as the producer schema is, and for the same reason: an unknown key is a
typo, a hand-edit against the contract, or a field added to one surface and not the
other.

### 9.3 Cross-field rules

Numbered to stand alone; they are not a continuation of §2a and share nothing with it.

1. **Cover co-requirements.** `cover` present requires `cover_source` and
   `cover_caption`. Enforced in zod, mirroring §2a rule 1.
2. **`updated` is never before `published`.** A post amended before it existed is a
   date typo, and it renders as one.
3. **`sources` URLs are absolute and unique.** The same source cited twice is a
   drafting artefact, not two pieces of evidence.
4. **The audit must resolve.** `data/factchecks/<factcheck>.json` must exist, must
   parse, and must carry no claim in an unresolved state. Enforced by `/validate`
   check 22, not by zod, because zod cannot read a file outside the collection.
5. **No hardcoded figures.** A numeral in the body that states a count this repository
   already knows — producers published, producers in a region, terms in the glossary,
   the ownership split — is written as a `<Figure>` (§9.5), never typed. Check 22.
6. **A removed claim stays removed.** *Added 2026-08-13.* No claim verdicted `removed`
   in the audit may have its text back in the published body. The fact-check stage
   already refuses to *return* one, but that ran once, at the moment the model
   answered. UX.md §6 lets a published post be edited in place and the save writes
   straight into `_published`, so nothing re-checked the body that ships — a post
   could carry, verbatim, the sentence its own audit records as deleted for being
   false, with every check green. Reproduced against the shipped corpus before the
   rule was written. Enforced by check 22 on what is published and by the publish gate
   on what is about to be, through one shared comparison (`blog.restored_claims`).

### 9.4 The claim audit — `data/factchecks/<slug>.json`

Committed, per TRD.md §3, and reachable from the deploy allow-list. One file per post,
written by the fact-check stage and amended by the reviewer resolving claims.

```json
{
  "post": "who-owns-the-adelaide-hills",
  "checked": "2026-08-13",
  "model": "the MODEL_FACTCHECK id, as read from .env",
  "drafted_by": "the MODEL_ARTICLE id, as read from .env",
  "claims": [
    {
      "id": "c1",
      "text": "The verbatim sentence from the draft that makes the claim.",
      "verdict": "supported | unsupported | removed",
      "reason": "Why, in one sentence.",
      "source": "The source that stands it up, or null."
    }
  ]
}
```

`verdict` is a closed vocabulary of three and it is the whole point of the file:

- **`supported`** — a source in the post's `sources` stands the claim up. `source` names it.
- **`unsupported`** — the fact-check could not stand it up and left it in place for a human. **This is the unresolved state**, and it blocks publish (UX.md §6). It is resolved by the reviewer either finding the source, editing the claim, or accepting the deletion — never by the reviewer overriding the verdict.
- **`removed`** — the fact-check deleted the claim from the draft. The `text` is retained verbatim so the deletion renders struck through with its reason beside it (UX.md §6). **A deletion that leaves no trace is indistinguishable from a claim that was never made**, which is why the record is committed rather than kept in staging.

`model` and `drafted_by` are recorded because the adversarial split is the mechanism
this stage exists for (TRD.md §7.6), and an audit that does not say who checked whom
cannot show the split held. Two identical ids in that pair is a self-review and the
pipeline warns about it in the log and in the file.

### 9.5 `<Figure>` — the data component

UX.md §6: "A number in a post that ought to come from the data is a data component,
never typed prose." This is that component, specified here before it was built rather
than after, because a component named in a checklist and defined nowhere gets
implemented from imagination (TRD.md §3's 2026-08-12 amendment, on `ExtractiveAnswer`).

`<Figure of="…" member="…" />` resolves at build time against `producers.json` and the
hand-authored registers, and renders a plain numeral in the body's own type. No badge,
no callout, no styling of its own — a figure is a word in a sentence.

The query set is **closed**. An unknown `of`, a `member` that is not in that query's
vocabulary, a missing `member` where one is required, or a `member` supplied to a
keyless query all **fail the build** naming the file, exactly as a bad enum value on a
producer does.

**The attribute is `member`, not `key`, and that is not a style choice.** MDX compiles
to JSX, and the automatic JSX runtime lifts `key` out of props before the component is
called — a `<Figure of="region" key="adelaide-hills" />` would arrive with no member at
all and fail as though the author had omitted it. Named `member` so the trap cannot be
sprung.

**A count of zero is not a failure.** A region in the register with no published
producers answers `0`, which is a true answer to a question that was asked correctly;
present-only generation is a rule about *listings*, not about arithmetic. The failure
case is a `member` the vocabulary has never heard of, which is a typo, and the
distinction is what keeps this component from failing a build over an honest zero.

| `of` | `member` | Renders |
|---|---|---|
| `published` | — | Every published producer. |
| `region` | a region slug | Producers whose `regions` include it. |
| `subregion` | a subregion slug | Producers whose `subregions` include it. |
| `state` | a `STATES` value | Producers in that state. |
| `variety` | a variety slug | Producers listing that variety. |
| `practice` | a `PRACTICE_KEYS` value | Producers whose flag is true. |
| `ownership` | an `OWNERSHIP_STATES` value | Producers in that ownership state. |
| `regions` | — | Regions with ≥1 published producer. |
| `glossary` | — | Glossary terms. |

Every one of these is a count the build already computes for a page. The component
reads the same helpers the pages read; it does not add a second way to count anything.

**Why the set is closed rather than an expression language.** A post that can evaluate
arbitrary queries is a post that can assert an arbitrary figure, which is the problem
restated. Nine named counts cover what a post about this guide has any business
stating, and the tenth is a prompt to come back and add it deliberately.
