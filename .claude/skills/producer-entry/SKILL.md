---
name: producer-entry
description: The register, the honesty rule and the editorial guardrails for anything a reader sees — producer entries, FAQ answers, foreword copy, admin UI strings, blog posts. Use when writing or editing reader-facing prose, when reviewing a staged draft's body copy, when a Gatekeeper rule needs interpreting, or before hand-editing an entry in the review pane.
---

# Producer entry — the register and the rules

## Where the rules actually live

**`PROMPTS/gatekeeper.md` is the authority.** The banned-word list, the hedge
list, the tasting-descriptor list, the visit-tell list, the not-X-but-Y patterns,
the conditional-claim phrases and the US-spelling pairs are all authored there,
in fenced blocks, and **this skill does not restate them**.

That is deliberate. `/validate` check 6 parses those same fenced blocks, so there
is exactly one copy of every list and it is the copy the Gatekeeper is actually
run with. A second hand-kept copy here would drift, and the first symptom would
be a lint that passes copy the model was never told to avoid, or a reviewer
applying a rule the pipeline no longer enforces.

**Read `PROMPTS/gatekeeper.md` before editing reader-facing prose.** Read
`PROMPTS/architect.md` for what the drafting stage is told about structure and
register.

*(Amended 2026-08-07, Gate 5. CLAUDE.md previously said the lists were "mirrored
into" this skill. They are referenced by it instead, for the reason above.)*

## The honesty rule — CLAUDE.md rule 6, non-negotiable

**Nobody on this project has visited these cellar doors or tasted these wines.**

No fabricated visit. No invented tasting note. No first-hand sensory claim. No
sentence may imply otherwise.

This is not a style preference. It is the reason the directory can be trusted at
all, and it is the single rule most likely to be broken by accident, because the
source material actively invites breaking it: a winery's own site is full of its
own tasting notes, written in the present tense, ready to be paraphrased.

Two specific traps:

- **Laundering the producer's tasting notes.** "Dense and plush, a real crowd
  pleaser" is the winery's marketing copy. Moved into an entry it reads as the
  directory describing the wine. It may appear **only** inside a `<Pull>` as a
  marked quotation, attributed.
- **Second person that implies presence.** "As you pull up the drive" and "you'll
  find the cellar door tucked behind the shed" are visit claims wearing a
  different hat.

## What to do instead

**Attribute claims that are claims.** "The producer states that the fruit is
farmed organically" is honest. "The fruit is farmed organically" is the directory
vouching for something it has not inspected.

**Report silence as a fact about the source.** "The producer is explicit about
this rather than leaving a reader to infer a claim from silence" is real
information, and it is the kind a field guide exists to give.

**Explain rather than assert.** Telling a reader *why* an uncertified organic
grower is ordinary at that scale is the value. It needs no first-hand claim.

**Write short when the source is thin.** 350 words of true beats 700 of padding.
Padding is the mechanism by which every rule above actually gets broken.

## Four phrases that require their evidence

Not banned — conditional. Each may be used only when the specific fact is stated
in the entry itself (CLAUDE.md editorial guardrails):

| Phrase | Requires |
|---|---|
| `single-vineyard` | the vineyard named |
| `old vines` | the vine age or planting year stated |
| `family-owned` | the owning family named |
| `award-winning` | the specific award stated |

"A genuine family business" that names no family does not license
`family-owned`. Write what the page supports: that the producer describes itself
as a family business.

## Certification is a labelling claim about a real business

`organic: certified` requires a **named certifier** — ACO, NASAA, AUS-QUAL,
Demeter. Without one the correct value is `practising` at most, with the
ambiguity recorded in `confidence_notes`. Same for `biodynamic`.

"Sustainable", "low-input", "minimal intervention" and "natural" are **none of
these things**. They are different claims and are never upgraded.

The pipeline enforces this in `orchestrator._finalize_frontmatter`, and
`/validate` check 9 fails on it. Do not hand-edit around either.

## Independence is never a tone judgement

CLAUDE.md rule 8. No agent and no editor decides independence from marketing
prose. A warm family story is not evidence of independence; a corporate-sounding
page is not evidence of a parent. The determination runs off `data/ownership.json`
and extracted ownership signals. Load the `ownership-check` skill for that.

## Australian English

Everywhere a reader can see, including the admin UI and FAQ answers (CLAUDE.md
rule 9). `practise` the verb, `practice` the noun. `licence` the noun, `license`
the verb.

## Before you call an entry done

- Every fact traces to the source document. Anything that does not is cut.
- No sentence implies anyone was there.
- No flavour, aroma, texture or finish outside a marked `<Pull>`.
- Any conditional phrase above has its evidence in the same entry.
- `python3 -m admin.pipeline.validate_register` is clean, or every hit is one
  you have read and judged.
