---
# Drafted at Gate 4, 2026-08-07. SHIPPED at Gate 10, 2026-08-13, as
# `/methodology/`.
#
# This file is the authored source for the methodology page. It was drafted
# here, alongside the system it describes, because it is the published
# definition of independence and the document producers will argue with, and
# writing it after the fact would let the definition drift to match whatever
# the code happened to do. It is now rendered at `/methodology/` and linked
# from the footer, the corner menu, the homepage foreword and every producer
# page's independence line.
#
# The note above and this one are YAML comments rather than prose because
# everything below the frontmatter is reader-facing from Gate 10 onward. Build
# notes do not ship, and they are kept rather than deleted.
#
# Section order below is fixed by UX.md §2.5 and is not an editorial choice.
# The copy is Australian English and obeys the editorial guardrails: no banned
# words, no em dashes, no not-X-but-Y, no hedges. It is linted against
# `PROMPTS/gatekeeper.md` by /validate check 6, which is what this draft asked
# for when the list did not yet exist.
#
# The page supplies its own <h1> from `title`, so the body starts at <h2>.
title: Methodology
description: >-
  How this guide decides that a producer is independent, what the rule
  excludes, and how each determination is made and recorded.
updated: 2026-08-13
---

## What this site is, and how it is paid for

This is a field guide to independent Australian winemakers.

It is free to use. It carries no advertising, no sponsored listings and no paid
placement. No producer can pay to appear here, to rank higher, to change what
their entry says, or to have an entry removed on request. Nothing on this site
is purchasable.

That comes first because every claim after it depends on it. A directory that
sells placement cannot make a credible statement about who owns the businesses
it lists.

## What independence means here

A producer is listed here only where it has no corporate owner.

Any corporate ownership blocks publication. That includes a minority stake, and
it includes membership of a multi-label family group. The only publishable state
is a producer with no parent company at all.

## What the rule excludes

Stated as kinds of business, never as named businesses:

- a producer with an outside investor holding any share of the business, however
  small;
- one label among several under a family or portfolio group, even where the
  group itself has no corporate owner;
- a label owned by a wine company, a drinks company or an investment vehicle;
- a supermarket private label;
- a virtual brand with no winemaking operation of its own;
- a retailer's or a restaurant's house label.

> This is stricter than the trade's ordinary use of the word. It excludes
> businesses that many people, including the people who run them, would fairly
> call independent.

## Why the rule is strict

A bright line can be applied the same way to every producer. A soft one gets
argued case by case, and the arguing is won by whoever has the most to spend on
it.

A rule that bends for a good story bends hardest for the businesses with the
best storytellers, which are rarely the small ones. Drawing the line further out
than the trade does, and publishing where it sits, means a reader can work out
for themselves what an entry here does and does not tell them.

## How a determination is made

**A hand-maintained deny-list, checked before a producer enters the queue.**
It records companies known to own labels that trade under their own names, with
a source and a date against every record. A producer is checked against it three
ways, independently: by name, by the domain of its own website, and by its
Australian Business Number where one is published. Any one of the three is
enough to stop a producer entering the review queue.

**Ownership signals, extracted from the producer's own pages.** Mentions of a
parent, group or holding company, an ABN, an address shared with another label,
a contact address on another label's domain, and statements of the "part of the
X family" kind. These are recorded as evidence to be weighed. They are never
read as a verdict on their own.

**Evidence of ownership, of one of three kinds.** Any one of these is
sufficient, and it is recorded with a date:

- a registry lookup, meaning an ASIC or ABN search that identifies the operating
  entity and shows no corporate parent;
- the producer's own published ownership statement, meaning an about page or
  similar that names who owns the business;
- a named independent trade source stating ownership, such as wine media, a
  regional association register, or an importer or distributor listing.

Where these conflict, the registry lookup wins, and the conflict is recorded
against the entry.

> A source that fails to mention a parent company is not evidence that there is
> none. It has to say who owns the business.

That sentence carries more weight here than any other. "A genuine family
business" names no family. "Independently owned and operated" names no owner.
"Since 1974, our family has" says nothing about who owns it today.

## When the deny-list matches the wrong business

A deny-list matches on words, and words are shared. A winemaker's surname can
sit inside the name of a company that bought their old label years after they
left it. A vineyard can carry the name of the town it stands in, and a corporate
brand can carry that same name.

So a match on part of a longer trading name never rejects a producer by itself.
It holds the entry, and a person then has to establish which business the
register actually names. Often the register is right. Sometimes it has caught a
surname or a place name, and the producer in front of us is a separate business
that happens to share a word.

Where that judgement clears a producer, it is recorded in the entry itself,
against four things: which of the three checks matched, what it matched, the
register record it matched under, and the date that record carried when the
judgement was made. A written reason sits alongside them. Without that record
the entry fails our own validation suite and cannot ship, so a false positive
has to be judged and documented rather than left alone or argued about once and
forgotten.

The date is what stops an exemption becoming permanent. It is a judgement about
the register as it stood on a given day, and not a standing decision about a
name. If that record later changes, because the producer has since been bought
or because we have learned something we did not know, the exemption stops
applying on its own and the entry is held again for a fresh determination.

Three things an exemption can never do:

- It cannot clear a match on the producer's exact trading name, on its website
  domain, or on its ABN. Each of those identifies the business itself rather
  than a word it shares with another.
- It cannot be used on an entry whose ownership we have not confirmed. Evidence
  strong enough to show the register matched the wrong business has already
  named the right owner.
- It is never a route to listing a producer we know to be owned. A documented
  parent company excludes an entry, and nothing overrides that.

## When nobody publishes who owns a winery

Most small producers never publish an ownership statement. They are not hiding
anything; it simply does not occur to a working winery to put its shareholding
on its website, and there is no public register in Australia that fills the gap.
The business register will name the entity that trades, but it does not show who
stands behind it. So for a large share of Australian wine, the honest answer to
"who owns this?" is that we looked and could not find out.

That leaves three possible things to do, and only one of them is honest. We could
guess from how the website reads, which is the one test that fails in both
directions at once. We could leave every such producer out, which would mean a
directory of Australian wine missing most of the small producers it exists to
document. Or we can list them and say plainly what we do not know.

**Every entry on this site is therefore in one of two states, and the entry says
which:**

- **Ownership confirmed.** A dated source names who owns the business: a
  register lookup, the producer's own published statement, or a named trade
  source. The entry shows that source and its date. The independence claim on
  this site applies to it.
- **Ownership not confirmed.** No such source could be found. The entry is
  listed, it carries a visible notice saying so, and **this site makes no claim
  about that producer's independence in either direction.**

The second state is not a suspicion and it is not a lesser grade of the first.
It records the absence of published evidence, nothing more. It is common, and it
is common among exactly the small independent makers this directory was built
for.

Three things do not change when an entry is unconfirmed. A producer known to
have a parent company is still excluded outright. Unconfirmed means the owner
is unknown to us, never that a parent is known and tolerated. A producer whose
name, domain or business number matches a known portfolio owner is still
excluded, because that is a case where somebody *does* publish the ownership and
it is the wrong answer. And the entry is still written from published sources
under the same rules as every other.

If you want only the producers whose ownership has been confirmed, the notice on
each entry is what tells you, and it appears on listing pages as well as on the
entry itself.

Independence is treated as a fact about ownership. It is never inferred from how
a website reads. Corporate portfolio brands are built to read as small and
independent, and a genuinely independent producer with a thin website can read
as corporate, so any test based on tone fails in both directions at once.

## A person decides, every time

No entry is published on a machine verdict.

The pipeline reads pages, extracts ownership signals and checks the deny-list.
It can stop a producer, and it does. It cannot publish one. Clearing a producer
for publication requires a person to record the source, the kind of evidence and
the date, and to approve the entry. Where the automated checks raise anything
ambiguous, the entry cannot be approved until that specific point has been
resolved in writing.

What counts as ambiguous is drawn narrowly on purpose. A page that names the
family or the people who own the business is evidence, and it is the evidence we
ask for. It is recorded, and it does not by itself make an entry ambiguous. A
mention of a parent company, an address shared with another label, a contact
address on a different label's domain, a trading number that will not resolve,
or wording that places the business inside a group: each of those holds the
entry until a person has answered it. The distinction is drawn against a fixed
list of phrases, not against how a page reads.

This is stated because the alternative is what a reader will reasonably assume.

## Where the facts come from

Every entry is documented from published sources: the producer's own website
first, then regional association registers and named trade sources.

Nobody working on this guide has visited these cellar doors or tasted these
wines. There are no tasting notes anywhere on this site and no sentence is
written to imply otherwise. Where an entry describes a wine, it is describing
what the producer has published about it.

Where a producer does not state something, the entry leaves it out. A blank
field means the information is not published, and it is never filled with a
reasonable guess.

## How confident we are

Every fact that matters carries a record of where it came from and how strongly
it is established.

**Published by the producer** means the producer states it on their own site. It
is the level almost everything on this site currently sits at. It is honest
about what it is: the producer's own account of their business, recorded and
dated, not independently confirmed.

**Confirmed by the operator** would mean the producer has reviewed the entry and
confirmed the detail. **Observed on a visit** would mean somebody went and saw
it. Neither is claimed anywhere on this site today, and neither will appear
against an entry unless the work behind it has actually been done.

## Telling us we are wrong

Errors run in both directions, and a rule this strict will produce both kinds.

Write to us at the contact address on this site. Two commitments, stated as
commitments:

- **A producer listed here that has a corporate parent we missed is removed.**
  Show us the ownership and the entry comes down.
- **A producer wrongly excluded is reinstated**, with the evidence recorded and
  dated so the correction is visible and the mistake is not repeated.

Where the deny-list itself is wrong about a business, the deny-list is corrected,
dated, and the reason recorded. A wrong record in it is a factual error about a
real business and is treated as one.

Where the deny-list is right, the answer is this page. A producer excluded by
this rule is not being called dishonest. They fall outside a line this site drew
deliberately and published in advance.

## Coverage

Coverage is being built region by region, starting with Adelaide Hills, McLaren
Vale, the Yarra Valley and the Mornington Peninsula.

As at 2026-08-13 the guide lists **97 producers**. The four regions above carry
them: 36 in the Adelaide Hills, 24 on the Mornington Peninsula, 21 in McLaren
Vale and 19 in the Yarra Valley. A producer working fruit from more than one
region is listed under each, so those figures add to more than 97. A further
handful sit in the Clare Valley, the Eden Valley, the Barossa Valley, Langhorne
Creek, the Southern Fleurieu and Wrattonbully, which are covered incidentally
rather than deliberately, because a producer in one of the four regions also
works fruit there.

Of the 97, 48 have their ownership confirmed against a dated source and 49 do
not. Every other Australian wine region is uncovered so far.

A region covered thinly, or not at all, is where the work has reached. It is
never a judgement about what is worth drinking, and the absence of a producer
from this site is not a statement about that producer.

These figures are counted by hand and carry the date they were counted. A figure
here that has gone stale is a figure that has gone stale, and it is never a claim
that coverage stopped.

## Last updated

**2026-08-13.** The page was published on this date, and the coverage figures
above were counted on it. The definition of independence did not change.

Substantive changes to the definition of independence, with dates:

- **2026-08-07.** First published definition. Any corporate ownership blocks
  publication, including minority stakes and multi-label family groups.
- **2026-08-09.** Added the *ownership not confirmed* state. Until this date, a
  producer whose ownership could not be established from a published source was
  not listed at all. It is now listed, with a visible notice, and this site
  makes no independence claim for it. **The rule itself did not change**: a
  documented parent company still blocks publication, and a match against the
  register of known portfolio owners still blocks publication. What changed is
  that silence is now recorded and shown to you, rather than being treated as
  grounds for leaving a producer out.
- **2026-08-10.** Wrote down how a match against the wrong business is cleared,
  under *When the deny-list matches the wrong business* above. **The rule itself
  did not change**, and neither did what the register blocks. Until this date a
  judgement that the register had caught a shared surname or a place name was
  recorded in working notes that were never published and did not travel with
  the site's source. It is now recorded in the entry, it names the register
  record and the date it was judged against, and it expires by itself when that
  record changes.

A definition that changes silently is not a definition. Every future change to
what "independent" means on this site is added to this list, with its date, and
the previous wording stays readable in the site's history.
