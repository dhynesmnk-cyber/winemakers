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
| 6 | Urban Winery Sydney (A. Retief) | `https://urbanwinerysydney.com.au/` | Sydney / regional NSW | Urban winery on regional fruit. Location vs fruit-source separation. |

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

### 3. Gemtree — certification claimed, certifier absent

The site carries "Certified Organic & Biodynamic" in its header but **names no certifying body** in its page content — no ACO, no NASAA, no Demeter. It describes itself as "a genuine family business" without naming the family. The tasting room was closed at time of verification.

**Expected, and all three matter:**

- `organic` and `biodynamic` must **not** be recorded as `certified`, because SCHEMA.md §2a rules 2 and 3 require a named certifier and `/validate` check 9 fails without one. The correct output is `practising` with the ambiguity recorded in `confidence_notes`, or the draft held for a reviewer to look up the certification register. **Recording `certified` here is a labelling claim about a real business and is the worst failure this pipeline can produce.**
- `ownership_source` is weak. "A genuine family business" does not name who owns it, and SCHEMA.md §4.2 requires a source that *positively states* ownership — silence is not evidence of absence. Expect `independence: check`, not `clear`.
- `cellar_door` must reflect the closure rather than inventing hours.

**This draft is allowed to need reviewer intervention. That is the point of the row.**

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

### 6. Urban Winery Sydney (A. Retief) — location is not fruit source

An urban winery at Moore Park in Sydney, making wine on site under its own A. Retief label from fruit sourced from regional NSW growing areas.

**Expected:** `location` records Moore Park, NSW. `regions[]` records the **NSW growing regions the fruit comes from**, not Sydney. `category: urban_winery`. `fruit_source: purchased`, recorded neutrally — SCHEMA.md §1.4 is explicit that purchased fruit is not a demerit.

Conflating the two fields breaks both query directions, and urban wineries working regional fruit are common among exactly the producers this directory lists. If this row publishes with Sydney in `regions[]`, the schema's most important geographic distinction has failed in practice regardless of what the field definitions say.

---

## Gaps — what is not covered, and why

Stated plainly rather than padded with unverified rows.

- **No Yarra Valley row.** The Yarra Valley Smaller Wineries directory lists twenty member wineries but does not publish their own domains, and resolving each one was more verification than this document needed. Yarra Valley is a coverage region (Gate 8), not a fixture gap — add a row here if a Yarra-specific failure mode turns up.
- **No label-only producer with no cellar door.** This is a real gap: SCHEMA.md is explicit that a producer with null coordinates and `cellar_door: none` must publish normally, and no fixture currently proves it. **Until one is added, Gate 5 must test this with a hand-written staging file** rather than assuming it works.

  **Discharged 2026-08-07 (Gate 5), and still open as a seed gap.** `example-label-only.mdx` is that hand-written file. It carries a `location` with only a `state`, null coordinates and `cellar_door: none`, and it was taken through approve to a rendered page: correct rows in every table, derived JSON regenerated, no map slot, and real copy for the absent cellar door. The path is proven. What is still missing is a *real* producer of this shape, so this gap stays listed — the fixture is a stand-in for a SEED row, not a replacement for one, and it comes out before Gate 8 like every other fixture.
- **No négociant.** Row 6 covers purchased fruit, but not the négociant category specifically — buying *finished wine* to blend under one's own label is a different business from buying fruit, which is why SCHEMA.md §1.1 splits them.
- **Noisy Ritual (Brunswick East) was considered and excluded.** The site is live but announces the business is closing, final day of trade 13 June. Harvesting a closing business would produce an entry that is wrong the week it publishes.

---

## Ethics

**These are real businesses.** Do not publish any of these drafts to the live site during testing without reviewing them as a human first. Row 1 must never be published at all — it exists to be rejected, and a Wolf Blass entry appearing on a directory of independent winemakers would be a factual error about a real company on the exact axis the site claims authority over.

Harvesting honours `robots.txt` and runs at one request at a time with a identifying User-Agent. These sites are being read, not scraped at volume.
