"""schema_surfaces.py — `/validate` check 13. Gate 2.

**The four-surface schema diff.** CLAUDE.md rule 7 says any vocabulary change
lands in all four consumers in the same commit, name-matched, and calls it the
highest-risk-if-broken invariant in the build. This module is the thing that
makes that rule enforceable rather than merely written down.

The failure it exists to catch is quiet, not loud: a field added to the zod
schema but not the DDL validates at build time and then silently fails to reach
SQLite, so the producer pages render it and every aggregation page behaves as
though nobody has it. Nothing errors. The site is just wrong.

── The surfaces ──────────────────────────────────────────────────────────────

    1. the zod schema             site/src/content/config.ts        Gate 1
    2. the SQLite DDL             admin/pipeline/data_store.py      Gate 2
    3. the Harvester validator    admin/pipeline/orchestrator.py    Gate 5
    4. the admin editor           admin/schema.py                   Gate 3

plus two that are not consumers but are where the contract is *written down*:
SCHEMA.md §2's frontmatter table, and the hand-mirrored `config.ts`/`config.py`
vocabulary pair.

**A surface whose gate has not shipped is reported as pending, not passed.**
The alternative — treating an absent file as agreement — would let this check
report clean for three more gates and then start failing on work that was
already wrong when it landed. Every run prints which surfaces it compared and
which it is still waiting for, so the count is visible at every gate exit.

── The disposition table ─────────────────────────────────────────────────────

The zod↔DDL comparison cannot be a set diff: the two surfaces are deliberately
not the same shape. `location` is one zod object and five DDL columns;
`practices` is one zod object and a 1:1 wide table; `verification` is in zod and
in no table at all. So every frontmatter field carries an explicit **declared
disposition** in `FIELD_DISPOSITION` below, and the check asserts that
disposition holds.

That is what makes a new field fail rather than pass: a field added to zod with
no entry here is an undeclared field, and an undeclared field is exactly the
drift this check is looking for. Adding the entry is a deliberate act that
forces the author to say where the data goes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin import config as py_config  # noqa: E402
from admin.config import ROOT  # noqa: E402
from admin.pipeline import data_store  # noqa: E402

ZOD_SCHEMA_PATH = ROOT / "site" / "src" / "content" / "config.ts"
CONFIG_TS_PATH = ROOT / "site" / "src" / "config.ts"
GLOSSARY_TS_PATH = ROOT / "site" / "src" / "data" / "glossary.ts"

#: Surfaces that land at a later gate. Reported as pending, never as agreement.
PENDING_SURFACES = {
    "admin/schema.py": ("KNOWN_FIELDS, the admin frontmatter editor", 3),
    "admin/mdx_preview.py": ("the review-pane preview", 3),
    "admin/pipeline/orchestrator.py": ("the Harvester JSON validator", 5),
    "PROMPTS/architect.md": ("the Architect prompt", 5),
    "PROMPTS/gatekeeper.md": ("the Gatekeeper prompt", 5),
}


# =============================================================================
# 1. Where every frontmatter field goes
# =============================================================================

#: field -> ("column", db column) | ("flattened", (columns…)) | ("child_table",
#: table) | ("wide_table", table) | ("rendered_only", reason)
#:
#: SCHEMA.md §3 is the authority for every entry. `rendered_only` is a claim
#: that SCHEMA.md makes explicitly, not a place to park a field somebody could
#: not be bothered storing.
FIELD_DISPOSITION: dict[str, tuple[str, object]] = {
    "name": ("column", "name"),
    "parent_company": ("column", "parent_company"),
    "ownership_source": (
        "flattened",
        ("ownership_source", "ownership_source_method", "ownership_source_date"),
    ),
    "category": ("column", "category"),
    "founded_year": ("column", "founded_year"),
    "website": ("column", "website"),
    "location": ("flattened", ("address", "suburb", "state", "latitude", "longitude")),
    "regions": ("child_table", "producer_regions"),
    "primary_region": ("column", "primary_region"),
    "subregions": ("child_table", "producer_subregions"),
    "cellar_door": ("column", "cellar_door"),
    "cellar_door_hours": ("column", "cellar_door_hours"),
    "cost": ("column", "cost"),
    "tasting_fee": (
        "flattened",
        ("tasting_fee_aud", "tasting_fee_waived_on_purchase"),
    ),
    "minimum_age": ("column", "minimum_age"),
    "organic": ("column", "organic"),
    "organic_certifier": ("column", "organic_certifier"),
    "biodynamic": ("column", "biodynamic"),
    "biodynamic_certifier": ("column", "biodynamic_certifier"),
    "fruit_source": ("column", "fruit_source"),
    "practices": ("wide_table", "practices"),
    "vessels": ("child_table", "producer_vessels"),
    "varieties": ("child_table", "producer_varieties"),
    "wine_styles": ("child_table", "producer_wine_styles"),
    "production_band": ("column", "production_band"),
    "annual_production_cases": ("column", "annual_production_cases"),
    "buy_online": ("column", "buy_online"),
    "ships_nationally": ("column", "ships_nationally"),
    "shop_url": ("column", "shop_url"),
    "logistics": ("wide_table", "logistics"),
    "summary": ("column", "summary"),
    # `has_image` is a derived flag, not the path. SCHEMA.md §3 stores whether
    # there is a photograph, not which one.
    "image": ("column", "has_image"),
    "verification": ("rendered_only", "SCHEMA.md §3: not stored in SQLite"),
    "change_log": ("rendered_only", "SCHEMA.md §3: not stored in SQLite"),
    "drafted": ("rendered_only", "SCHEMA.md §3: metadata, same posture as verified"),
    "verified": ("rendered_only", "SCHEMA.md §3: metadata, not stored"),
    "source_url": ("rendered_only", "SCHEMA.md §3: metadata, rendered as the citation"),
    "image_source": ("rendered_only", "SCHEMA.md §2a rule 1: attribution, rendered"),
    "image_caption": ("rendered_only", "SCHEMA.md §2a rule 1: attribution, rendered"),
    "faq": ("rendered_only", "SCHEMA.md §2: renders as FAQPage, not queried"),
}


# =============================================================================
# 2. Reading each surface
# =============================================================================


def _schema_md_fields() -> set[str]:
    """The field names in SCHEMA.md §2's frontmatter table."""
    text = (ROOT / "SCHEMA.md").read_text(encoding="utf-8")
    section = text.split("## 2. MDX Frontmatter", 1)[-1].split("### Fields deliberately absent", 1)[0]
    return set(re.findall(r"^\| `(\w+)`", section, re.MULTILINE))


def _zod_fields() -> set[str]:
    """Top-level keys of `producerFrontmatter`'s object literal.

    Bounded to that one block: the sub-schemas above it (`locationSchema` and
    friends) indent their keys identically, and `.superRefine()` below it
    contains `path:`/`message:` keys that are not fields.
    """
    text = ZOD_SCHEMA_PATH.read_text(encoding="utf-8")
    block = text.split("const producerFrontmatter = z", 1)[-1].split("\n  .strict()", 1)[0]
    return set(
        re.findall(
            r"^    (\w+):\s*(?:z\b|enumOf\(|uniqueArray\(|\w+Schema\b)",
            block,
            re.MULTILINE,
        )
    )


def _ddl_tables() -> dict[str, list[str]]:
    """`{table: [columns]}` parsed out of the DDL data_store actually executes."""
    tables: dict[str, list[str]] = {}
    for match in re.finditer(
        r"CREATE TABLE (\w+)\s*\((.*?)\n\);", data_store.SCHEMA_SQL, re.DOTALL
    ):
        table, body = match.group(1), match.group(2)
        columns = []
        for line in body.splitlines():
            line = line.split("--", 1)[0].strip()
            column = re.match(r"^(\w+)\s+(TEXT|INTEGER|REAL)\b", line)
            if column:
                columns.append(column.group(1))
        tables[table] = columns
    return tables


def _ts_tuple(text: str, name: str) -> list[str] | None:
    """A `export const NAME = [...] as const;` string tuple from a .ts file."""
    match = re.search(
        rf"export const {name}(?::[^=]+)? = \[(.*?)\]\s*as const;", text, re.DOTALL
    )
    if not match:
        return None
    return re.findall(r'"([^"]+)"', match.group(1))


def _variety_slugs_from_glossary() -> list[str]:
    """`VARIETY_SLUGS` as `glossary.ts` defines it: variety entries, in order.

    `config.ts` derives `VARIETY_KEYS` from this rather than retyping it, so the
    glossary is the authority. `admin/config.py` cannot import TypeScript and
    carries the list literally, which is the copy that drifts and the reason
    this comparison exists.
    """
    text = GLOSSARY_TS_PATH.read_text(encoding="utf-8")
    return re.findall(r'vocabulary:\s*"variety",\s*\n\s*value:\s*"([^"]+)"', text)


# =============================================================================
# 3. The comparisons
# =============================================================================


def _compare_field_sets(failures: list[str], pending: list[str]) -> None:
    """zod ↔ SCHEMA.md §2 table, and zod ↔ the admin editor once it exists."""
    zod = _zod_fields()
    if not zod:
        failures.append(
            "the zod schema surface parsed as empty — producerFrontmatter's block "
            "was not found in site/src/content/config.ts"
        )
        return

    schema_md = _schema_md_fields()
    only_zod = zod - schema_md
    only_table = schema_md - zod
    if only_zod:
        failures.append(
            f"fields in the zod schema but not SCHEMA.md §2's table: "
            f"{', '.join(sorted(only_zod))}"
        )
    if only_table:
        failures.append(
            f"fields in SCHEMA.md §2's table but not the zod schema: "
            f"{', '.join(sorted(only_table))}"
        )

    admin_schema = ROOT / "admin" / "schema.py"
    if admin_schema.is_file():
        text = admin_schema.read_text(encoding="utf-8")
        match = re.search(r"KNOWN_FIELDS\s*[:=].*?[\(\[\{](.*?)[\)\]\}]", text, re.DOTALL)
        known = set(re.findall(r'"([^"]+)"', match.group(1))) if match else set()
        if not known:
            failures.append("admin/schema.py exists but KNOWN_FIELDS did not parse")
        else:
            only_zod = zod - known
            only_admin = known - zod
            if only_zod:
                failures.append(
                    f"fields in the zod schema but not admin KNOWN_FIELDS: "
                    f"{', '.join(sorted(only_zod))}"
                )
            if only_admin:
                failures.append(
                    f"fields in admin KNOWN_FIELDS but not the zod schema: "
                    f"{', '.join(sorted(only_admin))}"
                )
    else:
        pending.append("admin/schema.py — KNOWN_FIELDS, the admin frontmatter editor (Gate 3)")


def _compare_storage(failures: list[str]) -> None:
    """Every zod field has a declared disposition, and that disposition holds."""
    zod = _zod_fields()
    tables = _ddl_tables()
    producer_columns = set(tables.get("producers", ()))

    undeclared = zod - set(FIELD_DISPOSITION)
    if undeclared:
        failures.append(
            f"frontmatter field(s) with no declared disposition in "
            f"schema_surfaces.FIELD_DISPOSITION: {', '.join(sorted(undeclared))}. "
            f"Say where the data goes — a column, a flattened set, a child table, "
            f"a wide table, or rendered-only with the SCHEMA.md reason."
        )
    stale = set(FIELD_DISPOSITION) - zod
    if stale:
        failures.append(
            f"FIELD_DISPOSITION names field(s) the zod schema no longer has: "
            f"{', '.join(sorted(stale))}"
        )

    for field, (kind, target) in sorted(FIELD_DISPOSITION.items()):
        if field not in zod:
            continue
        if kind == "column":
            if target not in producer_columns:
                failures.append(
                    f"{field}: declared as producers.{target}, which the DDL has no column for"
                )
        elif kind == "flattened":
            missing = [column for column in target if column not in producer_columns]  # type: ignore[union-attr]
            if missing:
                failures.append(
                    f"{field}: declared as flattened into {', '.join(missing)}, "
                    f"which the DDL has no column(s) for"
                )
        elif kind in ("child_table", "wide_table"):
            if target not in tables:
                failures.append(f"{field}: declared as table {target}, which the DDL does not create")

    # Every array field in the contract must have a child table. This is
    # SCHEMA.md §3's correction to the handover: an open-ended array cannot live
    # in a 1:1 wide boolean table, and porting the reference's `facilities`
    # shape to these five is the named mistake to avoid.
    for field, (kind, target) in FIELD_DISPOSITION.items():
        if kind != "child_table":
            continue
        if field not in data_store.ARRAY_FIELD_TABLES:
            failures.append(
                f"{field}: has a child table in the DDL but no entry in "
                f"data_store.ARRAY_FIELD_TABLES, so the rebuild never writes it"
            )
            continue
        table, _column = data_store.ARRAY_FIELD_TABLES[field]
        if table != target:
            failures.append(
                f"{field}: FIELD_DISPOSITION says {target}, ARRAY_FIELD_TABLES says {table}"
            )
    for field in data_store.ARRAY_FIELD_TABLES:
        if FIELD_DISPOSITION.get(field, ("", ""))[0] != "child_table":
            failures.append(
                f"{field}: data_store writes a child table for it, but "
                f"FIELD_DISPOSITION does not declare it as one"
            )

    # The DDL and the upsert must agree in both directions, or the rebuild
    # writes a column that does not exist, or leaves one silently NULL forever.
    for column in data_store.PRODUCER_SCALAR_COLUMNS:
        if column not in producer_columns:
            failures.append(f"the DDL has no column '{column}', which the upsert writes")
    for column in producer_columns:
        if column != "slug" and column not in data_store.PRODUCER_SCALAR_COLUMNS:
            failures.append(
                f"producers.{column} exists in the DDL but the upsert never writes it"
            )

    # The wide boolean tables carry exactly their closed key set.
    for table, keys in (
        ("practices", py_config.PRACTICE_KEYS),
        ("logistics", py_config.LOGISTICS_KEYS),
    ):
        columns = [column for column in tables.get(table, ()) if column != "slug"]
        if columns != list(keys):
            failures.append(
                f"the {table} table's columns {columns} are not the SCHEMA.md §1 "
                f"key set {list(keys)}, in order"
            )


def _compare_config_pair(failures: list[str]) -> None:
    """`site/src/config.ts` ↔ `admin/config.py`: same names, same order, members.

    Nothing generates one from the other. The mirror is held by discipline, and
    this is the check that notices when discipline lapses. A near-synonym is a
    failure, not a nuance.
    """
    text = CONFIG_TS_PATH.read_text(encoding="utf-8")
    for name in (
        "CATEGORIES",
        "CELLAR_DOOR_STATES",
        "CERTIFICATION_STATES",
        "FRUIT_SOURCE",
        "PRODUCTION_BANDS",
        "PRACTICE_KEYS",
        "LOGISTICS_KEYS",
        "VESSEL_KEYS",
        "WINE_STYLE_KEYS",
        "CONFIDENCE_TIERS",
        "VERIFIABLE_FIELDS",
        "OWNERSHIP_EVIDENCE_METHODS",
        "STATES",
        "COVERAGE_REGIONS",
    ):
        ts_values = _ts_tuple(text, name)
        py_values = getattr(py_config, name, None)
        if py_values is None:
            failures.append(f"{name}: present in config.ts, absent from admin/config.py")
            continue
        if ts_values is None:
            failures.append(f"{name}: present in admin/config.py, not parsed from config.ts")
            continue
        if ts_values != list(py_values):
            failures.append(
                f"{name}: config.ts and admin/config.py disagree.\n"
                f"      config.ts: {ts_values}\n"
                f"      config.py: {list(py_values)}"
            )

    # VARIETY_KEYS is the copy that drifts: config.ts derives it from
    # glossary.ts, and Python cannot import a TypeScript module, so
    # admin/config.py carries all 58 slugs literally.
    glossary_values = _variety_slugs_from_glossary()
    if not glossary_values:
        failures.append("VARIETY_KEYS: no variety entries parsed from glossary.ts")
    elif glossary_values != list(py_config.VARIETY_KEYS):
        only_glossary = [v for v in glossary_values if v not in py_config.VARIETY_KEYS]
        only_python = [v for v in py_config.VARIETY_KEYS if v not in glossary_values]
        detail = []
        if only_glossary:
            detail.append(f"in glossary.ts only: {', '.join(only_glossary)}")
        if only_python:
            detail.append(f"in admin/config.py only: {', '.join(only_python)}")
        if not detail:
            detail.append("same members, different order")
        failures.append(
            "VARIETY_KEYS: glossary.ts and admin/config.py disagree — " + "; ".join(detail)
        )


def run() -> tuple[list[str], list[str]]:
    """Returns (failures, pending surfaces)."""
    failures: list[str] = []
    pending: list[str] = []

    _compare_field_sets(failures, pending)
    _compare_storage(failures)
    _compare_config_pair(failures)

    for relative, (what, gate) in sorted(PENDING_SURFACES.items()):
        if relative == "admin/schema.py":
            continue  # reported by _compare_field_sets, which reads it
        if not (ROOT / relative).is_file():
            pending.append(f"{relative} — {what} (Gate {gate})")

    return failures, pending


# =============================================================================
# The self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one.

    Each surface reader is fed a deliberately drifted copy of the real text, and
    must report the drift. A parser that silently returns an empty set agrees
    with everything, which is the failure mode this check would be worst at
    noticing on its own.
    """
    errors: list[str] = []

    # Every reader must return something. An empty surface is agreement with
    # everything, and would make this whole check a no-op.
    for label, values in (
        ("zod fields", _zod_fields()),
        ("SCHEMA.md §2 fields", _schema_md_fields()),
        ("DDL tables", _ddl_tables()),
        ("glossary varieties", _variety_slugs_from_glossary()),
    ):
        if not values:
            errors.append(f"selftest: the {label} reader parsed nothing")

    zod = _zod_fields()
    if "tasting_fee" not in zod or "practices" not in zod:
        errors.append(
            f"selftest: the zod reader missed a known field — got {len(zod)} fields, "
            f"tasting_fee/practices absent"
        )
    tables = _ddl_tables()
    for table in ("producers", "practices", "logistics", "producer_varieties"):
        if table not in tables:
            errors.append(f"selftest: the DDL reader did not find the {table} table")

    # Drift must be CAUGHT. Each fixture below is a real-shaped corruption, and
    # the corresponding comparison must report it.
    saved_disposition = dict(FIELD_DISPOSITION)
    saved_columns = data_store.PRODUCER_SCALAR_COLUMNS
    saved_arrays = dict(data_store.ARRAY_FIELD_TABLES)
    try:
        # 1. A field in zod with no declared disposition.
        FIELD_DISPOSITION.pop("summary", None)
        failures: list[str] = []
        _compare_storage(failures)
        if not any("no declared disposition" in f and "summary" in f for f in failures):
            errors.append("selftest: an undeclared frontmatter field was NOT caught")
        FIELD_DISPOSITION.update(saved_disposition)

        # 2. A column the upsert writes that the DDL does not have.
        data_store.PRODUCER_SCALAR_COLUMNS = (*saved_columns, "vintage_chart")
        failures = []
        _compare_storage(failures)
        if not any("vintage_chart" in f for f in failures):
            errors.append("selftest: a written column missing from the DDL was NOT caught")
        data_store.PRODUCER_SCALAR_COLUMNS = saved_columns

        # 3. An array field the rebuild would never write, because the reference's
        #    `facilities` shape was ported to it instead of a child table.
        #
        #    Guarded rather than assumed: if `varieties` is already missing, the
        #    real comparison below is what reports it, and this fixture has
        #    nothing left to corrupt. A self-test that presumes the thing it
        #    tests is intact fails as a traceback instead of a finding.
        if "varieties" in data_store.ARRAY_FIELD_TABLES:
            data_store.ARRAY_FIELD_TABLES.pop("varieties")
            failures = []
            _compare_storage(failures)
            if not any("ARRAY_FIELD_TABLES" in f and "varieties" in f for f in failures):
                errors.append("selftest: an array field with no child table was NOT caught")
            data_store.ARRAY_FIELD_TABLES.clear()
            data_store.ARRAY_FIELD_TABLES.update(saved_arrays)

        # 4. The config pair disagreeing. A near-synonym is the realistic case.
        saved_categories = py_config.CATEGORIES
        py_config.CATEGORIES = ("estate_winery", "boutique_winery")  # type: ignore[misc]
        failures = []
        _compare_config_pair(failures)
        if not any("CATEGORIES" in f for f in failures):
            errors.append("selftest: a drifted config.ts/config.py vocabulary was NOT caught")
        py_config.CATEGORIES = saved_categories  # type: ignore[misc]

        # 5. VARIETY_KEYS drifting from the glossary — the copy most likely to.
        saved_varieties = py_config.VARIETY_KEYS
        py_config.VARIETY_KEYS = tuple(saved_varieties[:-1])  # type: ignore[misc]
        failures = []
        _compare_config_pair(failures)
        if not any("VARIETY_KEYS" in f for f in failures):
            errors.append("selftest: a drifted VARIETY_KEYS list was NOT caught")
        py_config.VARIETY_KEYS = saved_varieties  # type: ignore[misc]
    finally:
        FIELD_DISPOSITION.clear()
        FIELD_DISPOSITION.update(saved_disposition)
        data_store.PRODUCER_SCALAR_COLUMNS = saved_columns
        data_store.ARRAY_FIELD_TABLES.clear()
        data_store.ARRAY_FIELD_TABLES.update(saved_arrays)

    return errors


def main() -> int:
    # The self-test corrupts fixtures on purpose, so it is the code most likely
    # to raise on a surface that is already broken. Report that as a finding and
    # carry on to the real comparison — a crash here must never be what stops
    # the check that matters from running.
    try:
        errors = _selftest()
    except Exception as exc:  # noqa: BLE001
        errors = [f"selftest: raised {exc!r} — a surface is broken enough to break its own fixture"]

    failures, pending = run()
    errors.extend(failures)

    if errors:
        print(f"VALIDATE 13 FAIL — {len(errors)} issue(s)")
        for message in errors:
            print(f"  {message}")
        return 1

    compared = len(_zod_fields())
    print(
        f"VALIDATE 13 PASS — selftest ok; {compared} frontmatter fields agree across "
        f"SCHEMA.md §2, the zod schema and the SQLite DDL; config.ts and "
        f"admin/config.py mirror exactly"
    )
    for surface in pending:
        print(f"  pending: {surface}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
