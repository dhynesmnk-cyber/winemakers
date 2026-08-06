# HANDOVER — session state as at 2026-08-07 (Wave 2 close)

**This is session state, not specification.** It records where the build got to and what happens next. Update it at the end of a working session, or delete it once the gates are underway and `CLAUDE.md` carries the whole story. Do not cite it as a source of truth: the five specification documents outrank it in every case.

---

## Where things are

| | |
|---|---|
| **Repo** | `/home/dhynesmnk/winemakers` — own git repo, branch `main`, no remote yet |
| **Reference** | `/home/dhynesmnk/Bathers'/` — **READ-ONLY.** Quote every path; the folder name has an apostrophe |
| **Approved plan** | `/home/dhynesmnk/.claude/plans/handover-independent-wise-hickey.md` |
| **Original brief** | The handover document pasted into the first session. Superseded by the plan and the five docs |

`$HOME` is itself a git repo (`origin: kittys-pickles.git`), so `winemakers/` is a nested repo inside it, exactly as `Bathers'` is. That is intentional. Do not `git add` from `/home/dhynesmnk`.

## What the project is

A field guide to independent Australian winemakers. Free to use, no ads, no sponsored listings. One producer profile per independent winemaker or label, route `/producer/[slug]/`. Wines are attributes, not pages.

The word doing the work is **independent**. It is the inclusion criterion, the editorial position, and the reason the site exists.

## Status

**Wave 0 — closed.** Data contract frozen, operating instructions written, gate-exit tooling in place before Gate 1 opens.
**Wave 1 — closed.** Five specification documents, conflict list empty.
**Wave 2 — closed 2026-08-07.** Region spine, ownership deny-list, glossary and design assets. Six conflicts found; all six resolved at the close, four of them by amending `SCHEMA.md` and `DESIGN.md` in place with dated notes. See the decision table below and `CONSTANTS-REQUIRED.md` §4.
**Gate 1 — in progress.** Approved to begin at the Wave 2 close.

```
521ed1e  Wave 2: ownership-check skill and data-curator agent
0e5a1eb  Wave 2: the 44-glyph icon set, colour tokens and the fauna registry
51f29b5  Wave 2: glossary entries for every §1 vocabulary
0597d14  Wave 2: seed the ownership deny-list
8218335  Wave 2: the Australian GI register
d688712  Add HANDOVER.md — session state for a fresh window
b3bb73a  Wave 1: TRD, UX, DESIGN and the support pack
4e649c8  Wave 0: close out the vocabulary sign-off
a9de8fe  Wave 0: data contract, operating instructions and gate-exit tooling
```

### Committed so far

```
CLAUDE.md      126 lines   operating instructions, 9 prime rules, gates G1–G11
SCHEMA.md      524 lines   14 vocabularies, 38-field frontmatter table, DDL, independence system
TRD.md         390 lines   fixed stack, repo structure, out-of-scope with rationale
UX.md          619 lines   admin hub, independence review flow, region-first public site
DESIGN.md      634 lines   visual spec, --vine / --claret tokens, icon inventory, fauna brief
README.md       81 lines   feed order for a cold session, file map
SEED.md        109 lines   6 verified fixture producers, one per failure mode
.env.example              environment contract, one block per concern
.claude/       skills: schema-change, gate-exit · agents: schema-guardian · commands: validate

WAVE 2
site/src/data/regions.ts        28 zones, 71 regions, 42 subregions — verified against Wine Australia
site/src/data/glossary.ts       121 entries, 13 vocabularies, zero orphans — carries the 58-variety seed set
data/ownership.json             22 owners, 164 labels, 103 domains, 1 verified ABN
site/src/icons/paths.ts         44 glyphs, DESIGN.md §6's inventory exactly
site/src/styles/tokens.css      the six tokens declared four times; contrast floor verified
site/src/icons/animals.ts       9 fauna keys; artwork not yet commissioned
Icons and logos/FAUNA-BRIEF.md  the illustrator's commissioning brief
CONSTANTS-REQUIRED.md           Wave 2 → Gate 1 handoff: decisions, flagged conflicts, gaps
.claude/       + skills: ownership-check · agents: data-curator
```

**Read `CONSTANTS-REQUIRED.md` before starting Gate 1.** It is the written list of
what the Wave 2 files need `config.ts` / `config.py` to contain, the decisions Gate 1
inherits, and how each of the six flagged conflicts was resolved.

### Doc precedence

**SCHEMA.md > TRD.md** for data. **UX.md / DESIGN.md > TRD.md** for interface. Flag any conflict either way, even when precedence resolves it.

### Naming, so it does not get confused again

- **Waves W0–W4** — build-time orchestration, who works when. Only in the plan file.
- **Gates G1–G11** — the sequential blocking build contract. In `CLAUDE.md`. This is the one that matters.

The original brief used `W1–W4` for both. It does not any more.

---

## Confirmed decisions

Do not re-litigate these. Each was put to the user and answered.

| Decision | Answer |
|---|---|
| Repo location | New directory, own git repo. `winemakers` is a working name; the repo name is **not** the brand |
| **Independence rule** | **Strict.** Any corporate ownership blocks publication, including minority stakes and multi-label family groups. `parent_company: null` is the only publishable value |
| Ownership evidence | **Any one of three** — registry lookup, producer's own published statement, or a named trade source. Must *positively state* ownership; silence is not evidence of absence. Registry wins on conflict |
| Hosting | Netlify (site) + Fly.io (admin) + GitHub as transport. Ported from the reference as-is |
| v1 coverage | **150–300 producers, region-deep** |
| Seed regions | **Adelaide Hills, McLaren Vale, Yarra Valley, Mornington Peninsula.** `regions.ts` still carries the full GI register |
| `cellar_door_hours` | Freeform string, not a per-day object |
| Site name | **Undecided.** `SITE_NAME` is a placeholder constant in `config.ts`. Never hardcode a guess. Avoid "Where We Pour" |
| Deferred | Claim flow, Stripe, operator outreach, Google Places discovery. Each has its rationale in `TRD.md` §8 |

**On the strict rule.** The user chose it after being shown a control-vs-equity alternative, so it is settled. Its consequence is recorded in `SCHEMA.md` §4.1 and must stay visible: it excludes producers the trade universally calls independent — a maker with a 20% outside investor, one of four labels under a family group that is itself unowned. The methodology page therefore has to define the term *as this site uses it* rather than relying on a reader's assumption, and `ownership.json` has to seed family groups and minority holdings, not just outright portfolio ownership.

---

## Next task — Gate 1

Astro 5 SSG + Tailwind v4 per TRD §3, the `config.ts` / `config.py` hand-mirrored pair, the zod producer schema built programmatically from the tuples, the sample MDX in `_published`, the base layout, and `ProducerEntry` / `Pull` / `TippedPhoto` / `Icon` with real styles. Done-condition in `CLAUDE.md`.

**Start by reading `CONSTANTS-REQUIRED.md`.** Gate 1 owns `config.ts` and `config.py`, and that document is the list of what Wave 2's files need them to contain, plus the decisions Gate 1 inherits.

Three things in the done-condition already have material waiting:

- **The zod schema** builds its sub-schemas from the tuples (SCHEMA.md §8). `VARIETY_KEYS` is settled: import `VARIETY_SLUGS` from `glossary.ts` rather than retyping 58 slugs.
- **The dual-mode token machinery** is written. `site/src/styles/tokens.css` is a standalone partial; fold it into `global.css`. Its hexes still need looking at on a real display before this gate closes, per DESIGN.md §2.
- **`Icon.astro`** reads `site/src/icons/paths.ts`, which is complete at 44 glyphs and exports `assertIconCoverage` for the build-time check that a value with no glyph fails the build.

---

## Wave 2 — CLOSED 2026-08-07. Kept as history, not a live requirement.

Four deliverables, no code dependency between them, so they can run in parallel. They need only the frozen vocabulary in `SCHEMA.md` §1.

| Deliverable | File it owns | Done when |
|---|---|---|
| **Regions** | `site/src/data/regions.ts` | Full Australian GI register — every registered GI, its zone, subregions, town lists. Every state has ≥1 region; every subregion belongs to exactly one region; the four seed regions have complete town lists |
| **Ownership** | `data/ownership.json` | Every major Australian portfolio owner seeded with labels, domains, aliases, ABNs, source, date. **Must also seed multi-label family groups and minority holdings** — the strict rule means those block too. No label under two parents |
| **Glossary** | `site/src/data/glossary.ts` | One explainer per value across every `SCHEMA.md` §1 vocabulary. Zero orphans in either direction |
| **Design assets** | `site/src/icons/paths.ts`, token block, fauna brief | Every icon key in `DESIGN.md` §6's inventory has a 24×24 stroke-only path using `currentColor` |

Also authored in Wave 2, because both must exist before Gate 4 opens:
- `.claude/skills/ownership-check/SKILL.md` — the §4 determination procedure and its evidence requirements
- `.claude/agents/data-curator.md` — maintains the three data files, validates against frozen enums, reports orphans

### The one rule that makes parallel work safe

**`site/src/config.ts` and `admin/config.py` are owned exclusively by the Gate 1 agent.** No Wave 2 agent creates or edits either. Deliver standalone files plus a written list of the constants you need to exist. `DESIGN.md`'s "Constants required" section is the model.

Sub-agents do not commit. They return file sets; the orchestrator integrates and commits in small gate-prefixed units.

---

## Open items

1. **The starter colour hexes are verified arithmetically and have still never been looked at.** Every text token clears 4.5:1 on both surfaces in both modes, reproducing DESIGN.md §2's table. §2 requires a look on a real display before Gate 1 closes, recorded as a dated note in `tokens.css`. Light `--ink-faded` clears by 0.18 on `--paper-raised` and is the value most likely to move.
2. **The fauna artwork has not been commissioned.** `Icons and logos/FAUNA-BRIEF.md` is the brief and is ready to send. `ANIMALS_AVAILABLE` is empty and every margin slot renders nothing until it is filled, which DESIGN.md §7's zero-image default already requires to look intentional.
3. **`ownership.json` needs re-verifying on a standing basis, not once.** Three records already moved under it: Stonier left Accolade in 2022, Knappstein left in 2025, and both would have been wrong rejections had Wave 2 not caught them. Vinarchy is cutting roughly 40% of its brands and Endeavour announced a Pinnacle restructure in May 2026. `/validate` check 8 re-checks every published producer against the file for exactly this reason.
4. **`logistics_vineyard_tours` is the weakest glyph in the set.** It reads at 32px and gets busy at 14px. DESIGN.md §10's rule applies: if you are unsure it meets the document, it doesn't. Put it in front of the Gate 1 design review.
5. **Two `SEED.md` gaps, both documented in that file.** No fixture proves a label-only producer with no cellar door and null coordinates publishes correctly — **Gate 5 must test this with a hand-written staging file** until one is found. And no négociant fixture, so the `negociant`/`garagiste` category split is untested.
6. **Site name.** Still open by design. It blocks nothing, but it will need answering before launch.
7. **Schema.org type.** `LocalBusiness` is retained. Moving to `Winery` or `FoodEstablishment` needs explicit sign-off and lands at Gate 10.

## Decided at the Wave 2 close, 2026-08-07

Eight questions were put and answered. Do not re-litigate these either.

| Question | Answer |
|---|---|
| `ownership.json` `verdict` field | **Kept and signed off.** `reject` blocks outright; `check` routes to human review and never auto-publishes. `SCHEMA.md` §4.3 amended to match, along with `category` and `abns` |
| Northern Territory vs `/validate` check 12 | **Keep the non-GI entry.** `registered_as: "none"`, stated in the data as not a Geographical Indication. Check 12 unchanged |
| The four spec inconsistencies | **All fixed in place, dated.** `SCHEMA.md` §2 cross-reference and §4.3 example; `DESIGN.md` §6's missing `OWNERSHIP_EVIDENCE_METHODS` row and its renumber |
| Minority-holding depth | **Coverage regions swept**, national sweep deferred. Genuine small stakes need registry lookups, not web reading |
| `au-places.ts` | **Dropped. Open item closed.** TRD.md §2.5's decline stands. The approved plan and TRD.md now disagree on the record; the plan file is still deliberately unedited |
| Glossary URLs | **Namespaced.** `/glossary/practice-wild-ferment/`. Gate 6 owns the route and may still override; `slug` is the only field that would change |
| Margin fauna | **Will be commissioned.** Gate 1 builds `MarginAnimal.astro` rendering nothing until `ANIMALS_AVAILABLE` is populated. Brief is ready to send |
| What follows Wave 2 | **Begin Gate 1**, then stop at its done-condition for approval before Gate 2 |

## Hazards

- **Monthly spend limit was hit on 2026-08-06.** Four Wave 1 sub-agents terminated mid-task. Three had already written their files; one had not. If sub-agents fail this way again, do the work inline — it is cheaper anyway, since a cold agent re-derives context this session already has.
- **The reference repo has stale text.** Do not copy blindly. Its `SCHEMA.md` prose says "nine" facilities while its DDL lists twelve; `Map.astro` was removed but its embedded-JSON idiom still powers search; its colour hexes were amended three times; `venues.json`/`venues.geojson` are vestigial, written by the admin and read by no page. `CLAUDE.md` catalogues these.
- **The reference's deploy guard has no automated test.** It was only ever exercised as a manual gate exit, unlike every later validator which carries `errors = _selftest() + run()`. That gap is closed deliberately as `/validate` check 15 at Gate 7. Do not port the gap.
- **`SEED.md` row 1 is Wolf Blass and must never publish.** It exists to be rejected. It names no parent company anywhere on its own site and reads as a standalone winery — only the deny-list catches it, by name, by domain, and by `ABN 55 004 094 599`. Seed `ownership.json` with all three before running Gate 4.

## Starting a fresh session

> Read CLAUDE.md, SCHEMA.md, TRD.md, UX.md and DESIGN.md, then read HANDOVER.md for where the build got to. Wave 0 and Wave 1 are closed; begin Wave 2.

Gate 1 does not open until Wave 2 closes — the glossary, the region spine and the ownership table are inputs to it.
