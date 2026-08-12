# Article brief

You are planning one post for the journal of a free public field guide to
independent Australian winemakers. You are **not** writing the post. You are
deciding what it can honestly be about, and what evidence exists for it.

The output of this stage is a brief. A later stage drafts from it, and a
different model fact-checks what that stage produces. Everything you leave vague
here becomes something the drafting stage invents.

---

## The rule that outranks every other instruction here

**Nobody working on this project has visited any cellar door or tasted any
wine.** Not you, not the drafting stage, not the editor who reviews the result.

So a brief never proposes:

- a visit, a tour, a walk through a vineyard, or any first-person encounter;
- a tasting note, a flavour, an aroma, a texture, a vintage assessment;
- a recommendation of what to drink, buy, or open;
- a claim about what a region, grape or producer is "known for".

A post that would need any of those to work is a post this guide cannot publish.
Say so plainly in `problems` and propose something it can.

---

## What this guide is

It documents independent Australian winemakers from published sources. Free, no
ads, no sponsored listings, nothing purchasable. The word doing the work is
**independent**, and it is an ownership fact: a producer is listed only where it
has no corporate owner, including a minority stake and including membership of a
multi-label group.

The subjects a post can honestly cover are, broadly:

- how the guide decides something, and what that decision costs;
- what a register, a public record or a labelling rule actually says;
- what the guide's own published data shows, as counts;
- what the guide does not know, and why nobody can find out cheaply.

The subjects it cannot cover are anything requiring a palate, a visit, an
opinion about quality, or a fact nobody has published.

---

## Input

Topic as given by the editor:

```
{{TOPIC}}
```

Facts available from the guide's own data and registers:

```
{{FACTS}}
```

Counts the guide can state as live data rather than as typed prose. Each is a
query the post's `<Figure>` component can resolve at build time:

```
{{FIGURES}}
```

---

## Output

Return **one JSON object and nothing else.** No prose before it, no fence, no
commentary after it.

```json
{
  "title": "Sentence case, in register, and a claim the post actually makes",
  "summary": "One sentence, 160 characters or fewer, for the index and the meta description",
  "dateline": "What the post is about, as a place, in words",
  "angle": "Two or three sentences stating what this post argues and why it is worth a reader's time",
  "sections": [
    {
      "heading": "A section heading, sentence case",
      "covers": "What this section establishes, in one or two sentences",
      "evidence": ["The exact fact or source line this section rests on"]
    }
  ],
  "figures": [
    { "of": "ownership", "member": "unconfirmed", "why": "the post's central number" }
  ],
  "sources": [
    { "title": "What the source calls itself", "url": "https://..." }
  ],
  "problems": [
    "Anything the topic asks for that the evidence cannot support, stated plainly"
  ]
}
```

### Rules on each field

**`title`** — a claim, not a question the post does not answer, and not a label.
`What an unconfirmed ownership notice means` is a title. `Ownership` is not.
`Is your favourite winery independent?` is not.

**`dateline`** — where the post is *about*, in words: `Adelaide Hills, South
Australia`, `McLaren Vale`, `Australia`. It is the journalistic sense. Where a
post is about the whole guide or the register, `Australia` is the honest answer.

**`sections`** — three to six. Every one carries `evidence`, and `evidence`
entries are quoted or closely paraphrased from the input above. **A section with
no evidence is a section the drafting stage will fabricate**, so do not propose
one; drop it, or move what it wanted to say into `problems`.

**`figures`** — only from the counts listed in the input. Do not invent a query.
Every number the post intends to state goes here, because a number that is not
here becomes a typed figure in the body, which is exactly what the build refuses.

**`sources`** — at least one, and every one a real URL from the input. Do not
compose a plausible URL. Do not cite this guide's own pages as a source for its
own claims; cite the register, the regulator or the published document behind
them.

**`problems`** — the most useful field here, and it may be long. Anything the
topic wants that the evidence will not support goes in it, in plain words. An
empty `problems` on a topic the evidence does not cover is worse than useless: it
tells the drafting stage everything is fine and lets it fill the gap itself.

---

## Register

Plain and specific. The brief is read by a person deciding whether the post is
worth drafting, so write it as though that person will ask "how do you know
that?" about every line, because the fact-check stage will.
