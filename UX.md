# UX.md — Behavioural Specification

**DESIGN.md governs how things look. This file governs how things behave. Both are binding, and both outrank TRD.md on interface questions (CLAUDE.md rule 3). SCHEMA.md outranks this file on data questions; where this document names a field, it names the SCHEMA.md field, and any disagreement is a spec bug to be flagged, never silently resolved.**

**Failure states specified here are requirements, not suggestions. A silent failure is a bug against this document.**

Two conventions carried from the reference build (CLAUDE.md, working style): superseded rules are annotated in place with a date and never deleted; new engagements are appended as a dated block. This file starts clean, so it carries no dated annotations yet. The first revision adds one rather than editing a line away.

All copy specified here, including admin copy, is Australian English and obeys the editorial guardrails in `PROMPTS/gatekeeper.md`: no banned words, no em dashes, no not-X-but-Y, no hedges.

---

## 1. The Admin Control Hub

A single-screen local web app (FastAPI + Jinja2 + vanilla JS, no SPA framework). The screen is organised as a left-to-right pipeline that mirrors the actual workflow:

```
┌──────────────┬──────────────────────────────┬────────────────┐
│   HARVEST    │        REVIEW QUEUE          │   REVIEW PANE  │
│  URL input   │  (staging list, two chips    │   (selected    │
│  Batch queue │   per row: draft + owner)    │    draft)      │
│  Blocked     │                              │                │
├──────────────┴──────────────────────────────┴────────────────┤
│  PROGRESS (streaming log, full-width footer row)             │
├───────────────────────────────────────────────────────────────┤
│  DEPLOY (footer row, stacked directly below progress)        │
└───────────────────────────────────────────────────────────────┘
```

There is no discovery panel. Google Places discovery is deferred and out of scope for this build; seed URLs come from `SEED.md` and from the reviewer's own reading. There is no claim review screen, because there is no claim flow.

The streaming log and the Deploy strip together form one unified footer band running the full width of the window, log row on top of the Deploy row, so pipeline output stays visible whichever column has focus. The log is never nested inside the Harvest column.

The hub header carries the site name (from `SITE_NAME`, a placeholder until the brand is chosen), a link to the Blog screen (§6), and a link to `data/ownership.json` opened read-only in a viewer pane. The deny-list is edited in a text editor, never through the hub (§1.4.7).

### 1.1 Harvest panel

Two ways in, one runner.

- **Single URL.** A text input and a `Harvest producer` button. The button disables while a job runs; the input stays editable so the next URL can be queued mentally rather than mechanically.
- **Batch.** A textarea accepting one URL per line, up to `BATCH_MAX_URLS`, and a `Queue batch` button. Pasting the whole of `SEED.md`'s URL block is the expected use. Blank lines and lines that do not parse as an `http(s)` URL are dropped on submit and reported as a count (`3 lines ignored: not URLs`), never silently.

Batch harvest is required at this project's target coverage of 150 to 300 producers (CLAUDE.md Gate 8). It is not a convenience.

**Runner model.** One job at a time, serial, never concurrent. The batch queue is a server-held list, not browser state, so a forty-URL run survives a page reload, a closed tab and a restarted browser. Reopening the hub reattaches to the running job and replays the log buffer for the current item.

**Queue rows.** Each queued URL renders as a row: the URL (truncated from the middle, with the full value in `title`), its position, and a state:

| State | Meaning |
|---|---|
| `QUEUED` | Waiting. |
| `RUNNING` | The current job. One row at most is ever in this state. |
| `STAGED` | Finished, draft written. Shows the slug as a link that selects it while the draft is still in the review queue, and as plain text naming where the draft went once it is not (amended 2026-08-13, below). |
| `BLOCKED` | Stopped by the ownership determination before a draft was written (§1.4.4). Shows the reason in one line. |
| `FAILED` | Stopped by any other failure (§1.5). Shows the failing stage and the one-line reason. |
| `SKIPPED` | Not attempted: duplicate slug, or the reviewer skipped it. |

**Per-URL isolation is the rule of the batch.** Any failure of any kind ends that item and advances to the next one. A failed item never stops the run, never rolls back an earlier item, and never leaves a partial file in `_staging/`. A draft is written by a single atomic write at the end of the pipeline, so an aborted item leaves nothing behind.

**Queue controls.** `Pause after current` (finishes the running item, then stops with the rest still `QUEUED`), `Resume`, `Retry failed` (requeues every `FAILED` row, leaving `BLOCKED` rows alone, because a `BLOCKED` row is a determination and not a transient error), `Clear finished` (removes `STAGED` and `SKIPPED` rows from view; the drafts themselves are untouched). There is no `Clear all` and no way to delete a `BLOCKED` row from the UI; blocked records are history (§1.4.4).

**Queue summary line**, always present above the rows: `12 queued, 1 running, 7 staged, 2 blocked, 1 failed`.

**Amended 2026-08-13, signed off.** The `STAGED` row previously read ~~"Finished, draft written, now in the review queue. Shows the slug as a link that selects it."~~ That is a present-tense claim about a draft, made by a row that outlives it. The queue is durable across restarts by design, and a draft leaves `_staging/` on the first approve, so the row goes on offering a link to a review-queue row that is no longer there. Found live at 59 `STAGED` rows against an empty review queue, 55 of them published days earlier, and every one of the 59 links did nothing at all when clicked.

`Clear finished` is not the answer to it. That is a manual control, and the panel must not depend on somebody having remembered to press it in order to stop misreporting. **A `STAGED` row states what the harvest did, which is history and stays; where the draft is *now* is resolved server-side each time the queue is read** — `staging`, `published`, `rejected` or `gone` — and the row draws the slug as a link only in the first case. In the other three it is plain text saying where the draft went. **A control that cannot act is not drawn**, and no click on a queue row ever ends in silence.

Pruning the row instead was considered and refused. A `STAGED` row belongs beside a `BLOCKED` one as the record of what a run of forty URLs did, and dropping each row as its draft was approved would erase that record while the reviewer was still working through it.

**No queue state is added and none is removed.** `STAGED` still means the harvest wrote a draft. The whereabouts is a separate and perishable fact about the content directories, resolved on read and never written to `harvest_queue.json`, which holds URLs and per-URL status only.

**Empty state:** `No URLs queued. Paste one URL, or a list of them, to begin.`

### 1.2 The streaming log pane

Every stage streams a line as it happens (SSE, falling back to polling). This is the load-bearing rule of the whole admin surface, carried verbatim in intent from the reference:

> Trust in the pipeline comes from visibility. **Never replace this with a spinner.**

A representative run:

```
09:14:02  fetching https://example.com/about                  ok (48 kB)
09:14:03  extracting text (trafilatura)                       ok (7.1 kB)
09:14:03  ownership deny-list: name, domain, ABN              ok, no match
09:14:09  harvester agent ({MODEL_HARVESTER})                 ok, independence: check
09:14:09  ownership determination                             CHECK, 2 signals
09:14:17  architect agent ({MODEL_ARCHITECT})                 ok, 612 words
09:14:22  gatekeeper agent ({MODEL_GATEKEEPER})               ok, 588 words
09:14:22  varieties matched 4 of 5                            unmatched: "Nero d'Avola"
09:14:22  geocoding 12 Example Road, Basket Range             ok, -34.9285, 138.7401
09:14:22  saved to _staging/example-wines.mdx                 OWNERSHIP: CHECK
09:14:24  downloaded 4 candidate images to temp_data/images/example-wines/
09:14:24  tokens in/out: harvester 4.1k/1.2k, architect 3.0k/2.4k, gatekeeper 5.4k/2.3k
09:14:24  batch 3 of 12 complete
```

Rules for the pane:

- Model IDs are printed as read from `.env` and are never hardcoded anywhere, including in this document's examples (CLAUDE.md stack constraints). The braces above are placeholders.
- Three levels, distinguished by colour per DESIGN.md and by a text prefix so colour is never the only carrier: `info`, `warn`, `error`.
- Token usage prints once per item, at the end. Cost visibility is a requirement at 150 to 300 producers.
- The pane holds `MAX_LOG_LINES` lines and drops from the top. It autoscrolls only while the reader is already at the bottom; scrolling up pins the view and shows a `Jump to latest` control.
- A `Copy log` control copies the current buffer as plain text. Failure reports get pasted into commits and issues, and retyping them introduces errors.
- The pane is the same pane for harvest, approve, image publish and deploy. There is one log, not four.

**Empty state:** `Idle. The log fills as the pipeline runs.`

### 1.3 Review Queue

A vertical list of everything in `content-staging/_staging/`, newest first. Each row carries:

- producer name and slug,
- primary region and state, as words (`Adelaide Hills, SA`), never as codes,
- category, as the word from `CATEGORIES` (`garagiste`), never an abbreviation,
- age (`2h`, `3d`),
- **two chips, always both present**: a draft-status chip and an ownership chip.

Draft status:

| Chip | Meaning |
|---|---|
| `DRAFTED` | Schema-valid, prose within bounds, ready for review. |
| `IMG PENDING` | Otherwise ready, and has candidate images awaiting the separate publish action (§4). |
| `FLAGGED` | The pipeline completed and validation found problems: a missing or invalid required field, coordinates outside AU bounds, prose under `MIN_PROSE_WORDS` or over `MAX_PROSE_WORDS`, an empty `regions` array, a `summary` over `SUMMARY_MAX_CHARS`. |
| `UNREADABLE` | The file could not be parsed at all (hand-placed file, broken YAML, missing frontmatter delimiter). The row shows the parse error and offers `Open in editor` and `Move to _rejected`. An unreadable file never crashes or empties the queue. |

Ownership:

| Chip | Meaning |
|---|---|
| `CLEAR` | No deny-list hit and no **escalating** ownership signals. Still requires a recorded `ownership_source` before approval (§1.4.5). |
| `CHECK` | An escalating signal was extracted, or a determination was inconclusive. **Blocked from approval until the reviewer records an `ownership_source` and resolves every escalating signal.** |
| `RESOLVED` | A `CHECK` whose escalating signals are all resolved and whose `ownership_source` is recorded. Approve is now available. This chip exists so a reviewer can see at a glance which checks are still outstanding. |

**Amended 2026-08-07 (Gate 5), signed off.** These three rows said "signals were extracted" without qualification, which is how the code behaved: any populated signal escalated to `CHECK`. That made `CLEAR` structurally unreachable, because `PROMPTS/harvester.md` instructs the `statements` key to capture ownership claims *in either direction*, so a page positively naming its owning family was escalated for saying so — penalising the exact evidence §1.4.5 and SCHEMA.md §4.2 require. Basket Range Wine was the case that exposed it.

Four of the five `ownership_signals` keys now escalate on their own: `parent_company_mentions`, `abn`, `shared_address`, `shared_contact_domain`. `statements` escalates only when a fixed lexicon in `ownership.PARENT_PATTERNS` finds group phrasing in it. **All five are still extracted, still rendered as rows in §1.4.2's table, and still written to the sidecar** — nothing stops being evidence, and a non-escalating `statements` row may still be resolved, it simply does not block approval. The Harvester's own `check` still tightens and still routes silence to a human, and rule 3 below is unchanged: a `CLEAR` cannot be approved without a recorded source.

`REJECT` never appears in this queue. An ownership reject aborts before a draft is written (CLAUDE.md Gate 5) and appears in the Blocked list instead (§1.4.4).

Selecting a row loads it in the Review Pane. `↑` and `↓` move selection. Rows older than `STALE_DRAFT_DAYS` show their age in the warn colour and the word `stale`; an unresolved ownership check left sitting in the queue is the specific thing this is watching for.

The queue header carries counts: `9 drafted, 3 check, 1 flagged`.

**Empty state:** `No drafts staged. Harvest a producer URL to begin.`

### 1.4 The Review Pane

The human-in-the-loop verification surface. Split view.

**Left: rendered preview** of the MDX using the *actual public producer-page styles*, by importing the same CSS the site ships. Reviewing in a different skin from what ships is how errors slip through. The preview re-renders on the same debounce as autosave.

**Right: structured frontmatter editor**, ordered as field groups. The ownership panel (§1.4.1) is the first group, is pinned, and is the only group that cannot be collapsed.

#### Field groups

1. **Ownership.** §1.4.1. Pinned first.
2. **Identity.** `name`, `category` (select over `CATEGORIES`), `founded_year`, `website`, `summary` with a live character counter against `SUMMARY_MAX_CHARS`.
3. **Place.** `location.address`, `location.suburb`, `location.state` (select over `STATES`), `regions` (multi-select over the `regions.ts` GI register), `primary_region` (select constrained to the current members of `regions`; changing `regions` re-validates it immediately), `subregions` (multi-select constrained to the subregions of the currently selected regions, per SCHEMA.md §2a rule 5).
   **No coordinate inputs.** Coordinates are geocoded from the address and cached. A failed geocode means the producer publishes with no map pin, and it never blocks approval (SCHEMA.md §2: null coordinates do not block publication). The pane shows the resolved coordinates as read-only text, or the words `no coordinates, this producer publishes without a map pin`.
4. **Visiting.** `cellar_door` (select over `CELLAR_DOOR_STATES`), `cellar_door_hours` (freeform text; the input is disabled and the value cleared when `cellar_door` is `none`, per SCHEMA.md §2a rule 7), `cost` (freeform text), `tasting_fee.fee_aud` and `tasting_fee.waived_on_purchase`, `minimum_age`. The `tasting_fee` group carries a `Delete tasting fee` control, because SCHEMA.md §2a rule 8 requires deleting the whole object rather than leaving a figure the `cost` string cannot corroborate. The pane shows the dollar amounts it can scrape from `cost` beside the fee input, so the reviewer can see the corroboration or its absence without opening `/validate`.
5. **Farming and making.** `organic` and `biodynamic` (selects over `CERTIFICATION_STATES`), each with its certifier input **enabled only when the state is `certified`** and forced to null otherwise, in both directions, live (SCHEMA.md §2a rules 2 and 3). `fruit_source` (select over `FRUIT_SOURCE`). `practices`: exactly the four `PRACTICE_KEYS` as toggles, all four always rendered, all four always written. There is no way to add a fifth. `vessels`: multi-select over `VESSEL_KEYS`.
6. **Wines.** `varieties` (multi-select over `VARIETY_KEYS`), `wine_styles` (multi-select over `WINE_STYLE_KEYS`). Any variety the Harvester named that did not match a `VARIETY_KEYS` slug appears here as an `Unmatched` line listing the raw strings (§1.5). The reviewer maps it by hand or leaves it out; extending the closed list is a schema change and is not done from this screen.
7. **Scale and commerce.** `production_band` (select over `PRODUCTION_BANDS`), `annual_production_cases`, `buy_online`, `ships_nationally`, `shop_url` (marked required and blocking while `buy_online` is true, per SCHEMA.md §2a rule 6). The band the case figure implies is shown beside the figure, so an inconsistency is visible before `/validate` check 10 catches it.
8. **Logistics.** The ten `LOGISTICS_KEYS` as toggles. The whole object may be omitted; a `Clear logistics` control removes it rather than writing ten `false` values.
9. **FAQ.** Up to `FAQ_MAX_ITEMS` question and answer pairs, add and remove controls, with a note that answers are drafted strictly from the Harvester's facts.
10. **Provenance, read-only.** `verification` rendered as a table of field, source link, tier and date. `change_log` rendered as a dated list when present. `drafted` and `source_url` read-only. `verified` read-only with one action, `Verify with today's date`, used on a re-harvest.

**Controls are labelled with words.** There is no badge system and no abbreviation codes anywhere in this editor (SCHEMA.md §2, fields deliberately absent). Toggles read `wild ferment`, `unfined`, `dog friendly`.

**Saving.** Edits save to the staging file on change, debounced, with a subtle `saved 12:06` mono timestamp. No save button, no unsaved-changes modal. A save that fails shows `save failed: {reason}` in the warn colour and retries on the next edit; it never fails silently.

**Field errors.** Every failing field is highlighted with its specific message inline (`summary is 184 characters, limit is 160`; `organic_certifier must be null unless organic is certified`). All failures show at once. The pane never reports the first error only.

**Duplicate warning.** When the draft's normalised website or normalised name matches a published or staged producer, the pane shows a warning row naming the other entry with a link to it. This is a warning, never a block; the reviewer decides.

**Actions.** `Approve` (primary) and `Reject` (secondary). Keyboard `A` and `R`. Both are also always visible as buttons; nothing in this hub is reachable by keyboard alone.

**Undo, not confirmation.** Approve and reject show a 3-second inline undo (`Approved. Undo?`) rather than a confirmation dialog. Confirmation dialogs slow a review session; undo keeps it fast and safe. The server holds a wider grace window (`UNDO_WINDOW_SECONDS`) than the client's 3 seconds, so a click at the boundary succeeds rather than racing. Undo after the server window has closed reports `undo window has closed, this approval is final` and offers the `Unpublish` action instead.

**Approve does, in order:**

1. validate the frontmatter against the schema; any failure blocks and highlights;
2. **assert the ownership gate** (§1.4.5); failure blocks with the specific missing element named;
3. move the file from `_staging/` to `_published/`;
4. move the ownership sidecar from `_staging/` to `DETERMINATIONS_DIR`;
5. rebuild the derived data: upsert the producer row on slug, delete-then-insert every child row table, regenerate the derived JSON;
6. ensure forewords exist for any region, subregion, state, variety or practice this producer is the first published member of;
7. advance selection to the next queue item.

Steps 3 to 6 are one action from the reviewer's point of view. A failure at step 5 or 6 is logged and does not roll back the publish, because the derived data is disposable and fully rebuildable; the log says so plainly (`derived rebuild failed: {reason}. Run the rebuild command; the published file is correct.`).

**Reject** moves the file to `_rejected/` with a one-line reason, stored as a `.reason.txt` sidecar alongside the MDX and the ownership sidecar. It never hard-deletes. The reason field offers presets, selectable by click or by typing the first letter, and free text is always allowed:

- `Not an independent producer`
- `Ownership unresolved`
- `Not a wine producer`
- `Retailer or restaurant`
- `Virtual brand or private label`
- `Insufficient published facts`
- `Duplicate of an existing entry`

**Keyboard map.** `↑` `↓` move queue selection. `A` approve. `R` reject (focuses the reason field). `U` undo. `O` jump to the ownership panel. `E` focus the first editor field. `/` focus the harvest URL input. `Esc` close the current sub-pane or cancel a reject. `?` opens the shortcut list. No shortcut approves without the ownership panel having been rendered, and there is no bulk approve of any kind.

**Empty state:** `Select a draft from the queue to review it.`

---

#### 1.4.1 Independence review

This section has no analogue in the reference build. It is the reason the site exists (CLAUDE.md, prime rules), and it is the one part of the hub where the interface's job is to make a reviewer slow down.

The governing rule, from CLAUDE.md rule 8 and SCHEMA.md §4:

> Independence is an ownership fact, never a tone judgement. No agent decides independence from marketing prose. `check` never auto-publishes.

The ownership panel is the first thing in the review pane, above the producer's name. It cannot be collapsed, and it renders for every draft including a `CLEAR` one.

#### 1.4.2 What the panel shows

**The verdict, as a word.** `Clear` or `Check`. It is displayed, never edited. There is no control anywhere in this hub that sets the verdict by hand. What a reviewer records is evidence and resolutions; the gate is then satisfied or it is not.

**The basis, in one line.** Which check produced the verdict:

- `Clear: no deny-list match on name, domain or ABN, and no ownership signals extracted.`
- `Clear: no deny-list match on name, domain or ABN, and the extracted statement names no parent.`
- `Check: 2 ownership signals extracted.`
- `Check: ABN could not be read from the page.`
- `Check: an extracted statement names a group or a corporate owner — "…".`

The second and fifth lines were added with the 2026-08-07 amendment above. The basis is the durable public record — it is what answers a producer who disputes the determination (§1.4.6) — so it may never claim "no ownership signals extracted" over a determination that extracted one, and where a statement caused the escalation it is quoted rather than counted.

**The deny-list result, as three named checks, always all three, whether they hit or not.**

```
Deny-list, data/ownership.json (updated 2026-08-04)
  name    "Example Wines"            no match
  domain  example.com                no match
  ABN     12 345 678 901             no match
```

On a hit, the row expands to the matched record in full: the `parent`, the value that matched, which of `labels` / `domains` / `aliases` it matched, and that record's own `source` link and `updated` date. The panel never says only "matched". A reviewer must be able to see the evidence behind a block without opening a JSON file.

**The ownership signals table, always rendered.** One row per `ownership_signals` key from SCHEMA.md §5, with the empty case shown as words rather than as an absent row:

| Signal | What is shown |
|---|---|
| `parent_company_mentions` | Each verbatim phrase, quoted, with a link to the source URL it came from. |
| `abn` | The ABN as extracted, formatted, with a link to the ABR lookup for that number. |
| `shared_address` | The address, and where the deny-list knows another label at it, that label's name and parent. |
| `shared_contact_domain` | The contact email domain, and the label that owns that domain where known. |
| `statements` | Each verbatim statement, quoted (`"part of the X family of wineries"`). |

Empty state for the table: `No ownership signals extracted from this page.` This is displayed, not hidden, because the absence of signals is itself a finding the reviewer needs to see and it is explicitly **not** evidence of independence (§1.4.5).

**`parent_company`, as an editable field.** The null value renders as the literal word `null`, never as an empty box, because an empty box reads as "not filled in yet" and `null` here is a positive assertion. Typing any non-empty value into it immediately and visibly blocks approval:

> `parent_company is set. This producer cannot be published (SCHEMA.md §4.1). Reject it, or clear the field if it was entered in error.`

The panel offers `Reject as corporately owned`, which pre-fills the reject reason with the parent's name.

**`ownership_source`, as three controls.** A `source` field (a URL, or a described citation such as `ABN Lookup, ABN 12 345 678 901`), a `date` field defaulting to today, and a three-way evidence-kind selector matching SCHEMA.md §4.2:

- `registry` (ASIC or ABN lookup identifying the operating entity and showing no corporate parent)
- `producer_statement` (the producer's own published ownership statement, naming who owns the business)
- `trade_source` (a named independent trade source stating ownership)

Any one of the three is sufficient. The panel states that beneath the selector, along with the rule that matters most:

> A source that fails to mention a parent is not evidence of absence. It must positively state who owns the business.

**Conflict handling.** Where sources conflict, the registry wins, and the panel offers a `Conflict noted` free-text field. That note is written to the staging sidecar's `confidence_notes`, and is surfaced in the pane on every later visit to this draft. It is not published frontmatter.

**Dates side by side.** The panel shows `ownership_source.date` next to `verified` so the reviewer can see how old the ownership evidence is relative to the rest of the entry. Display only, no block.

#### 1.4.3 What the reviewer does, per verdict

**`clear`.** The panel renders in its summary form: verdict, basis line, the three deny-list rows, the empty signals table, and the `ownership_source` controls. The reviewer records an `ownership_source` and approves. Nothing else is required. This is the common path and it must stay fast.

**`check`.** The panel renders expanded, and two things are required before approval:

1. **A recorded `ownership_source`**: a non-empty `source`, a `date`, and an evidence kind. All three.
2. **Every signal resolved.** Each row in the signals table carries a resolution control with exactly three options, and a one-line note field:

   | Resolution | Meaning | Effect |
   |---|---|---|
   | `Explained` | The signal has an innocent explanation, stated in the note (`the shared address is a contract winery, not common ownership`). | Row resolved. |
   | `Confirms a parent` | The signal establishes corporate ownership. | Sets `parent_company` to the value the reviewer types, which immediately blocks approval and offers the reject action. |
   | `Not relevant` | The signal is noise (`the ABN belongs to the web developer's footer boilerplate`). | Row resolved. |

   A note is required for `Explained` and for `Confirms a parent`. `Not relevant` may be recorded without one.

   While any row is unresolved, `Approve` is disabled and the reason is stated in text beside the button, not only as a tooltip: `2 ownership signals are unresolved.`

   Resolving every row moves the queue chip from `CHECK` to `RESOLVED`.

3. **The unresolvable case.** A `check` the reviewer cannot settle is rejected with the `Ownership unresolved` preset. The draft moves to `_rejected/` with its ownership sidecar intact, so the next person to see the URL can read what was already established. Rejecting for ownership is a normal outcome and the queue never treats it as an error.

**`reject`.** Never reaches this panel. See below.

#### 1.4.4 The Blocked list

An `independence: reject` verdict, from either the deny-list or the Harvester's own signal-based determination, aborts the run **before a draft is written** (CLAUDE.md Gate 5). No file lands in `_staging/`. That is correct behaviour, and it still needs an on-screen state, because an abort a reviewer cannot see is a silent failure.

The pipeline writes a blocked record to `BLOCKED_DIR` as `<slug>.json` carrying the URL, the extracted name, the verdict, the full `ownership_signals`, the deny-list check results including any matched record, and a timestamp. The harvest column's third pane, **Blocked**, lists these newest first.

Each row shows the name, the URL, and the reason in one line (`deny-list: name matches Treasury Wine Estates` or `harvester: 4 signals, statements name a parent group`). Selecting a row opens the same signals table and deny-list block the review pane uses, read-only.

**Actions differ by source of the reject, deliberately:**

- **Deny-list reject.** No override action exists in the UI. The only route is to correct `data/ownership.json`, which is hand-maintained, carries a source and a date per record, and is edited in a text editor. The row offers `Open data/ownership.json` and `Re-harvest`, in that order, and `Re-harvest` runs the URL again from scratch so the corrected deny-list is what decides. The interface never lets a click overrule the deny-list, because the deny-list is the artefact `/validate` check 8 audits against.
- **Harvester signal reject.** One action, `Re-harvest as check`. It re-runs the URL with the machine verdict floored at `check` rather than `reject`, so the draft enters the queue with the ownership panel expanded and every `check` rule applying: source required, every signal resolved. This downgrades a machine abort to a human decision. It never skips the human decision. The action is recorded in the blocked record with a timestamp, and the resulting draft's sidecar carries `verdict_overridden_from: reject`, which the review pane displays as a prominent line: `This draft was re-harvested after an automatic ownership reject. Read the signals carefully.`

Blocked records are never deleted from the UI. They are the record of what the site refused and why, and at 150 to 300 producers the same URL will be reached for twice.

**Empty state:** `Nothing blocked. Producers stopped by the ownership rule appear here with their evidence.`

#### 1.4.5 The hard rules

These are requirements, not defaults.

1. **`check` cannot be approved without a recorded `ownership_source`.** A non-empty `source`, a `date` and an evidence kind. The `Approve` control is disabled while any of the three is missing, and the missing element is named in text.
2. **`check` never auto-publishes.** There is no bulk approve, no "approve all clear", no auto-approve setting, no keyboard shortcut that approves a draft whose ownership panel has not been rendered, and no API route that publishes without passing the same gate the UI enforces. The gate lives in the approve function, not in the template.
3. **`clear` also requires an `ownership_source`.** A `clear` verdict is an absence of signals. Absence of signals is not evidence of a negative (SCHEMA.md §4.2), and `ownership_source` is a required field on every producer (SCHEMA.md §2). `clear` differs from `check` only in that the panel opens in summary form and no signals need resolving.
4. **The verdict is never editable.** There is no control that sets `clear`. CLAUDE.md rule 8 in interface form.
5. **A non-null `parent_company` blocks approval unconditionally.** No override, no force flag, no admin escape hatch. SCHEMA.md §2a rule 10 and §4.1.
6. **Every published producer carries its determination at publish time, never backfilled** (CLAUDE.md Gate 8). There is no "publish now, source later" path, and no field in this hub can be left for a later pass.
7. **The hub never edits `data/ownership.json`.** It reads it, displays it, links to it and reports its `updated` date. Editing it is a deliberate act in a text editor, committed like any other data change.

#### 1.4.6 What is retained

On approve, the ownership sidecar moves from `_staging/<slug>.ownership.json` to `DETERMINATIONS_DIR/<slug>.json`. It is retained and never deleted, the same posture as `_rejected/`. The published frontmatter carries the durable public record (`ownership_source`, plus `verification.parent_company` as a `{source, tier, date}` block, since `parent_company` is in `VERIFIABLE_FIELDS`); the sidecar carries the working evidence, including signals that were resolved as `Not relevant` and would otherwise vanish. When a producer argues with the determination, the sidecar is the file that answers them.

On reject, the sidecar moves to `_rejected/` alongside the MDX and the reason file.

---

### 1.5 Failure states, all required

Every row is a required on-screen state. A failure with no defined state is a bug against this document.

| # | Failure | Behaviour |
|---|---|---|
| 1 | Bad or unreachable URL, fetch fails or times out at `FETCH_TIMEOUT_SECONDS` | Log line in the error colour with the HTTP status or the word `timeout`; the item ends cleanly; a single-URL run retains the URL in the input for retry; a batch item is marked `FAILED` and the run advances. **No retry action is offered** — see row 1a for the one exception. |
| 1a | **Fetch refused with `403` or `503`** | Row 1's behaviour, plus a `Retry with Playwright` action on that item, user-triggered exactly as row 3. Log adds `the site refused a plain fetch. Retry with Playwright.` The action is offered only on these two statuses, and never on an item that already came through Playwright. |
| 2 | `robots.txt` disallows the fetch | Log line in the error colour naming the rule; item ends; no retry offered and no override control. |
| 3 | Thin page: extracted text under `THIN_EXTRACTION_CHARS` | Log warns `thin extraction: 220 chars`; a `Retry with Playwright` action appears on that item, user-triggered only (CLAUDE.md stack constraints); the item ends without drafting. In a batch, the action is offered on the row and the run continues. |
| 4 | Malformed agent JSON or MDX | One automatic re-ask with the parse error appended to the prompt. On a second failure, the raw output is saved to `temp_data/failed/{slug}-{stage}-{time}.txt` and logged with the path. Never silently discarded. |
| 5 | Harvester returns `name: null` | Log: `harvester could not identify a wine producer on this page`, followed by any `confidence_notes`. Item ends. This is the not-a-producer case and it is not an error state. |
| 6 | **Ownership reject, deny-list** | Aborts before a draft is written. Log in the error colour naming the matched parent, the matched value and which list it came from. A blocked record is written (§1.4.4) and the batch row reads `BLOCKED`. No draft, no partial file. |
| 7 | **Ownership reject, Harvester verdict** | Aborts before a draft is written. Log in the error colour with the signal count and the first statement quoted. Blocked record written; `Re-harvest as check` offered (§1.4.4). |
| 8 | **Ownership check** | The pipeline continues and a draft is written. Log line reads `OWNERSHIP: CHECK` at the save step, and the queue row carries the `CHECK` chip. Approve is blocked until §1.4.5's rules are satisfied. This is not a failure and the run does not slow for it; it is a failure only if it publishes. |
| 9 | Slug collision with `_published` or `_staging` | Halt before drafting. Log `slug 'example-wines' exists in _published, skipping`, with a link that selects or opens the existing entry. Batch row reads `SKIPPED`. The re-harvest path sets the documented allow-existing flag and still writes only to `_staging/`. |
| 10 | Geocode failure or no address to geocode | Log warns `geocode failed, publishing without a map pin`. **Never blocks.** The review pane states the same in words. Null coordinates are a first-class outcome (SCHEMA.md §2). |
| 11 | Unmatched variety, region or subregion | The Harvester returns names as stated. Any value that does not slugify to a member of `VARIETY_KEYS` or of `regions.ts` is dropped from the field and logged: `unmatched variety: "Nero d'Avola", not in VARIETY_KEYS`. The review pane shows an `Unmatched` line under the field with the raw strings. Never silently dropped, because a silent drop is how a producer's actual varieties disappear. |
| 12 | `regions` empty after slug matching | The draft is still written so a human can supply the region from the address, and it is chipped `FLAGGED`. Approval is blocked by schema validation (`regions` requires at least one member). |
| 13 | Agent transport failure: API error, rate limit, overload | Log the status and any `retry-after`. The job pauses, retries once, then fails cleanly. In a batch the run resumes at the next item. A rate limit that recurs three times in one batch pauses the whole queue with `queue paused: repeated rate limiting. Resume when ready.` |
| 14 | Any batch item failure, of any kind above | Isolated to that item. The row takes its state, the reason shows on the row, the run advances. No rollback of earlier items, no partial files, no aborted queue. |
| 15 | Schema validation fails on approve | Approve blocked. Every failing field highlighted with its specific message in the editor (`latitude is out of range for Australia`). All failures at once. |
| 16 | **Approve blocked by the ownership gate** | Approve disabled, with the reason in text beside the control: `ownership_source is missing` / `2 ownership signals are unresolved` / `parent_company is set`. Never a silent no-op, never a disabled button with no explanation. |
| 17 | Undo requested after the server window closed | `undo window has closed, this approval is final`, and the `Unpublish` action is offered instead, which parks the file in `DELETED_DIR` timestamped and rebuilds the derived data. |
| 18 | Derived rebuild fails after a successful publish | Logged in the warn colour with the reason and the rebuild command to run. The publish is not rolled back; the derived data is disposable by design (SCHEMA.md §3). |
| 19 | Foreword generation fails for a new region or variety | Logged in the warn colour. Non-fatal. The page renders without a foreword rather than not rendering. |
| 20 | Unreadable staging file | Listed in the queue as `UNREADABLE` with the parse error, `Open in editor` and `Move to _rejected`. The queue still renders every other row. |
| 21 | Candidate image download fails | Logged in the warn colour per image. Non-fatal. Approving with no image is the normal path (§4). |
| 22 | Deploy diff contains a path outside the allow-list | Deploy refuses and lists the offending tracked files by path. This is the guard `/validate` check 15 self-tests. |
| 23 | `npm run build` fails at the pre-push gate | Push blocked. The build output streams into the log pane in full. The commit, if already made, stands; the push does not happen. |
| 24 | `git push` fails | The actual git error text is surfaced. Never "something went wrong". |
| 25 | Netlify build poll fails or times out | Logged with the build ID and a link to the Netlify log. The deploy is reported as `pushed, build status unknown`, which is the truth. |
| 26 | IndexNow ping fails | Logged in the warn colour. Non-fatal, never blocks. |

*Row 1a added 2026-08-09 (engagement block, carried-over defect B). Until then row 1 offered no retry on any fetch failure, and `offer_playwright` was reachable only from row 3. The code was a correct reading of this table; what was wrong was SEED.md §2's claim that d'Arenberg exercised the user-triggered Playwright path end to end through the hub. It could not: Cloudflare answers a plain fetch with `403`, which is row 1, so the only way to that path was a direct call outside the admin. The new row is deliberately narrow. A `403` or `503` is a statement about the client, and a browser is a different client; a timeout, a `404` and a `500` say nothing a browser changes, so they keep row 1's silence.*

**Empty states are directions, not moods.** Every pane has one, and each one tells the reader what to do next:

| Pane | Empty state |
|---|---|
| Harvest queue | `No URLs queued. Paste one URL, or a list of them, to begin.` |
| Blocked | `Nothing blocked. Producers stopped by the ownership rule appear here with their evidence.` |
| Review queue | `No drafts staged. Harvest a producer URL to begin.` |
| Review pane | `Select a draft from the queue to review it.` |
| Signals table | `No ownership signals extracted from this page.` |
| Candidate images | `No candidate images. This producer publishes without a photograph, which is the normal case.` |
| Log | `Idle. The log fills as the pipeline runs.` |
| Deploy | `Nothing to publish. Approve a draft first.` |

### 1.6 Deploy strip

The lower row of the unified footer band, separated from the three columns above by its own border.

- **Status summary**, always visible: `4 files staged for publish, last deploy 2d ago`.
- **`Deploy` opens a diff preview**: the exact file list to be committed, with the change type per file. Only these paths are ever committed:
  - `site/src/content/producers/_published/`
  - `site/public/images/` (published producer images)
  - `data/directory.db`
  - the derived JSON under `site/src/data/` (including `forewords.json`)
  - `data/ownership.json`
  - `site/src/content/blog/_published/` and `site/public/blog-images/`

  `content-staging/` in all its forms, `temp_data/` and `.env` are gitignored, and **the deploy refuses to run if any of them is tracked**, listing the offending files. The refusal is exercised by a fixture self-test, not asserted (`/validate` check 15).
- **Pre-push build gate.** `npm run build` runs before the push, streaming into the log pane. A failure blocks the push (§1.5 row 23).
- **Commit message** auto-generated and editable: `Publish: jauma-wines, gentle-folk (+2 producers)`.
- Then `add`, `commit`, `push`, each streaming to the log pane, followed by a Netlify build poll and an IndexNow ping.
- Push failure surfaces the actual git error.

---

## 2. Public Site, Page Behaviour

The site's job is to get a reader from "I am going to the Adelaide Hills" to a producer they can visit or buy from, in as few plain steps as possible, with no JavaScript required at any point on that path.

### 2.1 The homepage is region-first

**This replaces the reference's homepage entirely.** That page embeds every venue's data into the document and reveals rows with client-side filters. At 150 to 300 producers with regions, subregions, varieties, styles, vessels and practices per entry, that page becomes a large document that is unreadable without JavaScript and unhelpful with it. The homepage here is a chooser over regions, and lists paginate. This is a design decision taken up front (CLAUDE.md Gate 6), not a performance fix applied later.

**Content order, top to bottom:**

1. **Masthead.** The site logo as a real `<a href="/">` (§2.4a), the tagline, and the standing line `Free to use. No ads. No sponsored listings.`
2. **Foreword.** Two short paragraphs of editorial prose: what the guide covers, and what *independent* means here, with the word linked to `/methodology/`. The link is not decorative. The definition is the site's central claim and the reader is one click from the full statement of it from the first screen.
3. **Search.** A single text input matching name, suburb, region, subregion, state, category and variety against a build-time embedded index, showing up to `SEARCH_MAX_RESULTS` results as a list of plain typographic links directly beneath the input, keyboard-navigable with `↑` `↓` `Enter` `Escape`. At this dataset size the embedded index stays small enough to ship in the document; when it stops being small, it moves to a fetched JSON file and the behaviour does not change. **Requires JavaScript**, and degrades to a `<noscript>` line pointing at the region chooser below. Search is an accelerator. It is never the only route to anything.
4. **The region chooser. This is the primary navigation of the site and the main content of the homepage.** GI regions grouped by state, present-only: a region with zero published producers does not appear, and the build logs the skip. Each entry is a plain anchor to `/region/[region]/` with its producer count as a plain numeral (`Adelaide Hills · 46`), never a badge. States are headings, and each state heading is itself a link to `/[state]/`. The whole chooser is server-rendered anchors and is complete with JavaScript disabled.
5. **Latest entries.** The `HOMEPAGE_LATEST_COUNT` most recently drafted producers as `ProducerEntry` rows, server-rendered, followed by one link: `All producers, A to Z`, to `/producers/`. This is a fixed-length slice. **The homepage never renders more than `HOMEPAGE_LATEST_COUNT` producer rows and never embeds the full dataset.**
6. **Browse by grape, by practice, by state.** Three plain text link lists, present-only, to `/variety/[grape]/`, `/practice/[key]/` and `/[state]/`. Text links, not chips in boxes, not icon tiles.
7. **Footer.** Methodology, glossary, blog, sitemap, and the standing no-ads line repeated once.

**How a reader gets from landing to a producer.** Every one of these paths is specified and every one except search works with JavaScript disabled:

| Path | Clicks | Needs JS |
|---|---|---|
| Home, region, producer | 2 | no |
| Home, region, subregion, producer | 3 | no |
| Home, state, region, producer | 3 | no |
| Home, latest entries, producer | 1 | no |
| Home, all producers, page N, producer | 2 or 3 | no |
| Home, grape or practice, producer | 2 | no |
| Home, search, producer | 1 | yes |
| Any producer page, its region or grape or practice, sibling producer | 2 | no |

A producer page is a hub, not a terminus. Every producer links out to its region, its subregions, its state, each of its varieties and each of its true practices, which is also what satisfies `/validate` check 17's requirement that every producer be reachable from at least three aggregation pages.

### 2.2 Pagination, sitewide

Real pagination, server-rendered, crawlable.

- **Page size** is `PRODUCERS_PER_PAGE` on every listing.
- **Page 1 is the bare route.** `/region/adelaide-hills/`, not `/region/adelaide-hills/page/1/`. Page 1 is never also available at a second URL, so there is no duplicate content and no canonical juggling.
- **Pages 2 and up take a `page/` segment**: `/region/adelaide-hills/page/2/`, `/variety/shiraz/page/3/`, `/producers/page/4/`. The literal `page` segment exists to keep `/region/[region]/page/2/` from colliding with `/region/[region]/[subregion]/`, which a bare `/region/adelaide-hills/2/` would do. The same shape is used on every route for consistency, including those with no collision risk.
- **The pager is a list of links.** Previous, the page numbers, next. Not a button, not "load more", never infinite scroll. Infinite scroll is the pattern pagination exists to avoid: it breaks the back button, hides the tail of a list from crawlers, and gives a reader no way to say where they are.
- `rel="prev"` and `rel="next"` on every page in a series; a self-canonical on each page; every page in `sitemap.xml`.
- Page 2 and up carry the same foreword and heading as page 1 and add `, page 2` to the `<title>`.
- A listing under `PRODUCERS_PER_PAGE` renders with no pager at all rather than a pager reading `1`.

`/producers/` is the A to Z index of every published producer, paginated by this rule. It is the completeness route: everything is reachable from it, in one predictable order, with no filter applied.

### 2.3 Producer page

Route `/producer/[slug]/`. Content order per DESIGN.md. Behaviour:

- **The dateline** carries ~~the primary region, the state and the category, as words. `Adelaide Hills, South Australia. Garagiste.`~~ — **amended 2026-08-12, signed off.** The three-component form stands as history, not a live requirement. It disagreed with DESIGN.md §15, which frames every entry as a herbarium sheet and asks for "the collector's date and locality beside it" by name — neither of which the three components carry. Both are interface documents, so doc precedence could not separate them (CLAUDE.md rule 3); the conflict was put to the user with the alternatives and settled in DESIGN.md §15's favour, because the herbarium framing is load-bearing across the whole design and the three-component form was the more generic statement. The dateline renders, in this order and each present-only: **the suburb, the state, the primary region, every listed subregion, the category, and the founded year**, joined by `·` and rendered as words. The primary region and the subregions are links; the rest is plain text. `Balhannah · South Australia · Adelaide Hills · Lenswood · Estate winery · Founded 1989`. Subregions are unbounded, so the line is too: the longest in the corpus at this date is nine components (`aphelion`, five subregions). A component that repeats one already printed is dropped rather than printed twice, compared on **rendered names and not slugs** (engagement 2026-08-12). The card dateline in `ProducerEntry.astro` is a shorter cousin — suburb, state, primary region, category — and prints no subregion and no founded year, which is why its dedupe has only the region to collide with.
- **The independence line is not optional.** Every producer page states, in the provenance block, that the producer is independent and where that was established: `Independent. Ownership checked against {ownership_source.source} on {ownership_source.date}.` The source is a link when it is a URL. The word `Independent` links to `/methodology/`. This is the public face of the determination and the site's whole claim; a page without it is a bug.
- **Wines** render as word lists: varieties (each linking to `/variety/[grape]/`), wine styles, vessels. A variety appears only when the source named it (SCHEMA.md §5, evidence or nothing).
- **Practices** render only the true ones, each linking to `/practice/[key]/`. There is no row reading "not unfined". An absent practice is absence of evidence and the page does not assert it either way.
- **Certification** renders the state and the certifier together or not at all: `Certified organic (ACO)`. `certified` without a named certifier never renders, because it never publishes (`/validate` check 9).
- **Cellar door.** `cellar_door_hours` renders verbatim as written, because it is a freeform display string by design (SCHEMA.md §2) and reformatting it into a grid misrepresents an appointment-only producer. When `cellar_door` is `none`, the block is one line saying there is no cellar door, with a link to the shop when `buy_online` is true.
- **Cost.** The freeform `cost` string is what a reader sees. `tasting_fee` never renders as a bare number on a producer page; it exists to power comparison tables and structured data (SCHEMA.md §2: structured numbers alongside the freeform string, never replacing it).
- **Map.** A pin renders only when both coordinates are non-null. Absent coordinates render no map affordance and no empty container. A label-only producer with no cellar door is a first-class entry and its page must not read as broken.
- **Provenance.** `verification` renders as a list of field, source, tier in plain words (`published by the producer`), and date. `change_log`, when present, renders as a dated list of what changed and when.
- **FAQ** renders only when `faq` is present and non-empty.
- **Nothing on this page implies a visit.** No rating, no stars, no review widget, no "we tried", no tasting note. CLAUDE.md rule 6 is a rule about the interface as much as about the prose: an affordance that invites a first-hand claim is a violation even when it is empty.
- **Photographs**, where present, always carry visible source attribution in the caption line (§4).
- **Outward links**: the primary region, each subregion, the state, each variety, each true practice, the methodology page, and the producer's own website and shop.
- Pull quotes are generated at build time from `<Pull>` spans marked in the MDX, never duplicated text.

### 2.4 Programmatic pages

All present-only generation: loop the taxonomy, skip on zero, log the skip, never render an empty page (CLAUDE.md Gate 6).

| Route | Contents |
|---|---|
| `/region/` | The hub. Every GI region with at least one published producer, grouped by state, with counts. Linked from the homepage and the footer. |
| `/region/[region]/` | Foreword, then the subregion link row (present-only, with counts), then the paginated producer list **for the whole region**. A producer in a subregion appears on both its subregion page and its region page; the region page is the superset and never a remainder list. Breadcrumb: Home, Regions, Adelaide Hills. |
| `/region/[region]/[subregion]/` | Foreword, paginated producer list, a link up to the region, and a link row of sibling subregions. Breadcrumb four deep. |
| `/[state]/` | State roll-up: the regions in that state with counts, then the paginated producer list for the state. Generated from the closed `STATES` tuple, so the eight state slugs are the only top-level dynamic paths; no other top-level route may take one of those slugs. |
| `/variety/[grape]/` | Foreword, a glossary line defining the grape, paginated producers listing that variety. |
| `/practice/[key]/` | Foreword, the glossary definition of the practice, a line stating plainly that the flag comes from the producer's own published material, paginated producers. |
| `/glossary/` and `/glossary/[key]/` | Generated unconditionally for every value of every closed vocabulary in SCHEMA.md §1, including the confidence tiers. Glossary pages exist whether or not a producer uses the term, which is what `/validate` check 11 enforces in both directions. |
| `/producers/` | A to Z index, paginated (§2.2). |
| `/methodology/` | §2.5. |
| `/blog/` and `/blog/[slug]/` | Hand-authored posts (§6). |

**`low_intervention` is not a route parameter and never will be.** SCHEMA.md §1.6 removes it from the schema; this document removes it from the URL space. An editorial page at `/low-intervention/` composed from the four `PRACTICE_KEYS` facts is allowed, and it must read as an explainer rather than as a filter: it may link to the four practice pages, and it may not present itself as a facet, a toggle or a producer attribute.

**Forewords.** Each programmatic page carries a build-time-generated foreword paragraph, drafted once by the pipeline into `forewords.json`, human-editable, and never regenerated on every build. Copy that churns every build is copy nobody trusts. Forewords for regions, subregions, states, varieties and practices live in separate keyed buckets in the one file.

**Every programmatic page carries**: a self-canonical, a descriptive title in the house register (`Independent winemakers of the Adelaide Hills`), a meta description drawn from the foreword's first sentence, a `BreadcrumbList` and an `ItemList`, and cross-links both up (to its hub) and sideways (to sibling regions, subregions or varieties).

### 2.5 The methodology page

On the reference build the methodology page is a trust signal. Here it is **the published definition of independence**, and it is the document producers will argue with. It is drafted at Gate 4, alongside the system it describes, and ships at Gate 10.

It must contain, in this order:

1. **What the site is and how it is paid for.** Free, no ads, no sponsored listings, no paid placement, nothing purchasable. Stated first because every claim after it depends on it.
2. **The definition of independence as this site uses it**, stated plainly and without qualification: a producer is listed only where it has no corporate owner. Any corporate ownership blocks publication, including a minority stake, and including membership of a multi-label family group.
3. **What the rule excludes, as a list, in plain words.** This is the part that must not be softened, and it is written about kinds of business, never about named businesses:
   - a producer with an outside investor holding any share of the business, however small;
   - one label among several under a family or portfolio group, even where the group itself has no corporate owner;
   - a label owned by a wine company, a drinks company or an investment vehicle;
   - a supermarket private label;
   - a virtual brand with no winemaking operation of its own;
   - a retailer's or a restaurant's house label.

   Followed by the sentence that does the work, in the site's own voice:

   > This is stricter than the trade's ordinary use of the word. It excludes businesses that many people, including the people who run them, would fairly call independent.

4. **Why the rule is strict.** A bright line can be applied the same way to every producer. A soft one gets argued case by case, and the arguing is won by whoever has the most to spend on it.
5. **How a determination is made.** The hand-maintained deny-list checked on name, domain and ABN before a producer enters the queue; the ownership signals extracted from the producer's own pages; the three kinds of evidence that count (a registry lookup, the producer's own published ownership statement, a named independent trade source); that any one of the three is sufficient; that the registry wins where they conflict; and the rule that carries the most weight:

   > A source that fails to mention a parent company is not evidence that there is none. It has to say who owns the business.

6. **That a human decides.** No entry publishes on a machine verdict. The pipeline extracts and flags; a person records the source and approves. Stated because the alternative is what a reader will assume.
7. **Where the facts come from, and the honesty rule in public.** Every entry is documented from published sources. Nobody working on this guide has visited these cellar doors or tasted these wines, there are no tasting notes anywhere on the site, and no sentence implies otherwise. Where a producer does not state something, the entry leaves it out.
8. **Confidence tiers in plain words.** What `published by the producer` means today, what `confirmed by the operator` would mean, and that almost everything currently sits at the first of those. Honest about its limits, with no claim to a verification step that has not run.
9. **How to tell us we are wrong, in both directions.** A plain contact line, and two commitments stated as commitments: a producer who shows us a corporate parent we missed is removed, and a producer wrongly excluded is reinstated with the evidence recorded and dated. Both directions, because a rule this strict will produce errors of both kinds.
10. **Coverage.** Which regions are populated, and the sentence that thin coverage is where the work has reached rather than a judgement about what is worth drinking.
11. **A dated `Last updated` line**, and a short list of substantive changes to the definition with their dates. A definition that changes silently is not a definition.

The page is linked from the footer of every page, from the site navigation, and from every producer page's independence line (CLAUDE.md Gate 10).

### 2.6 Theme toggle

- A plain text control in the site navigation, on every page type. Never a floating control in its own right.
- Defaults to the visitor's OS preference via `prefers-color-scheme`. No state is presented as wrong; whichever mode is active is simply the current state.
- Activating it (click, or `Enter` or `Space` when focused) flips the mode and writes the explicit choice to `localStorage`, which then wins over `prefers-color-scheme` for the rest of the visit and on return, until cleared.
- No transition or animation on switch. An instant state change, consistent with §3's motion posture.
- **Works with JavaScript disabled**: the control still renders as a real, focusable element and is inert without JS. The page themes correctly from `prefers-color-scheme` alone, so a no-JS visitor always gets a correctly themed page, without the override.
- The admin hub has no manual toggle. Automatic only.

### 2.7 Site logo and home link

- Renders in flow at the top of every public page, above the navigation, as a real `<a href="/">`, keyboard-reachable and operable like any other link. Never a decorative image.
- Larger on the homepage, where it replaces a standalone `<h1>`; the smaller default size everywhere else. No other sizes and no other states.
- Works with JavaScript disabled: a plain anchor and a CSS-masked background image.
- **`SITE_NAME` is a placeholder.** No brand name is hardcoded anywhere in markup, copy, structured data, titles or this document. Everything reads it from `site/src/config.ts`.
- Not present in the admin hub, which has its own header.

---

## 3. Interaction Rules, site-wide

These are the disciplines the reference build earned, carried forward.

**No modals, no toasts, no cookie banners, no floating buttons, no interstitials, no newsletter overlays, no chat widgets.** A navigation drawer, if DESIGN.md specifies one, is the single narrow exception, and it must be a real element whose links are in the document and reachable with JavaScript disabled. It does not reopen the door to modals generally.

**Every JavaScript affordance has a `<noscript>` line or a crawlable fallback.** The complete list, and there may be no additions to it without a corresponding entry here:

| Affordance | Fallback with JS disabled |
|---|---|
| Search | `<noscript>` line: `Search needs JavaScript. Browse by region, grape or state below.` The region chooser directly beneath it is the fallback. |
| Theme toggle | Control renders and is inert; the page themes from `prefers-color-scheme` (§2.6). |
| Navigation drawer, if any | Its links render in flow. |
| Producer map pin | The address renders as text regardless; the map is additive. |
| Any motion | Additive only. Nothing is hidden, gated or revealed by a script (§3, motion). |
| Pagination | Path-based server-rendered links. No JavaScript involved at any point. |

The admin hub is exempt from the no-JS requirement. It is a local tool for one operator, not a public page, and its log pane is a stream by nature. Every other rule in this section applies to it.

**Filters are text, not chips in boxes.** Where a listing offers a filter, it is a row of plain text links or plain text toggles in the house mono register, with the active one marked by an underline and by `aria-pressed`, never by a filled pill, a coloured box, a rounded tag or a count bubble. Colour is never the only carrier of state.

**State lives in the URL.**

- Pagination is path-based: `/variety/shiraz/page/2/`.
- Any filter or sort is a query parameter, written with `history.replaceState` as it changes, and read on load so a pasted URL reproduces the view exactly.
- The back button always works and never re-runs a filter into a different result.
- No client-side routing that swallows navigation. If Astro view transitions are enabled by DESIGN.md, browsers without support get a normal full page load, which is the framework's documented fallback.

**Full keyboard access.** Every interactive element is reachable and operable by keyboard. Focus order follows reading order. Focus is always visible, and `:focus-visible` styling is never removed. Nothing traps focus. No affordance is available by keyboard alone or by pointer alone.

**Reduced motion is respected.** `prefers-reduced-motion: reduce` shows the same final, correct state with no flash and no missing content. Motion is additive only: every page renders full, final content and layout with JavaScript disabled, and nothing is hidden behind an animation that may not run.

**Nothing implies a visit or a tasting.** No ratings, no stars, no scores, no "best of" ordering that is not explicitly defined, no review widgets, no affiliate booking buttons. Ordering on every listing is stated in words where it is not obvious (`newest first`, `A to Z`), because unstated ordering reads as a ranking.

**Semantic markup.** Listings are lists. Comparisons are `<table>` with `<caption>` and `<th scope>`. Headings descend without skipping. Every image has an `alt`. Every link says where it goes without its surrounding sentence.

---

## 4. Image Handling, the separate approval object

**Default posture: pages are designed to be complete with zero images.** Scraped images are a staging convenience and an opt-in enhancement, never auto-published. A label-only producer with no photograph is a normal entry, and the interface must never suggest otherwise.

Pipeline:

1. **Harvest** downloads up to `MAX_CANDIDATE_IMAGES` candidate images from the producer's own site into `temp_data/images/<slug>/`, with a `manifest.json` recording each source URL. These exist locally only; `temp_data/` is gitignored and is never edited by hand (CLAUDE.md rule 5).
2. In the review pane, candidates appear as a thumbnail strip below the frontmatter editor, **each showing its source URL as visible text**. The reviewer must be able to see that an image came from the producer's own domain before publishing it. An image from a stock library, a regional tourism board or another label's site is rejected by eye at this step, which is the only step where that judgement is possible.
3. **Publishing an image is a separate deliberate action from approving the prose.** The reviewer selects at most one image and activates `Publish image`. That single action:
   - resizes and compresses it to at most `PUBLISHED_IMAGE_MAX_PX` on the long edge, webp, into the site's assets under the slug name;
   - writes `image`, `image_source` and `image_caption` into the frontmatter, the caption in the register SCHEMA.md §2 specifies (`LOT I. — THE HOME BLOCK, LOOKING WEST.`), reviewer-editable;
   - **inserts the corresponding `<TippedPhoto>` tag into the MDX body in the same write.** Frontmatter alone renders nothing; the producer page renders a photograph exclusively from the body tag. Setting the fields without the tag produces a file that claims an image and shows none. The two halves are one action, always.
   - moves the row's chip from `IMG PENDING` to its normal state.
4. **`Remove image`** is the exact reverse and is available on both a staged draft and an already-published producer: it drops the three fields, strips the body tag, deletes the published asset, and rebuilds the derived data. On any takedown request it is a single action.
5. **Published images always render with visible source attribution** in the caption line, on every page where the image appears.
6. **Approving prose with no image selected is the normal path, not an error.** The queue never nags about a missing image, never sorts imageless drafts differently, and never shows a placeholder frame where a photograph would be.
7. No image is published for a producer whose ownership determination is unresolved. Approve is blocked in that state anyway (§1.4.5); stating it here closes the path where an image is published to a draft that then never publishes.

---

## 5. What "Done" Looks Like Per Session

A review session should feel like this:

> Open the hub. Paste ten seed URLs, press `Queue batch`, watch the log fill. Two come back blocked on the deny-list with the matched parent named; one comes back `check`. Arrow down the queue. For each draft: read the ownership panel first, paste the ABN lookup or the producer's own ownership page into `ownership_source`, pick the evidence kind, correct a practice toggle or a variety the Harvester over-read, press `A`. For the `check`, read both signals, resolve one as `Explained` with a note about the contract winery, resolve the other as `Not relevant`, record the source, press `A`. One draft has no published facts worth a page: `R`, `Insufficient published facts`. Glance at the deploy diff. Deploy. Close.

Ten drafts reviewed in under fifteen minutes, with an ownership source recorded on every single one. Any friction beyond that, meaning dialogs, page reloads, mystery states, a disabled button with no stated reason, or a silent failure, is a UX bug against this specification.

Two things a finished session leaves behind:

- **Nothing undetermined.** No draft sits in the queue with an unresolved ownership check because the reviewer meant to come back to it. The queue's age column and `stale` marker exist to make that visible on the next session (§1.3).
- **Nothing published without its evidence.** Every producer that went to `_published/` this session carries an `ownership_source` recorded at the moment it published, and its determination sidecar sits in `DETERMINATIONS_DIR`. Backfilling is not a recovery path; it is the thing this specification exists to prevent (CLAUDE.md Gate 8).

---

## 6. Blog Authoring

A second admin screen at `/blog`, linked from the hub header. Separate from the producer review workflow because posts are hand-authored and editorially drafted rather than harvested.

- **Two-pane layout**: a post list (drafts and published posts together, each with a status chip) and an editor.
- **Editor fields**: title, summary, dateline, an optional cover image, and a rich-text body editor. All fields autosave on the same debounce as the producer frontmatter editor (§1.4), with the same `saved 12:06` timestamp and the same visible failure behaviour.
- **In-body images** upload immediately on insert and return their URL. There is no separate publish-image step for blog images, because a post's images are part of the authored draft rather than harvested candidates needing a curation decision. This is deliberately different from §4, which is producer-specific.
- **The editorial agent chain** (`article_brief`, then `article_draft` with `house_voice`, then `factcheck`) runs from this screen, streaming into the same log pane as everything else. The fact-check is run by a different model from the drafting model, and that split is not an implementation detail to be optimised away: a drafting model is a poor judge of its own confabulation.
- **The fact-check result renders inline as a list of claims with verdicts.** A claim the fact-check removed renders as a visible deletion with the original text struck through and the reason beside it. A deletion that leaves no trace is indistinguishable from a claim that was never made, and the reviewer needs to see which claims the model could not stand up.
- **Publish is blocked** while any fact-check claim is unresolved, and blocked while title, summary or dateline is missing, with the specific missing element named. Publishing moves the post from `content-staging/_blog_staging/` into `site/src/content/blog/_published/`, converting staged images to `site/public/blog-images/` in the same action.
- **Editing an already-published post updates it in place.** No re-publish step. New images at this stage go straight to the published image directory, since the post is already live.
- **Delete draft** removes an unpublished draft outright, with no reject-and-keep, because there is no harvested output to preserve a record of. Deleting an already-published post is not offered; publishing is a considered action.
- **No hardcoded figures.** A number in a post that ought to come from the data (a producer count, a region count, a price) is a data component, never typed prose. The register lint and `/validate` check 6 report first-person visit tells and unsourced tasting descriptors in blog bodies exactly as they do in producer entries: nobody here has tasted anything, and that applies to the blog word for word.

**Empty states:** post list, `No posts yet. Start a draft to begin.` Editor, `Select a post to edit it, or start a draft.`

### Amendment, 2026-08-13 (Gate 11): two things this section named and did not define

Both were put to the user with their alternatives and signed off the same day.

**1. "A rich-text body editor" is a source editor with a toolbar and a live preview.** Not WYSIWYG, and no editor package is vendored. The full reasoning is a dated decision in TRD.md §2.5; the short form is that WYSIWYG round-trips MDX through HTML, and `<Pull>`, `<TippedPhoto>` and `<Figure>` do not survive that trip — a WYSIWYG surface renders them as inert text and saves them back as prose. The preview pane carries the weight instead, rendering with the public site's real CSS through the same `mdx_preview` renderer the producer review pane uses.

*The toolbar writes markdown syntax into the textarea at the cursor: bold, italic, heading, link, `<Pull>`, image insert. It is an accelerator over the source, never a layer above it.*

**2. "A data component" is `<Figure of="…" member="…" />`**, specified in SCHEMA.md §9.5 before it was built, with a **closed** set of nine queries and a build failure on anything outside it. It renders a plain numeral in the body's own type — no badge, no callout, no styling of its own, because a figure is a word in a sentence and DESIGN.md §160's no-cards rule does not stop at the blog.

*Closed rather than an expression language for the reason this bullet exists at all: a post that can evaluate an arbitrary query is a post that can assert an arbitrary figure, which is the problem restated one level down.*

**Also recorded, because this section's last bullet is now only half true.** It says check 6 "reports first-person visit tells and unsourced tasting descriptors in blog bodies exactly as they do in producer entries". Until Gate 11 it did not, because check 6 read `PUBLISHED_DIR` and METHODOLOGY.md and nothing else. It does now — published post bodies, `summary`, `dateline` and `title` all join the lint, and the count line says how many post files it read. The bullet was a statement of intent written at Wave 2 and is now a statement of fact.
