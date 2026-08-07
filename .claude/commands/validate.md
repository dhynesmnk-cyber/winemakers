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

### 16. No-JS and reduced-motion render — *G1*
The built site renders correctly with JavaScript disabled: every producer, every programmatic route, and every navigation affordance is reachable. Under `prefers-reduced-motion: reduce`, every element renders fully visible in its final position. Any content that only appears after JS runs = fail.

---

## Checks pending their gate

Listed here so the suite's shape is visible from the start. Each lands as its own commit at the gate named. Until then, report `n/a — lands at Gate N`.

| # | Check | Gate |
|---|---|---|
| 5 | **Link check** — every internal href resolves to a built page; a producer page exists for every slug in the derived JSON and vice versa; every region/subregion/variety/practice page has ≥1 producer; no page links to a draft; **no dead programmatic routes** | G6 |
| 6 | ~~**Register lint**~~ — **SHIPPED 2026-08-07 at Gate 5.** Moved to the core section above; row kept so the numbering stays readable | G5 |
| 8 | **Ownership determination** — no producer published without `ownership_source` carrying a non-empty source and a date; **no producer published with a non-null `parent_company`**; zero hits when every published name, domain and ABN is checked against the `data/ownership.json` deny-list | G4 |
| 9 | **Certification integrity** — `organic: certified` without a named `organic_certifier` fails; same for `biodynamic`. A certifier named while the state is not `certified` also fails | G4 |
| 10 | **Numeric cross-checks** — every `tasting_fee.fee_aud` falls within the range of dollar amounts stated in the freeform `cost` string; `annual_production_cases`, when present, falls inside `production_band` | G4 |
| 11 | **Glossary coverage** — every enum value across every §1 vocabulary has a `glossary.ts` entry, and every glossary entry maps to a live enum value. Orphans in either direction = fail | G6 |
| 12 | **Region taxonomy lint** — every `primary_region` exists in `regions.ts`; every `regions[]` member exists; every `subregions[]` member belongs to a region listed in that producer's `regions[]`; every state in `STATES` has ≥1 region | G6 |
| 13 | **Four-surface schema diff** — `python3 -m admin.pipeline.schema_surfaces` exits 0. SCHEMA.md §2 table, the zod schema, `admin/schema.py`'s `KNOWN_FIELDS` and the SQLite DDL name-match exactly; child tables exist for every array field; the prompts and `mdx_preview.py` describe the structured fields | G2 |
| 14 | **Provenance integrity** — every populated `VERIFIABLE_FIELDS` entry carries a `{source, tier, date}` record; no tier is lower than the same field's tier in the previous commit | G4 |
| 15 | **Deploy-guard self-test** — a fixture proving the tracked-file guard *refuses* a staged illegal file, and passes a clean tree. **This is a test, not an assertion** — it must exercise the guard code, not merely restate the invariant check 7 already covers | G7 |
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
