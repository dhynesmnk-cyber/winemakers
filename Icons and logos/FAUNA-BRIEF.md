# Margin fauna — commissioning brief

**For an illustrator. Nine pieces.** Authored Wave 2, 2026-08-07. The visual
specification behind it is `DESIGN.md` §6a, which this document does not
replace: where the two disagree, DESIGN.md wins.

This artwork is **not** to be generated from the specification. It is drawn.

---

## What the work is

A field guide to independent Australian winemakers. The site reads as a printed
survey volume: ink on warm paper, one column of prose, hairline rules, no cards,
no photography beyond one tipped-in plate per producer.

These nine drawings are the only decoration on the site. They sit in the wide
right margin of the homepage, beside section openers, at 40 to 64 pixels. One
per section break, never inline with the copy, never on any other page.

They are the kind of thing a naturalist puts in the margin of a notebook:
observed, specific, dry, faintly comic in posture. Never cartooned, never
anthropomorphised.

---

## The nine subjects

Wine-country fauna. The animals that actually live in Australian vineyard
country, not the ones on a tourism poster.

| # | Subject | Note |
|---|---|---|
| 1 | **Silvereye** (*Zosterops lateralis*) | The small grape-eating bird every vineyard net in the country is up against. Also the recommended site mascot: small, instantly drawable, endemic, and a thief. |
| 2 | **Willie wagtail** | Tail fanned. |
| 3 | **Australian raven** or **grey currawong** | Perched, in profile. |
| 4 | **Short-beaked echidna** | Mid-amble. |
| 5 | **Eastern blue-tongue lizard** | Flattened, basking. |
| 6 | **Working kelpie** | Sitting, ears up. The dog asleep in every winery shed. |
| 7 | **Guinea fowl** | Upright. Genuinely used for pest control in vineyards. |
| 8 | **Merino or Wiltipoll ewe** | Head down grazing. Under-vine grazing is a real practice in organic and biodynamic blocks. |
| 9 | **Blue-banded bee** (*Amegilla*) | In flight, at a scale that reads. |

Substitutions within wine-country fauna are fine: kookaburra, ringtail possum,
wedge-tailed eagle, bogong moth.

**Not acceptable.** Foxes, rabbits or starlings drawn as pests to be shot.
Anything holding, drinking or pouring wine. Anything wearing clothing. Koalas or
other "iconic Australia" tourism fauna chosen for recognisability rather than for
actually being in a vineyard.

---

## Treatment — read this before drawing

The artwork is **recoloured at runtime by a CSS mask that reads only the PNG's
alpha channel.** The image is used as a stencil and painted with a flat colour.

> **Only the silhouette exists.** Colour, tone, shading and internal linework in
> a different colour will all flatten to one solid shape. Any internal detail —
> an eye, a wing bar, a leg separated from a body, the gap between an ear and a
> head — must be cut as a **hole in the alpha channel**, not painted in a lighter
> colour.

So:

- Draw as **flat silhouette with knocked-out detail**. Think a rubber stamp, a
  stencil, or a bird-guide plate reduced to two values.
- **No outline-only artwork.** An unfilled outline masks to a hairline ring and
  disappears at 48px.
- **No gradients, no soft edges, no anti-aliased glow, no drop shadow, no cast
  shadow, no ground line, no baseline, no frame, no background.** Fully
  transparent everywhere the animal is not.
- **No text, no signature, no watermark.**
- One subject per file. No pairs, no scenes.
- **The silhouette must be readable at 48px.** Test it at 48px before delivering.
  A tail, ear or beak that vanishes at that size needs thickening.
- Roughly square aspect, subject filling the frame.

The single most common way this brief gets missed is delivering a beautiful
drawing whose detail lives in tone. Squint at it in greyscale, then threshold it
to pure black and white. What survives is what the site will show.

---

## Deliverables

| | |
|---|---|
| **Source artwork** | This directory, `Icons and logos/`. Full resolution, at least 1024px on the long edge. PNG with a real alpha channel. |
| **Filenames** | Descriptive and matching the registry keys below. Not generator hashes. |

Filenames, exactly:

```
silvereye.png
willie-wagtail.png
australian-raven.png
echidna.png
blue-tongue-lizard.png
kelpie.png
guinea-fowl.png
ewe.png
blue-banded-bee.png
```

### What happens to them afterwards

The build produces the served copies; the illustrator does not. Recorded here so
the source artwork is delivered in a state the pipeline can work from.

- Downscaled to roughly 192px on the long edge, which is about three times the
  64px display ceiling.
- **Alpha-cropped to the subject's bounding box**, with no transparent padding.
  This is why the source must have no baseline, frame or ground line: they crop
  as part of the subject and throw the sizing out.
- Kept under about 40KB each.
- Written to `site/public/animals/`. Generated from the source, never
  hand-edited.
- Registered in `site/src/icons/animals.ts`, which already carries the nine keys
  and their paths. Adding artwork means adding its key to `ANIMALS_AVAILABLE`;
  nothing else moves.

---

## Placement and colour, for context

The illustrator does not set these. They are here so the drawing is made for the
place it goes.

- Light mode paints the silhouette in `--ink-faded`, a warm mid grey-brown.
  Dark mode forces pure white.
- **No colour-coding by species or meaning.** These are decoration, not notation.
  A reader must never be able to work out a fact about a producer, a region or a
  category from which animal is in the margin.
- `aria-hidden="true"`. Never linked, never captioned.
- Collapses out of the layout below 1024px.

---

## Rights

Original work, commissioned. Delivered with the right to use, modify, downscale
and recolour it on this site and in its published material. Confirm the terms in
writing before starting.
