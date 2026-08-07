# SEED.md — Pipeline fixture producers

Gate 5's done-condition runs against these URLs. Each is chosen for a **distinct failure mode**, not for coverage — these are the fixtures that prove the pipeline handles the hard cases, and several deliberately sit outside the four seed regions.

**Every URL below was fetched and verified on 2026-08-07.** What each row claims about a site is what the site actually said on that date, quoted where it matters. Sites change; re-verify before relying on a row, and update the date. The honesty rule (CLAUDE.md rule 6) applies to this document exactly as it applies to a producer entry — a fixture whose expected outcome was guessed rather than observed is worse than no fixture, because it makes a broken pipeline look tested.

| # | Producer | URL | Region | The failure mode it tests |
|---|---|---|---|---|
| 1 | Wolf Blass | `https://www.wolfblass.com/en-au/` | Barossa | **Corporate portfolio label that must be REJECTED.** The most important row. |
| 2 | d'Arenberg | `https://www.darenberg.com.au/the-story` | McLaren Vale | Florid marketing copy and the winery's own tasting notes. Banned-word and descriptor stress. **Playwright-only, see below.** |
| 3 | Gemtree Wines | `https://gemtreewines.com/` | McLaren Vale | Certification claimed, certifier not named. Weak ownership evidence. |
| 4 | Basket Range Wine | `https://basketrangewine.com.au/about` | Adelaide Hills | Clean independent baseline. Practising, not certified. |
| 5 | Myrtaceae | `https://www.myrtaceae.com.au/` | Mornington Peninsula | Thin page. Appointment-gated cellar door. Fee with unstated waiver. |
| 6 | A. Retief | `https://aretief.com.au/` | Gundagai / regional NSW | Location vs fruit-source separation. **URL amended 2026-08-08, see below** — `urbanwinerysydney.com.au` no longer resolves. |

---

## Expectations per run

### 1. Wolf Blass — must be rejected, and only the deny-list can do it

This row exists to prove the central claim of SCHEMA.md §4: **independence is an ownership fact and is not inferable from prose.**

Wolf Blass is publicly documented as a Treasury Wine Estates brand. Its own site names **no parent company anywhere** — not in the footer, not in the copyright line, not in a privacy link. It presents as a standalone winery with its own origin story ("Our Barossa Valley Home", "From Tin Shed To World Class Home"). The only corporate trace on the page is the trading entity in the terms of sale:

> Your contract of sale will be with Wolf Blass ABN 55 004 094 599

**Expected:** `independence: reject`. The Harvester's `ownership_signals.parent_company_mentions` should come back **empty**, and that must not be read as evidence of independence. The rejection comes from `data/ownership.json` matching on name, on domain, and on the ABN above — three independent paths, and Gate 4's done-condition requires each to work on its own.

**This run fails the gate if the draft is written at all.** A tone-based test passes this site comfortably, which is precisely why the pipeline must not use one. Seed `ownership.json` with the TWE label list, the domain, and this ABN before running Gate 4.

### 2. d'Arenberg — publishes, but only after the prose is stripped to facts

**Amended 2026-08-07 (Gate 5), against two things observed live.** The row's URL was `https://www.darenberg.com.au/` and is now `/the-story`. Both changes are recorded here rather than made quietly, because a fixture that was silently repointed is a fixture nobody can audit.

**It needs the Playwright fallback.** Plain httpx gets Cloudflare `403` from this site, while the site's own `robots.txt` permits crawling and asks for `Crawl-delay: 1`. So the published policy allows us and a WAF heuristic does not. The fallback clears it **with our own descriptive user agent unchanged** — no browser-agent spoofing, which would be evading a block rather than honouring a policy. This is the one SEED row that exercises the user-triggered Playwright path end to end.

**The homepage was the wrong target.** Its extraction is 9,039 characters of privacy policy and *zero* words about the winery, on every trafilatura setting — not an extractor bug, but the honest consequence of a marketing homepage where the longest run of continuous prose genuinely is the legal boilerplate. That extraction is well over `THIN_EXTRACTION_CHARS`, so nothing would have stopped it reaching the Harvester. `fetcher.BoilerplateExtraction` now refuses it, and this row is the fixture behind that guard.

`/the-story` extracts 62,304 characters and carries the copy quoted below, which is what the row exists to test.

Family-owned since 1912, fourth generation, no parent company. It should pass the independence check cleanly. The test is the writing.

The site's copy is florid by design ("The Art of Being Different"), and its wine descriptions are the producer's own tasting notes:

> Dense and plush, a real crowd pleaser thanks to the generosity of fruit characters
>
> Tannins that are long, lively, gritty and youthful with fragrant fruit minerality

**Expected:** a publishable draft with **none of that language surviving**. Specifically:

- Zero banned-list words in the body, summary or FAQ.
- **No tasting descriptors at all.** These are the winery's marketing notes, not observations, and nobody on this project has tasted the wine. "Dense and plush" must not be laundered into the entry as though the directory were describing the wine. This is the single most likely way the honesty rule gets broken on this project, and this row is the canary.
- Facts kept: founding year 1912, the Osborn family, the McLaren Vale address, varieties actually named.

A draft that reads like the winery's own website has failed, even if every individual fact in it is true.

**Amended 2026-08-08 (Gate 5), after the run.**

**The canary passed.** Zero register-lint hits on body, summary and FAQ. None of `plush`, `crowd pleaser`, `generosity`, `gritty`, `minerality`, `lively` or `youthful` survived, and no tasting descriptor of any kind appeared. The facts the row asks to be kept were kept: 1912, the Osborn family, McLaren Vale, Chester Osborn as chief winemaker since 1984, and NASAA named for both certifications. The Playwright fallback cleared the Cloudflare 403 exactly as this row predicted, with our own user agent unchanged.

**It took two defects to get there, both found by this row.**

The first is the one worth remembering. The Architect returned frontmatter whose FAQ answer read `answer: The sparkling wine is the stated exception: DADD, later rebranded…` — an unquoted colon, which YAML reads as a key separator, so the document stopped parsing. UX.md §1.5 row 4 promises "one automatic re-ask with the parse error appended" for malformed JSON **or MDX**. The Harvester and Gatekeeper both got that re-ask because they passed a real validator to `agents.call`. The Architect passed an identity function and parsed its output afterwards, so the content tier never saw the error. **The stage that writes the most text was the one stage with no second chance**, and this URL failed outright after a successful browser fetch and two paid model calls. The cause was in the prompt as much as the code: rule 2 tells the model to replace em dashes with a colon, in frontmatter and FAQ alike, and never told it to quote the result.

The second: `slugify` swept accents into hyphens, so `Mourvèdre` became `mourv-dre`. Five varieties already in the frozen §1 vocabulary — `albarino`, `gewurztraminer`, `gruner-veltliner`, `pedro-ximenez`, `blaufrankisch` — were unreachable by their correct spelling, and row 11 was faithfully reporting each as unmatched and dropping it. Row 11 exists so a producer's varieties are never silently lost; it was doing its job on input that should have matched.

Four varieties are still unmatched here and three of them are a vocabulary question, not a bug: `Mourvèdre` folds to `mourvedre`, but the vocabulary carries the Australian name `mataro` and there is no synonym mechanism. `Mencía` and `Chambourcin` are absent outright. Recorded rather than fixed, because adding an enum value is a four-surface change (CLAUDE.md rule 7) and needs sign-off.

### 3. Gemtree — certification claimed, certifier absent

The site carries "Certified Organic & Biodynamic" in its header but **names no certifying body** in its page content — no ACO, no NASAA, no Demeter. It describes itself as "a genuine family business" without naming the family. The tasting room was closed at time of verification.

**Expected, and all three matter:**

- `organic` and `biodynamic` must **not** be recorded as `certified`, because SCHEMA.md §2a rules 2 and 3 require a named certifier and `/validate` check 9 fails without one. The correct output is `practising` with the ambiguity recorded in `confidence_notes`, or the draft held for a reviewer to look up the certification register. **Recording `certified` here is a labelling claim about a real business and is the worst failure this pipeline can produce.**
- `ownership_source` is weak. "A genuine family business" does not name who owns it, and SCHEMA.md §4.2 requires a source that *positively states* ownership — silence is not evidence of absence. Expect `independence: check`, not `clear`.
- `cellar_door` must reflect the closure rather than inventing hours.

**This draft is allowed to need reviewer intervention. That is the point of the row.**

**Amended 2026-08-08 (Gate 5), after the run. This row found the most serious defect in the build so far.**

The certification half was right on the first pass: `organic: practising`, `biodynamic: practising`, both certifiers null. The pipeline refused to record `certified` without a named certifier, which is the failure this row calls the worst one possible.

The ownership half was wrong, and it was wrong in the code, not in the row. The run returned `clear` with the basis "no deny-list match on name, domain or ABN, **and no ownership signals extracted**". `determine` started every producer at `clear` and only an escalating signal moved it, so a page that said nothing whatever about ownership was cleared **on the strength of its silence** — the reading SCHEMA.md §4.2, `ownership.py`'s own docstring and the `ownership-check` skill all forbid in the same words.

The consequence reaches past this row. Row 1 exists to prove the deny-list is necessary because Wolf Blass names no parent anywhere. It proves something narrower than intended if silence alone clears everyone: a portfolio label **not yet in the register**, on an equally silent site, was publishable as independent. The register was carrying the whole load with nothing behind it.

Worse, the draft was published carrying `ownership_source.method: producer_statement`, which asserts the producer stated their ownership. Nothing of the sort was extracted. The method was hardcoded, and when that was fixed the Architect supplied one itself — `ownership_source` has always been in `PIPELINE_OWNED_FIELDS`, where "no agent's output survives", but the stamp deferred to the agent whenever it wrote something. A fabricated provenance claim in the field whose only purpose is auditability.

Both are fixed. This row now returns `check`, with the basis "the source does not state who owns this business", no `ownership_source` at all, and approval blocked until a human records real evidence. **The row did exactly what it was written to do**, and it did it by predicting an answer the code could not yet produce — the same way row 4 did, and for the same reason: it was written from the spec rather than from the implementation.

### 4. Basket Range Wine — the clean baseline

A family-run Adelaide Hills winery and vineyard, second-generation winemaker Sholto Broderick with parents Phillip and Mary, farming since the 1980s. The About page states ownership plainly, which satisfies SCHEMA.md §4.2 route 2.

The vineyard is described as farmed "using sustainable practices" — **not** organic, **not** biodynamic, **not** certified.

**Expected:** `independence: clear`, a publishable draft on the first pass, `organic: none` or `practising` with a confidence note, both certifiers null, and varieties drawn only from those the page actually names (Pinot Noir, Chardonnay, Cabernet Sauvignon, Merlot, Petit Verdot). "Sustainable" must not be silently upgraded to "organic" — they are different claims and only one of them is on the page.

This is the row that should produce the least reviewer work. If it doesn't, something upstream is wrong.

**Amended 2026-08-07 (Gate 5), after the run.** Two corrections, recorded rather than made quietly, on the same standard row 2 was held to.

**The URL.** The row said `https://basketrangewine.com.au/` and the run used `/about`. The prose above already said "The About page states ownership plainly", so the table and the prose had disagreed since the row was written, and the run followed the prose. The table now says `/about`.

**The outcome, and it did not match.** The row predicted `clear`; the pipeline returned `check` and a person resolved it by hand. It was right about the producer and wrong about the code. The About page names Phillip, Mary and Sholto Broderick, which is exactly the SCHEMA.md §4.2 route 2 evidence this row was written to produce — but any populated `ownership_signals` key escalated to `check`, and `PROMPTS/harvester.md` files a positive ownership claim under `statements`. So the entry was escalated for containing its own evidence. `ownership.py` was amended the same day (SCHEMA.md §4.5, UX.md §1.4.2); this row now returns `clear` as written, and it did so before the fixture was re-run, from the signals the original run extracted.

**This row did its job.** It was the fixture that exposed the rule, and it exposed it by predicting an answer the code could not yet produce. A fixture that had been written to match the implementation would have agreed with it and found nothing.

### 5. Myrtaceae — thin page, appointment gate, unstated waiver

Roughly 250–300 words of content on the cellar-door page, mostly visitor logistics. Located at Red Hill, Mornington Peninsula. Weekend hours are published but reservations are required. Tasting fee is five dollars; **whether it is waived on purchase is not stated.**

**Expected:**

- The thin extraction should trip the low-content threshold and surface the Playwright-fallback path rather than silently producing a near-empty draft.
- `cellar_door: by_appointment`, not `open`. Published weekend hours with a required reservation is exactly the state the enum exists to capture, and exactly what a boolean would have destroyed.
- `tasting_fee.fee_aud: 15` — **no.** `fee_aud: 5`, and `waived_on_purchase: null`, not `false`. Unstated is not the same as no, and guessing here would be a fabricated commercial term.
- `cost` must corroborate the structured fee, or `/validate` check 10 fails.
- A short entry is the correct output. Per the Architect's integrity rules, 350 words of true beats 700 of padding.

**Amended 2026-08-08 (Gate 5), after the run. The first expectation is met; the rest cannot be tested against this producer.**

The homepage extracts 457 characters and trips `THIN_EXTRACTION_CHARS`, logging `thin extraction: 457 chars` and offering the Playwright retry without drafting — exactly failure-table row 3, exactly what this row asks for. **The retry changes nothing.** Playwright fetched 128.2 kB of HTML and trafilatura still extracted 457 characters, because the text genuinely is not there. `/about` is the site's largest page at 981 characters, still under the 1000 threshold; `/cellardoor`, which carries the $5 fee and names John and Julie as owners, is 269.

So Myrtaceae's entire web presence sits below the threshold on every page. The cellar-door, fee and waiver expectations above are **untestable against this producer** and are recorded as such rather than being made to pass by lowering the bar for one row.

**This surfaces a conflict, flagged rather than resolved (CLAUDE.md rule 3).** CLAUDE.md's Gate 5 done-condition says "each URL in SEED.md runs end to end producing a schema-valid staged draft". This row's own first expectation is that the correct outcome is **no draft**. SEED.md is the more specific document about what each row should do, so the run is counted as correct, but the done-condition's wording does not cover a row whose right answer is to stop.

### 6. Urban Winery Sydney (A. Retief) — location is not fruit source

An urban winery at Moore Park in Sydney, making wine on site under its own A. Retief label from fruit sourced from regional NSW growing areas.

**Expected:** `location` records Moore Park, NSW. `regions[]` records the **NSW growing regions the fruit comes from**, not Sydney. `category: urban_winery`. `fruit_source: purchased`, recorded neutrally — SCHEMA.md §1.4 is explicit that purchased fruit is not a demerit.

Conflating the two fields breaks both query directions, and urban wineries working regional fruit are common among exactly the producers this directory lists. If this row publishes with Sydney in `regions[]`, the schema's most important geographic distinction has failed in practice regardless of what the field definitions say.

**Amended 2026-08-08 (Gate 5). The URL changed, and the change is recorded rather than made quietly.**

`urbanwinerysydney.com.au` **no longer resolves.** `getaddrinfo` returns `Name or service not known` for both the apex and `www`, while `google.com`, `basketrangewine.com.au` and `gemtreewines.com` resolve from the same machine in the same second — so this is the domain, not the network. It was fetched and verified on 2026-08-07, one day before.

The business publishes at **`aretief.com.au`**, which is live and is plainly the same operation: Alex Retief, winemaking since 2008, with `Gundagai · Hilltops · Tumbarumba · Sydney` in its own masthead. The row now points there, with user sign-off.

**The core assertion held.** `regions` came back `['gundagai', 'hilltops', 'tumbarumba']` — the NSW growing regions, with **Sydney correctly absent**. That is the one thing this row exists to prove.

Two of the row's specifics no longer match, because the new site is not the old one rather than because the pipeline erred: `location` records Gundagai and `category` reads `estate_winery`, since `aretief.com.au` foregrounds the family vineyard where `urbanwinerysydney.com.au` foregrounded the Moore Park winery. **The urban-winery half of this row is therefore no longer covered** — `category: urban_winery` and a metropolitan location against regional fruit are currently tested by nothing. Recorded as an open gap below.

The run also returned `check`, not `clear`: the page names no owner, and after the 2026-08-08 amendment described under row 3 that is correctly a request for a human rather than a clearance.

---

## Gaps — what is not covered, and why

Stated plainly rather than padded with unverified rows.

- **No Yarra Valley row.** The Yarra Valley Smaller Wineries directory lists twenty member wineries but does not publish their own domains, and resolving each one was more verification than this document needed. Yarra Valley is a coverage region (Gate 8), not a fixture gap — add a row here if a Yarra-specific failure mode turns up.
- **No label-only producer with no cellar door.** This is a real gap: SCHEMA.md is explicit that a producer with null coordinates and `cellar_door: none` must publish normally, and no fixture currently proves it. **Until one is added, Gate 5 must test this with a hand-written staging file** rather than assuming it works.

  **Discharged 2026-08-07 (Gate 5), and still open as a seed gap.** `example-label-only.mdx` is that hand-written file. It carries a `location` with only a `state`, null coordinates and `cellar_door: none`, and it was taken through approve to a rendered page: correct rows in every table, derived JSON regenerated, no map slot, and real copy for the absent cellar door. The path is proven. What is still missing is a *real* producer of this shape, so this gap stays listed — the fixture is a stand-in for a SEED row, not a replacement for one, and it comes out before Gate 8 like every other fixture.
- **No urban winery, as of 2026-08-08.** Row 6 covered it until `urbanwinerysydney.com.au` stopped resolving; its replacement leads with a regional vineyard, so `category: urban_winery` and a metropolitan location against regional fruit are now tested by nothing. This is a real gap in the shape row 6 was written for, not a coverage gap: the distinction between where a winery stands and where its fruit grows is the one SCHEMA.md calls its most important geographic split.
- **No producer whose site is below the extraction threshold can be drafted.** Row 5 is that producer, and Myrtaceae is not unusual: a small maker with a 250-word site is a normal shape for this directory. The pipeline currently declines all of them. Whether `THIN_EXTRACTION_CHARS` is right, or whether a thin page should draft a short entry a human completes, is an open question and not a Gate 5 one.
- **No variety synonyms.** `Mourvèdre` does not reach `mataro`, and a producer naming it that way loses it. Row 2 surfaced this. Mataro is among the most planted red varieties in the country.
- **No négociant.** Row 6 covers purchased fruit, but not the négociant category specifically — buying *finished wine* to blend under one's own label is a different business from buying fruit, which is why SCHEMA.md §1.1 splits them.
- **Noisy Ritual (Brunswick East) was considered and excluded.** The site is live but announces the business is closing, final day of trade 13 June. Harvesting a closing business would produce an entry that is wrong the week it publishes.

---

## Ethics

**These are real businesses.** Do not publish any of these drafts to the live site during testing without reviewing them as a human first. Row 1 must never be published at all — it exists to be rejected, and a Wolf Blass entry appearing on a directory of independent winemakers would be a factual error about a real company on the exact axis the site claims authority over.

Harvesting honours `robots.txt` and runs at one request at a time with a identifying User-Agent. These sites are being read, not scraped at volume.
