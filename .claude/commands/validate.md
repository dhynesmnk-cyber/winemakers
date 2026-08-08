---
description: Gate-exit validation suite. Runs every check the build has landed so far and reports pass/fail.
---

# /validate

This command must pass clean before any gate is declared done and before any deploy.

**Report only. Do not fix anything during this command.** If a check fails, report it with enough detail to act on and move to the next check. Fixing is separate work, done after the report, followed by a re-run.

Checks land with the gate that needs them, each as its own commit right after the feature it guards. Checks below are annotated with the gate that introduces them; a check whose gate has not yet shipped is skipped and reported as `n/a`.

## Output contract

A summary table — check number, name, result, details — then the word **VALIDATE PASS** or **VALIDATE FAIL** on its own line.

`VALIDATE PASS` requires every applicable check to pass. Warnings (check 6) and notes (checks 1, 8 and 14) do not fail the suite, but every hit must be listed with file and line so a human can judge it.

---

## Core checks

### 1. Schema validation — *G1*
Every MDX file in `site/src/content/producers/_published/` **and** `content-staging/_staging/`: parse the frontmatter and validate against the SCHEMA.md §2 contract. Required fields present; types correct; enums drawn from the §1 vocabularies; `location.state` present; AU coordinate bounds when latitude/longitude are non-null; `summary` ≤160 chars; `practices` object strict with exactly the four keys; `image` co-requirements (`image_source`, `image_caption`).

Also assert the §2a cross-field rules that zod owns: certifier co-requirements (2, 3), `primary_region` ∈ `regions` (4), `shop_url` when `buy_online` (6), `cellar_door_hours` absent when `cellar_door: none` (7).

Report per file, per field. Any failure = fail.

*Amended 2026-08-08 (Gate 7): one message, in `_staging` only, is reported as a **note** rather than an error — an entirely absent `ownership_source`, and only when the determination sidecar exists and records a verdict other than `clear`.*

*The contract above is a publish-time one: no producer publishes without a dated source that positively states who owns the business (SCHEMA.md §4.2). A draft in the queue has not published. `orchestrator.py` deliberately leaves the field absent when the Harvester extracted no ownership statement, because `producer_statement` would then be the determination deciding itself from prose (CLAUDE.md rule 8) and there is no other honest route to a `method`; a reviewer records it from real evidence instead. Failing check 1 on that state would mean the suite could never pass while the queue held a `check` draft, which at Gate 8's coverage is permanent, and a check that always fails is a check nobody reads. That is the reasoning check 8 already records for its own advisory tier.*

*The demotion is narrow by design, and every boundary is asserted in the module's self-test. A malformed `ownership_source` still fails. A staging file with no sidecar still fails, so a hand-placed draft that simply forgot the field is still caught and Gate 3's done-condition keeps its backstop. A `clear` verdict missing the field still fails, because the orchestrator stamps it on `clear` and its absence there is a real fault. `_published` is untouched: there, an absent `ownership_source` is always an error. Approval is untouched too — `schema.validate_frontmatter` and `ownership.approval_blocks` both still refuse, which is what keeps this a reporting change and nothing more.*

### 2. Slug integrity — *G1*
No duplicate slugs across `_staging` + `_published`. All filenames kebab-case. Slug is never a frontmatter field.

### 3. Derived-data freshness — *G2*
Regenerate the SQLite DB and the derived JSON to a temp location and diff against what is committed. Any drift = fail — it means someone edited published content without re-running approve or rebuild.

Then run the rebuild twice and confirm the two outputs are byte-identical. A non-idempotent rebuild is a fail even when the diff against committed is clean; it usually means a child-table rebuild is insert-only rather than delete-then-insert.

### 4. Astro build — *G1*
`cd site && npm run build`. Zero errors, zero warnings.

### 7. Repo hygiene — *G1*
`git status` and `git ls-files` must show no tracked files under `temp_data/`, `content-staging/`, or any `.env` other than `.env.example`. Tracked = fail. Check `git ls-files` specifically, not just `git status` — a force-added file shows as clean in status.

### 13. Four-surface schema diff — *G2*
`python3 -m admin.pipeline.schema_surfaces`. Exit 0 required.

CLAUDE.md rule 7's enforcement. The zod schema, the SQLite DDL, the Harvester validator and the admin editor must name-match, plus the two places the contract is *written down* — SCHEMA.md §2's table and the hand-mirrored `config.ts`/`config.py` pair.

The failure it exists to catch is quiet: a field added to zod but not the DDL validates at build time, silently fails to reach SQLite, and every aggregation page then behaves as though no producer has it. Nothing errors; the site is just wrong.

The zod↔DDL comparison is not a set diff, because the surfaces are deliberately not the same shape — `location` is one zod object and five columns, `practices` a 1:1 wide table, `verification` in no table at all. Every field carries a declared disposition in `FIELD_DISPOSITION`, and the check asserts that disposition holds. **A field added to zod with no entry there fails as undeclared**, which is what forces an author to say where the data goes.

A surface whose gate has not shipped is reported as **pending, not passed**; every run prints which surfaces it compared and which it is still waiting on.

### 8. Ownership determination — *G4*
`python3 -m admin.pipeline.validate_ownership`.

No producer published without an `ownership_source` carrying a non-empty source and a date; **no producer published with a non-null `parent_company`**; zero hits when every published name, domain and ABN is re-checked against the `data/ownership.json` deny-list.

**The re-check matters as much as the first pass.** `ownership.json` grows. A producer published cleanly in March can become a deny-list hit in September because somebody bought them, and nothing else in the system notices. This is what turns the register from a gate a producer passes once into a standing audit of everything already published.

The ABN is read from the retained determination sidecar in `DETERMINATIONS_DIR`, not from frontmatter — an ABN is pipeline evidence, not published record, and SCHEMA.md §2 has no ABN field deliberately. A published producer with **no** retained determination is itself reported: UX.md §1.4.6 requires the sidecar to survive the approve, so a missing one means a producer reached `_published` by some route that bypassed the hub.

The self-test runs against a fixture register rather than `data/ownership.json`, so its guarantees hold whatever the real register happens to contain on the day.

### 9. Certification integrity — *G4*
`python3 -m admin.pipeline.validate_crossfield` (with check 10; one module, one command).

`organic: certified` without a named `organic_certifier` fails; the same for `biodynamic`. A certifier named while the state is **not** `certified` also fails.

Reads `_published` and `_staging` both — finding an unbacked certification claim after it has moved into `_published` is finding out too late.

An unbacked certification claim is a claim about a real business's legal standing, made in public, on a page that business did not write. It is the class of error that damages a producer rather than the site.

### 10. Numeric cross-checks — *G4*
Every `tasting_fee.fee_aud` falls within the range of dollar amounts stated in the freeform `cost` string; `annual_production_cases`, when present, falls inside `production_band`.

These are the SCHEMA.md §2a rules zod cannot see: they compare a structured number against a freeform string and against a config range. SCHEMA.md §2a puts them in Python specifically because **the regex that scrapes dollar amounts from the freeform string is shared with the display helper — one regex, one home.** That home is `admin/schema.py::dollar_amounts`, and this module calls it rather than writing a second one.

### 14. Provenance integrity — *G4*
`python3 -m admin.pipeline.validate_provenance`.

Every populated `VERIFIABLE_FIELDS` entry carries a `{source, tier, date}` record, and **no tier is lower than the same field's tier in the previous commit** (SCHEMA.md §2a rule 12, §2b).

The no-downgrade half is a rule about change over time, so it needs a previous state to compare against, and this project has exactly one durable record of previous state: git. The comparison is against `HEAD`, read with `git show`. A file not in `HEAD` is new and has nothing to downgrade from. **A repository with no commits, or an unavailable git, reports the fact and skips that half rather than passing silently** — a check that cannot run must never look like a check that passed.

Why a downgrade matters more than it looks: `observed_on_visit` and `operator_confirmed` are the two tiers this pipeline cannot generate — it only ever sets `published_by_producer` (SCHEMA.md §1.11). Those stronger tiers only ever arrive from a person who did the work, so a silent downgrade discards that work and replaces it with a machine's weaker claim. `parent_company` is on `VERIFIABLE_FIELDS` deliberately, and UX.md §1.4.6 makes its `{source, tier, date}` block the durable public half of the ownership determination. That is the entry this check exists for above all the others.

### 6. Register lint — *G5*
`python3 -m admin.pipeline.validate_register`.

Greps every `_published` body, plus `summary` and the FAQ answers, for the banned-word list, the hedge list, tasting descriptors, first-person visit tells, not-X-but-Y, em dashes, US spellings and conditional claims. **Warnings, not failures** — a human judges them — but every hit is listed with file and line, and the module's self-test must pass.

Every list is parsed from `PROMPTS/gatekeeper.md`, where they are authored. There is no second copy in Python: a lint that drifts from the prompt the Gatekeeper is actually run with would pass copy the model was never told to avoid.

`<Pull>` quotations are masked before matching. They are verbatim producer words, the Gatekeeper is told to leave them untouched, and a producer calling their own wine "plush" inside a marked quotation is a fact about what they published.

Also lints `METHODOLOGY.md`, which asked in its own text to be linted against this list once it existed.

### 5. Link check — *G6*
`python3 -m admin.pipeline.validate_links`. **Requires check 4 to have run**, because it reads `site/dist` rather than `src`: a route Astro decided not to emit looks fine in source and 404s in production.

Every internal href resolves to a built page; a producer page exists for every slug in the derived JSON and vice versa; every region/subregion/variety/practice page has ≥1 producer and every member with ≥1 producer has a page; no page links to a slug still in `_staging`; every `sitemap.xml` entry was built.

`PENDING_ROUTES` carries routes owned by a later gate — currently `/methodology/` (G10), `/blog/` and `/rss.xml` (G11) — with the gate that owns each. They are **printed on every run**, and the check **fails if one starts resolving while still listed**, so the list shrinks when a gate ships rather than permanently permitting a live route.

### 11. Glossary coverage — *G6*
`python3 -m admin.pipeline.validate_glossary`.

Both directions. `config.ts`'s `labelsFor` already fails the build on the forward direction (DESIGN.md §9); the reverse is what this earns its place on — an entry whose enum value was renamed or removed keeps its page and defines a term the schema no longer has. Also checks `see_also` targets resolve and every entry carries the term, short and definition its page renders.

`VERIFIABLE_FIELDS` is excluded, because it is a list of field names rather than a vocabulary of values. The exclusion is read from `COVERED_VOCABULARIES` in `glossary.ts` rather than decided here, and the self-test asserts an uncovered vocabulary is **not** required to be complete.

### 12. Region taxonomy lint — *G6*
`python3 -m admin.pipeline.validate_taxonomy`.

Every `primary_region` exists in `regions.ts` and is among that producer's `regions[]`; every `regions[]` member exists; every `subregions[]` member belongs to a region the producer lists; every state in `STATES` has ≥1 region. Region and subregion relationships are checked in both directions.

Reads frontmatter with `read_frontmatter`, not `parse_frontmatter` — a file failing check 1's schema bar must still have its regions checked rather than vanishing from this check's count.

### 15. Deploy-guard self-test — *G7*
`python3 -m admin.pipeline.validate_deploy`.

**A test, not an assertion.** Check 7 asserts that nothing illegal is tracked right now; this asks whether the guard *would refuse* if something were. Six fixture cases, each in a throwaway repository built as a bare origin plus a clone so `pull` and `push` behave as they do in production. `deploy.py` takes `root` and `site_dir` as parameters, so the fixtures drive the same functions the admin calls.

The central case force-adds **and commits** `temp_data/harvest_queue.json`, so `git status` reports a clean tree and only `git ls-files` knows it is there. That trap is asserted before the guard is tested against it.

Covers: a clean tree passing; the tracked `temp_data/` file; a tracked `.env` refused while `.env.example` is not; a changed path outside the publish set; `npm run build` failure blocking the push; and a happy path that commits and pushes only allowed paths. That last one is a positive control — without it every refusal case would also pass against a deploy that never worked at all.

`_poll_netlify` is the one patched boundary, because the fixture's commit will never appear in anyone's Netlify account. The two build-gate cases need `npm`; without it they are skipped, reported as a note, and the gate's refusing branch is exercised instead.

### 16. No-JS and reduced-motion render — *G1*
The built site renders correctly with JavaScript disabled: every producer, every programmatic route, and every navigation affordance is reachable. Under `prefers-reduced-motion: reduce`, every element renders fully visible in its final position. Any content that only appears after JS runs = fail.

### 20. Review-pane preview integrity — *engagement 2026-08-09*
`python3 -m admin.pipeline.validate_preview`.

Six bodies through `mdx_preview.render_body`, asserting three properties: tag balance in order, no `<<<`/`>>>` sentinel surviving into the output, and untrusted source prose arriving escaped rather than as live markup. Both components are asserted to actually render, so the check cannot pass on a renderer that emits nothing.

**Added against a defect that shipped at Gate 3 and survived four gates.** The sentinel was written inline at each call site and trimmed by a hardcoded three characters, so the tag's own angle brackets doubled as sentinel characters and the trim took the `<` off `<blockquote>` and the `>` off `</blockquote>`. Every pull-quote in the review pane rendered as raw markup. Nothing in the suite had ever looked at the preview's output, and the preview is the reviewer's only view of a draft before it publishes — a component that renders as text there is a component nobody is reviewing.

Two fixtures exist because of how the defect was possible rather than what it broke: one body carrying angle brackets in its own prose, because the sentinel and the payload were made of the same character, and one hostile body, because harvested prose is untrusted text rendered into the admin.

---

## Checks pending their gate

Listed here so the suite's shape is visible from the start. Each lands as its own commit at the gate named. Until then, report `n/a — lands at Gate N`.

| # | Check | Gate |
|---|---|---|
| 5 | ~~**Link check**~~ — **SHIPPED 2026-08-08 at Gate 6.** Moved to the core section above; row kept so the numbering stays readable | G6 |
| 6 | ~~**Register lint**~~ — **SHIPPED 2026-08-07 at Gate 5.** Moved to the core section above; row kept so the numbering stays readable | G5 |
| 8 | ~~**Ownership determination**~~ — **SHIPPED 2026-08-07 at Gate 4** (`41e9eec`). Moved to the core section above; row kept so the numbering stays readable | G4 |
| 9 | ~~**Certification integrity**~~ — **SHIPPED 2026-08-07 at Gate 4** (`4dabc02`). Moved to the core section above | G4 |
| 10 | ~~**Numeric cross-checks**~~ — **SHIPPED 2026-08-07 at Gate 4** (`4dabc02`, with check 9). Moved to the core section above | G4 |
| 11 | ~~**Glossary coverage**~~ — **SHIPPED 2026-08-08 at Gate 6.** Moved to the core section above | G6 |
| 12 | ~~**Region taxonomy lint**~~ — **SHIPPED 2026-08-08 at Gate 6.** Moved to the core section above | G6 |
| 13 | ~~**Four-surface schema diff**~~ — **SHIPPED 2026-08-07 at Gate 2** (`2bc90ad`). Moved to the core section above | G2 |
| 14 | ~~**Provenance integrity**~~ — **SHIPPED 2026-08-07 at Gate 4** (`c548dcb`). Moved to the core section above | G4 |
| 15 | ~~**Deploy-guard self-test**~~ — **SHIPPED 2026-08-08 at Gate 7.** Moved to the core section above; row kept so the numbering stays readable | G7 |
| 17 | **Internal-linking graph** — every published producer is linked from ≥3 aggregation pages; every comparison and region page is reachable from a hub; zero orphans. Pages below the minimum-producer threshold must skip-and-log, visible in the build output, never fail | G9 |
| 18 | **JSON-LD structural validation** — `Organization`, `WebSite`, `LocalBusiness`, `BreadcrumbList`, `FAQPage`, `ItemList`, `DefinedTermSet`, `DefinedTerm` across every page type | G10 |
| 19 | **`llms.txt` integrity** — references only live routes | G10 |

---

---

## Pipeline fixtures — *added at Gate 5, 2026-08-07*

`python3 -m admin.pipeline.validate_pipeline`. Exit 0 required.

Not a numbered check. It is the mechanised form of CLAUDE.md's Gate 5 fixture done-conditions, which name four things only deliberately broken fixtures can show: a bad URL and a malformed-JSON simulation failing per the UX.md §1.5 failure table, a ten-URL batch completing with per-URL failures isolated, and the Harvester's `independence: reject` aborting before a draft is written.

It is recorded here rather than left as a gate-exit ritual for the same reason check 15 exists: the reference implementation left its deploy guard covered only by a manual gate exit, and that is the one place the discipline lapsed.

Runs fully offline — scripted fake client, stubbed fetch, temp directories — so it works in a bare clone with no API key. Covers failure-table rows 1, 2, 3, 4, 5, 7, 8, 9 and 11, the certification downgrade, the token ledger and the Gatekeeper fallback.

---

## Pagination — verified at Gate 6, mechanised by data

Gate 6's done-condition includes "the homepage renders and paginates without loading the full dataset". At three published producers and `PRODUCERS_PER_PAGE` 24 no pager ever renders, so pagination was verified on 2026-08-08 by temporarily setting the page size to 1 and rebuilding:

- page 1 stayed at the bare route and `/producers/page/1/` was **not** emitted;
- pages 2 and 3 appeared under the `page/` segment, each with a self-referential canonical;
- `rel="prev"`/`rel="next"` were present in both the head and the pager anchors, and absent at the ends of the series;
- `, page 2` was appended to the `<title>` while the `<h1>` and the foreword stayed unchanged;
- check 5 passed against the paginated build: 151 pages, 151 sitemap entries, every page of every series listed.

**No permanent fixture was added, deliberately.** Check 5 already asserts that every `/page/N/` link resolves and every sitemap entry was built, so from Gate 8 onward — where four regions carry 150 to 300 producers — it exercises real multi-page series on every run with no special-case scaffolding. A fixture that existed only to manufacture a second page would be testing the fixture.

---

## The self-test pattern

This project has **no test framework** — no pytest, no CI. Instead each validator module carries its own fixture self-test that runs as part of the check itself:

```python
def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    ...

def main() -> int:
    errors = _selftest() + run()
```

This is what mechanises CLAUDE.md's "deliberately corrupted fixture" done-conditions: the regression fails the same command that runs the real check. Any new validator ships with one. Check 15 exists specifically because the reference implementation left its deploy guard covered only by a manual gate exit, which is the one place that discipline lapsed.
