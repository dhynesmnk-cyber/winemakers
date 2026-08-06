# Independent Winemakers Directory — Build Package

A field guide to independent Australian winemakers. Free to use, no ads, no sponsored listings.

This repository is a build package, not a finished product. The specification documents are complete and frozen; the code is built through the gates in `CLAUDE.md`, in order.

## Feed order for Claude Code

1. **Clone or drop this folder into an empty repo root**, including `.claude/` and `.env.example`. The `.claude/` directory carries the skills, the durable subagents and the `/validate` command — they are committed deliverables, not session state, and the build depends on them existing before Gate 1 opens.

2. **Copy the environment file** and fill it in:
   ```bash
   cp .env.example .env
   ```
   Only `ANTHROPIC_API_KEY`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` are needed to reach Gate 5. Everything else has a working default or degrades in a documented way.

3. **Open Claude Code and say:**
   > Read CLAUDE.md, SCHEMA.md, TRD.md, UX.md and DESIGN.md, then begin Gate 1.

4. **Verify each gate's done-condition before approving the next.** Run `/validate`, and actually exercise the deliberately-corrupted-fixture conditions rather than reading past them. The `gate-exit` skill walks the procedure. A gate that closes without its fixture being seen to fail has not been tested.

## Where the truth lives

Five documents, and a precedence order that resolves conflicts between them.

| Document | Governs | Precedence |
|---|---|---|
| `CLAUDE.md` | *How* you work — prime rules, the gate sequence, working style | Rules 6 and 7 are non-negotiable |
| `SCHEMA.md` | The producer data contract — vocabularies, frontmatter, DDL, the independence determination | **Outranks TRD.md for data** |
| `TRD.md` | Stack, repo structure, requirements per layer, out-of-scope decisions | |
| `UX.md` | Behaviour — admin hub, public site, failure states | **Outranks TRD.md for interface** |
| `DESIGN.md` | Visual specification — tokens, type, layout grammar, icon system | **Outranks TRD.md for interface** |

Flag any conflict you find either way, even when the precedence rule resolves it. A conflict that gets silently resolved is a spec bug that comes back.

## File map

```
CLAUDE.md ................ operating instructions, prime rules, gates G1–G11
SCHEMA.md ................ the data contract — four consumers, one vocabulary
TRD.md ................... technical requirements, fixed stack, out of scope
UX.md .................... behavioural specification
DESIGN.md ................ visual specification
SEED.md .................. Gate 5 fixture producers, one per failure mode
README.md ................ this file
.env.example ............. environment contract, one block per concern

.claude/
  commands/validate.md ... the gate-exit suite; report-only, never fixes
  skills/
    schema-change/ ....... four-consumer propagation (the highest-value skill)
    gate-exit/ ........... how a gate actually closes
  agents/
    schema-guardian.md ... read-only drift audit across the schema surfaces
```

Authored as the build proceeds, at the gate that needs them: `.claude/skills/ownership-check/` and `.claude/agents/data-curator.md` (Wave 2), `.claude/skills/producer-entry/` and `.claude/agents/design-reviewer.md` (Gate 1), `.claude/agents/content-auditor.md` (Gate 5).

## The two rules that matter most

**The honesty rule.** Entries are documented from published sources. No fabricated visit, no invented tasting note, no first-hand sensory claim. Nobody on this project has visited these cellar doors or tasted these wines. It is the reason the directory can be trusted at all, and it applies to the blog, the comparison pages and the admin UI exactly as it applies to a producer entry.

**One contract, four consumers.** Any vocabulary change — a field, an enum value, a validator — lands in the zod schema, the SQLite DDL, the Harvester JSON validator and the admin frontmatter editor *in the same commit*, name-matched. This is the highest-risk-if-broken invariant in the build.

## Independence

The word doing the work is **independent**. It is the inclusion criterion, the editorial position, and the reason the site exists.

The rule is strict: **any corporate ownership blocks publication**, including minority stakes and multi-label family groups. `parent_company: null` is the only publishable value. This is stricter than the trade's ordinary use of the word, which is why the methodology page must define the term as this site uses it rather than relying on a reader's assumption.

Independence is an ownership fact and is never inferred from prose. Corporate portfolio brands are engineered to read as small and independent — that is their design brief — and a genuinely independent producer with a thin website may read as corporate. The determination runs off `data/ownership.json` and extracted ownership signals, never a tone judgement. See `SCHEMA.md` §4.

## The reference build

`/home/dhynesmnk/Bathers'/` is a mature, live build of this same architecture for a different domain. It is the worked example, and it is **read-only** — nothing here writes to it. The folder name contains an apostrophe, so quote every path that touches it:

```bash
ls "/home/dhynesmnk/Bathers'/admin/pipeline"
```

Do not copy its text blindly. `CLAUDE.md` catalogues its known stale spots.
