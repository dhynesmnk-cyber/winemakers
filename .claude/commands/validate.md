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

*Amended 2026-08-13 (Gate 11): a **second, smaller comparison** for the post contract — SCHEMA.md §9.2, the zod `postFrontmatter` and `blog.py`'s `POST_FIELDS`. Deliberately not folded into the producer diff: a post has **two** consumers rather than four (§9.1 records why there is no SQLite table and no Harvester validator), and a shared diff would make every blog field look like a rule-7 field. It also diffs the claim-audit vocabulary against SCHEMA.md §9.4, so a third spelling of the three verdicts fails before it exists. The count is printed on every run, because a silent second comparison is one nobody knows ran.*

### 8. Ownership determination — *G4*
`python3 -m admin.pipeline.validate_ownership`.

No producer published without an `ownership_source` carrying a non-empty source and a date; **no producer published with a non-null `parent_company`**; zero hits when every published name, domain and ABN is re-checked against the `data/ownership.json` deny-list.

**The re-check matters as much as the first pass.** `ownership.json` grows. A producer published cleanly in March can become a deny-list hit in September because somebody bought them, and nothing else in the system notices. This is what turns the register from a gate a producer passes once into a standing audit of everything already published.

The ABN is read from the retained determination sidecar in `DETERMINATIONS_DIR`, not from frontmatter — an ABN is pipeline evidence, not published record, and SCHEMA.md §2 has no ABN field deliberately. A published producer with **no** retained determination is itself reported: UX.md §1.4.6 requires the sidecar to survive the approve, so a missing one means a producer reached `_published` by some route that bypassed the hub.

*Amended 2026-08-10.* A deny-list hit judged a false positive is cleared by an `audit_exemptions` entry in the producer's **frontmatter** (SCHEMA.md §2, §2a rules 15–17), never by the determination sidecar. The sidecar's `hits_to_resolve` still governs the *queue* and still blocks approval; it is gitignored volume state, so a resolution recorded only there does not travel with the repository, and a correctly judged surname collision failed this check forever with no route to green except unpublishing an independent producer.

An exemption is honoured only while `parent` and `register_updated` still match the live register record. If the record moves, the exemption is **stale** and the hit fails again — that is what keeps this a standing audit rather than a permanent waiver on a name. Exemptions that do apply are printed as **notes** on every run, so a suppressed hit stays visible.

Three things an exemption can never do, each asserted in the self-test: clear an **exact** name match, clear a **domain** or **ABN** match (rule 15), or accompany an `unconfirmed` entry (rule 16).

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

*Amended 2026-08-13 (Gate 11): published post bodies join it, plus their `title`, `summary` and `dateline`. UX.md §6 had said this check already did that; it read `PUBLISHED_DIR` and `METHODOLOGY.md` and nothing else, so the statement was intent rather than fact until the blog existed. `sources[].title` is deliberately exempt — it is what a source calls itself, and a register with `world-class` in its name is a fact about the register rather than this guide's register drifting. The self-test carries a fixture post asserting all four, so a field dropped from the lint fails here rather than silently ceasing to be checked.*

### 5. Link check — *G6*
`python3 -m admin.pipeline.validate_links`. **Requires check 4 to have run**, because it reads `site/dist` rather than `src`: a route Astro decided not to emit looks fine in source and 404s in production.

Every internal href resolves to a built page; a producer page exists for every slug in the derived JSON and vice versa; every region/subregion/variety/practice page has ≥1 producer and every member with ≥1 producer has a page; no page links to a slug still in `_staging`; every `sitemap.xml` entry was built.

`PENDING_ROUTES` carries routes owned by a later gate, with the gate that owns each. They are **printed on every run**, and the check **fails if one starts resolving while still listed**, so the list shrinks when a gate ships rather than permanently permitting a live route.

*It is now **empty**, which is the intended end state. `/methodology/` came off on 2026-08-13 (Gate 10); `/blog/` and `/rss.xml` came off the same day (Gate 11). All three are hard requirements like any other route. The mechanism stays — a future gate that links a route before building it adds an entry, and the check keeps biting.*

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

### 17. Internal-linking graph — *G9*
`python3 -m admin.pipeline.validate_graph`. **Requires check 4 to have run**, because it reads `site/dist`: a link that exists in a component but lands on a route Astro never emitted is not a link.

Every published producer is linked from ≥`MIN_AGGREGATION_LINKS` **distinct aggregation pages**; every comparison and region page is reachable from its hub; zero orphans.

The count is of distinct pages rather than of links, because `ProducerEntry` links a producer twice (name and thumbnail) and that is still one route to it. **Producer pages are excluded from the count on purpose** — a producer linking to a sibling is lateral movement, not an aggregation route, and counting it would let a cluster of cross-linked producers satisfy the rule while sitting off every listing.

Paginated state routes count. At the current corpus every state listing runs to several pages, and counting only page 1 reported 13 producers as under-linked on the first run. The other aggregation families carry their pager under a prefix already.

**The threshold half is checked by recomputing it, not by reading the log.** The skip-and-log behaviour lives in `comparisons.ts`, which is TypeScript. Parsing the build log would assert that a message was printed, not that the right pages exist, so the expected comparison set is recomputed from `producers.json` and `MIN_COMPARISON_PRODUCERS` and `dist` is asserted to hold exactly it. A threshold that stopped being applied shows up as an unexpected page; one applied too hard shows up as a missing one. `MIN_COMPARISON_PRODUCERS` is read from `admin/config.py`, which check 13 already proves mirrors `config.ts` exactly — that is what makes this a second *reading* of one rule rather than a second copy of it.

### 18. JSON-LD structural validation — *G10*
`python3 -m admin.pipeline.jsonld_validator`. **Requires check 4 to have run**, because it reads `site/dist`: a builder that is correct in TypeScript but never reaches a page has not shipped.

Offline, as the gate requires. No network call, no Rich Results request, no vendored schema.org vocabulary. `Organization`, `WebSite`, `LocalBusiness`, `BreadcrumbList`, `FAQPage`, `ItemList`, `DefinedTermSet` and `DefinedTerm` across every page type: required keys, absolute URLs, consecutive `position` values, and `@id` references that resolve.

**The half worth having is the agreement check.** A generic schema linter answers "is this well-formed?", which is the cheap half. `data/jsonld.ts` is written to the rule that nothing is asserted in structured data that the page does not show, because a field a reader cannot see is a claim nobody proofreads. So this check reads both: a `FAQPage` must carry exactly the question count the page renders and a page with no FAQ section must carry none; a `BreadcrumbList`'s names must be the visible trail's labels, in order; an `ItemList` must count the rows the page lists; a `LocalBusiness`'s `url` must be the page it is on. Structured data that drifts from its page does not announce itself, which is why the rule needs a mechanism rather than a convention.

**The honesty rule, mechanised.** `aggregateRating`, `review`, `priceRange` and `openingHours` fail anywhere in the graph. Nobody here has visited these cellar doors or tasted these wines (CLAUDE.md rule 6), so there are no ratings and no reviews to report; `priceRange` would be a guess; `openingHours` would be invented structure over `cellar_door_hours`, which is a freeform display string by schema design. These are exactly the four fields a well-meaning later edit adds because a rich-results guide recommends them.

**An unknown `@type` fails.** TRD.md §2 declined `Winery` for v1 with sign-off, and CLAUDE.md Gate 10 requires any move beyond `LocalBusiness` to be a dated TRD.md exception. A new type fails here until it is added deliberately, which is the prompt to go and write the exception first.

*Amended 2026-08-13 (Gate 11): **`BlogPosting` is the first widening of that set**, and the mechanism worked as designed — the build failed here until the exception was written into TRD.md §2.5. `Blog` as a type is still refused: the journal index is a listing and carries `ItemList`, like every other listing on the site. Its agreement rules are the same shape as the others: `headline` must equal the rendered `<h1>`, `datePublished` and `dateModified` must be dates the page prints, `citation` must count the sources printed at the post's foot, and `url` must be the canonical. Nine new self-test cases on their own post fixture.*

`@id` resolution is **site-wide, not per page**, because a cross-page reference is the point of an `@id`: a glossary term page belongs to a `DefinedTermSet` declared once on `/glossary/` rather than copied onto all 123 term pages.

Sixteen self-test cases, one per rule, each requiring the error to *name* the thing it broke — an error is not evidence if it fires for an unrelated reason.

### 19. `llms.txt` integrity — *G10*
`python3 -m admin.pipeline.validate_llms`. **Requires check 4 to have run**, because it reads `site/dist`.

Every link in `/llms.txt` is absolute, on this site, and resolves to a route the build actually emitted. The four standing links — methodology, glossary, region hub, producer index — are required by name, because a file that quietly stopped listing the methodology page would still pass a pure dead-link check, and that link is the one this file exists to hand over.

**Why this is not check 5's job.** Check 5 walks the internal hrefs in built HTML; `llms.txt` is plain text served outside the page graph, so nothing in check 5 has ever read it. The consequence differs too: a reader who follows a broken link sees a 404 and knows, whereas the reader of this file is a model that will repeat what the file says without being able to check it. A hallucinated route in a directory whose whole claim is documentary accuracy is worse than a 404.

**The one numeric claim is recomputed, not trusted.** The file states the ownership split in prose, because a model summarising this site without it reports every entry as independent, which is not what the site claims. That figure is recomputed from `producers.json` and required to match, and its disappearance is itself a failure.

**The origin is read from the build**, out of `dist`'s own canonical, rather than from `admin/config.py` — `.env` overrides `SITE_URL` at runtime, so `config.py` answers "what does this machine think the site is" rather than "what did this build emit". The self-test uses a fixed fixture origin for the same reason: a self-test that depends on the environment it runs in proves something different on every machine.

### 20. Review-pane preview integrity — *engagement 2026-08-09*
`python3 -m admin.pipeline.validate_preview`.

Six bodies through `mdx_preview.render_body`, asserting three properties: tag balance in order, no `<<<`/`>>>` sentinel surviving into the output, and untrusted source prose arriving escaped rather than as live markup. Both components are asserted to actually render, so the check cannot pass on a renderer that emits nothing.

**Added against a defect that shipped at Gate 3 and survived four gates.** The sentinel was written inline at each call site and trimmed by a hardcoded three characters, so the tag's own angle brackets doubled as sentinel characters and the trim took the `<` off `<blockquote>` and the `>` off `</blockquote>`. Every pull-quote in the review pane rendered as raw markup. Nothing in the suite had ever looked at the preview's output, and the preview is the reviewer's only view of a draft before it publishes — a component that renders as text there is a component nobody is reviewing.

Two fixtures exist because of how the defect was possible rather than what it broke: one body carrying angle brackets in its own prose, because the sentinel and the payload were made of the same character, and one hostile body, because harvested prose is untrusted text rendered into the admin.

### 21. Editorial-gate self-test — *G8*
`python3 -m admin.pipeline.validate_editorial`.

**A test, not an assertion**, on the same footing as check 15. Check 6 reports what the corpus says; this asks whether the approve action *would refuse* a draft carrying an absolute ban.

Seven fixture cases, one per blocking list, so a category dropped from `BLOCKING_LINT_KINDS` fails here rather than silently ceasing to be enforced. Also asserts that `summary` and the FAQ answers are linted and not the body alone, that a `<Pull>` quotation does **not** block, and that a `conditional claim` does **not** block.

**Added against a real failure of the model stage.** The Gatekeeper passed a draft using `curated` twice — ban 1 in `PROMPTS/architect.md`, a plain string on an enumerated list check 6 already matches perfectly. A model is the wrong instrument for a fixed list, so the enumerated bans became an approve-time gate using the same matcher, and the model budget stays on judgement the lists cannot express.

`conditional claim` is excluded by design: `single-vineyard`, `old vines`, `family-owned` and `award-winning` are permitted when the entry states their evidence, so whether a hit is a fault depends on the rest of the entry. Of thirteen hits in one real batch, seven were entries correctly naming the owning family or attributing the claim and reporting the gap. A gate that blocked those would teach a reviewer to route around it.

The staged drafts the gate currently refuses are printed on every run, as notes rather than failures — a draft in the queue has not published, and the gate is what stops it.

### 22. Blog integrity — *G11*
`python3 -m admin.pipeline.validate_blog`.

The three SCHEMA.md §9.3 rules zod structurally cannot see. The cover
co-requirements, the `updated` ordering, duplicate source URLs, the 160-character
summary bound and `.strict()` all fail `npm run build` with a field-level error
already, and are deliberately not restated here — a second implementation of a
rule is the one that drifts.

**The claim audit must resolve.** `data/factchecks/<factcheck>.json` exists,
parses, names the post it belongs to, and carries no claim in the `unsupported`
state. Publishing is blocked on an unresolved claim in the admin (UX.md §6); this
is the standing audit over what is *already* published, because a post can reach
`_published` by a route that is not the screen.

**A `removed` claim keeps its text verbatim.** UX.md §6: a deletion that leaves
no trace is indistinguishable from a claim that was never made. The record IS the
deletion, so an empty `text` on a removed claim fails.

**No hardcoded figures.** A numeral stating a count this repository holds is a
`<Figure>`, never typed prose. Nothing else catches this: a typed `97 producers`
renders perfectly, reads correctly, and is wrong after the next harvest with
nobody told.

*The typed-figure scan was wrong when it landed and the live corpus is what
showed it.* It required the countable noun adjacent to the numeral, so it read
straight past `97 independent Australian winemakers` while its fixture said
`97 producers` and passed — Gate 9's carried-forward note in a different
disguise, a fixture testing what it was written against rather than the shape of
the sentence people write. It now allows up to three modifiers between, excludes
determiners and copulas in the gap, and drops four-digit years when modifiers
intervene, so `in 2019 the region had` stays clean while `2000 producers` does
not. Both fixtures assert the boundary.

**It fails rather than warns**, unlike check 6. Register drift is a judgement a
human makes in context; a missing audit, an unresolved claim and a stale typed
count are each either true or not.

A self-review audit — one whose `model` equalled its `drafted_by` — is reported
as a **note**. The post is published and the audit says plainly that the drafting
model checked itself; failing would demand a re-check nobody can do
retroactively.

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
| 17 | ~~**Internal-linking graph**~~ — **SHIPPED 2026-08-12 at Gate 9.** Moved to the core section above; row kept so the numbering stays readable | G9 |
| 18 | ~~**JSON-LD structural validation**~~ — **SHIPPED 2026-08-13 at Gate 10.** Moved to the core section above; row kept so the numbering stays readable | G10 |
| 19 | ~~**`llms.txt` integrity**~~ — **SHIPPED 2026-08-13 at Gate 10.** Moved to the core section above; row kept so the numbering stays readable | G10 |
| 22 | ~~**Blog integrity**~~ — **SHIPPED 2026-08-13 at Gate 11.** Moved to the core section above; row kept so the numbering stays readable | G11 |

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
