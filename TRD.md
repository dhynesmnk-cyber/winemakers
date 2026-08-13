# Technical Requirements Document
## A Field Guide to Independent Australian Winemakers

**This document is the authoritative build spec. It is accompanied by CLAUDE.md (process), SCHEMA.md (data contract), UX.md (behaviour), DESIGN.md (visual), PROMPTS/ (agent prompts) and SEED.md (test data). Where those files are more specific than this one, they win: SCHEMA.md outranks this document for data, UX.md and DESIGN.md outrank it for interface (CLAUDE.md rule 3). Flag any conflict either way rather than resolving it silently.**

**Ported from the worked example at `/home/dhynesmnk/Bathers'/` — read-only, never written to. Where this document diverges from the reference, the divergence is marked and dated. Where it is silent, the reference's shape is the intended shape.**

---

## 1. Objective

A field guide to independent Australian winemakers. Free to use, no ads, no sponsored listings.

The core entity is a **producer profile** — one independent winemaker or label per entry, at `/producer/[slug]/`. Wines are attributes of a producer (varieties, styles, vessels, practices), not pages of their own; see §8.

A Python admin app orchestrates an AI pipeline (scrape → extract → draft → polish) into a staging queue. A human reviews and approves. Approved MDX files and the derived data artefacts are committed and pushed to GitHub, which triggers a static Netlify build. No cloud database, no CMS, no runtime backend for the public site.

The word doing the work is **independent**. It is the inclusion criterion, the editorial position and the reason the site exists. Independence is an ownership fact determined from `data/ownership.json` and extracted ownership signals (SCHEMA.md §4) — never inferred from marketing prose, never decided by a single agent. Strict: any corporate ownership blocks publication, including minority stakes and multi-label family groups. `parent_company: null` is the only publishable value.

**v1 coverage target: 150–300 producers, region-deep across Adelaide Hills, McLaren Vale, Yarra Valley and Mornington Peninsula** (CLAUDE.md Gate 8). Region-deep, not nationally thin. This target is a stack decision as much as an editorial one — it is roughly ten times the reference's dataset, and it is why §4's homepage differs from the reference's (§4.6) and why §7's batch harvest queue is a requirement rather than a convenience (§7.4).

**`SITE_NAME` is a placeholder constant.** The brand name is undecided. It is referenced by name everywhere and its value is set once, in `site/src/config.ts`, when the name is chosen. Nothing in this build hardcodes a guess, in copy, in metadata, in the repo name or in a deployed hostname.

---

## 2. Core Stack (fixed — do not substitute)

### 2.1 The stack

Versions are pinned exactly, without carets, as the reference pins them. This is a known-good set that ships a working build of this exact architecture; a drive-by upgrade is a dependency change and falls under CLAUDE.md rule 2.

| Layer | Choice | Version | Why this, and why pinned |
|---|---|---|---|
| Frontend | Astro, SSG mode | `astro@5.18.2` | Static output only, zero client JS by default, content collections with build-time zod validation — the mechanism that makes SCHEMA.md enforceable at build time rather than by convention. |
| Content | MDX integration | `@astrojs/mdx@4.3.14` | Producer bodies carry components (`<Pull>`, `<TippedPhoto>`). Plain Markdown cannot. |
| Styling | Tailwind CSS v4 via the Vite plugin | `tailwindcss@4.3.3`, `@tailwindcss/vite@4.3.3` | **v4, CSS-first: there is no `tailwind.config.js` and none is to be created.** Layout and utility only. Every colour and type token is a CSS custom property owned by DESIGN.md. Tailwind's default grey palettes are banned. |
| Motion | `gsap` core + `ScrollTrigger` + `SplitText` | `gsap@3.15.0` | In-page scroll-linked effects only. Carried from the reference under a dated exception — see §2.5. |
| Page transitions | Astro's built-in `<ClientRouter />` | ships inside `astro` | Zero new dependency. Available to DESIGN.md for cross-page photo persistence; must degrade to a plain navigation with JS off. |
| Data | SQLite via the Python **stdlib `sqlite3`** — `data/directory.db`, committed — plus generated `site/src/data/producers.json` | stdlib | No ORM, no driver package. Frontmatter is canonical; the DB and JSON are derived artefacts fully regenerated on approve (§5). |
| Admin app | Python 3.11+, FastAPI + Jinja2 templates + vanilla JS | `fastapi==0.115.0`, `uvicorn==0.32.0`, `jinja2==3.1.2` | Server-rendered HTML, hand-written JS, no build step and no bundler for admin assets. **No React, no SPA framework, no CDN script tags.** |
| Frontmatter | PyYAML | `PyYAML==6.0` | Parses and re-serialises MDX frontmatter for the admin editor and every validator. The one place YAML round-tripping has to be exact. |
| Scraping | httpx + trafilatura | `httpx==0.27.2`, `trafilatura==1.12.2` | httpx is the single outbound HTTP client for everything: harvest fetches, geocoding, the Netlify build poll, the IndexNow ping. trafilatura extracts main content from the fetched HTML. Respect `robots.txt`; 20s timeout; one job at a time. |
| JS-render fallback | Playwright | `playwright==1.48.0` | **User-triggered per URL only, never automatic.** Version is pinned to the Docker base image tag (§2.4) — moving one moves the other. |
| Images | Pillow | `Pillow==10.4.0` | Downscale and format-normalise candidate producer photographs in the image pipeline (UX.md §4). |
| AI | Anthropic SDK | `anthropic==0.39.0` | The one vendor SDK in the build, justified by its typed error classes (`RateLimitError`, `APIStatusError`, `APIConnectionError`), which are what the transport retry tier in §7.3 discriminates on. Instantiated with `max_retries=0` so the single mandated retry is ours and is visible in the log pane. |
| AI models | Harvester + Gatekeeper on the fast model, Architect on the prose model | from `.env` | **Model IDs live in `.env` and are never hardcoded in source.** Defaults cascade (§2.3) so overriding one variable still yields valid IDs everywhere. |
| Deploy | git push → Netlify build | — | Triggered from the admin deploy strip (§6.5). |
| Hosting | Netlify (static site) + Fly.io (admin app) + GitHub (transport) | — | §2.4. |

**Everything the pipeline needs beyond the above comes from the standard library**: `sqlite3`, `pathlib`, `subprocess` (git), `json`, `re`, `hmac`/`hashlib`, `smtplib`, `socket`, `difflib`.

### 2.2 Dependency posture

CLAUDE.md rule 2 is a house posture, not a formality. It is stated here so a future session can see the shape of the rule rather than only its text:

- **Raw httpx over vendor SDKs.** Any third-party HTTP API this project ever calls is called with `httpx` against its REST endpoints. The reference proved this out against Stripe, Google Places, Nominatim, GoatCounter and Netlify without installing a single vendor package. The Anthropic SDK is the one exception, for the reason in the table.
- **Stdlib over convenience packages.** `smtplib` not a mail library, `hmac`/`hashlib` not a signature library, a hand-rolled `.env` parser not `python-dotenv`, stdlib `sqlite3` not an ORM, plain multipart handling not `python-multipart`.
- **No client-side libraries.** Search is substring matching over an embedded JSON index, not a fuzzy-search package (§4.7). Admin JS is hand-written. Any vendored asset (as the reference vendored Quill) is committed into `admin/static/vendor/`, never loaded from a CDN.
- **Adding a dependency is an ask**, with what it is for and what the no-dependency alternative would be, recorded as a dated exception in this section on approval.

### 2.3 Two load-bearing config quirks (port verbatim)

Both live at the top of `admin/config.py` (owned by Gate 1, mirrored into `site/src/config.ts` where the constant is shared). Neither is optional and neither is decorative.

1. **The IPv4-only `socket.getaddrinfo` monkeypatch**, installed at import time, before any httpx client exists. Some sandboxed environments advertise an IPv6 route that is a black hole — packets vanish, no RST, no ICMP unreachable. curl falls back to IPv4 (RFC 8305); Python's socket stack does not, and hangs inside `connect()` past any per-call timeout. Every external call this project makes goes through httpx, so DNS resolution is forced to IPv4 process-wide, once, here. Harmless where IPv6 works; this project has no IPv6-only dependency.
2. **The hand-rolled `.env` parser** — a minimal `KEY=VALUE` reader, no `python-dotenv`, for a format this simple. Paired with **cascading model defaults**: a variable that is not set falls back to another resolved variable rather than to a literal, so a real `.env` that overrides only `MODEL_ARCHITECT` still yields a valid ID for every downstream role. `.env` is read-only, never committed, never printed (CLAUDE.md rule 5).

### 2.4 Hosting and transport

Three parties, ported from the reference as-is.

**Netlify — the public site.** Root `netlify.toml` with `base = "site"`, `command = "npm run build"`, `publish = "dist"`. Build triggered by a push to `main`. The Netlify default subdomain is 301-redirected to the apex host once a custom domain exists, so no duplicate host stays crawlable — one line in `netlify.toml`, added at the domain switch, not before. The site performs zero runtime data fetching (§4.4), so there is nothing else to configure.

*Amended 2026-08-09, with sign-off: **the domain switch is taken in two steps, and the first one is now done.** `SITE_URL` reads `https://winemakers.netlify.app` in `site/src/config.ts` and as `admin/config.py`'s default, replacing `https://example.invalid` and `https://example.com` respectively.*

*This is the host half of the switch only. `SITE_NAME` stays pending: the brand name is still undecided and is still not to be guessed (§1). The two were never one decision, and leaving the host on a placeholder because the name was unresolved had three live costs — the production sitemap served 156 `<loc>` entries on a host that does not resolve, the IndexNow ping would have declared a `keyLocation` on a domain the site does not own, and every request to a producer's website identified itself with a methodology link nobody could follow.*

*The Netlify subdomain is not a stand-in for the apex domain; this section already names it as the public host until a custom domain exists, and 301s it afterwards. The second step, when the brand lands, is this value in three places: the two configs and `.env`.*

*Amended 2026-08-08 (Gate 7), with sign-off: `netlify.toml` carries a fourth key, `NODE_VERSION = "20"` under `[build.environment]`. Netlify's default Node version has moved more than once and would move this build under us on a day nothing in the repository changed. 20 is the version the Dockerfile installs from NodeSource, so the admin's pre-push `npm run build` gate (§6.5) and Netlify's own build run the same major version. A gate that passes on one version and fails on another is not a gate. The three keys above are otherwise unchanged.*

**Fly.io — the admin app.** App name and hostname carry `SITE_NAME`'s eventual value and are therefore **not to be chosen or registered until the brand name is** (§1); until then the app is run locally. `fly.toml`: `primary_region = 'syd'`, a persistent volume mounted at `/data`, `[http_service]` on `internal_port = 8787` with `force_https = true`, `auto_stop_machines = 'off'`, `auto_start_machines = true`, `min_machines_running = 1`, one `shared-cpu-1x` / 1024mb VM.

**Dockerfile.** `FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy` — the base image already carries Python plus Chromium's OS dependencies matching the pinned `playwright==1.48.0`, so there is no hand-rolled apt list for headless-browser support. Add `git`, `ca-certificates`, `curl`; add Node 20 from NodeSource (the distro's Node is too old for Astro 5). **Only `admin/requirements.txt` is copied from the build context** and pip-installed; the application code is not baked into the image.

**`docker-entrypoint.sh`** — runs on every container boot:

1. Requires `GITHUB_PAT`; fails loudly if absent.
2. Configures git identity and a credential helper that echoes the token **from the environment per invocation** — never written to `.git/config` or any file on disk.
3. Clones the repo into `/data/repo` on first boot; on subsequent boots `fetch --prune` then **`reset --hard origin/main`**. Not `pull --ff-only`: the volume checkout accumulates runtime writes to tracked, committed derived artefacts (`data/directory.db`, `site/src/data/producers.json`), a fast-forward pull aborts on that dirt, and under `set -euo pipefail` an abort crash-loops the machine. The committed derived files are authoritative; a tracked-file reset leaves all gitignored volume state (`temp_data/`, `content-staging/`, `node_modules/`) untouched.
4. **Materialises `.env` from Fly secrets** (injected as ordinary environment variables) under `umask 077`, one heredoc mirroring `.env.example`'s key set exactly, with the same cascading defaults as §2.3. Never committed, never echoed.
5. `pip install -q -r admin/requirements.txt` as a safety net for requirements drift between image build and the branch just pulled.
6. `npm ci && npm run build` in `site/` — **non-fatal**, wrapped so a failure logs a warning and continues. The admin is the tool used to fix a broken content file; a broken content file must never keep it down. Gives the admin its preview CSS, its `/site-dist` views and a warm cache for the deploy strip's pre-push build gate.
7. `exec uvicorn admin.app:app --host 0.0.0.0 --port "${ADMIN_PORT:-8787}"`.

**GitHub — the transport.** The admin's deploy strip is the only path from disk to live (§6.5). Every write in this system stops at "updated on disk" and waits for a human to click Deploy. **There is no automatic push path** — the reference had exactly one (its Stripe claim webhook), and this project does not carry the feature that created it (§8).

**Volume state that must never be committed:** `temp_data/`, `content-staging/`, `.env`, `node_modules/`. The deploy guard enforces this as an allow-list, and `/validate` check 15 exercises the guard against a deliberately staged illegal file rather than merely asserting the invariant.

### 2.5 Dated exceptions and deliberate non-ports

**2026-08-06 exception (carried forward) — `gsap@3.15.0`, one new frontend dependency.** CLAUDE.md rule 2 applies; this is that ask, documented as approved, inheriting the reference's 2026-07-30 approval and its scope unchanged: **in-page scroll-linked effects only** — restrained parallax on the tipped-in photograph, hairline self-draw on enter-view, staggered per-line text reveal on enter-view. *No-dependency alternative considered:* native CSS `animation-timeline: scroll()`/`view()`, rejected because Firefox has not shipped scroll-driven animations as of early 2026 and because per-line stagger measured against actual rendered line breaks (which reflow with viewport width and with `font-display: swap` variable faces) is materially harder to hand-roll than to buy. *Why gsap specifically:* one npm package including `ScrollTrigger` and `SplitText`, both free under the standard no-charge licence since 2024; roughly 27 KB gzipped for core plus 10–15 KB for the two submodules, tree-shaken figure to be confirmed at implementation time. **Two conditions on carrying it:** DESIGN.md owns whether any given effect exists at all (it outranks this document for interface), and **no content may depend on gsap to be readable** — `/validate` check 16 requires every element to render fully visible in its final position with JS disabled and under `prefers-reduced-motion: reduce`.

**2026-08-06 — deliberate non-ports.** Present in the reference, not carried, so nobody ports them by reflex:

| Reference component | Status here | Why |
|---|---|---|
| Leaflet + map tiles, `venues.geojson` | Not carried | The reference removed its map (2026-07-26) and the GeoJSON is vestigial — written by the admin, read by no page. There is no map in this build and no runtime tile fetch (§4.4). Coordinates are still stored (SCHEMA.md §2) for JSON-LD `geo` and for a plain "where" line; a producer with null coordinates is a first-class entry. |
| `au-places.ts` gazetteer, 50 km near-me | Not carried | Belongs to a homepage this project replaces (§4.6). Distance is not how anyone chooses a winery to visit — region is. |
| OSRM drive-time | Not carried | Depends on the coordinates-and-distance framing above. |
| Google Places discovery | Deferred — §8 | |
| Quill.js vendored editor, Stripe, claim flow, GoatCounter | Deferred or out of scope — §8 | **Amended 2026-08-13 (Gate 11): the Quill half is now decided, not deferred.** §8 never mentioned Quill, so this row pointed at a section that did not carry it — the same dangling-attribution defect §3's 2026-08-12 amendment recorded for `ExtractiveAnswer`. See the 2026-08-13 entry below. The other three are unchanged. |

**2026-08-06 — Schema.org, decided now, shipped at Gate 10.** Producer pages emit generic **`LocalBusiness`**, deliberately, not `Winery`. `Winery` reads as a cellar door with a tasting room, and a materially large share of this dataset is `garagiste`, `negociant` and label-only producers with no premises a reader can visit — the same mislabel trap the reference hit with `DaySpa`. Specificity is carried by the entry's own structured fields and by `DefinedTerm`s, not by a narrower type. CLAUDE.md Gate 10's done-condition requires any move beyond `LocalBusiness` to be recorded here as a dated exception with explicit sign-off, or explicitly declined; **this is that decision, declined for v1**.

*Shipped 2026-08-13 (Gate 10), and the declination held: 97 producer pages emit `LocalBusiness` and nothing emits `Winery`. It is now **enforced rather than merely recorded** — `/validate` check 18 fails on any `@type` outside the site's allowed set, so widening the type means adding it there deliberately, which is the prompt to come back and write the exception first. No exception has been taken.*

**2026-08-13 — the structured-data set, and four things deliberately absent (Gate 10).** The graph is `Organization` + `WebSite` on every page, `BreadcrumbList` wherever a path up exists, `ItemList` on every listing, `LocalBusiness` + `FAQPage` on producer pages, and `DefinedTermSet`/`DefinedTerm` across the glossary. Every node is built in `site/src/data/jsonld.ts`; no page hand-writes a schema.org object.

Four omissions are decisions rather than gaps, recorded here because each is something a later reader will assume was forgotten:

- **No `aggregateRating`, `review` or `priceRange`.** Nobody on this project has visited these cellar doors or tasted these wines (CLAUDE.md rule 6), so there are no ratings and no reviews to report, and the guide publishes no bottle prices. Check 18 fails the build on all three rather than leaving it to discipline — these are exactly the fields a well-meaning later edit adds because a rich-results guide recommends them.
- **No `openingHours`.** `cellar_door_hours` is a freeform display string by schema design (SCHEMA.md §2, "never reformatted into a grid"). Parsing it into schema.org's opening-hours grammar would invent structure the source does not have, and would do it silently on the entries it got wrong.
- **No `SearchAction` on `WebSite`.** Search is client-side over an index embedded at build time (§4.7). There is no `/search?q=` route to declare, and a `SearchAction` is a promise about a route.
- **No `logo` on `Organization`.** The site's mark is set in type (`SiteLogo.astro`) and there is no image file to point at. An `Organization` claiming a logo URL that 404s is worse than one claiming none.

*`Organization.email` is emitted conditionally and is currently **absent**, because `SITE_CONTACT_EMAIL` is still the Wave 2 placeholder at `example.invalid`. A machine-readable contact address that cannot receive mail is a worse claim than no contact address; the footer's `mailto:` shows the placeholder to a reader, who can see what it is, and a crawler cannot. The line publishes the address the moment `config.ts` carries a real one.*

**2026-08-13 exception (Gate 11), with sign-off — `BlogPosting` joins the allowed `@type` set.** This is the first widening of the set since Gate 10 closed it, and it is written here first because that is exactly the mechanism §2's 2026-08-13 entry built: `/validate` check 18 fails on any `@type` outside its allow-list, so a new type cannot ship without somebody coming here to say why.

**Scope: `BlogPosting` on `/blog/[slug]/` and nothing else.** `Blog` as a type on the index is **not** taken — the index is a listing and it carries `ItemList`, exactly like every other listing on the site. `Article` and `NewsArticle` are not taken either; a post here is a post on a blog, and the narrower claim is the true one.

*Why this is a different question from `Winery`.* The `Winery` declination is about **mislabelling an entity**: a large share of the producer corpus has no cellar door, so the narrower type would assert a premises that does not exist. A post is a post. There is no share of the corpus for which `BlogPosting` is the wrong noun, and the type asserts nothing beyond what the page prints.

**What it emits**, every field taken from what the page renders: `headline`, `description`, `datePublished`, `dateModified` (only where `updated` is set), `author` and `publisher` both pointing at the `Organization` `@id`, and `citation` built from the post's `sources`. **`author` is the site, not a person**, because this guide carries no bylines and inventing one to fill a recommended field is the same defect as inventing a logo URL.

`citation` is the entry worth having. It is the machine-readable half of SCHEMA.md §9.2's required `sources`, and check 18 asserts its length equals the source count the page prints — so a post cannot cite one thing to a reader and three to a crawler.

**2026-08-13 decision (Gate 11) — the blog body editor is hand-rolled, and no editor package is added.** UX.md §6 asks for "a rich-text body editor". §2.5's table above listed the reference's vendored Quill as deferred, pointing at a §8 that never mentioned it, so the question had never actually been answered. It is answered here, put to the user with the alternatives and signed off the same day.

**What ships:** a textarea over the post's own MDX source, a hand-rolled formatting toolbar writing markdown syntax (bold, italic, heading, link, `<Pull>`, image insert), and a live preview rendered through `admin/mdx_preview.py` — the same renderer the producer review pane uses, and the one `/validate` check 20 already guards.

*No-dependency alternative considered — and it is the one taken*, so the shape of this entry is the inverse of §2.5's gsap exception. **Vendoring Quill was rejected on three counts, none of them the package's size.** It emits HTML, so a post would need an HTML→MDX converter on every save, which is either a second dependency or a hand-rolled parser doing the hardest job in the build. `<Pull>` and `<TippedPhoto>` do not survive that round trip — a WYSIWYG surface renders them as inert text and saves them back as prose, which silently destroys the one thing a post body carries that plain markdown cannot. And MDX would stop being canonical: the file on disk would become a serialisation of the editor's state rather than the thing the author wrote, which is exactly the relationship TRD.md §5 refuses between frontmatter and the derived DB.

*The cost is stated plainly: this is not WYSIWYG, and an author who wants one will not get one from the toolbar. The preview pane is what carries that weight, and it renders with the public site's real CSS.*

---

## 3. Repository Structure

One repo, two clearly separated applications sharing a content directory. **No Python import reaches into `site/`; no Astro code reaches into `admin/`.** All cross-cutting paths are defined once — `admin/config.py` for Python, `site/src/config.ts` for Astro — and imported everywhere else (CLAUDE.md rule 4). That pair is hand-mirrored and is owned by Gate 1.

```
/site                            # Astro project
  astro.config.mjs               # output: "static"; integrations: [mdx()];
                                 #   vite.plugins: [tailwindcss()]  — no tailwind.config.js
  package.json                   # the four pinned npm deps from §2.1
  /public
    /fonts                       # three self-hosted woff2 faces (DESIGN.md)
    /images                      # published producer photographs — committed
  /src
    config.ts                    # GATE 1 OWNS THIS. Closed vocabularies (SCHEMA.md §1) as
                                 #   `as const` tuples, site constants, shared helpers.
                                 #   Hand-mirrored with admin/config.py.
    /content
      config.ts                  # zod collection schema — mirrors SCHEMA.md §2 exactly,
                                 #   sub-schemas built programmatically from the tuples (SCHEMA.md §8)
      /producers
        /_published              # approved MDX — the ONLY producer content Astro builds from
      /blog
        /_published              # hand-authored posts (Gate 11) — shipped 2026-08-13
    /components                  # ProducerEntry, Pull, TippedPhoto, Icon, GrainOverlay,
                                 #   SiteLogo, Footer, ThemeToggle, SearchBox, FAQ,
                                 #   ComparisonTable  (DESIGN.md §164, §501)
                                 #   PostEntry, Figure (Gate 11) — SCHEMA.md §9.5 defines
                                 #     Figure's closed query set BEFORE it was built
                                 #   ~~ExtractiveAnswer~~ — see note below
    /icons/paths.ts              # hand-authored inline SVG icon set (DESIGN.md)
    /data
      producers.json             # GENERATED on approve — committed (§5)
      regions.ts                 # GI region + subregion register (Wave 2) — hand-authored
      glossary.ts                # one entry per enum value across every SCHEMA.md §1 vocabulary
      comparisons.ts             # comparison registry + minimum-producer threshold (Gate 9)
      forewords.json             # GENERATED region/taxonomy forewords (Gate 6) — committed
      jsonld.ts                  # every schema.org node builder (Gate 10) — see §2's
                                 #   2026-08-13 entry for what is deliberately absent
    /layouts/BaseLayout.astro    # dual-mode tokens, grain overlay, embedded search index (§4.7)
    /pages                       # see §4.2 for the route table
    /scripts/motion.ts           # the only gsap call site
    /styles
/admin                           # FastAPI app
  app.py                         # routes, SSE log streams, HTTP Basic Auth
  config.py                      # GATE 1 OWNS THIS. Paths, env, model IDs, vocab mirrors,
                                 #   IPv4 monkeypatch, .env parser (§2.3)
  schema.py                      # KNOWN_FIELDS — the admin frontmatter editor's field contract
  mdx_preview.py                 # renders staged MDX with the public site's real CSS
  requirements.txt               # the nine pinned pip deps from §2.1
  /pipeline
    agents.py                    # the two retry tiers (§7.3)
    orchestrator.py              # Harvester JSON validator + _finalize_frontmatter (SCHEMA.md §6)
    harvest.py  queue.py         # single harvest; the batch queue (§7.4)
    ownership.py                 # NEW — the independence determination (SCHEMA.md §4, Gate 4)
    data_store.py                # sole owner of directory.db and producers.json (§5)
    staging.py  verification.py  geocode.py  images.py  deploy.py  forewords.py
    schema_surfaces.py           # /validate 13 — the four-surface diff
    link_graph.py  jsonld_validator.py  validate_*.py
                                 # jsonld_validator.py = /validate 18 (Gate 10);
                                 #   validate_llms.py  = /validate 19 (Gate 10)
    blog.py  article_pipeline.py  article_factcheck.py     # Gate 11 — shipped 2026-08-13
    validate_blog.py             # /validate 22 (Gate 11)
  /templates                     # index.html, preview.html, partials/
  /static                        # admin.css, admin.js — hand-written, no build step, no CDN
/PROMPTS                         # loaded at call time, never embedded (§7.2)
  harvester.md  architect.md  gatekeeper.md  foreword.md
  article_brief.md  article_draft.md  house_voice.md  factcheck.md
/data
  directory.db                   # committed derived DB — disposable, always rebuildable (§5)
  ownership.json                 # NEW — hand-maintained ownership deny-list (SCHEMA.md §4.3).
                                 #   Committed. Has no analogue in the reference.
  /factchecks                    # committed per-article claim audits (Gate 11)
/content-staging                 # OUTSIDE site/src/content so Astro never builds a draft
  /_staging  /_rejected  /_deleted  /_blog_staging  /_article_staging
  /_blocked                      # AMENDED 2026-08-07 — see below
  /_determinations               # AMENDED 2026-08-07 — see below
/temp_data                       # GITIGNORED — never edited by hand (CLAUDE.md rule 5)
  /images  /failed  harvest_queue.json  geocode_cache.json
/.claude
  /agents/schema-guardian.md
  /commands/validate.md
  /skills/gate-exit  /skills/schema-change  /skills/producer-entry
CLAUDE.md  SCHEMA.md  TRD.md  UX.md  DESIGN.md  SEED.md  README.md
METHODOLOGY.md                   # AMENDED 2026-08-07 — see below
Dockerfile  docker-entrypoint.sh  fly.toml  netlify.toml
.env  .env.example  .gitignore
```

### Amendment, 2026-08-13 (Gate 11): where the blog contract lives, and `/rss.xml`'s shape

Two things this tree named without defining.

**The blog frontmatter contract is SCHEMA.md §9**, authored at Gate 11 into the data document rather than into the zod file, because a contract only readable by opening TypeScript is a contract nobody checks against. It carries the same weight §2 carries for producers, and it is deliberately **two** surfaces rather than four: there is no SQLite table for posts and no Harvester validator, and §9.1 records why each omission is a decision. `schema_surfaces` grew a second, smaller comparison for the pair; posts are **not** folded into the producer diff, because a shared diff would make every blog field look like a rule-7 field and the first consequence would be somebody adding a producer field to `blog.py`.

**`/rss.xml` has no specification anywhere**, in this document, UX.md or DESIGN.md. `Footer.astro` has linked it since Gate 1 and §4.2's 2026-08-08 amendment assigned it to Gate 11 without saying what it should contain. Decided here rather than improvised in a route file: **RSS 2.0**, one `<item>` per published post in `published` order descending, carrying `title`, `link`, `guid` (the absolute post URL, `isPermaLink="true"`), `pubDate` in RFC 822, and `description` set to the post's `summary` and nothing else.

*The last one is the only real decision in that list. A feed carrying full post bodies would be a second rendering of the same prose with no `<Figure>` resolution a reader could trust and no way to correct it once fetched — every amendment recorded by `updated` would be invisible to anyone reading the copy in their reader. The summary plus a link sends the reader to the version that stays right. This is the same reasoning §4.4 uses to refuse runtime fetching, applied to the copy rather than to the data.*

### Amendment, 2026-08-12 (Gate 9): `ExtractiveAnswer` was never specified

The tree above attributed two components to "DESIGN.md / UX.md". `ComparisonTable` is genuinely specified there — DESIGN.md §164 and §501, UX.md §5 — and shipped at Gate 9. **`ExtractiveAnswer` is not mentioned in DESIGN.md, UX.md, SCHEMA.md or this document anywhere else.** The attribution was untrue: nothing defined what the component is, what it renders or what data feeds it.

Struck rather than guessed, per CONSTANTS-REQUIRED.md's rule that an undecided thing must never be invented to satisfy a checklist. **Deferred to Gate 10**, which owns `FAQPage` JSON-LD, the E-E-A-T work and the methodology page — the surface an extractable answer block would serve. If Gate 10 wants it, it gets a specification in UX.md or DESIGN.md first, and this line comes back with the attribution made true.

Recorded because a dangling component name in a file tree is the kind of thing a later gate implements from imagination rather than from a spec.

### Amendment, 2026-08-07 (Gate 4): three paths this tree did not name

UX.md §1.4.4 and §1.4.6 require `BLOCKED_DIR` and `DETERMINATIONS_DIR` by name, and CLAUDE.md's Gate 4 requires the methodology page to be drafted. None of the three appeared in the tree above. They are added here with their placement and its consequence, rather than left as an undocumented decision in `config.py`.

**`content-staging/_blocked/`.** One `<slug>.json` per producer stopped by the ownership rule before a draft was written, carrying the URL, the extracted name, the verdict, the full `ownership_signals`, the deny-list result including any matched record, and a timestamp. Working state: it belongs with `_staging` and `_rejected`, it is gitignored, and the deploy allow-list (§6.5) does not carry it. Records are never deleted (UX.md §1.4.4).

**`content-staging/_determinations/`.** The retained ownership sidecar, one `<slug>.json` per published producer, moved there by the approve action (UX.md §1.4.6). Same placement, same posture, and **the same consequence, which is load-bearing and is stated here because it changed a `/validate` check**: a gitignored determination does not travel with the repository, so `/validate` check 8 **reports** a missing determination and does not fail on it. Failing would fail the check on every fresh clone, which trains whoever runs it to ignore the result.

That is an acceptable trade only because the durable public record lives elsewhere and is committed: `ownership_source` in the frontmatter, asserted by check 8, and `verification.parent_company` as a `{source, tier, date}` block, asserted by check 14. The sidecar holds the working evidence behind those, including signals resolved as `Not relevant` that would otherwise vanish.

*If the sidecar is ever needed as the answer to a producer's dispute months later, on a machine that is not the one that approved the entry, this placement is wrong and `DETERMINATIONS_DIR` moves to `data/determinations/`, committed, alongside `ownership.json` and `data/factchecks/`. That is a live question, not a settled one, and it is recorded here so the decision gets made deliberately rather than discovered.*

**`METHODOLOGY.md`, at the repository root.** The authored source for `/methodology/`, drafted at Gate 4 alongside the system it describes and rendered into a page at Gate 10 (§4.2's route table already carries the route). It sits with the other authored prose documents rather than in `site/` because building it now would ship it before Gate 10, and Gate 10's done-condition is that the page is live **and linked**.

*Shipped 2026-08-13, and it stayed at the repository root. A `methodology` content collection whose `base` points outside `site/` is what renders it there, through Astro's own markdown pipeline — no second markdown dependency and no hand-rolled parser (CLAUDE.md rule 2). The file gained frontmatter in the same change, carrying `title`, `description` and `updated`; its Gate 4 drafting preamble became YAML comments, because everything below the frontmatter is reader-facing from that date and build notes do not ship. `/validate` check 6 lints the body alone for the same reason, with frontmatter lines blanked rather than dropped so a reported line number still points at the real line.*

**Why `_staging` and `_rejected` sit outside `site/src/content`.** Astro content collections glob everything in a collection directory; keeping drafts out of the tree entirely is more robust than relying on an underscore-prefix exclusion. The collection loader points at `_published` only. The approve action moves the file across into `site/src/content/producers/_published/`; nothing else writes there (CLAUDE.md rule 5).

**Constants that must exist.** Named here so the Gate 1 agent has a checklist; that agent owns the `config.ts` / `config.py` pair exclusively and this document never sets their values except where a value is itself a decision recorded below.

| Constant | Home | Purpose |
|---|---|---|
| `SITE_NAME`, `SITE_TAGLINE`, `SITE_URL`, `SITE_CONTACT_EMAIL` | `config.ts` | **`SITE_NAME` is a placeholder until the brand name is chosen (§1).** |
| `CATEGORIES`, `CELLAR_DOOR_STATES`, `CERTIFICATION_STATES`, `FRUIT_SOURCE`, `PRODUCTION_BANDS`, `PRACTICE_KEYS`, `LOGISTICS_KEYS`, `VESSEL_KEYS`, `WINE_STYLE_KEYS`, `VARIETY_KEYS`, `CONFIDENCE_TIERS`, `CONFIDENCE_TIER_RANK`, `VERIFIABLE_FIELDS`, `STATES` | both, hand-mirrored | SCHEMA.md §1. Closed `as const` tuples; zod sub-schemas built from them programmatically, never an inline enum literal. |
| `AU_LATITUDE_BOUNDS`, `AU_LONGITUDE_BOUNDS` | both | SCHEMA.md §2 coordinate bounds. |
| `PRODUCTION_BAND_RANGES` | both | The numeric ranges behind `PRODUCTION_BANDS`, for SCHEMA.md §2a rule 9. |
| `PRODUCERS_PER_PAGE` | `config.ts` | Pagination page size (§4.6). Default 24; UX.md wins if it specifies otherwise. |
| `SEARCH_INDEX_INLINE_MAX` | `config.ts` | 500 — the producer count above which the embedded search index becomes a fetched one (§4.7). |
| `HOMEPAGE_LATEST_COUNT`, `SEARCH_MAX_RESULTS` | `config.ts` | **AMENDED 2026-08-08 — see below.** Both are named by UX.md §2.1 and were missing from this checklist. |
| `COVERAGE_REGIONS` | both | The four Gate 8 seed regions, so "which regions are populated" is data, not prose. |
| `MIN_COMPARISON_PRODUCERS`, `MIN_AGGREGATION_LINKS` | `config.ts` | Gate 9 thresholds; `MIN_AGGREGATION_LINKS` is 3 per `/validate` check 17. |
| `ROOT`, `SITE_DIR`, `PUBLISHED_DIR`, `STAGING_DIR`, `REJECTED_DIR`, `DELETED_DIR`, `DB_PATH`, `PRODUCERS_JSON_PATH`, `FOREWORDS_JSON_PATH`, `OWNERSHIP_JSON_PATH`, `PROMPTS_DIR`, `TEMP_DATA_DIR`, `IMAGES_DIR`, `FAILED_DIR`, `HARVEST_QUEUE_PATH`, `GEOCODE_CACHE_PATH` | `config.py` | Every cross-cutting path, defined once, `pathlib`, safe from the repo root. |
| `ANTHROPIC_API_KEY`, `MODEL_HARVESTER`, `MODEL_ARCHITECT`, `MODEL_GATEKEEPER`, `ADMIN_PORT`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `GEOCODER`, `GEOCODER_USER_AGENT`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`, `INDEXNOW_KEY` | `config.py`, from `.env` | With cascading defaults (§2.3). Model IDs never hardcoded. |
| `MODEL_ARTICLE`, `MODEL_FACTCHECK`, `MODEL_BRIEF`, `BLOG_PUBLISHED_DIR`, `BLOG_STAGING_DIR`, `ARTICLE_STAGING_DIR`, `FACTCHECKS_DIR` | `config.py` | Gate 11. ~~Named now so the key set is stable; unused until then.~~ **All live since 2026-08-13.** `MODEL_FACTCHECK` must differ from `MODEL_ARTICLE`: `FACTCHECK_IS_SELF_REVIEW` warns and stamps the audit when they collapse. |

`.env.example` mirrors the `.env` key set exactly, with comments and no values, and is the one `.env*` file that is tracked.

### Amendment, 2026-08-08 (Gate 6): two constants UX.md names and this checklist did not

UX.md §2.1 refers to `HOMEPAGE_LATEST_COUNT` and `SEARCH_MAX_RESULTS` by name as though they were already decided. Neither appeared in the table above, in `CONSTANTS-REQUIRED.md`, or in `config.ts`, and neither document gives a number. Gate 6 needs both to build the homepage, so the values are set here rather than left as bare literals in a template.

**`HOMEPAGE_LATEST_COUNT` = 8.** The homepage renders this many `ProducerEntry` rows, the most recently `drafted`, then one link to `/producers/`. Eight is long enough to show the guide is being added to and short enough that it cannot compete with the region chooser above it, which UX.md §2.1 item 4 calls the primary navigation and the main content of the page. It is a fixed-length slice: the homepage has no pager and mints no `/page/[n]/` route at the site root.

**`SEARCH_MAX_RESULTS` = 8.** The most results the search field offers at once. `↑`/`↓` reaches the last one without the list running off a phone viewport. Search is an accelerator and never the only route to anything, so truncating is not a loss of access.

Both live in `config.ts` alone. Neither has a Python consumer, so neither goes in the mirrored pair and check 13 does not diff them.

*Sorting for "most recently drafted" is `drafted` descending, then `name` ascending. The tiebreak is load-bearing rather than cosmetic: a batch harvest stamps one `drafted` date across a whole run, so without it the homepage's eight rows would reorder on every rebuild and the derived-artefact diff in check 3 would churn.*

### Amendment, 2026-08-08 (Gate 6): the state route's slug form

§4.2's route table gives `/[state]/` and UX.md §2.4 says the eight slugs come from the closed `STATES` tuple, but no document says whether the slug is the code or the name. It is the **slugified full name** — `/south-australia/`, `/victoria/`, `/new-south-wales/` — not `/sa/`, `/vic/`, `/nsw/`.

Every other public route on this site slugifies a human name, and DESIGN.md §5's `ProducerEntry` dateline states the rule for states specifically: words, not codes. A two-letter path would be the only route on the site that reads as an internal identifier. The tuple still governs which eight exist; only the rendering of each slug into a path changed.

---

## 4. Frontend Requirements

**UX.md owns behaviour, ordering and no-JS fallbacks. DESIGN.md owns every visual decision.** Both outrank this section. What follows is the build contract, not a restatement of either.

1. **Content collection `producers`** with a strict zod schema per SCHEMA.md §2, sub-schemas built programmatically from the `config.ts` tuples per SCHEMA.md §8, `z.coerce.date()` for every date. **The build must fail on any schema violation**, with a field-level error naming the file and the field. A wrong type, a missing required field and an unknown key against `.strict()` all fail.
2. **Routes.** Every programmatic page is generated **present-only**: loop the taxonomy, `continue` on zero, never emit an empty page (Gate 6).

   | Route | Source | Gate |
   |---|---|---|
   | `/` | region-first, paginated (§4.6) | G1/G6 |
   | `/producer/[slug]/` | one per `_published` MDX | G1 |
   | `/region/`, `/region/[region]/`, `/region/[region]/[subregion]/` | `regions.ts` ∩ published | G6 |
   | `/[state]/` | `STATES` ∩ published | G6 |
   | `/variety/[grape]/` | `VARIETY_KEYS` ∩ published | G6 |
   | `/practice/[key]/` | `PRACTICE_KEYS` ∩ published | G6 |
   | `/glossary/`, `/glossary/[key]/` | one entry per enum value, every vocabulary | G6 |
   | `/compare/`, `/compare/[slug]/` | `comparisons.ts` above threshold | G9 |
   | `/methodology/` | hand-authored; drafted at G4, ~~ships at G10~~ **shipped 2026-08-13** | G10 |
   | `/blog/`, `/blog/[slug]/` | blog collection; ~~ships at G11~~ **shipped 2026-08-13** | G11 |
   | `/sitemap.xml`, `/llms.txt`, `/rss.xml` | endpoints, not static files | G6/G10/G11 |

   `llms.txt` is **generated as an endpoint** rather than committed as a static file, so it cannot drift from the routes that exist.

   *Shipped 2026-08-13 (Gate 10), built from the same present-only helpers as the sitemap, and asserted from outside the generator by `/validate` check 19: every link absolute, on this site, and resolving to a route the build emitted. Check 5 could never have covered it — it walks internal hrefs in built HTML, and `llms.txt` is plain text outside the page graph.*

   **`/methodology/` came off `PENDING_ROUTES` on 2026-08-13 and `/rss.xml` and `/blog/` remain**, so the list is now two rather than three. That is the mechanism working as intended: a shipped route becomes a hard requirement, and the list shrinks at a gate exit rather than quietly permitting a live route.

   **Amendment, 2026-08-08 (Gate 6): `/rss.xml` belongs to Gate 11.** `Footer.astro` has linked it since Gate 1 and no route table in this document, UX.md or DESIGN.md ever mentioned it. It is the journal's feed, so it ships with the journal. Until then it sits in `PENDING_ROUTES` in `/validate` check 5, printed on every run alongside `/methodology/` (G10) and `/blog/` (G11), and the check fails if it starts resolving while still listed — so the list shrinks when a gate ships rather than quietly permitting a live route.
3. **Components.** `<Pull>` for pull-quotes and `<TippedPhoto>` for the single optional image, both usable from MDX bodies; `<ProducerEntry>` for list rendering; `<Icon>` for the hand-authored inline SVG set. Visual treatment per DESIGN.md.
4. **Zero runtime data fetching.** Everything comes from `getCollection("producers")` and the generated `producers.json` at build time. No client fetch, no serverless function, no third-party script — there is no map and therefore not even a tile request.
5. **No-JS and reduced-motion are build requirements, not courtesies.** Every producer, every programmatic route, every paginated page and every navigation affordance is reachable with JavaScript disabled. Under `prefers-reduced-motion: reduce`, every element renders fully visible in its final position. `/validate` check 16.
6. **2026-08-06 decision — the homepage is region-first with real pagination.** This is the scale change, and it is a design decision taken now, not a performance fix deferred to later.

   The reference's homepage embeds its whole dataset and filters it client-side, which is correct at 32 venues and wrong at 300. Three reasons it does not survive: it ships the entire dataset to every visitor on the highest-traffic page; a flat list of 300 producers is a wall, not a guide; and it buries the one claim this project is making, which is that four regions are covered *deeply*. A wall of 300 names reads thinner than four regions that read as complete.

   The contract:
   - The homepage presents **regions**, each with a producer count and a short foreword, plus an entry point to search. It does not render the producer list.
   - Producer lists live on region, subregion, state, variety and practice pages and are **paginated server-side** with Astro's `paginate()` at `PRODUCERS_PER_PAGE`, at `…/page/[n]/`, with `rel="prev"`/`rel="next"` and a self-referential canonical per page.
   - **No page loads or filters the full dataset in the browser.** The only client-side data on any page is the search index (§4.7).
   - Every paginated page is crawlable and reachable with JS disabled.
   - The reference's homepage chooser, its client-side category filter and its manual-postcode near-me are not ported (§2.5).
7. **2026-08-06 decision — the search index is embedded at build time now, and fetched later.** The reference's build-time-embedded-JSON idiom (originally the map's, now its search's) is the right one at this dataset size, and the threshold at which it stops being right is recorded here so the change is planned rather than rediscovered.

   A trimmed per-producer index entry — slug, name, suburb, state, primary region, varieties — is roughly 150–250 bytes. At 150–300 producers that is **about 40–80 KB uncompressed**, in the tens of KB over the wire after compression, embedded once in `BaseLayout.astro` and matched in the browser with plain case- and accent-insensitive substring matching. No fuzzy-search library (§2.2). The index carries only what is matched or displayed in a result row; it is not `producers.json`.

   **Above roughly 500 published producers — `SEARCH_INDEX_INLINE_MAX` — this switches** to a static `/search-index.json` fetched on first interaction with the search field. That is the only sanctioned exception to §4.4's zero-fetch rule, it is not in force at v1, and it is not to be built pre-emptively. Search degrades to "browse by region" with JS disabled, at any index size.
8. **Aggregation pages carry a foreword** generated at Gate 6 into `forewords.json` and committed — prose about the region, not a stitched-together list of the producers below it.

---

## 5. Data Layer Requirements

**The architecture rule: published MDX frontmatter is the source of truth. `data/directory.db` is a disposable derived artefact.** It can be deleted at any moment and rebuilt exactly from `_published`. Nothing in this system treats the DB as authoritative, and no feature may store state there that cannot be reconstructed from published content.

- **Tables exactly as SCHEMA.md §3.** The DDL lives there and is not restated here. Note in particular §3's correction to the reference's pattern: `practices` and `logistics` are **1:1 wide boolean tables** (fixed closed key sets), while `regions`, `subregions`, `varieties`, `wine_styles` and `vessels` are **true `(slug, value)` row tables**. The reference's `facilities` table is the former shape and cannot hold an open-ended array; porting it to the latter five is the mistake to avoid.
- **Rebuild is always full, never incremental.** `data_store.rebuild()` recreates the schema and reloads every `_published` file. There is no patch path.
- **Rebuilding twice must be byte-identical**, for both the DB and the derived JSON (`/validate` check 3). This is a design constraint on how the writer is built, not a hope: deterministic ordering (`ORDER BY slug`, sorted array members), no timestamps or run IDs in output, JSON serialised with fixed separators and sorted keys and a trailing newline. A non-idempotent rebuild fails the check even when the diff against the committed artefacts is clean — it usually means a child-table rebuild is insert-only.
- **Upsert on slug for `producers`; delete-then-insert per slug for every child table.** Re-approving an edited producer updates in place. A variety removed from the frontmatter must disappear from `producer_varieties`, not linger. Unpublishing removes every row for that slug (`ON DELETE CASCADE`).
- **A corrupted `_published` file is skipped and logged, never fatal to the whole rebuild.** One bad file must not cost the other 299.
- **`admin/pipeline/data_store.py` is the sole owner** of `data/directory.db` and `site/src/data/producers.json`. No other module writes either. `python -m admin.pipeline.data_store --rebuild` does exactly this from the CLI.
- **`site/src/data/producers.json` carries only what pages and the search index need**, not a dump of the frontmatter. It is committed, because it is an input to the Netlify build. There is **no GeoJSON artefact** — the reference's is vestigial (written by the admin, read by no page) and this project has no map.
- **`verification` and `change_log` are not stored in SQLite** (SCHEMA.md §3) — rendered and metadata only, same posture as `verified`.
- **`data/ownership.json` is hand-maintained and is not derived from anything.** It is committed, it is read by `ownership.py`, and it is never written by a rebuild. Its shape is SCHEMA.md §4.3; every record carries a source and a date, and no label appears under two parents.
- **The repo history is the backup.** `directory.db` is committed, so any rebuild can be diffed against, and reverted to, a known-good state.

---

## 6. Admin App Requirements

**Implement UX.md §1 in full.** This section states the contract, not the interface; UX.md outranks it.

1. **A single-screen hub.** Harvest panel with a streaming log pane, review queue reading `content-staging/_staging/`, review pane, deploy strip — one screen, not a set of pages the reviewer navigates between. Reviewing 300 producers is the job the interface exists for; a click-per-producer navigation makes it a chore that gets abandoned at forty.
2. **Review pane**: rendered preview using the public site's actual built CSS, frontmatter editor with debounced autosave, toggle chips for the practice and logistics booleans, approve/reject with keyboard shortcuts, a 3-second undo that fully reverses an approve. Approve moves the file to `_published`, upserts the DB, regenerates the derived JSON. Reject moves it to `_rejected` with a reason sidecar. A schema-invalid staging file is blocked from approval with field-level errors.
3. **The independence flag is surfaced in the review pane, not buried in a log** (Gate 4). The verdict (`clear | check | reject`) and the underlying `ownership_signals` are both visible. **`check` never auto-publishes** (CLAUDE.md rule 8) — clearing it is a deliberate human action that records an `ownership_source`, and a producer cannot be approved without one.
4. **Every failure state in the UX.md §1.5 table** is implemented, including the empty states.
5. **The deploy strip** ports the reference's `deploy.py` unchanged in shape (Gate 7): a diff preview showing only legal paths; a tracked-file guard checking `git ls-files` (not `git status` — a force-added file shows clean in status) against the pathspecs `temp_data`, `content-staging`, `.env`, `.env.*`, with `.env.example` allowlisted; a pre-push `npm run build` gate that blocks the push on failure; the push; a Netlify build poll reporting ready/failed rather than stopping at "push ok"; an IndexNow ping. One deploy lock, so no two paths can race a push.

   **`ALLOWED_PREFIXES`** — the only paths a deploy may touch:
   `site/src/content/producers/_published/`, `site/public/images/`, `data/directory.db`, `data/ownership.json`, `site/src/data/producers.json`, `site/src/data/forewords.json`, `site/src/content/blog/_published/`, `site/public/blog-images/`, `data/factchecks/`.
6. **The image pipeline is UX.md §4 verbatim**: candidate images are staging-only, publishing an image is a separate deliberate action, one image maximum per producer, attribution mandatory (`image_source` and `image_caption` are zod co-requirements, SCHEMA.md §2a rule 1), one-click removal.
7. **Auth.** HTTP Basic Auth via `ADMIN_USERNAME`/`ADMIN_PASSWORD`; both blank means no prompt, which is the local-dev case only. **Credentials are mandatory whenever the app is reachable beyond localhost**, set as Fly secrets and never in a committed file. *(2026-08-06: the reference's TRD still describes its admin as "runs on localhost only" while its own Dockerfile and fly.toml deploy it publicly. That line is stale there and is not ported.)*
8. **The admin UI is user-facing copy.** Australian English, and subject to the same banned-word and register rules as the public site (CLAUDE.md).

---

## 7. AI Pipeline Requirements

### 7.1 The three agents

**Harvester → Architect → Gatekeeper**, in that order, one job at a time.

- **Harvester**: fetched page → one JSON object per **SCHEMA.md §5**. *(Note for anyone porting from the reference: its TRD cites "SCHEMA.md §4" for this; in this project §4 is the independence determination and the Harvester JSON is §5.)* Validated by `_validate_harvester_json` for parseability, object-ness and the presence of every key in `HARVESTER_REQUIRED_KEYS`. A single markdown fence is stripped rather than being allowed to burn the one re-ask on formatting.
- **Architect**: the harvested JSON → an MDX draft. It writes a documented profile from the record and **never claims a first-hand visit, never invents a tasting note, a price, a variety, a certification or a date not present in the JSON**. Anything uncertain is omitted, not guessed. This rule also appears inside `PROMPTS/architect.md`; it is enforced in both places, and CLAUDE.md rule 6 makes it non-negotiable.
- **Gatekeeper**: draft → polished Australian-English MDX. Enforces the banned-word list, the em-dash ban, the not-X-but-Y ban and the hedge-word ban. **Instructed to leave `verification` and `change_log` untouched** (SCHEMA.md §6).

### 7.2 Prompts

Loaded from `PROMPTS/*.md` **at call time, never embedded in Python source**. This is what makes the editorial guardrails editable without a code change and reviewable as text, and it is why `PROMPTS/` is a top-level directory rather than a package resource. A prompt string literal in a `.py` file is a defect.

### 7.3 Retry tiers

Two tiers, exactly as the reference's `agents.py`, and no more:

- **Transport tier** — `RateLimitError`, 5xx `APIStatusError`, `APIConnectionError`: **one** retry, logged to the pane with the reason (and `retry-after` where the header carries it), then `AgentError`. A sub-500 status error raises immediately; it will not fix itself.
- **Content tier** — output that fails the stage's `validate()` callable: **one** re-ask with the validation error appended to the original prompt and "return corrected output only", then `MalformedOutput` carrying the raw text, saved to `temp_data/failed/` with a log line.

The SDK client is constructed with `max_retries=0` so the mandated retry is ours and the operator sees it happen. **Token usage is logged per call** — input and output — and totalled per run.

### 7.4 The batch harvest queue (required, not optional)

At 150–300 producers, a one-URL-at-a-time harvest panel is not a workable instrument; the reference never needed one at 32 venues and does not have one. This is a new component.

- Accepts a pasted list of URLs or a file (SEED.md is the test corpus).
- **Strictly serial** — one job at a time. Not a concurrency limit dialled to one: politeness to the sites being read and a single shared Anthropic rate-limit budget both point the same way.
- **Per-URL isolation.** One URL's failure — fetch, parse, agent, schema — is logged against that URL and the run continues. A batch of ten with two bad URLs produces eight drafts.
- **Durable across an admin restart.** Queue state persists to `temp_data/harvest_queue.json` (gitignored, reconstructible, holds only URLs and per-URL status — never in `data/`, which `rebuild()` recreates).
- Pause, resume and cancel; per-URL status visible; per-URL and run-total token usage in the log.
- Re-harvest of an already-published producer runs through the same queue, and **upgrades confidence tiers, never downgrades them** (SCHEMA.md §1.11, §2b), computing `change_log` against the previous frontmatter.

### 7.5 The independence gate inside the pipeline

- The Harvester **extracts `ownership_signals` and emits `independence: clear | check | reject`. It never decides alone** (SCHEMA.md §4.5). Signals are extracted, not judged; ownership is never inferred from tone, in either direction.
- **Deny-list checks on name, domain and ABN run before a draft enters the queue** — before the Architect is called, so a portfolio-owned label costs one cheap call rather than three. A `reject` verdict **aborts before any draft is written**, with the reason logged.
- A `check` verdict writes the draft, flags it and blocks auto-publish (§6.3).
- The explicit reject categories are SCHEMA.md §4.4: pure retailers, restaurants, large corporate portfolio brands, and the highest-volume false positive — virtual brands and supermarket private labels, which have plausible standalone sites by design.

### 7.6 Supporting pipeline behaviour

- **Fetching**: httpx with a descriptive user agent, `robots.txt` respected, 20s timeout. **Playwright is a user-triggered per-URL fallback for JS-heavy sites only** and is never invoked automatically.
- **Geocoding**: Nominatim over httpx (`GEOCODER=nominatim`), disk-cached, 1 request per second, descriptive user agent. Coordinates come from here alone; when it is unset or fails, `latitude`/`longitude` stay null and the producer publishes anyway (SCHEMA.md §2).
- **Pipeline-owned fields** are stamped by `_finalize_frontmatter()` per SCHEMA.md §6 — including re-imposing the Harvester's `determinations` onto the certification, fruit-source, practice and variety fields, which is enforced rather than trusted to survive two rewrite passes.
- **API key from `.env` only**, never logged, never echoed into a draft or a log line.
- **Gate 11's editorial chain** (`article_brief` → `article_draft` + `house_voice` → `factcheck`) uses separately configurable model IDs and preserves the adversarial split: **the fact-checking model is deliberately not the drafting model reviewing itself.** Drafting models are poor judges of their own confabulation.

---

## 8. Out of Scope (v1)

Each item carries its rationale, because "we didn't build it" and "we decided not to build it" age very differently.

### 8.1 Deferred — reconsidered after coverage

**Producer claim flow.** No `/claim/[slug]` page, no claim form, no claim records, no `status`/`claimed` field (SCHEMA.md §2, "Fields deliberately absent"). *Rationale:* coverage and data quality come first, and a claim flow with no outreach behind it is a button nobody presses. It also sits badly against the "no sponsored listings" promise — a claim path is the shortest route from "free field guide" to "pay to control your entry", and once that door is open the independence claim starts to look purchasable. The v1 correction channel is a contact address and the methodology page.

**Stripe and any payment path.** No payment package, no webhook, no `claims.db`. *Rationale:* there is nothing to sell. The reference's Stripe path also created the single automatic push-to-live in that system (§2.4); not carrying the feature keeps the invariant that every write stops at "updated on disk" until a human clicks Deploy.

**Operator outreach.** No producer mailing, no notification pipeline, no SMTP wiring. *Rationale:* outreach before coverage is noise — there is nothing to show a producer yet, and a first contact that reads as a pitch is the wrong first contact for a project whose credibility rests on being unpaid. Revisit once the four seed regions read as complete. `smtplib` remains the named implementation when it happens; still no new dependency.

**Google Places discovery.** No `discovery.py`, no `GOOGLE_PLACES_API_KEY`. *Rationale:* a metered API requiring a Cloud billing account, for a job that at this scale is better done by hand — candidate URLs come from regional association registers, the four regions' own directories and SEED.md. Places would also surface, in rank order, exactly the corporate-owned cellar doors the independence rule then rejects, which is the worst possible cost-per-usable-candidate. Revisit only if manual seeding stalls before the coverage target.

### 8.2 Out of scope, structurally

**Per-wine and per-vintage pages, scores, ratings, price tracking, stockist lists.** *Rationale:* wines are attributes of a producer, not entities. A wine-level entity multiplies the dataset by roughly ten, is vintage-perishable in a way a producer profile is not, and invites exactly the tasting notes nobody on this project can honestly write (CLAUDE.md rule 6). It would also turn a field guide into a shopping index.

**Any hosted database, serverless function or runtime backend for the public site.** *Rationale:* the published site is static files. See §4.4.

**User accounts, authentication for visitors, user reviews and ratings.** *Rationale:* an account system is a moderation and privacy obligation with no editorial payoff here; the entries are documented from published sources, and a five-star average would misrepresent that.

**Public analytics.** No page-view analytics, no dashboards. *Rationale:* the reference's narrow GoatCounter exception tracked its "Book Now" button; there is no equivalent conversion here, no ads and no affiliate links, so there is nothing an analytics script could tell this project that would change a decision.

**Advertising, affiliate links, sponsored placement, paid ranking.** *Rationale:* the promise in §1. This one does not get an exception later.

**Maps, tiles, browser geolocation, distance sorting, drive-time.** *Rationale:* §2.5. Region is how people choose a winery to visit; kilometres are not.

**Image galleries.** One image maximum per producer, per UX.md §4.

**An events calendar** (cellar-door events, vintage festivals, tastings). *Rationale:* perishable data with a maintenance cadence this project does not have. It is the same reason `cellar_door_hours` is a freeform display string rather than a seven-day grid (SCHEMA.md §2).

**A newsletter, a native app, and any non-Australian producer.** *Rationale:* scope discipline. The guide is Australian and it is a website.

**A `low_intervention` field.** SCHEMA.md §1.6, and it outranks this document: the term has no agreed definition and no certification, flagging it means arbitrating it, and the site would be argued with from both directions. An editorial page composed from the four `PRACTICE_KEYS` facts is fine; a field on anyone's entry is not.

**Public site search is *not* in this list.** *(2026-08-06: divergence from the reference, which listed search as out of scope in its §8 and then reversed it by exception on 2026-07-25. That reversal is accepted up front here — at 150–300 producers a directory without search is a directory nobody can use — and search ships as a first-class requirement per §4.7, on the same terms: client-side only, no backend, no new dependency, no runtime fetching at v1's index size.)*

---

## 9. Execution

Build proceeds through **the gates defined in CLAUDE.md, in order**, stopping at each gate for verification. They are not restated here; CLAUDE.md is the process document and duplicating its done-conditions would create a second, drifting copy. Do not begin a gate before the previous gate's done-condition passes and the work has been explicitly approved.

Read CLAUDE.md, SCHEMA.md, UX.md and DESIGN.md before writing any code. `/validate` (`.claude/commands/validate.md`) must pass clean before any gate is declared done and before any deploy; each new check lands as its own commit, right after the feature it guards.

**Two documentation habits, ported from the reference and in force in this document.**

- **Dated exceptions are recorded inline**, in the section they affect, in the form `2026-08-06 exception: …`, with what was approved, what the no-dependency or no-change alternative was, and why it was rejected. A decision whose reasoning is not written down gets re-litigated by the next session at full cost.
- **Superseded text is annotated in place with a date, never deleted.** A struck line with a note is history; a deleted line is a mystery.

**2026-08-06.** This document is authored at Wave 1, before any code exists. CLAUDE.md and SCHEMA.md are frozen and outrank it in their domains. The reference build at `/home/dhynesmnk/Bathers'/` is read-only; its known stale spots are catalogued in CLAUDE.md and should be checked against before copying any of its text.
