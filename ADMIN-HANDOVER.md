# Admin handover

*Written 2026-08-13, after the Gate 11 review sweep. Operational, not specification: TRD.md and UX.md remain the authority on what the admin does and why.*

**No secret value appears in this document.** Key *names* are listed; values live in `.env`, which is gitignored and must never be committed, printed, or echoed into a log (CLAUDE.md rule 5).

---

## 1. Read this first — the admin currently has no login

`ADMIN_USERNAME` and `ADMIN_PASSWORD` are both **present and empty** in `.env`.

`require_auth` in `admin/app.py` treats that as a deliberate state:

> Both blank means no prompt, which is the local-dev case only.

So today the admin serves **every route to anyone who can reach the port**, with no credential prompt. That is fine while it is bound to localhost and is what makes `uvicorn … --reload` pleasant to work with. It is **not** safe the moment the port is reachable from anywhere else — a tunnel, a LAN address, a `--host 0.0.0.0`, or the Fly container.

Everything behind that port is consequential: it approves producers into `_published`, publishes blog posts, spends Anthropic tokens, and pushes to git.

**Before exposing it anywhere, set both keys.** They are compared with `hmac.compare_digest`, so partial credentials fail closed; setting only one is not a valid state and will lock you out rather than half-protect you.

Two related notes:

- `GITHUB_PAT` is also empty, so the deploy strip's push will fail at the last step. Diff preview, the tracked-file guard and the pre-push build all run without it.
- `INDEXNOW_KEY` is set. The key file is generated at build time into `dist/` and never committed (the 2026-08-09 engagement records why).

---

## 2. Running it

```bash
# from the repository root
uvicorn admin.app:app --reload --port 8787
```

`ADMIN_PORT` defaults to `8787`. `uvicorn` binds `127.0.0.1` unless told otherwise — leave it that way unless section 1 is resolved.

**Use `.venv/bin/python` for anything validation-shaped.** Under the system interpreter, check 16 cannot import Playwright, reports `PARTIAL` and exits 0 — the suite looks green while its browser layer has never run. That trap has now fired three times by three different routes. **Read `PARTIAL` as "not verified", every time.**

```bash
.venv/bin/python -m admin.pipeline.validate_render     # check 16, ~25 min
cd site && npm run build                                # must be zero-warning
python -m admin.pipeline.data_store --rebuild           # DB + derived JSON
```

**Do not run `npm run build` while check 16 is running.** Astro empties `dist/` on build, and the check reads it — that produces a page of confident, meaningless 404 failures.

---

## 3. The two screens

### `/` — the producer hub (UX.md §1)

One screen, three columns: harvest panel with the log pane, review queue reading `content-staging/_staging/`, review pane with a rendered preview and the frontmatter editor. Keyboard-driven: the session UX.md §5 describes is arrow-down the queue, read the ownership panel first, `A` to approve, `R` to reject with a reason.

Approve moves the file to `_published`, upserts SQLite, regenerates the derived JSON, and opens a 3-second undo window. Nothing else writes to `_published`.

### `/blog` — the journal (UX.md §6)

Post list plus editor plus live preview. Two ways to start a post:

1. **Start draft** — a working title, then write it yourself.
2. **Brief, draft, house voice** — the editorial chain on a topic. Three model calls; it returns immediately and streams into the same log pane.

Then **Fact-check** as a separate action, on a different model. That split is the point of the gate and is recorded in the audit file, not just asserted: every audit carries `drafted_by` and `model`, and stamps `self_review: true` if they ever match.

**Publish is a gate, not a button.** It is blocked while any claim is unresolved, any of title/summary/dateline is missing, `sources` is empty, the audit is missing, or a claim the fact-check removed has its text back in the body. Every block names its own cause on screen.

Editing an already-published post saves in place and stamps `updated`, which renders as `Amended …`. Deleting a published post is not offered.

---

## 4. State on disk

| Path | What it is | Committed? |
|---|---|---|
| `site/src/content/producers/_published/` | Published producers | yes |
| `site/src/content/blog/_published/` | Published posts | yes |
| `data/factchecks/` | Claim audits | yes |
| `data/ownership.json` | The deny-list register | yes |
| `data/directory.db`, `site/src/data/producers.json` | Derived, rebuildable | yes |
| `site/public/images/`, `site/public/blog-images/` | Published imagery | yes |
| `content-staging/` | Queue, drafts, determinations, blog staging | **no** |
| `temp_data/` | Harvest queue, failed outputs, caches | **no** |

`content-staging/` and `temp_data/` are volume state. The deploy guard reads `git ls-files` rather than `git status` precisely because a force-added file under a gitignored path shows a clean tree forever.

**Never edit `_published` by hand, and never touch `temp_data/` manually.** The one sanctioned exception is the blog editor saving a published post, which is the author editing their own live post through the screen built for it.

---

## 5. Environment keys

Names only. `.env.example` documents each one in full; `docker-entrypoint.sh` materialises the same key set from Fly secrets, so **adding a key means adding it there too** or production silently falls back to a default.

| Group | Keys |
|---|---|
| Anthropic | `ANTHROPIC_API_KEY` |
| Models | `MODEL_HARVESTER`, `MODEL_ARCHITECT`, `MODEL_GATEKEEPER`, `MODEL_FOREWORD`, `MODEL_ARTICLE`, `MODEL_BRIEF`, `MODEL_FACTCHECK` |
| Admin | `ADMIN_PORT`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` |
| Site | `SITE_URL` |
| Deploy | `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`, `INDEXNOW_KEY`, `GITHUB_PAT` |
| Geocoding | `GEOCODER`, `GEOCODER_USER_AGENT` |

Model IDs are **never hardcoded in source**; changing a model is a config change. The defaults cascade, so overriding one still yields valid IDs everywhere — `MODEL_FOREWORD` is absent from the live `.env` and correctly falls back to `MODEL_ARCHITECT`.

**`MODEL_FACTCHECK` must differ from `MODEL_ARTICLE`.** If they collapse, the chain still runs, warns loudly, and writes `self_review: true` into the audit — an audit that says plainly it is worth less than it looks.

Two constants are **not** in `.env`: `SITE_NAME` and `SITE_CONTACT_EMAIL`. They are decisions recorded in `site/src/config.ts`. `SITE_NAME` is mirrored in `admin/config.py` and diffed by check 13. `SITE_URL` **is** env-driven and is deliberately *not* diffed — comparing the literal would pass on a machine whose live value differs, which is a known open gap.

---

## 6. Deploying

`/` → the deploy strip. Diff preview first, and read it: only legal paths may appear. The tracked-file guard, the pre-push `npm run build` gate, the Netlify poll and the IndexNow ping all run from there.

**Every write in this system stops at "updated on disk" until a human clicks Deploy.** There is no automatic push path and none is to be added.

Run the full suite before deploying. `/validate` is the gate-exit test and the pre-deploy test, and it is the same command.

---

## 7. Where the traps are

Five things that have each cost real time on this build:

1. **`PARTIAL` is not a pass.** Section 2. It has caught people out three times.
2. **The interpreter is load-bearing.** `.venv/bin/python`, not the system one.
3. **`git status` lies about force-added files.** The deploy guard reads the index for this reason; do not "simplify" it.
4. **A check that has never failed may be unable to fail.** Three checks here were blind to the exact defect they were best placed to catch. When a check has been green forever, test that it can go red.
5. **The editorial lint does not read Astro copy.** Check 6 lints `_published` bodies, post bodies and `METHODOLOGY.md`. It does **not** lint component strings, `llms.txt`'s paragraphs, or any admin UI text — and that is the largest known gap in the build. Reader-facing prose written in a `.astro` or `.ts` file is unguarded.

---

## 8. If something looks wrong

- **Suite green but the page looks wrong** → look at the page. Three defects here were found by screenshot and one by driving a file picker, none by a check.
- **A stage fails with "not valid JSON"** → check whether it is truncation first; `agents._truncated` diagnoses a `max_tokens` stop before validation, and the ledger now records what a failed call spent.
- **A producer will not approve** → read the ownership panel. `check` never auto-publishes, and a deny-list hit is never publishable as `unconfirmed`.
- **A post will not publish** → the screen lists every reason. There is no hidden one.
