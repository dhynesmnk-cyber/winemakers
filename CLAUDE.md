# CLAUDE.md — Operating Instructions

You are building the project specified in TRD.md. Read TRD.md, SCHEMA.md, UX.md, and DESIGN.md before writing any code. This file governs *how* you work.

The project is a field guide to independent Australian winemakers. Free to use, no ads, no sponsored listings. The word doing the work is **independent** — it is the inclusion criterion, the editorial position, and the reason the site exists.

## Prime rules

1. **Gates are sequential and blocking.** Work happens inside the current gate only. When a gate's done-condition passes, stop, summarise what was built and how you verified it, and wait for explicit approval before starting the next gate. Never begin work from a later gate "while you're in there."
2. **Ask before adding any dependency** not already named in TRD.md — npm or pip, however small. State what it's for and what the no-dependency alternative would be. The house posture is deliberate: raw-httpx over vendor SDKs, stdlib `smtplib` and `hmac`, a hand-rolled `.env` parser. Carry it.
3. **Never invent scope.** If the spec docs don't cover something, ask. If two docs conflict, the more specific document wins (SCHEMA.md > TRD.md for data; UX.md/DESIGN.md > TRD.md for interface); flag the conflict either way.
4. **File pathing:** all cross-cutting paths (content dirs, DB path, temp dirs) are defined once — `admin/config.py` for Python, `site/src/config.ts` for Astro — and imported everywhere else. No hardcoded relative paths in feature code. All Python file operations use `pathlib` and are safe to run from the repo root.
5. **Never touch:** `.env` (read-only, never commit, never print its values), anything in `temp_data/` manually, git history (no rebase/force-push), the `_published` directory by hand (only the approve action writes there).
6. **The honesty rule — non-negotiable.** Entries are documented from published sources. **No fabricated visit, no invented tasting note, no first-hand sensory claim.** Nobody on this project has visited these cellar doors or tasted these wines, and no sentence may imply otherwise. If you write or edit prompts, preserve this rule verbatim. It is the reason the directory can be trusted at all.
7. **One contract, four consumers — non-negotiable.** Any vocabulary change — a field, an enum value, a validator — lands in all four *in the same commit*, name-matched:
   1. the zod schema, `site/src/content/config.ts`
   2. the SQLite DDL, `admin/pipeline/data_store.py`
   3. the Harvester JSON validator, `admin/pipeline/orchestrator.py`
   4. the admin frontmatter editor, `admin/schema.py`

   This is the highest-risk-if-broken invariant in the build. The `schema-change` skill fires on any such edit; `/validate` check 13 diffs the four surfaces and fails on disagreement.
8. **Independence is an ownership fact, never a tone judgement.** No agent decides independence from marketing prose. The determination runs off `data/ownership.json` and extracted ownership signals (SCHEMA.md §4). `check` never auto-publishes.
9. Australian English in all user-facing copy, including the admin UI.

## Doc precedence

**SCHEMA.md > TRD.md** for data. **UX.md / DESIGN.md > TRD.md** for interface. Flag the conflict either way — a conflict that gets silently resolved is a spec bug that will come back.

## Stack constraints (recap — full detail in TRD.md §2)

Astro 5 SSG + Tailwind v4 (Vite plugin, no config file). FastAPI + Jinja2 + vanilla JS in the admin — no React, no SPA framework. SQLite via stdlib `sqlite3`. httpx + trafilatura, with Playwright as a user-triggered fallback only. Anthropic SDK; **model IDs come from `.env`, never hardcoded in source**. Nothing else without asking (rule 2).

Two config quirks are load-bearing and must be ported verbatim:

- The **IPv4-only `socket.getaddrinfo` monkeypatch** at the top of `admin/config.py`, before any httpx client exists. Some sandboxed environments advertise an IPv6 route that is a black hole; Python's socket stack does not fall back the way curl does, and hangs past any per-call timeout.
- The **hand-rolled `.env` parser** (no `python-dotenv`), plus cascading model defaults so overriding one env var still yields valid IDs everywhere.

## Commands

```bash
# site
cd site && npm run dev          # Astro dev server
cd site && npm run build        # static build — must pass with zero warnings for gate exits
# admin
uvicorn admin.app:app --reload --port 8787
# data
python -m admin.pipeline.data_store --rebuild   # rebuild DB + derived JSON from _published
# validation (gate-exit test — see .claude/commands/validate.md)
/validate
```

## The reference repo

`/home/dhynesmnk/Bathers'/` is the worked example this project ports from. **It is read-only. Nothing here writes to it.**

The folder name contains an apostrophe — quote every path that touches it:

```bash
ls "/home/dhynesmnk/Bathers'/admin/pipeline"
```

Do not copy its text blindly. Known stale spots: its `SCHEMA.md` prose says "nine" facilities while the DDL lists twelve; `Map.astro` was removed but its build-time embedded-JSON idiom still powers search; its colour hexes were amended three times; `venues.json`/`venues.geojson` are vestigial, written by the admin and read by no page.

## The Gates

### Gate 1 — Astro scaffold + zod producer schema
Astro 5 SSG + Tailwind v4 per TRD §3. `config.ts`/`config.py` authored as the hand-mirrored pair. Content collection `producers` with the full zod schema from SCHEMA.md, sub-schemas built programmatically from the `as const` key tuples (SCHEMA.md §8). The sample MDX from SCHEMA.md §7 placed in `_published`. Base layout with the three self-hosted faces, grain overlay, dual-mode token machinery. `ProducerEntry`, `Pull`, `TippedPhoto`, `Icon` components with real styles.
**Done when:** `npm run build` passes with the sample producer; deliberately corrupting one frontmatter field (wrong type, missing required, unknown key against `.strict()`) fails the build with a clear field-level error; the rendered sample page passes the DESIGN.md §10 test; site renders correctly with JS disabled and under `prefers-reduced-motion`; `/validate` checks 1–4, 7 and 16 pass clean.

### Gate 2 — Data layer + data model
`data_store.py` per TRD §5 and SCHEMA.md §3: schema creation, rebuild-from-published, upsert-on-slug, derived JSON generation. CLI rebuild command works. Note SCHEMA.md §3's correction — `practices` and `logistics` are 1:1 wide boolean tables; `regions`, `subregions`, `varieties`, `wine_styles` and `vessels` are true `(slug, value)` row tables.
**Done when:** rebuild from the sample MDX produces correct rows in every table and the derived JSON; running rebuild twice is byte-identical (idempotent); editing the sample's varieties and rebuilding updates rather than duplicates; deleting the DB and rebuilding restores it exactly; a corrupted `_published` file is skipped-and-logged, not fatal to the whole rebuild; `/validate` checks 3 and 13 pass.

### Gate 3 — Admin hub shell + staging queue
FastAPI app serving the single-screen layout from UX.md §1: harvest panel with the log pane wired and the pipeline stubbed, review queue reading `content-staging/_staging/`, review pane with rendered preview using public CSS, frontmatter editor with debounced autosave, approve/reject actions (move + upsert + regenerate + undo window), keyboard shortcuts, empty states.
**Done when:** with three hand-placed staging MDX files, a full keyboard review session works end to end; approving lands the file in `_published`, updates the DB and derived JSON, and the site builds with it; rejecting moves to `_rejected` with a reason sidecar; a schema-invalid staging file is blocked from approval with field-level errors; undo within 3s fully reverses an approve.

### Gate 4 — The independence system
The highest-priority new component; it has no analogue in the reference. `data/ownership.json` wired in; an `ownership.py` module emitting `clear | check | reject`; deny-list checks on name, domain and ABN running *before* a draft enters the queue; the admin review pane surfacing the flag and the underlying signals; `check` never auto-publishes. Draft the methodology page here even though it ships at G10 — it is the published definition of independence and the document producers will argue with.
**Done when:** a known portfolio-owned label in `ownership.json` is rejected by name, by domain and by ABN independently; a known independent producer returns `clear`; a producer with an ambiguous parent-company mention returns `check` and is visibly blocked from auto-publish in the queue; a deliberately staged supermarket private label and a virtual brand are both rejected; `/validate` checks 8, 9, 10 and 14 fail against fixtures carrying, respectively, a non-null `parent_company`, a `certified` state with no named certifier, a `tasting_fee` the `cost` string cannot corroborate, and a downgraded confidence tier.

### Gate 5 — AI pipeline integration
Harvester → Architect → Gatekeeper wired per TRD §7 and `PROMPTS/`, prompts loaded at call time and never embedded. Batch harvest queue — necessary at the target coverage, not optional. Streaming log per stage. The Harvester emits `ownership_signals` and feeds G4's determination; it never decides alone. Candidate-image download and the separate publish-image action per UX.md §4. All failure states in UX.md §1.5.
**Done when:** each URL in SEED.md runs end to end producing a schema-valid staged draft; drafts pass a spot-check against the Gatekeeper's rules (no banned words, Australian spelling, no fabricated visit or tasting claims); a deliberately bad URL and a malformed-JSON simulation both fail per the failure table; a batch of ten URLs completes with per-URL failures isolated; token usage appears in the log; the Harvester's `independence: reject` verdict aborts before a draft is written; `/validate` check 6 reports clean.

### Gate 6 — Programmatic surface + the scale redesign
`/region/[region]/`, `/region/[region]/[subregion]/`, `/[state]/`, `/variety/[grape]/`, `/practice/[key]/` — all present-only generation: loop the taxonomy, `continue` on zero, never an empty page. Forewords pipeline. **This gate carries the scale design change**: the homepage becomes region-first with real pagination, not a single client-filtered grid over the whole dataset. That is a design decision, not a later performance fix.
**Done when:** every region/subregion/variety/practice with ≥1 published producer resolves and appears in `sitemap.xml`; zero-producer taxonomy entries generate no page and log the skip; the homepage renders and paginates without loading the full dataset; every programmatic page is reachable with JS disabled; `/validate` checks 5, 11 and 12 pass.

### Gate 7 — Deploy strip
Diff preview before push, only legal paths; tracked-file guard with an allow-list; pre-push `npm run build` gate; Netlify build poll; IndexNow ping. Ported from the reference's `deploy.py` unchanged in shape.
**Done when:** only legal paths appear in the deploy diff; **the guard demonstrably refuses a deliberately staged tracked `temp_data/` file as an automated self-test, not a manual check** — this is `/validate` check 15 and it closes the one clear gap in the reference; `npm run build` failure blocks the push; a full harvest → approve → deploy cycle runs end to end against a SEED.md producer.

### Gate 8 — Coverage build-out
Publish 150–300 producers across the four seed GI regions — **Adelaide Hills, McLaren Vale, Yarra Valley and Mornington Peninsula** — each carrying complete data and a documented ownership determination **at publish time, never backfilled after**. Region-deep, not nationally thin: a region page that reads as complete is worth more than four that read as stubs. `regions.ts` still carries the full GI register from Wave 2; these four are simply the ones that get producers first.
**Done when:** each target region is populated to the point its region page reads as complete; every published producer carries an `ownership_source` and a full provenance block at publish time; zero producers published with a non-null `parent_company`; the full `/validate` suite passes against the expanded set; region/subregion/variety pages regenerate with no manual intervention beyond the normal approve action.

*Amended 2026-08-09, second amendment, signed off. **The second clause — "every published producer carries an `ownership_source`" — is superseded by the engagement block below.** It stands as history, not a live requirement. A producer may now publish in the `unconfirmed` ownership state, carrying no `ownership_source` and a visible notice that the site has not confirmed its ownership. The third clause is untouched and always will be: **zero producers published with a non-null `parent_company`.** Unconfirmed means the owner is unknown to us, never that a parent is known and tolerated.*

*Amended 2026-08-09, signed off. **The 150–300 range stands as the original sizing estimate, not as a live requirement.** It was written before any harvest existed. The measured position: 97 staged drafts, 92 of them in the four target regions, against which no ownership rule reaches 150 — the full ABN register was scanned (20,422,589 records) and 44 producers resolve to a unique entity, of which none clears on the registry alone under the rule chosen the same day. The gate now closes on the done-condition's own first clause, **each target region reading as complete**, which was always the real test; a count was only ever a proxy for it. Deepening coverage beyond that is a later dated block, not a reason to hold Gate 8 open.*

*Recorded the same day, because it bears on every count above: the three ownership evidence routes are not equally available. `producer_statement` requires a page that names who owns the business, and small wineries overwhelmingly do not publish one — an evidence pass over 46 drafts lacking a source produced three candidates and none cleared. `trade_source` has the same defect, because association registers list membership rather than ownership. **`registry` does not clear a producer on its own** (decided 2026-08-09): neither the ABR web service nor the bulk extract carries shareholder data, so an ABR record identifies the operating entity without showing no corporate parent, which is what the ownership-check skill requires of the method. It is used to reject on a deny-list hit and to corroborate; `method: registry` stays reserved for an ASIC extract, which is not funded. The practical consequence is that `producer_statement` carries essentially the whole corpus, and the publishable count is bounded by it.*

***CLOSED 2026-08-12.** All done-conditions met, and the first clause — each target region reading as complete, which the 2026-08-09 amendment made the gate's real test in place of a count — was judged met by the user on the figures below.*

*The corpus stands at **97 published**: by primary region, 33 Adelaide Hills, 17 McLaren Vale, 19 Yarra Valley, 24 Mornington Peninsula and 4 elsewhere; as the region pages render them, 36, 21, 19 and 24. All four carry forewords, and their subregion pages track the register rather than the corpus — 2 for Adelaide Hills, being its only registered GI subregions, against 7 and 6 trade-use districts for McLaren Vale and Mornington Peninsula. The staging queue is empty, 4 drafts sit rejected, and the ownership split is **48 `confirmed` against 49 `unconfirmed`**, close to parity rather than the three-to-one the 2026-08-09 second engagement forecast at the counts then available.*

*Every other clause was demonstrated rather than read: **zero producers published with a non-null `parent_company`** (97/97, the clause that never moves); a full provenance block on all 97 with no tier lower than at HEAD; the full suite green with checks 1–3, 5, 7–16 and 20–21 passing, check 6 warning only, and `npm run build` emitting 311 pages with zero warnings; and regeneration with no manual intervention, evidenced by check 3 rebuilding byte-identical twice and check 5 resolving 11,801 internal hrefs against 311 sitemap entries.*

*Two things carry forward into Gate 9. **The unmechanised dateline scan** (2026-08-12 engagement, note 1) is a known gap in a surface Gate 9 is about to add pages to. And **`producer_statement` still bounds the publishable count** — the constraint recorded 2026-08-09 is unchanged, so any later coverage block should size itself against that rather than against the original 150–300.*

### Gate 9 — Comparison pages + internal-linking graph
Comparison registry with a minimum-producer threshold that **skips-and-logs, never fails**. Semantic `<table>`/`<caption>`/`<th scope>` markup plus `ItemList`. Internal-linking rules enforced as a graph check.
**Done when:** a page exists for every comparison clearing the threshold; the threshold demonstrably skips a deliberately thinned fixture rather than failing; every producer is linked from ≥3 aggregation pages; every comparison page is reachable from a hub; `/validate` check 17 passes with zero orphans.

***CLOSED 2026-08-13.** All five done-conditions met, each recomputed by check 17 rather than read off the build log. **16 comparison pages** clear the 4-producer threshold and `dist/compare/` holds exactly those 16 beside its hub — no page for a comparison that does not clear, no comparison clearing without a page. **97/97 producers** are linked from ≥3 distinct aggregation pages, counting pages rather than links and excluding producer pages from the count, so a cluster of cross-linked producers cannot satisfy the rule while sitting off every listing. All 16 comparison pages are reachable from their hub, and there are **zero orphans across 328 pages**. Full suite green — checks 1–3, 5, 7–17 and 20–21 pass, check 6 warns only at 107 hits across 46 files (unchanged), the pipeline fixtures pass, and `npm run build` emits 328 pages with zero warnings. Check 16 completed its **browser layer** — PASS, not PARTIAL, under `.venv/bin/python`.*

*The skip-don't-fail condition is demonstrated three ways rather than once: the live build at `MIN_COMPARISON_PRODUCERS=5` exits 0 while dropping three pages; the mechanised self-test runs the thinned fixture on every invocation of check 17; and the self-test was itself sabotaged to prove it bites.*

*Three things are worth carrying forward:*

1. ***A self-test that hardcodes what the code under test reads from config will eventually blame the code for its own arithmetic.*** *Check 17's fixture hardcoded four producers while its expectation read `MIN_COMPARISON_PRODUCERS`; raising the threshold to 5 failed the CLEAN fixture with an error naming `comparisons.ts`, when the only thing wrong was the fixture. The threshold is an editorial dial meant to be tuned. The fixture now sizes itself from the constant and builds its thin pair at exactly one under it, so the boundary is what gets asserted; verified across 18 combinations of the two constants, and values it cannot express now report that limit rather than quietly asserting something narrower.*
2. ***Check 6 does not lint Astro copy.*** *It lints `_published` bodies and METHODOLOGY.md. The comparison table's empty "other varieties" cell shipped an em dash — banned in anything a reader sees — and no check would have caught it; it was found by reading the rendered page. Every reader-facing string authored in a component is outside the editorial lint, and Gate 10's JSON-LD and FAQ copy will add more of them.*
3. ***`ExtractiveAnswer` was struck from TRD.md's file tree rather than built.*** *It appears in no spec document: nothing defines what it is, what it renders or what feeds it. It is deferred to Gate 10, which owns the `FAQPage` and E-E-A-T work an extractable answer would serve. If it is wanted, it needs a spec first — a dangling component name in a file tree is the kind of thing a later gate implements from imagination.*

### Gate 10 — Structured data, E-E-A-T & methodology
`LocalBusiness` + `BreadcrumbList` + `FAQPage` + `ItemList` + `DefinedTermSet`/`DefinedTerm` JSON-LD; offline structural validator folded into `/validate`; the methodology page live and linked; `llms.txt` generated as an endpoint rather than a static file that drifts.
**Done when:** JSON-LD passes the offline validator on 100% of page types; the methodology page states the independence rule plainly, **including what it excludes**, and is linked from footer and nav; `llms.txt` references only live routes; any move beyond `LocalBusiness` (e.g. `Winery`) is recorded as a dated TRD.md exception with explicit sign-off, or explicitly declined.

***CLOSED 2026-08-13.** All four done-conditions met.*

***JSON-LD on 100% of page types** — check 18 reports 1,410 nodes across 329 pages, and every one of the 14 page types carries structured data: `Organization` + `WebSite` on all 329; `BreadcrumbList` on 328, the homepage being the sole exception because nothing sits above it; `LocalBusiness` + `FAQPage` on all 97 producer pages; `ItemList` on the 106 listing pages across six families and two hubs; `DefinedTermSet` on `/glossary/` and `DefinedTerm` on all 123 term pages.*

*Every node is built in `site/src/data/jsonld.ts`; no page hand-writes a schema.org object. Emission follows the data rather than the page — `BreadcrumbList` is built inside `Breadcrumbs.astro` from the same crumb array it renders, `ItemList` inside `TaxonomyPage.astro` from the same producer slice it lists — so two paths cannot disagree when there is only one array, and no page can forget to pass one.*

***The methodology page** is live at `/methodology/`, rendered from `METHODOLOGY.md` through a collection whose `base` points outside `site/`, so the document stays at the repository root where TRD.md §3 puts it and is still rendered by Astro's own markdown pipeline — no second markdown dependency. What the rule excludes is a six-item list of kinds of business, followed by the concession that it excludes businesses many people, including the people who run them, would fairly call independent. Linked four ways from a producer page: corner menu, footer, the unconfirmed notice and the provenance line. Screenshotted in both themes before being called done.*

***`llms.txt`** is an endpoint built from the same present-only helpers as the sitemap; check 19 resolves all 194 of its links against `dist` and recomputes its one numeric claim, the ownership split, from `producers.json`.*

***`Winery` stays declined.** The 2026-08-06 TRD.md decision is annotated in place as shipped and held, and it is now enforced rather than recorded: check 18 fails on any `@type` outside the allowed set, so widening it means adding it there deliberately, which is the prompt to write the exception first. No exception has been taken.*

*Full suite green — checks 1–3, 5, 7–21 pass, check 6 warns only at **98 hits across 45 files**, down from 107 across 46 because `METHODOLOGY.md` now lints clean; the pipeline fixtures pass; and `npm run build` emits **329 pages** with zero warnings. Check 16 completed its **browser layer** — PASS, not PARTIAL, under `.venv/bin/python`.*

*Two constants were flagged at the gate exit rather than papered over. **`SITE_URL` is resolved**: the local `.env` had been overriding it to `https://example.com`, so the harvest user agent identified every fetch as `+https://example.com/methodology` and `deploy.py` would have built its IndexNow `keyLocation` on a host the site does not own. Corrected by the user the same day and the suite re-run whole against it. **`SITE_CONTACT_EMAIL` is not**, and it carries forward below.*

*Three things are worth carrying forward:*

1. ***`SITE_CONTACT_EMAIL` is the last Wave 2 placeholder still live**, at `hello@example.invalid`. It sits in `site/src/config.ts`, not in `.env`, so an env change does not reach it. The footer publishes it as a working `mailto:` and the methodology page tells producers to "write to us at the contact address on this site" — which is the page whose entire job is to be answerable, and the address goes nowhere. `Organization.email` is emitted conditionally and is therefore currently absent, so nothing machine-readable asserts it; the reader-facing half still does. CONSTANTS-REQUIRED.md §2.4's never-guess rule governs it exactly as it governed `SITE_NAME`, so it needs a decision rather than a default.*
2. ***Nothing watches the `.env` override against the mirror.** Check 13 proves `config.ts` and `admin/config.py` agree, but it compares the Python *default literal* — `.env` wins at runtime and no check reads the result. The disagreement had been live for an unknown period and was found only because check 19's self-test happened to build fixture URLs from `SITE_URL` and behaved oddly. Check 19 now reads the origin from `dist`'s own canonical, which makes that check immune but watches nothing: the gap is still open, and it is the shape of defect that reaches production silently because every local surface looks right.*
3. ***The editorial lint's blind spot grew.** Gate 9 recorded that check 6 does not lint Astro copy. Gate 10 added more prose outside it: `llms.txt` carries several paragraphs authored in a TypeScript endpoint, and they are the paragraphs a model will read and repeat about what `independent` means here. Nothing lints them for banned words, em dashes or Australian spelling. Gate 11's blog copy lands inside check 6; this does not.*

### Gate 11 — Blog & editorial pipeline
Hand-authored blog collection plus the editorial agent chain (`article_brief` → `article_draft` + `house_voice` → `factcheck`), preserving the adversarial split: the fact-checking model is deliberately **not** the drafting model reviewing itself. Drafting models are poor judges of their own confabulation.
**Done when:** a post drafts, fact-checks and stages end to end; the fact-check demonstrably deletes a deliberately inserted false claim from a fixture; no published post contains a hardcoded figure that should be a data component; every post's body passes the banned-word and Australian-English lint.

### Engagement 2026-08-09 — carried-over defects from Gates 3 and 5

Appended after Gate 7 passed all four done-conditions. **Scope contract: the four defects and one deferred integration named below, and nothing else.** None is a Gate 7 regression; all were found while exercising Gate 7, against gates that had already closed. They are fixed here, in a dated block, rather than silently inside a gate that did not own them. **Gate 8 does not open until this block closes.**

1. **(C) The review pane rendered `<Pull>` and `<TippedPhoto>` as raw markup.** `mdx_preview.py` wrapped finished HTML in `<<<`/`>>>` sentinels and trimmed three characters from each end, but the emitted string let the tag's own angle brackets double as sentinel characters. The trim took the `<` off the opening tag and the `>` off the closing one. A Gate 3 defect: every draft reviewed since has had its pull-quotes judged through broken markup.
2. **(B) A Cloudflare 403 could not reach the Playwright fallback from the hub.** `offer_playwright` was set only on `ThinExtraction`. UX.md §1.5 row 1 defines no retry for a failed fetch, so the code was a correct reading of the spec and **the false statement was SEED.md §2's, that d'Arenberg exercises the user-triggered Playwright path end to end through the hub.** Resolved by amending UX.md §1.5 with a new row 1a, scoped to 403 and 503 — the statuses a browser fetch can actually clear. A timeout, a 404 and a 500 still offer nothing, because a retry that cannot work is worse than no retry at all.
3. **(D) `networkidle` is the wrong Playwright wait condition here.** It cannot fire on a page holding a connection open, which includes anything streaming server-sent events, and it stalls behind slow third-party embeds. d'Arenberg needed two attempts for this reason.
4. **(E) `gemtree` appears in both `_staging` and `_rejected`.** Investigated and **deliberately left in place.** The `_rejected` copy is the 2026-08-08 07:54 rejection for unsubstantiated ownership; the `_staging` copy is a 15:43 re-harvest, which is the supported §1.5 row 7 path. The re-harvest rewrote the prose but the determination is byte-identical apart from `checked_at`: still `check`, all five signals unpopulated. The rejection reason therefore still stands and the draft is still correctly blocked from approval. Clearing the `_rejected` copy would delete the only record of why.
5. **IndexNow has never fired.** The ping and its skip-guard are implemented and verified; `INDEXNOW_KEY` is present in `.env` but empty, and nothing served the `{key}.txt` file that `deploy.py` declares as `keyLocation`. The key file is generated at build time, so it reaches `dist/` and never git: `site/public/` is outside `ALLOWED_PREFIXES`, and a key committed to satisfy the guard would be a token in version control.

**Done when:** the preview renders both components as HTML; a 403 offers the Playwright retry on the row while a timeout and a 404 do not, asserted in `/validate`; a Playwright fetch of a page holding an open connection returns rather than timing out; the IndexNow key file is emitted when a key is set and no route is generated when it is not; the full `/validate` suite and `npm run build` pass.

***CLOSED 2026-08-09.** All five done-conditions met. Check 20 (`validate_preview`) asserts both components render as balanced, sentinel-free HTML; the pipeline fixtures cover failure-table row 1a, so a 403 offers the retry and a timeout and a 404 do not; the Playwright wait moved off `networkidle`; the IndexNow key file is emitted at build time only when a key is set. Full suite green — checks 1–16 and 20 pass, `npm run build` emits 156 pages with zero warnings. Item 4 (`gemtree` in both `_staging` and `_rejected`) closed as deliberately-left-in-place, per the reasoning recorded above. Gate 8 opens.*

### Engagement 2026-08-09 (second) — the `unconfirmed` ownership state

Appended while Gate 8 was open, and it changes Gate 8's own done-condition, so it is recorded here rather than applied silently inside the gate. **Scope contract: the data-contract change named below, its four-surface propagation, its rendering, its methodology copy and its validators. Nothing else.** Gate 8 does not close until this block closes.

**The problem, measured.** Of 98 staged drafts: 16 are `clear` with a source and publishable; 29 are `check` carrying a dated `producer_statement`; **53 carry no `ownership_source` at all**, and 43 of those have not one extracted ownership signal. The three evidence routes were already recorded as unequally available (the note above, same date). The consequence is that the queue's largest bucket is not "producers we suspect" but "producers whose owner nobody publishes", and the contract had no state for that. It had `clear`, which claims a fact, and `check`, which blocks forever.

**The change.** A third published state. `ownership_status: confirmed | unconfirmed`, a new §1.15 closed vocabulary.

- `confirmed` — a dated source positively states who owns the business. `ownership_source` present, exactly as today. The site makes its independence claim for this entry.
- `unconfirmed` — no such source was found. `ownership_source` is null, the entry publishes, **and the entry itself carries a visible notice that the site has not confirmed its ownership.** The site makes no independence claim for it.

**Three rules that do not move**, because they are what stop this from being a quiet abandonment of the criterion:

1. **`parent_company` must still be null.** `unconfirmed` is ignorance, not tolerance. A documented parent is still a reject.
2. **A deny-list hit is never publishable as `unconfirmed`.** `unconfirmed` requires the register to be *silent* on name, domain and ABN. A credible attribution that merely lacks a registry confirmation is exactly the case `check` exists for, and it keeps blocking.
3. **The notice is not a footnote.** It renders on the producer entry and travels to every aggregation card, because a region page that lists unconfirmed entries without saying so is the misrepresentation this change exists to avoid.

**The honest cost, recorded because it will not be obvious later.** At the counts above this publishes 43 unconfirmed against 16 confirmed — roughly three quarters of the directory in a state where the site's central claim does not apply. That ratio was put to the user with the numbers, and the alternative that would improve it (stopping the Harvester's prose verdict from tightening a determination the deny-list and the signals both cleared, which would move 20 drafts to `clear`) was offered and not taken. If the ratio is later judged wrong, that is the lever, and it is a rule change rather than a data problem.

**Done when:** the four surfaces plus SCHEMA.md, both config mirrors and `mdx_preview.py` name-match on `ownership_status`; `schema_surfaces` exits 0; a fixture with `unconfirmed` and a non-null `ownership_source`, and one with `confirmed` and none, both fail with a field-level error; a fixture with a deny-list hit is refused approval in the `unconfirmed` state; check 8 passes against the expanded contract and fails against each of those fixtures; the notice renders on the entry and on an aggregation card, with JS disabled; the methodology page states what `unconfirmed` means and what the site does not claim for it; `npm run build` passes with zero warnings.

***CLOSED 2026-08-10.** All done-conditions met. Full suite green — checks 1–3, 5, 7–16 and 20–21 pass, check 6 warns only, the pipeline fixtures pass, and `npm run build` emits 158 pages with zero warnings. The corpus migrated to 49 `confirmed` and 53 `unconfirmed`; the four published files parse identical to their previous revision apart from the new field.*

*Three things are worth carrying forward, because each was found by a check rather than by reading:*

1. *The **pipeline's `silence` fixture** asserted the old contract — that a draft with no ownership statement cannot be approved. That block is now gone deliberately, so the fixture was rewritten to assert what still must hold: the verdict is `check` and not `clear`, the draft claims no `producer_statement`, the state is stamped `unconfirmed` explicitly rather than by an absent key, and a draft claiming `confirmed` on the same silent evidence is still refused. Silence is still not independence; it is recorded now instead of blocking.*
2. *The **fixture register held only `reject` records**, so nothing in it could exercise a rule about what a reviewer may do with a queued draft — a `reject` never reaches the queue. §2a rule 14 needed a `check`-verdict record, which is now in the fixture. Rule 14's self-test caught a real gap in the first `approval_blocks` implementation before it landed.*
3. *Check 1's **note-demotion tier is now unreachable** and reports zero notes, because the condition it existed to forgive — a designed pipeline output that could never publish — no longer exists. It is annotated in place, kept only for drafts harvested before this date, and goes when the queue holds none.*

### Engagement 2026-08-10 — `audit_exemptions`, and three latent defects the corpus exercised

Appended while Gate 8 was open. Item 1 changes the producer data contract and what `/validate` check 8 enforces, so it is recorded here rather than applied silently inside the gate. **Scope contract: the four items below, and nothing else.** Gate 8 does not close until this block closes.

1. **Check 8 could not be brought to green without unpublishing an independent producer.** Its standing re-audit re-ran the deny-list and reported every hit, never consulting the resolution a reviewer had recorded. `Riposte by Tim Knappstein and Son` contains the register label `Knappstein`; the hit is a contained match that `ownership.check_name` already floors to `check`, it was judged correctly at publish time, and the judgement lived in the determination sidecar, which is gitignored volume state and does not travel with the repository. Resolved with a new frontmatter field, `audit_exemptions` (SCHEMA.md §1.16, §2, §2a rules 15–17), propagated across the four surfaces plus SCHEMA.md and both config mirrors in one commit. **An exemption is a judgement about a register state, never a waiver on a name**: it is honoured only while `parent` and `register_updated` still match the live record, so buying the exempted producer invalidates the exemption rather than being hidden by it.

2. **Check 16's browser layer could never finish.** `validate_render.py` navigated with `wait_until="networkidle"`, which timed out at 30s on the first page holding a connection open. This is the closed 2026-08-09 engagement's defect (D), fixed then in `fetcher.py` and missed here. It went unnoticed because the layer **skips silently when Playwright is unavailable**, and the suite had been run with the system interpreter rather than `.venv`, which reported PARTIAL and exited 0. Ported the fetcher's pattern: navigate on `domcontentloaded`, then give `networkidle` a bounded `PLAYWRIGHT_SETTLE_MS` budget and take whatever has rendered. The constant is imported from `fetcher.py`, not re-declared.

3. **`/producer/[slug]/` built every subregion href under `primary_region`.** Grosset is the first published producer whose subregions belong to a *secondary* region, so it linked to `/region/clare-valley/lenswood/`, a route that was never generated. Now reads the parent from `Subregion.region`, which the register documents as "exactly one, always". A Gate 6 defect that no corpus before this one could reach.

4. **Check 16 flagged the head `rel="prev"`/`rel="next"` links as external resource requests.** Its `<link>` allow-list carried `canonical` and `alternate` only. No browser fetches a rel=prev/next; it is a statement about sequence. Gate 6 verified pagination by temporarily setting the page size to 1 and deliberately added no fixture, so the first real multi-page build was the first time this check had ever seen one.

**On the sidecar, recorded because the instruction was to strip it entirely.** Check 8 retains exactly one sidecar read, `_determination_abn`. SCHEMA.md §2 has no ABN field by design, so there is nowhere in published record to read one from, and removing the read would silently drop the third of the deny-list's three paths for every published producer, against Gate 4's done-condition that name, domain and ABN each work independently. The resolution path is fully off the sidecar; the ABN is not, and the function's docstring says why. Moving it would need the ABN to become published record first, which is a further contract change and is not taken here.

**Done when:** check 16's browser layer completes across every built page; `audit_exemptions` name-matches across the four surfaces, SCHEMA.md and both config mirrors, and `schema_surfaces` exits 0; fixtures carrying a stale `register_updated`, a wrong `parent`, a `check` other than `name`, and an exemption on an `unconfirmed` entry each fail with a field-level error; an exact, domain or ABN match is provably unexemptable in the self-test; a live exemption is reported as a note rather than swallowed; the methodology page states what an exemption requires and that it expires; the full `/validate` suite and `npm run build` pass.

***CLOSED 2026-08-10.** All done-conditions met. Full suite green — checks 1–3, 5, 7–16 and 20–21 pass, check 6 warns only, the pipeline fixtures pass, and `npm run build` emits 311 pages with zero warnings. Check 13 reports 42 fields. Every new constraint was verified by deliberate violation rather than by reading: a stale `register_updated` and a wrong `parent` each fail check 8 with a named reason, and `check: domain` and an exemption on an `unconfirmed` entry each fail the build with a field-level error.*

*Two things are worth carrying forward:*

1. ***The interpreter is load-bearing when running the suite.** Under the system `python3`, check 16 reports PARTIAL and exits 0 because Playwright is not importable there, so the suite looks green while its browser layer has never run. That is how a 30-second navigation timeout survived across four gates. Run `/validate` with `.venv/bin/python`. The silent-skip behaviour is deliberate and stays — a check that says it did not run beats one that quietly degrades — but PARTIAL must be read as "not verified", not as a pass.*
2. ***Three of the four defects here were latent for gates and were exercised by the corpus, not by a code change.** The subregion href needed the first producer whose subregions sit under a secondary region; the `rel=prev/next` allow-list needed the first genuine multi-page series; the browser layer needed a page holding a connection open. Gate 6 verified pagination by temporarily setting the page size to 1 and deliberately added no fixture, reasoning that Gate 8's coverage would exercise it for real. That reasoning was right, and the cost is that the defects surfaced together, two gates later, in a check that had been reporting green.*

### Engagement 2026-08-12 — the brand name, and a dateline that printed its region twice

Appended while Gate 8 was open. Neither item is a Gate 8 regression; the first is a decision the build has been carrying as a placeholder since Wave 2, and the second is a Gate 6 rendering defect that only Gate 8's corpus could surface. **Scope contract: the two items below, and nothing else.** Gate 8 does not close until this block closes.

1. **`SITE_NAME` is decided: `winelister`.** Signed off 2026-08-12. It had been `SITE_NAME_PENDING` since Wave 2 under CONSTANTS-REQUIRED.md §2.4's rule that the brand name is undecided and **must never be guessed**. That rule is now discharged rather than relaxed, and §2.4 is annotated in place. The value is recorded verbatim as given, lowercase included, and the casing is decided in `config.ts` alone — no call site re-cases it. `admin/config.py` does not mirror `SITE_NAME`: it mirrors `SITE_URL` because the fetcher and the deploy strip need it, whereas the name is display-only and the site is its sole consumer. Check 13 passes unchanged, which is the assertion that the mirror is still exact.

2. **Two dateline builders printed the same locality twice.** `ProducerEntry.astro` composed `[suburb, state, primary_region]` and `/producer/[slug]/` composed `[suburb, state, primary_region, ...subregions]`, neither with a dedupe. A producer in the town of McLaren Vale, inside the McLaren Vale region, rendered `McLaren Vale · South Australia · McLaren Vale`; a producer in the town of Dromana, inside the Dromana subregion, rendered `Dromana · Victoria · Mornington Peninsula · Dromana`. 82 card instances across 14 producers in the two regions whose principal town carries the region's name, plus 9 producer pages colliding on a subregion. The comparison is on the **rendered names**, not the slugs, because a register entry whose name and slug differ would slip a slug comparison; the page checks the region and every listed subregion, the card only the region, because only the page prints subregions.

   *The subregion half was found by looking at a screenshot after the region half had been fixed, committed and reported clean. The scan that reported it clean used `[^<]+?` to read the dateline, which stops at the first tag — and the producer page, alone, wraps its region in an `<a>`. **A check whose regex cannot see the markup it is checking reports zero and means nothing.** The replacement strips tags first, scans all 703 datelines rather than the ones that happen to be flat, and asserts a positive control: Grosset must keep `Lenswood · Piccadilly Valley`.*

   **Flagged, not resolved (CLAUDE.md rule 3).** UX.md §452 specifies the producer-page dateline as "the primary region, the state and the category, as words", three components with no suburb and no subregion. The implementation prints five. DESIGN.md §15's herbarium framing wants "the collector's date and locality beside it", which reads the other way. Both are interface documents, so precedence does not separate them. The dedupe above is orthogonal to that disagreement and does not settle it; removing the locality outright would change every producer page and is a call for the user, not a side effect of a redundancy fix.

**A third thing was found while verifying, and is recorded because it invalidates a green run.** Mid-session, `~/.cache/ms-playwright` came to hold `chromium-1234` while the pinned `playwright==1.48.0` expects `chromium-1140`, and check 16 went from PASS to **PARTIAL, exit 0**, between two runs against the same corpus with no code change. This is the 2026-08-10 block's carried-forward note number 1 happening for a second time and by a second route: the first was the wrong interpreter, this was a browser cache moving underneath the right one. The silent-skip behaviour stays — a check that says it did not run still beats one that quietly degrades — but PARTIAL must be read as "not verified" every time, and a gate exit that reads PARTIAL as green has verified nothing.

**Done when:** no built page renders a dateline that repeats any component, asserted by a scan that strips tags before reading and that carries a positive control proving distinct localities survive; `SITE_NAME_PENDING` appears nowhere in `dist/`; CONSTANTS-REQUIRED.md §2.4 is annotated in place; check 13 exits 0; check 16 completes its **browser layer** rather than reporting PARTIAL; the full `/validate` suite and `npm run build` pass.

***CLOSED 2026-08-12.** All six done-conditions met. The dateline scan read 703 datelines across 186 built pages with tags stripped first, and found zero repeats; Grosset held the positive control at `Lenswood · Piccadilly Valley`. `SITE_NAME_PENDING` has no occurrence in `dist/` and the pages render `winelister`. CONSTANTS-REQUIRED.md §2.4 is struck through in place with the dated decision. Check 13 exits 0 at 42 fields. **Check 16 completed its browser layer** — PASS across all 311 pages, not PARTIAL. Full suite green: checks 1–3, 5, 7–16 and 20–21 pass, check 6 warns only at 107 hits across 46 files, the pipeline fixtures pass, and `npm run build` emits 311 pages with zero warnings. The corpus stands at 97 published — 33 Adelaide Hills, 17 McLaren Vale, 19 Yarra Valley, 24 Mornington Peninsula and 4 elsewhere by primary region — with an empty staging queue, 4 rejected, 48 `confirmed` against 49 `unconfirmed`, and zero non-null `parent_company`.*

*Item 2's flagged spec conflict is **now settled** rather than left open (`3e94a8c`). UX.md §452's three-component dateline is amended in place in DESIGN.md §15's favour: the herbarium framing asks for "the collector's date and locality beside it" by name, and it is load-bearing across the design, where the three-component form was the more generic statement. No code changed. **Gate 8's own closure is a separate decision and the gate stays open until it is taken.***

*Three things are worth carrying forward:*

1. ***The dateline scan was deliberately not mechanised**, decided 2026-08-12 after the alternatives were put with their costs. It was verified by deliberate violation — a repeat injected inside the `<a>`-wrapped region made it exit 1 naming the file, the dateline and the component, and the fixture was restored — but it lives outside the repository and **nothing watches the dateline from here**. Recorded plainly because this is the same shape as the defect it was written for: that one was reported clean by a scan whose regex could not see the markup it was checking. The difference is that this is a known gap rather than a false green. If a third dateline builder is ever added, it inherits no guard.*
2. ***Check 16's PARTIAL trap has now fired twice by two different routes** — the wrong interpreter, then a browser cache moving underneath the right one. This run passed with `~/.cache/ms-playwright` holding both `chromium-1140` and a stray `chromium-1234`, under `.venv/bin/python`. The rule stands and is worth restating: run the suite with `.venv/bin/python`, and read PARTIAL as "not verified" every time.*
3. ***The dateline has no upper bound**, because subregions are unbounded. The longest in the corpus is nine components (`aphelion`, five subregions); the amended §452 documents six component *kinds*, which is not the same as six components. Anything that lays out or truncates a dateline should be sized against the nine, not the six.*

## Working style

Small commits per logical unit within a gate, imperative messages, gate-prefixed (`Gate 4: …`) so the boundary stays greppable. No drive-by refactors. **Each new `/validate` check lands as its own commit, right after the feature it guards.** When a screenshot is possible, take one before claiming visual work is done. When you are unsure whether something meets DESIGN.md, it doesn't — ask.

Two documentation habits, both ported from the reference:

- **Superseded rules and gates are annotated in place with a date, never deleted.** "Shipped and closed before that revision; its done-condition stands as history, not a live requirement."
- **New engagements are appended as a dated block** with an explicit scope contract, sequenced and blocking exactly like the original gates.

## Editorial guardrails

The banned-word list, the em-dash ban, the not-X-but-Y ban and the hedge-word ban live in `PROMPTS/gatekeeper.md`, which is their single authored home; `PROMPTS/architect.md` carries the four bans as rules the drafting stage writes to, and `.claude/skills/producer-entry` **references** them rather than restating them. They apply to anything a reader sees, including the admin UI and FAQ answers.

*Amended 2026-08-07 (Gate 5): this previously said the lists were "mirrored into" the skill. They are not, and should not be. `/validate` check 6 parses the fenced blocks in `PROMPTS/gatekeeper.md`, so there is exactly one copy of every list and it is the copy the Gatekeeper is actually run with. A second hand-kept copy in a skill file would drift with nothing watching it, and the first symptom would be a lint passing copy the model was never told to avoid.*

Two rules worth restating here because they are specific to wine and easy to get wrong:

- **No unsourced tasting descriptors.** "Notes of…" only if the note is in the source facts. Nobody here has tasted anything.
- **No claim of certification without a named certifier**, and no use of `single-vineyard`, `old vines`, `family-owned` or `award-winning` unless the vineyard, the vine age, the ownership or the specific award is stated in the source.
