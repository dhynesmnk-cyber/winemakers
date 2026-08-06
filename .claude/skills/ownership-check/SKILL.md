---
name: ownership-check
description: The independence determination procedure and its evidence requirements. Use before publishing any producer, when a draft comes back `check`, when editing data/ownership.json or admin/pipeline/ownership.py, when a producer disputes their exclusion, or when writing or amending the methodology page. Also use when a deny-list match needs judging.
---

# Ownership check — the independence determination

**This is the reason the site exists.** SCHEMA.md §4 is the contract; this is how
you carry it out. If this procedure is wrong, everything else on the site is
decoration.

The word doing the work is **independent**. It is the inclusion criterion, the
editorial position, and the thing a reader is trusting when they use the
directory. A single corporate-owned producer published here damages the whole
set, because the claim being made is not about that entry, it is about every
entry.

## The rule

**Strict. Any corporate ownership blocks publication, including minority stakes
and multi-label family groups. `parent_company: null` is the only publishable
value.**

This was put to the user against a control-versus-equity alternative and chosen
deliberately (HANDOVER, confirmed decisions). It is settled. Do not re-litigate
it, and do not quietly soften it to fit a producer you like.

It is **stricter than the trade's ordinary use of the word**, and the exclusions
it produces are real:

- a maker with a 20% outside investor;
- one of four labels under a family group that is itself unowned;
- a fifty-year-old estate with its own cellar door, bought by a retailer.

Every one of those is called independent by people who work in wine. This site
calls them owned. **That is why the methodology page must define the term as this
site uses it** rather than relying on the reader's assumption, and why it must
state what the rule excludes rather than only what it includes.

## The first principle

**Independence is an ownership fact. It is never inferred from prose.**

Corporate portfolio brands are engineered to read as small and independent. That
is their design brief and they are good at it. A genuinely independent producer
with a thin website may read as corporate. **Any test based on tone fails
systematically in both directions.**

`SEED.md` row 1 is the proof. The Wolf Blass site names no parent company
anywhere: not in the footer, not in the copyright line, not in a privacy link.
It presents a standalone winery with its own origin story. Its only corporate
trace is the trading entity in the terms of sale. A tone-based test passes it
comfortably. It must be rejected, and only the deny-list can do it.

**No agent decides independence from marketing prose. The Harvester extracts
ownership signals; it never judges them.**

## Evidence of a negative

Because the rule is strict, `ownership_source` documents the **absence** of a
corporate parent. That is harder evidence than documenting a presence, and it is
where this procedure earns its keep.

One of the following is sufficient, recorded with a date and with the method
stored in `ownership_source.method`:

| Method | What it is |
|---|---|
| `registry` | An ASIC or ABN lookup identifying the operating entity and showing no corporate parent. |
| `producer_statement` | The producer's own published ownership statement: an about or our-story page that **names who owns the business**. |
| `trade_source` | A named independent trade source stating ownership: wine media, a regional association register, an importer or distributor listing. |

**Any one of the three is sufficient**, provided it is specific about who owns
the business and is recorded with a date.

**Where the three conflict, the registry wins, and the conflict is noted in
`confidence_notes`.**

### The sentence that does the most work

> **A source that merely fails to mention a parent is not evidence of absence. It
> must positively state ownership.**

Most weak determinations fail exactly here. "A genuine family business" does not
name a family. "Independently owned and operated" does not name an owner. "Since
1974, our family has…" does not say who owns it now. None of those is evidence.

If the strongest thing you have is a page that does not mention a parent, the
verdict is `check`, not `clear`.

## The procedure

1. **Run the deny-list first, before anything else.** `data/ownership.json` is
   checked on **name, domain and ABN**, independently. Any one of the three
   matching is a hit. Gate 4's done-condition requires each path to work on its
   own, so never collapse them into a single combined test.

2. **Read the record's `verdict` on a hit.**
   - `reject` — the attribution is documented. The draft is blocked and no file
     is written. Under no circumstance does a rejected producer reach the queue.
   - `check` — the attribution is credible but not confirmed against a registry.
     The draft goes to human review carrying the flag and the matching record.
     **It never auto-publishes.**

3. **Read the Harvester's `ownership_signals`.** Parent-company mentions, the
   ABN, a shared address, a contact email on another label's domain, and any
   "part of the X family" statements. Treat these as evidence to weigh, not as a
   verdict. **An empty `parent_company_mentions` array means nothing.** It is the
   normal state of a corporate portfolio site.

4. **Establish the positive statement of ownership.** Find one of the three
   evidence routes above. Record the URL, the method and the date.

5. **Set the verdict.**
   - `clear` — the deny-list is silent, the signals are clean, and there is a
     dated source that positively states ownership with no corporate parent.
   - `check` — anything ambiguous. A parent-company mention you cannot resolve, a
     shared address, an ownership page that names nobody, a `check`-verdict
     deny-list hit. **`check` never auto-publishes. That is the whole point of
     the state.**
   - `reject` — a documented corporate parent, or a `reject`-verdict deny-list
     hit, or one of the §4.4 categories below.

6. **Write it into the frontmatter at publish time, never afterwards.**
   `parent_company: null` and a complete `ownership_source` object with
   `{source, method, date}`. Gate 8's done-condition is explicit that the
   determination is made **at publish time, never backfilled**, and a backfilled
   provenance block is indistinguishable from a fabricated one.

## Reject categories

SCHEMA.md §4.4, in full:

- **Pure retailers.** Not producers.
- **Restaurants.** Not producers.
- **Large corporate portfolio brands.**
- **Virtual brands and supermarket private labels.** The highest-volume false
  positive, because they have plausible-looking standalone sites *by design*.
  That is what they are for.

The last of those is the one that will cost the most reviewer time and the one
most likely to slip through. A label with a nice site, a founder story, a
region and no winery is the shape to be suspicious of. Look for a physical
address, an operating entity, and someone's name.

## Maintaining `data/ownership.json`

The file's own header carries its rules. The load-bearing ones:

- **Every record carries a `source` URL and an `updated` date.** No exceptions.
- **No label appears under two parents.** The data-curator agent checks this.
- **ABNs are recorded only from a lookup or from the operator's own published
  trading terms**, with the source and the date. **Never guess an ABN, never
  infer one from a company name, and never carry one across from a related
  entity.** A wrong ABN in a deny-list rejects an innocent business by a number
  nobody will think to question.
- **A label goes in the file when it trades under its own name and a reader would
  reasonably take it for independent, but it is owned.** Ranges within a single
  family company do not go in: nobody is going to harvest "Rufus Stone" as a
  standalone producer, and listing it over-blocks without catching anything.
- **Name matching must not fire on a place name.** `Tatachilla` is both a
  Vinarchy label and a McLaren Vale locality carried in `regions.ts`. Match on
  the producer's name field, not on free text.
- **Surname matching is a trap.** All Saints Estate is run by members of the
  Brown family through a separate business and is not owned by Brown Family Wine
  Group. Match businesses, not families.

Changing this file changes the site's editorial position. `schema-change`'s last
section applies: it needs the methodology page updated alongside it and explicit
user sign-off before it lands.

## When a producer disputes their exclusion

This will happen, and the methodology page exists so that it can be answered
rather than argued.

1. **Check the determination against this procedure**, not against how the
   producer describes themselves.
2. **If the deny-list is wrong, fix the deny-list**, date the change, and record
   what the evidence was. A wrong entry in the file is a factual error about a
   real business and is corrected quickly and visibly.
3. **If the deny-list is right, the answer is the methodology page.** The rule is
   stricter than the trade's ordinary use of the word and the page says so. The
   producer is not being called dishonest. They are outside a line the site drew
   deliberately and published in advance.
4. **Never make a one-off exception.** An exception that is not in the rule is
   the point at which the directory stops being trustworthy, and it will not stay
   a single exception.

## Never

- Never decide independence from tone, prose, page design or how small a
  producer feels.
- Never read silence about a parent company as evidence there is none.
- Never let a `check` auto-publish.
- Never publish without `ownership_source`, and never backfill one.
- Never guess an ABN.
- Never widen the rule to fit a producer. Ask the user instead.
- Never publish `SEED.md` row 1. It exists to be rejected.

## What `/validate` enforces

Check 8, at Gate 4. Report-only, like every check:

- no producer published without `ownership_source` carrying a non-empty source
  and a date;
- **no producer published with a non-null `parent_company`**;
- zero hits when every published name, domain and ABN is re-checked against the
  deny-list.

The re-check matters as much as the first pass. `ownership.json` grows, and a
producer published cleanly in March can become a deny-list hit in September
because someone bought them. Check 8 is what notices.
