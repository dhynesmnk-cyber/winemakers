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

### Gate 9 — Comparison pages + internal-linking graph
Comparison registry with a minimum-producer threshold that **skips-and-logs, never fails**. Semantic `<table>`/`<caption>`/`<th scope>` markup plus `ItemList`. Internal-linking rules enforced as a graph check.
**Done when:** a page exists for every comparison clearing the threshold; the threshold demonstrably skips a deliberately thinned fixture rather than failing; every producer is linked from ≥3 aggregation pages; every comparison page is reachable from a hub; `/validate` check 17 passes with zero orphans.

### Gate 10 — Structured data, E-E-A-T & methodology
`LocalBusiness` + `BreadcrumbList` + `FAQPage` + `ItemList` + `DefinedTermSet`/`DefinedTerm` JSON-LD; offline structural validator folded into `/validate`; the methodology page live and linked; `llms.txt` generated as an endpoint rather than a static file that drifts.
**Done when:** JSON-LD passes the offline validator on 100% of page types; the methodology page states the independence rule plainly, **including what it excludes**, and is linked from footer and nav; `llms.txt` references only live routes; any move beyond `LocalBusiness` (e.g. `Winery`) is recorded as a dated TRD.md exception with explicit sign-off, or explicitly declined.

### Gate 11 — Blog & editorial pipeline
Hand-authored blog collection plus the editorial agent chain (`article_brief` → `article_draft` + `house_voice` → `factcheck`), preserving the adversarial split: the fact-checking model is deliberately **not** the drafting model reviewing itself. Drafting models are poor judges of their own confabulation.
**Done when:** a post drafts, fact-checks and stages end to end; the fact-check demonstrably deletes a deliberately inserted false claim from a fixture; no published post contains a hardcoded figure that should be a data component; every post's body passes the banned-word and Australian-English lint.

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
