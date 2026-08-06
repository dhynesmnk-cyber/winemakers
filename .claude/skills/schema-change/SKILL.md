---
name: schema-change
description: Propagation procedure for any change to the producer data contract. Use whenever adding, renaming, removing or retyping a frontmatter field, adding or removing an enum value, or editing a validator or refinement. Also use when reviewing a diff that touches site/src/content/config.ts, admin/pipeline/data_store.py, admin/pipeline/orchestrator.py, admin/schema.py, site/src/config.ts or admin/config.py.
---

# Schema change — the four-consumer propagation

CLAUDE.md rule 7 is non-negotiable: **one contract, four consumers, same commit, name-matched.** This is the highest-risk-if-broken invariant in the build. A field that lands in the zod schema but not the admin validator validates in one layer and silently fails in another, and the failure surfaces days later as a corrupted publish.

SCHEMA.md is the source of truth. It outranks TRD.md for data (CLAUDE.md rule 3). If SCHEMA.md doesn't describe the change yet, **update SCHEMA.md first** — it is consumer zero.

## The four consumers

Every one of these must be updated in the same commit. No exceptions, no follow-up commits.

| # | Surface | File | What changes |
|---|---|---|---|
| 0 | The contract | `SCHEMA.md` | The §2 frontmatter table row; any §1 vocabulary tuple; any §2a cross-field rule |
| 1 | zod schema | `site/src/content/config.ts` | The field's zod type, optionality, and any `.refine()`/`.superRefine()` |
| 2 | SQLite DDL | `admin/pipeline/data_store.py` | `SCHEMA_SQL` column or child table, plus the upsert and the scalar-column tuple |
| 3 | Harvester validator | `admin/pipeline/orchestrator.py` | `HARVESTER_REQUIRED_KEYS` and `_validate_harvester_json`, if the field is Harvester-sourced |
| 4 | Admin editor | `admin/schema.py` | `KNOWN_FIELDS` and the field's validation branch |

Two more surfaces exist and drift silently because they are hand-copies:

- `site/src/config.ts` **and** `admin/config.py` — the hand-mirrored enum pair. Any vocabulary change touches **both**. They are not generated from each other; nothing but discipline keeps them in step.
- `admin/mdx_preview.py` — a third independent copy of labels and icon paths, because Python/Jinja cannot import the TypeScript module.

## Procedure

1. **Update `SCHEMA.md` first.** The §2 table row, and the §1 tuple if it's an enum. State the type, whether it's required, and the rule.
2. **Decide the storage shape.** Scalars and flattened object members become columns on `producers`. A fixed closed set of booleans becomes a 1:1 wide table (`practices`, `logistics`). **An array becomes a true `(slug, value)` child row table** — never a wide table, never a delimited string. See SCHEMA.md §3.
3. **Update all four consumers in one edit pass**, before running anything.
4. **Update both config files** if a vocabulary tuple moved. Check `mdx_preview.py` too.
5. **Run the surface diff:** `python3 -m admin.pipeline.schema_surfaces` — it must exit 0.
6. **Rebuild and check idempotency:** `python -m admin.pipeline.data_store --rebuild`, twice. Byte-identical, or the child-table rebuild isn't delete-then-insert.
7. **Prove the new constraint bites.** Write a fixture that violates it, confirm the build or the validator fails with a clear field-level error, then restore. A constraint you have not seen fail has not been verified.
8. **Run `/validate`.** Checks 1, 3 and 13 are the ones this procedure targets.
9. **Commit all of it together**, imperative message, gate-prefixed.

## Naming

Names must match **exactly** across surfaces — `schema_surfaces.py` compares them as strings, and a near-synonym is a failure, not a nicety. The DDL is the one permitted divergence: nested objects are flattened, so `tasting_fee.fee_aud` becomes the column `tasting_fee_aud`. Flattened columns are checked against `data_store`'s scalar-column tuple rather than against the field name.

## Never

- Never write an enum literal inline. Build the zod sub-schema from the `as const` tuple so adding a key to the tuple carries the schema with it (SCHEMA.md §8).
- Never add a field to zod "for now" and wire the rest later. That is the exact failure mode rule 7 exists to prevent.
- Never store an array as a delimited string to avoid writing a child table.
- Never add `low_intervention`, or any field whose value the site would have to arbitrate rather than source. See SCHEMA.md §1.6.
- Never widen a field to make a stubborn producer fit. Ask.

## When the change touches the independence contract

`parent_company`, `ownership_source` and anything in `data/ownership.json` are load-bearing for the site's editorial position, not merely data. Any change there also updates the methodology page and `/validate` check 8, and needs explicit user sign-off before it lands. Load the `ownership-check` skill.
