---
description: Gate-exit validation suite. Runs every check the build has landed so far and reports pass/fail.
---

# /validate

This command must pass clean before any gate is declared done and before any deploy.

**Report only. Do not fix anything during this command.** If a check fails, report it with enough detail to act on and move to the next check. Fixing is separate work, done after the report, followed by a re-run.

Checks land with the gate that needs them, each as its own commit right after the feature it guards. Checks below are annotated with the gate that introduces them; a check whose gate has not yet shipped is skipped and reported as `n/a`.

## Output contract

A summary table — check number, name, result, details — then the word **VALIDATE PASS** or **VALIDATE FAIL** on its own line.

`VALIDATE PASS` requires every applicable check to pass. Warnings (check 6) do not fail the suite, but every hit must be listed with file and line so a human can judge it.

---

## Core checks (Gate 1–2)

### 1. Schema validation — *G1*
Every MDX file in `site/src/content/producers/_published/` **and** `content-staging/_staging/`: parse the frontmatter and validate against the SCHEMA.md §2 contract. Required fields present; types correct; enums drawn from the §1 vocabularies; `location.state` present; AU coordinate bounds when latitude/longitude are non-null; `summary` ≤160 chars; `practices` object strict with exactly the four keys; `image` co-requirements (`image_source`, `image_caption`).

Also assert the §2a cross-field rules that zod owns: certifier co-requirements (2, 3), `primary_region` ∈ `regions` (4), `shop_url` when `buy_online` (6), `cellar_door_hours` absent when `cellar_door: none` (7).

Report per file, per field. Any failure = fail.

### 2. Slug integrity — *G1*
No duplicate slugs across `_staging` + `_published`. All filenames kebab-case. Slug is never a frontmatter field.

### 3. Derived-data freshness — *G2*
Regenerate the SQLite DB and the derived JSON to a temp location and diff against what is committed. Any drift = fail — it means someone edited published content without re-running approve or rebuild.

Then run the rebuild twice and confirm the two outputs are byte-identical. A non-idempotent rebuild is a fail even when the diff against committed is clean; it usually means a child-table rebuild is insert-only rather than delete-then-insert.

### 4. Astro build — *G1*
`cd site && npm run build`. Zero errors, zero warnings.

### 7. Repo hygiene — *G1*
`git status` and `git ls-files` must show no tracked files under `temp_data/`, `content-staging/`, or any `.env` other than `.env.example`. Tracked = fail. Check `git ls-files` specifically, not just `git status` — a force-added file shows as clean in status.

### 6. Register lint — *G5*
`python3 -m admin.pipeline.validate_register`.

Greps every `_published` body, plus `summary` and the FAQ answers, for the banned-word list, the hedge list, tasting descriptors, first-person visit tells, not-X-but-Y, em dashes and US spellings. **Warnings, not failures** — a human judges them — but every hit is listed with file and line, and the module's self-test must pass.

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

---

## Checks pending their gate

Listed here so the suite's shape is visible from the start. Each lands as its own commit at the gate named. Until then, report `n/a — lands at Gate N`.

| # | Check | Gate |
|---|---|---|
| 5 | ~~**Link check**~~ — **SHIPPED 2026-08-08 at Gate 6.** Moved to the core section above; row kept so the numbering stays readable | G6 |
| 6 | ~~**Register lint**~~ — **SHIPPED 2026-08-07 at Gate 5.** Moved to the core section above; row kept so the numbering stays readable | G5 |
| 8 | **Ownership determination** — no producer published without `ownership_source` carrying a non-empty source and a date; **no producer published with a non-null `parent_company`**; zero hits when every published name, domain and ABN is checked against the `data/ownership.json` deny-list | G4 |
| 9 | **Certification integrity** — `organic: certified` without a named `organic_certifier` fails; same for `biodynamic`. A certifier named while the state is not `certified` also fails | G4 |
| 10 | **Numeric cross-checks** — every `tasting_fee.fee_aud` falls within the range of dollar amounts stated in the freeform `cost` string; `annual_production_cases`, when present, falls inside `production_band` | G4 |
| 11 | ~~**Glossary coverage**~~ — **SHIPPED 2026-08-08 at Gate 6.** Moved to the core section above | G6 |
| 12 | ~~**Region taxonomy lint**~~ — **SHIPPED 2026-08-08 at Gate 6.** Moved to the core section above | G6 |
| 13 | **Four-surface schema diff** — `python3 -m admin.pipeline.schema_surfaces` exits 0. SCHEMA.md §2 table, the zod schema, `admin/schema.py`'s `KNOWN_FIELDS` and the SQLite DDL name-match exactly; child tables exist for every array field; the prompts and `mdx_preview.py` describe the structured fields | G2 |
| 14 | **Provenance integrity** — every populated `VERIFIABLE_FIELDS` entry carries a `{source, tier, date}` record; no tier is lower than the same field's tier in the previous commit | G4 |
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
