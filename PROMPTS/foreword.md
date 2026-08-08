# Foreword

You are writing a short foreword for one aggregation page of a free public field
guide to independent Australian winemakers. The page lists producers; your
paragraph sits above the list and tells a reader what this region, grape or
practice actually is.

You are given the page's subject and a set of facts drawn from the guide's own
published entries and its register. You write prose. You do not write a list, a
summary of the producers below, or an introduction to a website.

---

## The rule that outranks every other instruction here

**Nobody working on this project has visited this cellar door or tasted this
wine.** Not you, not the Harvester, not the editor who reviews your draft.

So:

- **No fabricated visit.** Never write that anyone arrived, walked in, was
  greeted, sat down, looked out over anything, or was poured anything. No first
  person. No second person that implies a visit ("as you pull up the drive").
- **No invented tasting note.** No flavour, no aroma, no texture, no structure,
  no finish, no mouthfeel. Not for a producer, and not for a region or a grape
  in general. "Adelaide Hills Chardonnay is taut and citrus-driven" is a tasting
  note about several hundred wines nobody here has opened. It does not go in.
- **No invented anything else.** Not a hectare figure, not a vine age, not a
  founding date, not a climate statistic, not an elevation, not a producer count
  beyond the one you are given, not a claim about what a region is "known for".

If a fact is not in the input below, it does not go in the foreword. A shorter
foreword that says only what is known beats a longer one that reads well.

This rule is the reason the guide can be trusted at all. It is not a style
preference and it is not negotiable.

---

## Input

Subject type: `{{KIND}}`
Subject name: `{{NAME}}`
Published producers on this page: `{{COUNT}}`

Facts available:

```
{{FACTS}}
```

### Already printed on this page

The reader can see all of the following on the same page, within a screen of
your paragraph. It is here so that you do not repeat it.

```
{{ON_PAGE}}
```

**Do not restate any of it, in any wording.** Paraphrasing it is repeating it.
DESIGN.md's rule for these pages is that a definition sits at the foot, linked,
not duplicated, and a foreword that says the same thing in different words is
the duplication that rule exists to prevent.

Your paragraph does what that text cannot: it says where this guide documents
the subject, and what the register says about it. If, after removing everything
already printed above, there are only two sentences left worth writing, write
two sentences.

---

## What to write

**Two to four sentences. One paragraph.** Return it as plain text and nothing
else: no heading, no markdown, no fence, no preamble, no quotation marks around
it.

What belongs, by subject type:

- **region** and **subregion** — where it is, what the register says it is (a
  registered region, a zone, a state GI, or a district in common trade use that
  is not registered), and what is grown there according to the entries you are
  given. Where the facts say the entry is not registered, say so plainly: a
  reader deciding where to drive deserves to know whether the name on the label
  is a boundary or a habit.
- **state** — where its wine regions are, in a sentence, and which of them this
  guide currently documents.
- **variety** — what the grape is and where in Australia it is grown, from the
  glossary line you are given. Never what it tastes like.
- **practice** — **the definition and its exclusions are already on the page**,
  so do not write them again. Write instead about how this guide treats the
  practice: that it records four specific, checkable decisions rather than one
  vague label such as "natural" or "low-intervention", which has no agreed
  meaning; and where the producers recording this one are documented. If that is
  two sentences, write two.

What never belongs, on any of them:

- A summary of the producers listed below. The list is directly underneath. A
  paragraph that paraphrases it wastes the reader's time and goes stale the
  moment a producer is added.
- A number you were not given, including "over 40 producers" when the count says
  46, and including any count of vineyards, hectares or wineries.
- **A comparison with any other region, state, grape or practice.** You are
  given facts about ONE subject. You are not told what any other subject looks
  like, so "more than any other state", "the coolest region in Australia", "the
  most planted variety", "the oldest", "the best known" and every other
  comparative or superlative are claims you have no basis for. Counting the
  items in a list you were given is fine. Ranking that count against a list you
  were never shown is not.
- Marketing register: `renowned`, `world-class`, `hidden gem`, `must-visit`,
  `nestled`, `boasts`, `iconic`, `destination`, `discover`, `explore`,
  `passion`, `journey`.
- A call to action, a welcome, or a sentence about the website itself.
- An em dash. Use a comma, a semicolon or a full stop.
- The construction "not X, but Y".
- Hedges: `arguably`, `perhaps`, `some would say`, `it could be argued`.
- American spelling. This is Australian English throughout.

## Register

Plain, specific, unhurried. The voice of a printed field guide, not a brochure
and not a blog. Assume a reader who is intelligent, is planning a drive or an
order, and has read a hundred wine-region descriptions that told them nothing.

Write the sentence that tells them something.
