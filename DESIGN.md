# DESIGN.md — Visual Specification

**Read this before touching any UI code. Every visual decision derives from this file. If a choice is not covered here, ask — do not default.** Defaults regress to tech-startup generic, which is the one named failure mode (§10).

This document outranks TRD.md for interface (CLAUDE.md rule 3, doc precedence). It does not outrank SCHEMA.md for data: every key, enum value and field name quoted here is quoted *from* SCHEMA.md and must never be redefined here. Where this file names a vocabulary, it names SCHEMA.md §1's vocabulary.

**Provenance of this document.** It is a direct edit of the reference build's `DESIGN.md` (`/home/dhynesmnk/Bathers'/DESIGN.md`, read-only), not an independent invention. §§2–10's machinery — dual-mode tokens, the three-face type system, hairlines-not-borders, the tipped photograph, the inline-SVG icon renderer, the motion doctrine — is retained deliberately and largely unchanged. §1's mood, §2's accent names, §6's inventory, §6a's fauna and §7's page set are rewritten for this domain. Where a rule here differs from the reference, the difference is stated with its reason so nobody has to diff the two files to find out.

---

## 1. Direction

**A field guide. Ink on warm paper, inverted for dark mode.**

The site records independent Australian winemakers the way a regional flora records species: an entry per subject, a dateline, a fact row of checkable facts, a provenance line saying where each fact came from, and prose that takes its time. It is a survey document — privately printed, thorough, unhurried, and unsentimental about its subject. It is free to use, it carries no advertising and no sponsored listings, and it should look like a thing that has nothing to sell, because it hasn't.

The register is **the naturalist's monograph and the herbarium sheet**: a specimen mounted flat on warm paper, labelled in a small mono hand, with the collector's date and locality beside it. Every producer entry is a sheet in that collection.

### What it must never look like

- **A SaaS product.** No dashboards, no cards, no stat tiles, no pills, no trust badges, no "Get started".
- **A wine retailer.** No prices as headlines, no cart, no ratings, no shelf-talker language, no "shop by" merchandising grid, no bottle-shot wall. Buy links exist because a reader may want one; they are never the loudest element on a page (§7a).
- **A winery's own marketing site.** No hero photograph of a sunset over rows, no full-bleed video, no drop cap over a vineyard, no estate-crest lockup, no "our story".
- **Vivino, Airbnb, or a Google Maps sidebar.** No star ratings, no review counts, no teardrop map pins, no listing-card grid, no "10 best" chrome.
- **A wellness or lifestyle brand.** No soft-focus gradients, no oversized lowercase sans, no pastel.

### The letterpress ban — stated explicitly, and not negotiable

**This site is not a cellar notebook, not a letterpress wine merchant, not a chalkboard, not a leather ledger, not a vintage-label pastiche.** That direction is banned outright.

The reason is positional, not aesthetic. Cream stock, burgundy-and-gold, engraved vine ornament, wood-type condensed caps, a "since 18—" cartouche, hand-script overlays, deckled edges, wax seals, ruled ledger lines and price-column typography constitute the single most saturated visual language in wine. Every merchant, every importer, every natural-wine bar and roughly every second producer already uses some part of it. Adopting it would trade the one thing this site has — a distinctive position as an independent, free, evidence-first reference — for a look the reader has already learned to skim past. It would also, fatally, make the site look like it is *selling* wine, which is precisely the thing the independence rule (SCHEMA.md §4) exists to keep it clear of.

Concretely banned: ledger rules and ruled columns as decoration; ornamental borders, fleurons, flourishes and rules with terminals; any crest, shield, seal, ribbon or medal form; gold, foil, metallic or embossed effects; script/blackletter/wood-type faces; simulated print artefacts (ink bleed textures, torn paper, tape, deckle, stains, coffee rings); a burgundy or claret field used as a background or brand colour anywhere (§2).

The field-guide register carries the same virtues the letterpress register is usually reached for — restraint, physicality, seriousness, age — without the costume.

### The one photograph

A producer entry may carry exactly one image, treated as a plate tipped into the page (§4). It is never a hero, never full-bleed, never above the name. Every page must look finished with no image at all (§7, zero-image default). Images are garnish. The evidence is the text.

---

## 2. Colour

Six tokens. Two modes. Nothing else.

Light is the default register — ink on warm paper. Dark is the inversion of it, not a separate palette. Mode is auto-detected from `prefers-color-scheme` with a manual override (§5a) that wins.

### The tokens

`--paper`, `--paper-raised`, `--ink` and `--ink-faded` keep the reference's names and semantics exactly. The two accents are renamed for this domain:

| Reference | Here | Role |
|---|---|---|
| `--thermal` | **`--vine`** | The one accent. Links, focus rings, active/current state, the single button style. Nothing decorative. |
| `--oxide` | **`--claret`** | **Error and warning tone only.** Nothing else, ever. |

**`--claret` is not a brand colour and must never be used as one.** It is named for a wine because the palette is a wine site's palette, and that is exactly why it is dangerous: there is a permanent pull to paint a heading, a rule, a masthead or a hover state in it. Every one of those uses turns the site into a wine merchant (§1). `--claret` appears on a public page only when something has gone wrong — a form error, a validation message, a "this page is out of date" notice — and in the admin app for destructive and failure states (§8). If a screen shows `--claret` and nothing is wrong, it is a bug.

**`--vine` has a budget.** If more than roughly 5% of a screen is `--vine`, it is overused. It is a link underline and a focus ring far more often than it is a fill. There are no filled accent backgrounds on the public site.

### Starter values — **UNVERIFIED. Do not treat these as final.**

The reference amended its accent hexes **three times** (2026-07-26 twice, once more the same week) and shipped a light-mode `--ink-faded` that measures **3.92:1** against its own `--paper` — below the 4.5:1 floor its own quality section asserts. That is what an unverified hex costs when it is quoted as settled. The values below are starting points, chosen to satisfy the arithmetic on paper; they have **not** been looked at on a screen, in a room, against the grain overlay (§4), at 13px mono, or beside a photograph.

**Before Gate 1 closes, someone renders these on a real display in both modes and either confirms them or amends them here with a dated note.** The arithmetic clears the floor; the arithmetic is not the test.

**Light mode**

| Token | Starter hex | Contrast on `--paper` | on `--paper-raised` | Role |
|---|---|---|---|---|
| `--paper` | `#efeae0` | — | — | Page background. Warm off-white, herbarium sheet. Never clinical white. Carries the grain (§4). |
| `--paper-raised` | `#e6e0d3` | 1.10 vs `--paper` | — | Lifted surfaces: the producer-page appendix block, admin panes, the photo mount. Difference barely perceptible by design. |
| `--ink` | `#292723` | 12.43 | 11.33 | Primary text. Iron-gall dark — warm near-black with a green-grey undertone. Never pure black. |
| `--ink-faded` | `#676154` | 5.13 | 4.68 | Secondary text: datelines, captions, provenance lines, hairlines (at 25% opacity). |
| `--vine` | `#496845` | 5.23 | 4.77 | The accent. Vine-leaf green, deepened to hold the floor on light paper. |
| `--claret` | `#8e3b33` | 6.20 | 5.66 | Error and warning only. |

**Dark mode**

| Token | Starter hex | Contrast on `--paper` | on `--paper-raised` | Role |
|---|---|---|---|---|
| `--paper` | `#171512` | — | — | Warm near-black — charcoal with brown in it, never blue-black. |
| `--paper-raised` | `#1f1c18` | 1.07 vs `--paper` | — | Same role as light. |
| `--ink` | `#e6e0d2` | 13.85 | 12.89 | Warm off-white, aged paper made luminous. |
| `--ink-faded` | `#a49b88` | 6.61 | 6.16 | Same role as light. |
| `--vine` | `#8fb583` | 7.90 | 7.36 | Same hue as light `--vine`, lightened rather than reused — a colour dark enough for light paper is not legible on near-black paper. |
| `--claret` | `#c9736a` | 5.33 | 4.96 | Same lighten-for-dark method. |

**Contrast floor (binding).** Every text-weight token clears **4.5:1 against both `--paper` and `--paper-raised`** in its own mode. `--paper-raised` is not decorative; captions and appendix text sit on it, and a value checked only against `--paper` will fail there — this is exactly how the reference's light `--ink-faded` slipped through. Check both surfaces or the check is not done.

**Deepen for light, lighten for dark.** When an accent is amended, the two modes get the same hue at two lightnesses, derived from one another. Never paste one mode's hex into the other and hope.

### Banned in both modes

Tailwind's default grey scales used for colour (`slate`, `gray`, `zinc`, `neutral`, `stone`); pure `#000` and `#fff` (except the one documented fauna exception, §6a); any blue that reads "tech"; any purple; gradients of any kind; coloured glows; shadows of any colour, including black; gold, bronze, foil or metallic effects; burgundy, claret, oxblood or wine-red as a *surface* or brand field (see the `--claret` rule above); colour used as the sole carrier of meaning anywhere.

### The dual-mode machinery — declare every token four times

Retained from the reference verbatim in shape. In `site/src/styles/global.css` (Gate 1 owns the file; this is the spec it implements):

1. `:root` — the **light** values, plus `color-scheme: light dark` and `--grain-opacity`.
2. `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }` — the dark values. The `:not([data-theme="light"])` is load-bearing: it is what lets an explicit light choice survive a dark OS.
3. `:root[data-theme="dark"] { … }` — the dark values again.
4. `:root[data-theme="light"] { … }` — the light values again.

**Source order is the mechanism.** Blocks 3 and 4 come after block 2 so an explicit choice always wins. Do not "simplify" this into two blocks; the duplication is the feature.

An `@theme` block aliases each token (`--color-paper: var(--paper)` and so on) so any Tailwind colour utility that ever gets used follows the tokens rather than freezing a literal. Type faces are aliased the same way (`--font-display`, `--font-body`, `--font-mono`).

**The FOUC-avoiding head script.** A tiny `is:inline` script is the **first** thing in `<head>`, before any stylesheet: read the stored preference from `localStorage`, and if it is exactly `"light"` or `"dark"`, set `data-theme` on `document.documentElement`. Wrapped in `try/catch` — a browser with storage disabled must degrade to OS preference silently, not throw. It runs before first paint; anything later flashes the wrong mode. The storage key is a named constant (§ Constants).

Everything else about theming is CSS. There is no theme class toggling on `<body>`, no per-component mode branching, and no JavaScript reading colours.

---

## 3. Typography

Type carries the entire personality of this site. Three faces, three jobs, no substitutions.

| Role | Face | Usage |
|---|---|---|
| **Display** | **Fraunces** (variable, weight 300–600, high optical size, `SOFT` axis up for ink-spread) | Producer names, page mastheads, pull-quotes. Large, unhurried, generous. |
| **Body** | **Newsreader** (400 / 400 italic / 600) | All editorial prose. 17–19px, line-height 1.65, **measure capped at 65ch**. Italic for asides, summaries and pull-quote attribution. |
| **Utility** | **IBM Plex Mono** (400 / 500) | Datelines, locality lines, provenance and verification lines, fact rows, figures, admin chrome, frontmatter display, log output. Always small (12–13px), usually letterspaced 0.05em, often uppercase. |

Rules:

- **No sans-serif exists on the public site.** Never Inter, never `system-ui`, never Roboto, never any grotesque. IBM Plex Mono is the utility face; it is a monospace, not a sans, and it is not a substitute for one.
- **No `font-weight` ≥ 700 anywhere**, either app. Emphasis comes from size, italics, and the mono/serif contrast. If something needs to shout, make it bigger or set it in mono caps.
- **Display steps big.** Producer names at `clamp(2.5rem, 6vw, 4.5rem)`. Do not be timid; a timid display size is what makes a page read as a listing.
- **Real underlines on links**: `text-underline-offset: 3px`, `text-decoration-thickness: 1px`, `--ink-faded` underline turning `--vine` on hover/focus, 0.15s transition. **No hover colour-flip of the text itself.** No underline-on-hover-only.
- All three faces are **self-hosted woff2** from `site/public/fonts/`, declared with `font-display: swap`. Zero runtime font fetching, no Google Fonts link, no `@import` from a CDN.
- Numerals in the mono face for anything countable — years, case counts, fees, dates, coordinates, distances. Figures never appear in the display face.

---

## 4. Texture & Material

This is what separates "editorial" from "dashboard".

- **Grain.** A full-page noise overlay on every public page: inline SVG `feTurbulence` fractal noise, `mix-blend-mode: overlay`, `position: fixed`, `pointer-events: none`, opacity driven by `--grain-opacity` (~0.035 light, ~0.03 dark). Subtle enough that you only notice it when it is gone. **Tune the two modes independently** — `overlay` against warm off-white behaves nothing like `overlay` against near-black; do not assume one value carries. Verify visually before locking either in.
- **Rules, not borders.** Dividers are 1px hairlines in `--ink-faded` at 25% opacity (`color-mix(in srgb, var(--ink-faded) 25%, transparent)`). No boxed borders around content blocks. **`border-radius: 0` globally**, enforced by a `* { border-radius: 0 }` reset; nothing on the public site overrides it above 2px. **No box-shadows on the public site, ever.**
  - **One page-level exception, retained from the reference:** a single hairline frame around the whole page at the layout level (`.page-frame`, 0.5rem margin, one hairline border), scrolling with the content, never fixed. This is page chrome, not a box around a content block; individual sections and entries remain unbordered.
- **The tipped-in plate.** When a producer has a published image it is treated as a photograph tipped into a survey volume: inset (never full-bleed), a `--paper-raised` mount with a hairline edge and roughly 4px of mount showing on three sides with a deeper foot, the image sitting **flat** (no rotation — the reference removed its deterministic tilt and it is not coming back), and a mono caption beneath in `--ink-faded`, followed by an "image source" link.
  - **Caption register — vineyard and parcel, not plate numbers of specimens:**

    `LOT I. — THE HOME BLOCK, LOOKING WEST.`

    Uppercase, mono, roman-numeral lot, an em-free dash, a named parcel or block, and a bearing or aspect where one is knowable. `LOT II. — BLEWITT SPRINGS, OLD GRENACHE.` `LOT III. — THE WINERY YARD, VINTAGE.` This is the register SCHEMA.md §2 requires of `image_caption`; it is drafted from published source facts like everything else, and a bearing nobody published is not invented.
  - Photos are placed **mid-article, never at the top**, and never above the producer's name.
- **Section openers.** A small mono eyebrow in `--ink-faded`, letterspaced and uppercase, above a hairline, in the manner of a chapter head in a printed survey. **No icons in section openers.** No background fills, no numbered chips.
- **No modals. No toasts. No popovers. No tooltips beyond the native `title` attribute.** A message that matters goes in the page flow. The one fixed element on the site is the corner menu (§5b).

---

## 5. Layout Grammar

- **A single reading spine.** One column of prose, `max-width: 65ch`, placed asymmetrically — offset left of centre on wide screens, with the wide right margin carrying occasional mono margin-notes and the fauna motifs (§6a). **Never centred symmetric hero layouts.**
- **No cards.** Producer listings are typographic entries — name in display, mono locality/dateline, one-line summary in italic, present-only fact row — separated by hairlines, like a table of contents. No boxes, no fills, no shadows, no hover-lift. This is the single rule most likely to be violated by muscle memory; it is also the rule that most determines whether the site passes §10.
- **Whitespace is structural.** Section spacing 6–10rem on desktop. When in doubt, add space, not decoration.
- **Filters are text.** Every filter, facet and toggle on the public site is an inline mono text control — `wild ferment · unfined · unfiltered · minimal so₂` — with the active state carried by a `--vine` underline. No sidebar, no checkbox, no pill, no chip, no dropdown, no faceted-search rail. Filtering is a thing the reader does with words.
- **Present-only display, everywhere.** A producer's entry shows what is known about that producer and omits what is not. No greyed-out absent features, no "—" placeholders in a fixed grid, no "not specified" rows. A field guide does not record what was not there. (The one exception is the appendix's ownership line, §7, which is *always* present because its absence is the thing that would be misread.)
- **Tables are tables.** Comparison pages (Gate 9) use semantic `<table>` with `<caption>` and `<th scope>`, hairline rules between rows only, no zebra striping, no vertical rules, no wrapping card, mono in the cells, and horizontal scroll inside the table's own container on narrow screens — never a page that scrolls sideways.
- **Two narrow, named exceptions to "no cards / no thumbnails", both inherited from the reference:**
  1. `ProducerEntry` may show a small (~56–72px), unbordered, unrotated thumbnail of the producer's own tipped-in plate **when one exists**, beside the name/dateline text — no mount, no shadow, no change to the hairline rhythm. It exists solely to give the list→detail photo transition (§9) a shared element. Producers with no image show nothing extra. This is not a general reintroduction of thumbnails.
  2. The homepage's masthead (§5c) is centred. Nothing else on the homepage is, and no other page is.

---

## 5a. Theme Toggle

A narrow, deliberate exception to the site's otherwise toggle-free chrome.

- Renders **inside the corner menu's drawer** (§5b), in the first tier alongside search and Home — not in the page header, where it would compete with the masthead. It sits in the drawer's normal document flow; it is not itself fixed or floating.
- A plain mono text control in the "filters are text" idiom (§5) — not an icon, not a switch, not a pill. It reads as words and it toggles by activation.
- Auto-detects `prefers-color-scheme`; an explicit choice persists in `localStorage` and wins over the OS (§2, source order).
- **No animated transition on switch.** A plain state change. Cross-fading a whole palette is the kind of flourish §10 catches.
- Admin app: auto only, no manual toggle — it is a private single-operator workbench (§8).

## 5b. Corner Menu

**A narrow, named exception to "never fixed, never floating" — for this one control only.** Everything else in this file still holds: no modals, no toasts, no other floating chrome, no sticky headers, no back-to-top button.

- A single button fixed to the **top-right** of the viewport on every public page, labelled `MENU` in mono text. No icon on the button itself.
- Activation slides a full-height panel in from the right edge (`transform: translateX`, 0.35s ease). Click/tap to open — never hover-only, for touch parity. **No dimming scrim**: the page stays visible so the drawer reads as a leaf folding out of the document rather than an app off-canvas menu. A scrim is precisely the §10 failure mode.
- The panel is permanently mounted and toggled with a class plus `inert` / `aria-hidden`, not the `hidden` attribute (which cannot be transitioned). Closed, it is `inert`, so its links are not tabbable.
- Keyboard-operable: reachable by Tab, opens on Enter/Space, closes on `Escape` with focus returned to the button.
- Visual system unchanged inside the panel: `--paper-raised` background, a single hairline **left** border, no radius, no shadow, no banned colours.
- **Contents, three tiers:**
  1. Search, Home, and the theme toggle (§5a).
  2. **Primary — "Find a producer by region."** Every GI region with ≥1 published producer, grouped under its state, each region carrying its present subregions directly beneath it. Present-only: a region with no producers does not appear (CLAUDE.md Gate 6). At the target coverage this tier is the menu.
  3. **"More"** — three groups: *Browse by variety*, *Browse by practice* and *Browse by wine style* (each row a 20px glyph plus a mono label, §6); then *Glossary*, *Methodology* and *Journal*.

**Methodology is linked from the corner menu on every page and from the footer** (CLAUDE.md Gate 10). It is not buried under "More" alone.

## 5c. Site Logo / Home Button

A persistent home-link lockup rendered by the base layout on **every** page, above that page's own opening content, in flow and never floating.

- One shared renderer (`site/src/components/SiteLogo.astro`): the mascot mark — recoloured by the same CSS-mask technique as §6a's fauna, `--ink-faded` in light mode, pure white in dark — beside or above the wordmark set in Fraunces. The wordmark is **live text**, not an image.
- **Two sizes, no others.**
  - **Large**, index only: a frontispiece composition — mark above, wordmark below, centred as a block, with generous top clearance. Mark sized `clamp(6rem, 26vh, 11rem)` square. This is the one centred layout on the site (§5).
  - **Default**, every other page: `clamp(1.75rem, 4vw, 3rem)` text with a 2rem mark, left-aligned, `inline-flex`. Deliberately smaller than the index treatment so it reads as a home button rather than repeating a masthead above each page's own heading.
- A real `<a href="/">`. This is navigation, not decoration; the §6a margin motifs are decoration and are never linked.

**Deliberate departure from the reference.** The reference's large logo plays a one-time sequence where the wordmark rises in, holds, then **fades out permanently**, leaving a mark-only masthead — and because its at-rest style is `opacity: 0`, a reduced-motion visitor never sees the site's name at all. That is not carried over. Here the large logo's on-load motion is a plain fade-and-rise whose **at-rest state is the final, fully visible state** (§9), so reduced motion and no-JS both show the finished masthead. The reference's `opacity: 0` resting-state trick is kept in this document only as the rule for how *any* future disappear-type animation must be built if one is ever approved: its resting style must be the post-animation state, so the kill-switch lands on the correct frame rather than freezing mid-flight.

**Favicon and share image.** Generated from the same source artwork: `favicon-16x16.png`, `favicon-32x32.png` (transparent) and `apple-touch-icon.png` (opaque `--paper`-coloured background, per Apple's guidance against transparency). `site/public/images/og-share.webp` at 1200×630 is the default `og:image`/`twitter:image` — mark, wordmark and tagline on the **light** palette, since share surfaces sit outside this site's theme toggle and light reads reliably across clients. Neither asset is theme-aware; both are static files.

**Pending.** `SITE_NAME`, `SITE_TAGLINE` and the mascot species are not settled by this document — see §6a for the recommendation and § Constants for what Gate 1 must define.

## 5d. Footer

One shared component, rendered from the base layout as the last in-flow element of `.page-frame`, on every public page. No equivalent in the admin app.

- A single hairline top rule. No card, no box, no background distinct from `--paper`.
- Three mono-text contact links, each a 20px glyph (§6) **plus a visible mono label** — never icon-only: **email**, **Bluesky**, **RSS**. `--ink-faded` at rest, `--vine` on hover/focus.
- A links row in mono: *Methodology · Glossary · Journal · Sitemap*.
- **A colophon line** beneath, in mono `--ink-faded`, stating the site's position plainly: free to use, no advertising, no sponsored listings, no affiliate links. This is not a marketing claim; it is the fact that distinguishes the site, and it belongs where a printer's colophon goes. Keep it to one or two lines.
- No sitemap-style link columns, no newsletter capture, no social embeds, no "as seen in" row.

---

## 6. Icon System

Hand-authored inline SVG line icons, used for **fact display only**. The site is otherwise icon-free: section openers (§4), filter toggles (§5), the button style (§7a) and the corner-menu button itself stay plain text.

### Grammar (binding)

- One shared renderer, `site/src/components/Icon.astro`, reading paths from `site/src/icons/paths.ts`.
- **24×24 viewBox. Stroke-only. `stroke="currentColor"`. `fill="none"`. `stroke-width: 1.4`. Round caps and joins.** No fill, ever; no colour beyond the surrounding text colour, so glyphs stay tonal with the page rather than becoming decoration.
- **No icon package, no icon font, no SVG sprite fetched at runtime.** Every glyph is hand-authored inline, kept to simple primitives.
- **Four repeating primitives hold the set together: the bunch, the bottle, the barrel and the glass.** A new glyph should be assembled from these and from plain geometry (circle, rect, short arc) wherever it can be, so 44 glyphs read as one hand rather than a collection.
- **No negation slashes.** Every glyph in this set states a positive fact that a producer published. A slashed glyph reads as a prohibition sign.
- **No letterforms**, with one inherited exception: `parking` carries a stroke-drawn `P` in a rect, because that is what a parking symbol is.
- **No teardrop map pin.** Locality is marked with a survey triangle (§ inventory). The pin is a Google-Maps-sidebar tell and §1 bans the look.
- **Present-only.** Absent facts render nothing. No greyed-out glyphs.
- **Icons never appear alone in full context.** Full context (producer page) renders glyph + label text. Compact context (list rows) renders glyph only with a `title` attribute and an `.sr-only` label. **Where two glyphs in a set cannot be told apart at compact size — the still-wine glasses are the known case — the compact context renders the label text instead of the glyph.** An ambiguous glyph is worse than no glyph.
- **Icons are never the only carrier of meaning**, and never a badge, seal, shield, medal or ribbon. SCHEMA.md §2 is explicit: *no badge system, labels are words.* This icon set does not reopen that. It gives a word a mark to sit beside; it never replaces the word, and it never encodes a rank, a score or a level of trust.
- **Keys are namespaced by vocabulary** — `practice_*`, `logistics_*`, `style_*`, `vessel_*` — and derived mechanically from SCHEMA.md §1's `as const` tuples (`` `vessel_${key}` `` and so on), never hand-listed a second time. Namespacing is not cosmetic: `glass` is both a vessel and a drinking vessel, and an un-namespaced set collides. A vocabulary value with no glyph must fail the build, not render blank.

### Which vocabularies render as glyphs

Every SCHEMA.md §1 vocabulary is accounted for here.

| SCHEMA.md §1 vocabulary | Renders as | Note |
|---|---|---|
| §1.1 `CATEGORIES` (6) | **Words only** | The distinction between `negociant` and `garagiste` is a business fact, not a drawable one; a glyph set would caricature it. |
| §1.2 `CELLAR_DOOR_STATES` (3) | **2 glyphs** | `none` renders nothing (present-only). |
| §1.3 `CERTIFICATION_STATES` (3) | **2 glyphs** (one per subject) | `organic` / `biodynamic` each get one glyph, shown when the state is not `none`. **`practising` vs `certified` is carried in the label text, never by a glyph variant** — SCHEMA.md §1.3 makes that distinction load-bearing, and a shape that changes with certification is a trust badge. Where `certified`, the named certifier is displayed. |
| §1.4 `FRUIT_SOURCE` (3) | **1 shared glyph**, value in words | `purchased` is neutral (SCHEMA.md §1.4). One glyph for the row, three word values, no ranking. |
| §1.5 `PRODUCTION_BANDS` (5) | **1 shared glyph**, value in words | Never a bar, meter or gauge — that is a dashboard. |
| §1.6 `PRACTICE_KEYS` (4) | **4 glyphs**, present-only | |
| §1.7 `LOGISTICS_KEYS` (10) | **10 glyphs**, present-only | |
| §1.8 `VESSEL_KEYS` (7) | **7 glyphs** | |
| §1.9 `WINE_STYLE_KEYS` (7) | **7 glyphs** | |
| §1.10 `VARIETY_KEYS` | **1 shared glyph** (the bunch), names in words | A glyph per grape is undrawable and would become a badge system. |
| §1.11 `CONFIDENCE_TIERS` (4) | **Words only** | A tier rendered as a shield, tick or medal is a trust seal. Mono text, in the provenance line (§7). |
| §1.12 `VERIFIABLE_FIELDS` | n/a | Metadata, not displayed as a set. Also **not glossed** — it is a list of field names, not a vocabulary of values, so `/validate` check 11 skips it. |
| §1.13 `OWNERSHIP_EVIDENCE_METHODS` (3) | **Words only** | *Row added 2026-08-07. It was missing, which made the claim above it untrue and would have made check 11 report three false orphans.* Never a seal, tick or verification badge — DESIGN.md §7's methodology note bans exactly that art. Mono text, in the provenance line (§7). |
| §1.14 `STATES` (8) | **Words only** | Never flags, never a map. *Renumbered 2026-08-07, previously listed as §1.13.* |

### The inventory — 44 glyphs

Wave 2 authors the paths. This section specifies what each one is; it does not draw them.

**Practices (4) — SCHEMA.md §1.6**

| Key | Glyph |
|---|---|
| `practice_wild_ferment` | An open-topped fermenter: a shallow vessel whose contents dome above the rim line, with two short arcs rising off it. Not a yeast cell, not a bubble cluster. |
| `practice_unfined` | A tapered glass with three small particles held in suspension in the bowl — the wine left cloudy on purpose. |
| `practice_unfiltered` | A filter disc (circle crossed by three parallel chords) set *aside* from a straight pour line that bypasses it. The screen present but unused. |
| `practice_minimal_so2` | A single droplet suspended above a wide vessel mouth — one drop where a pour would be. |

**Wine styles (7) — SCHEMA.md §1.9.** Built on the glass primitive.

| Key | Glyph |
|---|---|
| `style_red` | Broad round bowl, short stem, foot. |
| `style_white` | Narrower U-bowl, longer stem, foot. |
| `style_rose` | The white bowl with a low level stroke and a single short arc at the rim. |
| `style_sparkling` | Tall narrow flute with three rising dots. |
| `style_skin_contact` | A shallow open vessel holding a half-berry with its skin drawn as a separate outer arc. |
| `style_fortified` | A squat straight-sided stemmed glass with a low measure stroke. |
| `style_dessert` | A single raisined berry — a berry outline with a puckered contour — on a short stem. |

> `style_red`, `style_white` and `style_rose` are the known compact-size ambiguity. Per the grammar rule above, list/compact contexts render their labels, not the glyphs.

**Vessels (7) — SCHEMA.md §1.8.** Built on the barrel primitive and plain geometry; these are the most genuinely distinguishable set on the site.

| Key | Glyph |
|---|---|
| `vessel_stainless` | Upright cylindrical tank, dished top, two short legs, a small valve at the base. |
| `vessel_oak_barrique` | Barrel on its side, three hoop lines, bung at top centre. |
| `vessel_oak_foudre` | Large upright staved cask, markedly wider relative to its height than the barrique, with a front hatch. Proportion carries the difference. |
| `vessel_concrete` | An egg — an ovoid on a low cradle, hatch line near the top. |
| `vessel_amphora` | Two-handled tapering vessel with a pointed base. |
| `vessel_ceramic` | Rounded jar, rolled lip, no handles, one incised band. |
| `vessel_glass` | A demijohn — rounded body, narrow neck, stopper stroke. |

**Logistics (10) — SCHEMA.md §1.7**

| Key | Glyph |
|---|---|
| `logistics_walk_ins_welcome` | An open door with a short swing arc. |
| `logistics_bookings_required` | A diary page with a ticked date. |
| `logistics_restaurant` | A plate circle with a fork left, knife right. |
| `logistics_picnic_provisions` | A basket with a handle and one cloth fold over the rim. |
| `logistics_dog_friendly` | A working dog's head in profile — muzzle and pricked ear. Not a paw print. |
| `logistics_family_friendly` | Two figures, one tall, one short: circle head plus body stroke each. |
| `logistics_wheelchair_access` | The standard wheelchair figure — circle head, seated body stroke, wheel arc. |
| `logistics_group_bookings` | Three overlapping circle heads in a row. |
| `logistics_vineyard_tours` | Two vine rows converging toward a horizon with a short path between them. |
| `logistics_parking` | Rect with a stroke-drawn `P`. The one letterform in the set. |

**Cellar door (2) — SCHEMA.md §1.2**

| Key | Glyph |
|---|---|
| `cellar_door_open` | A door standing open beneath a lintel line. |
| `cellar_door_by_appointment` | The same door, closed, with a small hand-bell beside it. |

**Certification (2) — SCHEMA.md §1.3**

| Key | Glyph |
|---|---|
| `organic` | A single leaf on a short stem with one midrib. |
| `biodynamic` | A crescent with a small sprout at its inner edge. |

**Vocabulary row markers (4)**

| Key | Glyph |
|---|---|
| `variety` | **The bunch** — a triangular cluster of berries with stem and one leaf. Marks the varieties line and the `/variety/` pages. |
| `fruit_source` | A vine row — three posts on a wire. |
| `production` | Two stacked cases, front face braced. Never a chart. |
| `bottle` | **The bottle** — a plain bottle silhouette. Marks buy-direct links and the shop. |

**Utility and appendix (5)**

| Key | Glyph |
|---|---|
| `hours` | Clock face with hands. |
| `cost` | A price tag with its hole. |
| `location` | **A survey triangle** — an equilateral outline with a centre dot. Not a map pin. |
| `website` | An arrow leaving a square. |
| `ships_nationally` | A carton with a tie band. |

**Footer (3)**

| Key | Glyph |
|---|---|
| `email` | Envelope: rect plus a flap V. |
| `bluesky` | Simplified two-wing mark, stroke-only — a simplification, not a traced brand asset. |
| `rss` | Corner dot with two arcs. |

### Sizes

Nothing renders above 40px without a further documented exception. The §6a fauna are a separately scoped decorative exception, not an icon size.

| Context | Size |
|---|---|
| Producer-page fact row (full) | 18px |
| List entry (`ProducerEntry`, compact) | 16px |
| Secondary chips (logistics, vessels) | 14px |
| Region / variety / practice page header | 16px |
| Corner-menu "browse by" rows | 20px |
| Footer links | 20px |
| Glossary index | 20px |
| Glossary detail page | 32px |
| Homepage secondary "browse by practice / by style" block | 40px |

---

## 6a. Margin Fauna Motifs — artwork brief

Sparse decorative illustration in the reading spine's wide right margin, where §6's glyphs are strictly functional. **Homepage only.**

**This section is a brief for an illustrator. Do not generate the artwork from this document.**

### What to draw — wine-country fauna

The animals that actually live in Australian vineyard country, drawn as a naturalist would note them in a margin: observed, specific, dry, faintly comic in posture but never cartooned, never anthropomorphised, never holding a wine glass. No bathing fauna, no seals, no otters, no capybaras — the reference's set is retired wholesale.

Nine subjects, one per section-opener slot:

1. **Silvereye** (*Zosterops lateralis*) — the small grape-eating bird every vineyard net in the country is up against. **Recommended as the site mascot** (§5c): small, instantly drawable, endemic, and a thief, which suits the register.
2. **Willie wagtail**, tail fanned.
3. **Grey currawong** or **Australian raven**, perched, in profile.
4. **Short-beaked echidna**, mid-amble.
5. **Eastern blue-tongue lizard**, flattened, basking.
6. **Working kelpie**, sitting, ears up — the dog asleep in every winery shed.
7. **Guinea fowl**, upright — genuinely used for pest control in vineyards.
8. **Merino or Wiltipoll ewe**, head down grazing — under-vine grazing is a real practice in organic and biodynamic blocks.
9. **Blue-banded bee** (*Amegilla*), in flight, at a scale that reads.

Substitutions within wine-country fauna are fine (kookaburra, ringtail possum, wedge-tailed eagle, bogong moth). **Not acceptable:** foxes, rabbits or starlings drawn as pests to be shot; anything holding, drinking or pouring wine; anything wearing clothing; koalas or "iconic Australia" tourism fauna chosen for recognisability rather than for actually being in a vineyard.

### Treatment — read this before drawing

The artwork is **recoloured at runtime via a CSS mask that reads only the PNG's alpha channel** (`mask-image` / `-webkit-mask-image`, painted with `background-color`). This has one consequence that governs everything else:

> **Only the silhouette exists. Colour, tone, shading and internal linework in a different colour will all flatten to a solid shape.** Any internal detail — an eye, a wing bar, a leg separated from a body, the gap between ear and head — must be cut as a **hole in the alpha channel**, not painted in a lighter colour.

So:

- Draw as **flat silhouette with knocked-out detail**. Think a rubber stamp, a stencil, or a bird-guide plate reduced to two values.
- **No outline-only artwork.** An unfilled outline masks to a hairline ring and disappears at 48px.
- **No gradients, no soft edges, no anti-aliased glow, no drop shadow, no cast shadow, no ground line, no baseline, no frame, no background.** Fully transparent everywhere the animal is not.
- **No text, no signature, no watermark.**
- One subject per file. No pairs, no scenes.
- **The silhouette must be readable at 48px.** Test it at 48px before delivering; a tail, ear or beak that vanishes at that size needs thickening.
- Roughly square aspect, subject filling the frame.

### Deliverables and where they live

| | |
|---|---|
| **Source artwork** | Repo-root **`Icons and logos/`** (committed source assets). Full-resolution, ≥1024px on the long edge, PNG with a real alpha channel. Descriptive filenames — `silvereye.png`, `willie-wagtail.png` — not generator hashes. |
| **Served copies** | **`site/public/animals/`**. Downscaled to ~192px on the long edge (≈3× the 64px display ceiling), **alpha-cropped to the subject's bounding box** with no transparent padding, and kept under ~40KB each. These are generated from the source, never hand-edited. |
| **Registry** | `site/src/icons/animals.ts` — an `AnimalKey` union and an `ANIMAL_SRC: Record<AnimalKey, string>` map, mirroring the reference's shape. |
| **Renderer** | `site/src/components/MarginAnimal.astro`. |

### Placement and colour

- Sized **40–64px** — larger than any §6 glyph, because these carry no label.
- Placed in the reading spine's wide right margin, **beside section openers only** — the masthead, the region index heading, the producer-index heading. Never inline with copy. Never more than one per section break. Never on any page but the homepage.
- **Light mode paints `--ink-faded`. Dark mode is forced to pure white (`#ffffff`)** — a deliberate, narrow exception to §2's "everything comes from the six tokens", scoped to this one decorative element, because the silhouettes read better at full contrast against near-black paper than the warm ink tones do.
- **No colour-coding by species or meaning.** Decoration, not notation. A reader must never be able to infer a fact from which animal is in the margin.
- `aria-hidden="true"`, never linked, never captioned.
- Collapses out of the layout below 1024px rather than being squeezed into the single-column spine.

---

## 7. Page-Specific Notes

### Homepage — region-first, with real pagination

The dataset is 150–300 producers (CLAUDE.md Gate 8). The reference's single client-filtered grid over the whole dataset does not survive that, and **this is a design decision, not a later performance fix** (CLAUDE.md Gate 6). The homepage is a region index, not a producer dump.

Order:

1. **Masthead** — the large site logo (§5c), centred, the one centred element on the site.
2. **A one-line mono subtitle**, then a short editorial foreword — real prose, two or three paragraphs, in register: what the guide covers, what *independent* means here, and a link to the methodology page. No value proposition, no "discover", no calls to action.
3. **START HERE — by region.** The primary way in. The four seed GI regions (Adelaide Hills, McLaren Vale, Yarra Valley, Mornington Peninsula) promoted with a producer count each, then the remaining GI regions with ≥1 published producer grouped by state beneath them. Plain mono text links, present-only, hairline-separated. No tiles, no maps, no imagery, no counts rendered as badges.
4. **A demoted secondary block** — *browse by variety · by practice · by wine style* — quieter heading treatment than the region row so it reads as secondary. 40px glyphs with labels (§6).
5. **The producer index**, paginated for real: server-rendered `/page/2/`, `/page/3/` routes with `<a>` links and `rel="prev"`/`rel="next"`, each page rendering only its own slice. **Not** a client-side filter over an embedded dump, **not** infinite scroll, **not** a "load more" button. It must work with JavaScript disabled and it must not ship the full dataset to the browser. Rows are `ProducerEntry` (§5).
6. Search lives in the corner menu (§5b), reachable from every page, not as a homepage hero field.

### Producer page — `/producer/[slug]/`

The core entity. Order:

1. **Name**, display face, large.
2. **Dateline row**, mono `--ink-faded`: suburb, state, primary region (linked), subregion if present, category in words, founded year if known.
3. **Fact row** — present-only glyphs + labels (§6): practices, wine styles, vessels, fruit source, production band, organic/biodynamic with certifier where `certified`.
4. **Prose**, 350–700 words in the reading spine, with one or two `<Pull>` quotes in display italic.
5. **The tipped-in plate** if an image exists (§4) — mid-article, never at the top.
6. **FAQ** if present (3–6 pairs, hard cap 8). Sits **above** the appendix: it is still editorial content, while the appendix is the page's practical close and should stay a stable landing spot regardless of how much FAQ exists. Plain `<h3>`/prose or `<details>` — no accordion chrome, no chevrons, no card wrap.
7. **The appendix block** — `--paper-raised`, mono, hairline-topped, in flow at the foot of the page. Address and locality (`location` glyph), cellar door state and hours, cost and tasting fee, the one button style linking to the producer's own site (§7a), the buy-direct link where `buy_online`, and ships-nationally where true.
8. **The provenance close** — this project's signature element, and it has no analogue in the reference. Three mono `--ink-faded` lines at the very foot:

   ```
   INDEPENDENT. NO PARENT COMPANY.
   OWNERSHIP DETERMINED 2026-08-06 — ASIC REGISTER LOOKUP.
   ENTRY DRAFTED 2026-08-06. VERIFIED 2026-08-06. SOURCE: PRODUCER'S OWN SITE.
   ```

   Set in mono, small, `--ink-faded`, hairline above, with the ownership source and `source_url` as real links. Where `verification` carries per-field records, a plain mono list of field → source → tier → date may follow, and where `change_log` has entries, a dated list of what changed.

   **Rules for this block.** It is **always present** — its absence would be read as "unknown", and per SCHEMA.md an undetermined producer is not publishable. It is set in words and dates, **never** as a badge, tick, shield, seal, meter, score or percentage. `CONFIDENCE_TIERS` values are spelled out in words. It never uses `--vine` as a "verified green" — it is `--ink-faded` like every other dateline, and the tokens do not encode approval. This block is the visual form of CLAUDE.md rule 6 (the honesty rule); it says where every claim came from, and it must read as a citation, not as a certification.

**No first-hand language anywhere in the chrome.** No "we visited", no "our pick", no editor's rating, no stars, no scores, no "recommended". CLAUDE.md rule 6 is a design constraint as much as an editorial one: there is no UI affordance on this site that could imply a visit or a tasting, because there was none.

### Region and subregion pages — `/region/[region]/`, `/region/[region]/[subregion]/`

Same shell. A generated foreword paragraph, then the present subregions as plain mono links, then `ProducerEntry` rows, paginated on the same mechanism as the homepage where a region is large. Must be indistinguishable in quality from the homepage. Present-only generation: a region with zero producers generates no page (CLAUDE.md Gate 6).

### State pages — `/[state]/`

Same shell, one level up: the state's regions as mono links with counts, then producers.

### Variety pages — `/variety/[grape]/`

Same shell. Foreword, the `variety` bunch glyph in the header at 16px, then producers working that grape. The grape's glossary definition sits at the foot, linked, not duplicated.

### Practice pages — `/practice/[key]/`

Same shell, one per `PRACTICE_KEYS` value. The practice's glyph at 16px in the header, a plain definition of what the practice is and — importantly — what it is not, then producers. **These four pages carry more definitional weight than any other programmatic page**, because SCHEMA.md §1.6 refuses a `low_intervention` field precisely so that these four checkable facts do the work instead. The copy must state what is checkable and what is not. If a `/low-intervention/` editorial page is ever composed from these four facts, it takes this same shell and states plainly that the term has no agreed definition.

### Glossary

Every enum value across every SCHEMA.md §1 vocabulary gets an entry (`/validate` check 11 fails on orphans in either direction). Index at 20px glyphs, detail pages at 32px. Definitions are plain, short, and say what the term excludes. No illustrations, no diagrams.

### Methodology

The published definition of independence, and the page producers will argue with. Plain prose in the reading spine, no diagrams, no flowcharts, no infographic, no badge art, **no "verified" seal graphics of any kind**. It states the strict rule from SCHEMA.md §4.1 (any corporate ownership blocks publication, including minority stakes and multi-label family groups), it states **what that excludes**, it lists the three acceptable forms of ownership evidence (§4.2), and it names the reject categories (§4.4). Linked from the footer and the corner menu on every page (CLAUDE.md Gate 10). Dated, and amended in place with a date rather than silently rewritten.

### Comparison pages (Gate 9)

Semantic `<table>` per §5. Hairline row rules only. Mono cells, display-face caption. Below the minimum-producer threshold, the page is skipped and logged, never rendered thin and never failed.

### Journal / blog (Gate 11)

Same typographic-entry list as the producer index — no cards, no thumbnails in the list. A post's cover image is a **plain full-width image with a `--paper-raised` mount border and no caption**, deliberately *not* the tipped-in plate treatment: the plate is the producer page's specimen signature, and a post cover functions as a banner. In-body images render at their natural size with no special framing.

### Zero-image default

**Every page must look complete and intentional with no images at all.** A producer with no published photo is a first-class entry and its page must not have a hole where an image would be — no placeholder, no grey box, no initials tile, no stock photograph. Test every page type with images removed before claiming it is done.

---

## 7a. Interactive elements — the one button style

The public site has exactly **one** button style (`.visit-btn`), used for outbound links to a producer's own site and shop. It must look like a stamped instruction, not a CTA.

- A real `<a>` styled as a button — it navigates, so never a `<button>`.
- Sits **in flow, inside the appendix block** (§7). Never fixed, never floating, never sticky, never repeated at the top of the page.
- IBM Plex Mono, uppercase, letterspaced 0.05em, 13px. Copy is instructional and neutral: `PRODUCER'S OWN SITE`, `BUY DIRECT`. Never "Shop now", "Order", "Book", "Discover", "Explore".
- 1px solid `--vine` border, `--vine` text, background stays `--paper-raised`. **No filled accent background** — a filled button would blow the `--vine` budget (§2) on a page that already shows `--vine` in links and the fact row. Hover/focus keeps border and text `--vine`: no colour flip, no fill, no glow, no lift.
- `border-radius: 0`. No shadow, no gradient, no icon inside the button.
- Padding ~0.75em vertical, ~1.25em horizontal; **minimum 44px tap height**.
- **Outbound links are never affiliate links and are never marked `sponsored`.** `rel="noopener"` only. The site takes no money from the businesses it documents, and nothing in the interface may imply otherwise — no "partner", no "book with", no price comparison widget.

The public site has **no other interactive controls** beyond: links, the theme toggle (§5a), the corner menu (§5b), the search field inside it, and the text filters (§5). There are **no forms on the public site** — no newsletter capture, no contact form, no claim flow, no reviews, no ratings, no comments. (SCHEMA.md is explicit that the claim flow is deferred and carries no fields.) If one is ever needed, it arrives as a dated, page-scoped exception here, in the mono utility face, one field per row inside the reading spine, no multi-column grid, no floating labels, no card-wrapped fieldsets.

---

## 8. Admin UI (visual only — behaviour in UX.md)

The admin hub inherits the palette (both modes, §2) and the mono utility face, and is allowed to be plainer: it is the workbench, not the guide.

- `border-radius` up to 4px and functional focus rings are fine here. Still no component library — hand-rolled, small, fast, no React (CLAUDE.md stack constraints).
- Log output in mono on `--paper`. **`--vine` for success lines, `--claret` for failures and destructive actions.** This is `--claret`'s main legitimate home.
- Theme is auto (`prefers-color-scheme`) only — no manual toggle (§5a).
- **The review pane's preview renders with the public CSS and no site JavaScript.** That is a hard constraint on §9's motion doctrine, not a nicety: anything that only becomes visible after JS runs is invisible to the reviewer approving it.
- **The independence flag is the most important thing on the review screen** (CLAUDE.md Gate 4). It is displayed as words plus the underlying extracted signals, in mono, with `check` and `reject` states in `--claret`. It is never a green tick. `check` must be visibly blocked from approval, not merely discouraged.
- Toggle chips for practices and logistics: mono, outline at rest, `--vine` fill when active. These exist in the admin only; the public site has no chips (§5).

---

## 9. Quality Floor

- **Responsive to 360px.** No horizontal page scroll at any width. Wide content (tables, code, long mono strings) scrolls inside its own container.
- **Visible keyboard focus everywhere**: `--vine` 1px outline, 2px offset. Never `outline: none` without a replacement.
- **Contrast floor 4.5:1** for all text against both `--paper` and `--paper-raised`, in both modes (§2).
- **Minimum 44px tap targets** for every interactive element.
- **Semantic HTML.** The site must read correctly with CSS off, and correctly with **JavaScript off**.
- **Grain overlay present on every public page** (§4).
- **Every enum value that renders as a glyph has one**; a missing glyph fails the build rather than rendering blank (§6).
- **Australian English in all user-facing copy**, including the admin UI and FAQ answers (CLAUDE.md rule 9). The editorial guardrails — banned words, the em-dash ban, the not-X-but-Y ban, the hedge-word ban — apply to interface copy too, not only to producer entries.

### Motion doctrine

Motion is restrained and it is always additive. Permitted, and nothing else without a dated exception here:

1. **Link underline and glyph colour transitions**, 0.15s. Glyphs use `stroke="currentColor"`, so transitioning `color` on the `<svg>` animates the stroke wherever an ancestor's hover/focus changes it.
2. **The corner-menu drawer slide** (§5b), a `transform` transition.
3. **A one-time on-load settle on the homepage**: top-level sections fade and rise ~10px; section-divider hairlines draw in left to right. CSS-only (`rise-in`, `draw-line`). Runs on every load, no session gating.
4. **Section-divider hairlines drawing in on first scroll into view**, sitewide, at the same 0.9s timing. A divider already on screen at setup is never pushed to a hidden start state — that is the classic reveal-on-scroll flash, and the setup must check the viewport first.
5. **Line-by-line reveal of headings and body copy** as they enter view, ~60ms between lines, using the same fade-and-rise timing family. A run longer than ~8–10 lines compresses rather than continuing to stretch, so no block outruns the ~0.7–0.9s family everything else settles within.
6. **Restrained parallax on two decorative layers only** — the tipped-in plate (§4) and the margin fauna (§6a). Hard ceiling: **~40px of accumulated offset** over a layer's full scroll-through. Never on text, never on interactive elements. Tuned to read as the weight of paper, not as a product-site hero.
7. **A persisting photograph between list and detail**, where a producer has a published image: the list thumbnail (§5) and the tipped-in plate share a `transition:name` and carry across via Astro's own View Transitions. Producers with no photo navigate normally.

Nothing loops. Nothing hijacks scroll. Nothing bounces, springs, or overshoots. No skeleton loaders, no shimmer, no spinners, no progress bars on the public site. No animation ever runs more than once per page view.

**Binding no-JS rule.** **Every element renders fully visible, in its final position, in plain server-rendered HTML with no JavaScript at all.** Motion is something JS *adds* on top of an already-correct page — never something a missing script leaves hidden or broken. This is not aspirational: the admin review pane's preview never loads site JS (§8), the site must survive with JS disabled (`/validate` check 16), and an entry that renders blank without JS cannot be reviewed or approved.

**Binding reduced-motion rule.** `prefers-reduced-motion: reduce` must render the **same final state, with no flash**, via **both**:

1. **The CSS kill-switch** — `@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }`. This covers every plain-CSS transition and keyframe animation above.
2. **The animation library's own guard** — `gsap.matchMedia()` keyed to `"(prefers-reduced-motion: no-preference)"`, wrapping all of items 4–6's setup. **The CSS kill-switch does not stop a JS animation library**, which writes inline `transform`/`opacity` via `requestAnimationFrame` rather than through the CSS `transition`/`animation` properties. Both guards are required; either one alone leaves a hole.

Any animation whose resting (un-animated) state is *not* its visible end state must set that resting state in plain CSS, so the kill-switch lands on the correct frame rather than freezing mid-flight. §5c explains why no such animation currently exists on this site.

> **Dependency flag — resolved 2026-08-07.** Items 4–6 presume a JS animation library and item 7 presumes Astro's `<ClientRouter />`. When this section was written TRD.md did not yet exist. It does now, and **TRD.md §2.5 carries `gsap@3.15.0` under a dated exception**, scoped to in-page scroll-linked effects only, with two conditions: this document owns whether any given effect exists at all, and no content may depend on gsap to be readable. **Items 4–6 are therefore authorised.** The binding no-JS and reduced-motion rules below hold regardless, and `/validate` check 16 enforces them.

When in doubt, prefer less motion, not more. Apply §10's test at a **mid-scroll position**, not only at the top of the page — scroll behaviour is where a restrained site most easily turns into a product site.

---

## 10. The Test

Before any gate closes, screenshot the work — **both modes, and at a mid-scroll position, not only the top** — and ask:

> **Could this screen be mistaken for a SaaS product, a wine retailer, or a winery's own marketing site?**

If yes, it fails the gate.

Then ask the second question, which is specific to this domain and which the first one will not catch:

> **Could this screen be mistaken for a letterpress wine merchant, a cellar notebook, or a ledger?**

If yes, it also fails — see §1. Passing the first test by retreating into the second is not passing.

The reference register is a **field guide**: a survey document, printed cheaply, made to be checked rather than admired. Not a product, and not a costume.

Two supporting checks, both quick, both catching the failures that slip past a screenshot:

- **The evidence check.** Point at any fact on the screen and ask where the reader can see it came from. If the provenance close (§7) is missing, decorative, or reads as a certification rather than a citation, the page fails regardless of how it looks.
- **The nothing-to-sell check.** Would a reader believe this site takes no money from the businesses it documents? If any element — a button, an accent fill, a photograph, a piece of copy — makes them wonder, that element is wrong.

**If you are unsure whether something meets this document, it doesn't. Ask.**

---

## Constants required

Named here so Gate 1 and the Wave 2 design-assets agent can define them in the right file. **This document does not create any of them.** Enums live in `site/src/config.ts` / `admin/config.py` as the hand-mirrored pair (SCHEMA.md §1); presentation constants live in `site/src/config.ts`.

**Identity** — `SITE_NAME`, `SITE_TAGLINE` (both pending a decision, §5c), `THEME_STORAGE_KEY`.

**Display labels**, one per SCHEMA.md §1 vocabulary, since §6 renders words for most of them — `CATEGORY_LABELS`, `CELLAR_DOOR_LABELS`, `CERTIFICATION_LABELS`, `FRUIT_SOURCE_LABELS`, `PRODUCTION_BAND_LABELS`, `PRACTICE_LABELS`, `LOGISTICS_LABELS`, `VESSEL_LABELS`, `WINE_STYLE_LABELS`, `VARIETY_LABELS`, `CONFIDENCE_TIER_LABELS`, `STATE_NAMES`, and region/subregion display names from `regions.ts`.

**Icons** — `IconKey` union and `ICON_PATHS` in `site/src/icons/paths.ts`; `ICON_SIZES` mapping §6's context table to pixel values; the namespacing helpers that derive `practice_*`, `logistics_*`, `style_*`, `vessel_*` keys from the §1 tuples.

**Fauna** — `AnimalKey` union and `ANIMAL_SRC` in `site/src/icons/animals.ts`.

**Pagination** — `PRODUCERS_PER_PAGE` (§7), and `SEED_REGIONS` for the four regions promoted on the homepage.

**CSS custom properties** — the six tokens (`--paper`, `--paper-raised`, `--ink`, `--ink-faded`, `--vine`, `--claret`) declared four times each (§2); `--grain-opacity`; the `@theme` aliases `--color-*`, `--font-display`, `--font-body`, `--font-mono`; and, only if the motion dependency is approved, `--ease-graceful`, `--motion-line-stagger`, `--motion-parallax-max`.

**Shared classes** — `.page-frame`, `.reading-spine`, `.mono`, `.sr-only`, `.visit-btn`, `.rise-in`, `.draw-line`, `.draw-line-on-view`, `.margin-animal`.

**Font files** in `site/public/fonts/` — `fraunces-variable.woff2`, `newsreader-variable.woff2`, `newsreader-400italic.woff2`, `ibm-plex-mono-400.woff2`, `ibm-plex-mono-500.woff2`.

**Components** this document assumes — `BaseLayout.astro`, `SiteLogo.astro`, `Footer.astro`, `CornerMenu.astro`, `ThemeToggle.astro`, `SearchBox.astro`, `GrainOverlay.astro`, `Icon.astro`, `MarginAnimal.astro`, `TippedPhoto.astro`, `Pull.astro`, `ProducerEntry.astro`, `FactRow.astro` (the present-only glyph row), `Provenance.astro` (§7's provenance close), `FAQ.astro`.

---

## Amendment discipline

Superseded rules are **annotated in place with a date, never deleted** (CLAUDE.md working style). A colour that gets amended keeps its old hex visible with the date it was replaced and the reason. This document exists partly because the reference's amendment history is legible: three accent revisions, each dated, each explaining its method — which is how anyone reading it now knows the light `--ink-faded` was never verified. Keep that legibility.
