"""data_store.py — the data layer. Gate 2. TRD.md §5, SCHEMA.md §3.

**The architecture rule: published MDX frontmatter is the source of truth, and
`data/directory.db` is a disposable derived artefact.** It can be deleted at any
moment and rebuilt exactly from `_published`. Nothing treats the DB as
authoritative and no feature may store state here that cannot be reconstructed
from published content. The repo history is the backup: `directory.db` is
committed, so any rebuild can be diffed against a known-good state.

**This module is the sole owner of `data/directory.db` and
`site/src/data/producers.json`.** No other module writes either (TRD.md §5).

── The two table shapes, and the mistake to avoid ────────────────────────────

SCHEMA.md §3 corrects the build handover here, and the correction is the whole
design of this file. The reference's `facilities` table is a **1:1 wide table of
fixed boolean columns**. That shape is right for `practices` and `logistics`,
whose keys are a closed set. It **cannot hold an open-ended array**. So
`regions`, `subregions`, `varieties`, `wine_styles` and `vessels` are true
`(slug, value)` row tables — five child tables, not five sets of columns.

── Idempotency is a design constraint, not a hope ────────────────────────────

`/validate` check 3 rebuilds twice and fails on any byte of difference, in the
DB *and* the JSON. That is achieved by construction:

* deterministic ordering everywhere — `ORDER BY` on every read, sorted array
  members, `sorted()` over the published glob;
* no timestamps, run IDs, row counts or file paths in any output;
* JSON with fixed separators, sorted keys and a trailing newline;
* a fixed number of write transactions per rebuild, because SQLite's header
  carries a change counter that increments per transaction;
* **delete-then-insert per slug on every child table.** An insert-only child
  rebuild is the usual cause of a non-idempotent rebuild, and it also leaves a
  removed variety lingering in `producer_varieties` forever.

── What this module does NOT validate ────────────────────────────────────────

Full schema validity belongs to `/validate` check 1 and to the zod schema at
build time. This module checks only what the DDL's NOT NULL columns require,
because its contract is different: **a corrupted `_published` file is skipped
and logged, never fatal to the whole rebuild.** One bad file must not cost the
other 299.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    DB_PATH,
    LOGISTICS_KEYS,
    PRACTICE_KEYS,
    PRODUCERS_JSON_PATH,
    PUBLISHED_DIR,
)

_logger = logging.getLogger("admin.data_store")


# =============================================================================
# 1. The DDL — SCHEMA.md §3, verbatim
#
# CONSUMER 2 OF 4 (CLAUDE.md rule 7). A column added here without the matching
# move in the zod schema, the Harvester validator and the admin editor is the
# highest-risk-if-broken failure in the build. `/validate` check 13 diffs the
# four surfaces; the `schema-change` skill fires on any edit to this block.
# =============================================================================

SCHEMA_SQL = """
CREATE TABLE producers (
  slug TEXT PRIMARY KEY,          -- matches MDX filename; no separate UUID
  name TEXT NOT NULL,
  parent_company TEXT,            -- always NULL on published rows; column kept so
                                  -- the invariant is queryable, not merely asserted
  ownership_source TEXT NOT NULL,
  ownership_source_method TEXT NOT NULL,
  ownership_source_date TEXT NOT NULL,
  category TEXT NOT NULL,
  founded_year INTEGER,
  website TEXT NOT NULL,
  -- location, flattened
  address TEXT,
  suburb TEXT,
  state TEXT NOT NULL,
  latitude REAL,
  longitude REAL,
  primary_region TEXT NOT NULL,
  -- visiting
  cellar_door TEXT NOT NULL,
  cellar_door_hours TEXT,
  cost TEXT,
  tasting_fee_aud REAL,           -- flattened from tasting_fee
  tasting_fee_waived_on_purchase INTEGER,
  minimum_age INTEGER,
  -- farming and winemaking
  organic TEXT NOT NULL,
  organic_certifier TEXT,
  biodynamic TEXT NOT NULL,
  biodynamic_certifier TEXT,
  fruit_source TEXT NOT NULL,
  -- scale
  production_band TEXT NOT NULL,
  annual_production_cases INTEGER,
  -- commerce
  buy_online INTEGER NOT NULL DEFAULT 0,
  ships_nationally INTEGER NOT NULL DEFAULT 0,
  shop_url TEXT,
  summary TEXT NOT NULL,
  has_image INTEGER NOT NULL DEFAULT 0
);

-- 1:1 wide boolean tables (fixed closed key sets)
CREATE TABLE practices (
  slug TEXT PRIMARY KEY REFERENCES producers(slug) ON DELETE CASCADE,
  wild_ferment INTEGER NOT NULL,
  unfined INTEGER NOT NULL,
  unfiltered INTEGER NOT NULL,
  minimal_so2 INTEGER NOT NULL
);
CREATE TABLE logistics (
  slug TEXT PRIMARY KEY REFERENCES producers(slug) ON DELETE CASCADE,
  walk_ins_welcome INTEGER NOT NULL DEFAULT 0,
  bookings_required INTEGER NOT NULL DEFAULT 0,
  restaurant INTEGER NOT NULL DEFAULT 0,
  picnic_provisions INTEGER NOT NULL DEFAULT 0,
  dog_friendly INTEGER NOT NULL DEFAULT 0,
  family_friendly INTEGER NOT NULL DEFAULT 0,
  wheelchair_access INTEGER NOT NULL DEFAULT 0,
  group_bookings INTEGER NOT NULL DEFAULT 0,
  vineyard_tours INTEGER NOT NULL DEFAULT 0,
  parking INTEGER NOT NULL DEFAULT 0
);

-- (slug, value) child row tables — one row per array member
CREATE TABLE producer_regions (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  region TEXT NOT NULL,
  PRIMARY KEY (slug, region)
);
CREATE TABLE producer_subregions (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  subregion TEXT NOT NULL,
  PRIMARY KEY (slug, subregion)
);
CREATE TABLE producer_varieties (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  variety TEXT NOT NULL,
  PRIMARY KEY (slug, variety)
);
CREATE TABLE producer_wine_styles (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  wine_style TEXT NOT NULL,
  PRIMARY KEY (slug, wine_style)
);
CREATE TABLE producer_vessels (
  slug TEXT NOT NULL REFERENCES producers(slug) ON DELETE CASCADE,
  vessel TEXT NOT NULL,
  PRIMARY KEY (slug, vessel)
);
"""

#: Scalar columns on `producers`, in DDL order, excluding the `slug` PK. Built
#: once so the INSERT/UPDATE SQL and the params dict cannot drift apart, and so
#: `/validate` check 13 has one tuple to diff the DDL against.
PRODUCER_SCALAR_COLUMNS = (
    "name",
    "parent_company",
    "ownership_source",
    "ownership_source_method",
    "ownership_source_date",
    "category",
    "founded_year",
    "website",
    "address",
    "suburb",
    "state",
    "latitude",
    "longitude",
    "primary_region",
    "cellar_door",
    "cellar_door_hours",
    "cost",
    "tasting_fee_aud",
    "tasting_fee_waived_on_purchase",
    "minimum_age",
    "organic",
    "organic_certifier",
    "biodynamic",
    "biodynamic_certifier",
    "fruit_source",
    "production_band",
    "annual_production_cases",
    "buy_online",
    "ships_nationally",
    "shop_url",
    "summary",
    "has_image",
)

#: Frontmatter array field -> (child table, value column). The five true
#: `(slug, value)` row tables of SCHEMA.md §3. Check 13 asserts a child table
#: exists for every array field in the contract by reading this map.
ARRAY_FIELD_TABLES = {
    "regions": ("producer_regions", "region"),
    "subregions": ("producer_subregions", "subregion"),
    "varieties": ("producer_varieties", "variety"),
    "wine_styles": ("producer_wine_styles", "wine_style"),
    "vessels": ("producer_vessels", "vessel"),
}

#: The DDL's NOT NULL columns, expressed as the frontmatter that has to be there
#: for a row to be insertable. This is deliberately NOT the full SCHEMA.md §2
#: contract: check 1 and the zod schema own that. A file failing this is skipped
#: and logged, and the rebuild carries on.
REQUIRED_FIELDS = (
    "name",
    "ownership_source",
    "category",
    "website",
    "location",
    "primary_region",
    "cellar_door",
    "organic",
    "biodynamic",
    "fruit_source",
    "production_band",
    "summary",
)


# =============================================================================
# 2. Reading `_published`
# =============================================================================


def read_frontmatter(path: Path) -> dict[str, Any]:
    """The frontmatter mapping, parsed and nothing more. Raises ValueError.

    Separated from `parse_frontmatter` because the two questions are different.
    This one asks "what does this file say"; `parse_frontmatter` then asks "can
    this become a DB row", which is a stricter bar carrying REQUIRED_FIELDS.

    `/validate` check 12 wants the first question. A file missing `category` is
    check 1's problem, and check 12 must still see its `regions[]` rather than
    have the file vanish from its count without a word.
    """
    slug = path.stem
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{slug}: missing frontmatter delimiter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{slug}: unterminated frontmatter block")
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise ValueError(f"{slug}: unparseable YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{slug}: frontmatter is not a mapping")
    return data


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Frontmatter dict for one MDX file. Raises ValueError on anything unusable.

    The DB-insertability bar: everything `read_frontmatter` does, plus the
    NOT NULL columns the DDL needs.
    """
    slug = path.stem
    data = read_frontmatter(path)

    missing = [field for field in REQUIRED_FIELDS if data.get(field) is None]
    if missing:
        raise ValueError(f"{slug}: missing required field(s) {', '.join(missing)}")
    # `parent_company` is legitimately null, so it cannot be checked by
    # truthiness with the rest. The KEY must still be present: an absent key is
    # an undetermined producer, which is not publishable (SCHEMA.md §2).
    if "parent_company" not in data:
        raise ValueError(f"{slug}: missing required field parent_company")
    if not isinstance(data["location"], dict) or not data["location"].get("state"):
        raise ValueError(f"{slug}: location.state is required")
    ownership = data["ownership_source"]
    if not isinstance(ownership, dict) or not all(
        ownership.get(key) for key in ("source", "method", "date")
    ):
        raise ValueError(f"{slug}: ownership_source needs source, method and date")
    practices = data.get("practices")
    if not isinstance(practices, dict) or any(
        key not in practices for key in PRACTICE_KEYS
    ):
        raise ValueError(f"{slug}: practices must carry all four §1.6 keys")
    return data


def iter_published(published_dir: Path = PUBLISHED_DIR):
    """Yield `(slug, frontmatter)` for every readable file, sorted by slug.

    Skips and logs rather than raising. The DB is disposable and rebuildable
    (TRD.md §5), and one hand-edited file must not take the whole directory
    down with it. The skip is a warning on the logger the admin's log pane
    reads, so a reviewer sees which file dropped out and why.
    """
    if not published_dir.is_dir():
        return
    for path in sorted(published_dir.glob("*.mdx")):
        try:
            yield path.stem, parse_frontmatter(path)
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            _logger.warning("rebuild: skipping %s — %s", path.name, exc)


def _iso(value: Any) -> str | None:
    """Dates as `YYYY-MM-DD` strings. YAML hands back both dates and strings."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _producer_params(slug: str, data: dict[str, Any]) -> dict[str, Any]:
    """Flatten frontmatter into one row-params dict keyed by the DDL's columns."""
    location = data.get("location") or {}
    ownership = data.get("ownership_source") or {}
    tasting_fee = data.get("tasting_fee") or {}
    waived = tasting_fee.get("waived_on_purchase")
    return {
        "slug": slug,
        "name": data["name"],
        # Always NULL on a published row. The column exists so `/validate`
        # check 8 can ask the question in SQL rather than trusting an assertion.
        "parent_company": data.get("parent_company"),
        "ownership_source": ownership.get("source"),
        "ownership_source_method": ownership.get("method"),
        "ownership_source_date": _iso(ownership.get("date")),
        "category": data["category"],
        "founded_year": data.get("founded_year"),
        "website": data["website"],
        "address": location.get("address"),
        "suburb": location.get("suburb"),
        "state": location.get("state"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "primary_region": data["primary_region"],
        "cellar_door": data["cellar_door"],
        "cellar_door_hours": data.get("cellar_door_hours"),
        "cost": data.get("cost"),
        "tasting_fee_aud": tasting_fee.get("fee_aud"),
        # Tri-state, not a flag: null means the producer does not say, which is
        # different from saying no. Only coerce to 0/1 when a value is present.
        "tasting_fee_waived_on_purchase": None if waived is None else int(bool(waived)),
        "minimum_age": data.get("minimum_age"),
        "organic": data["organic"],
        "organic_certifier": data.get("organic_certifier"),
        "biodynamic": data["biodynamic"],
        "biodynamic_certifier": data.get("biodynamic_certifier"),
        "fruit_source": data["fruit_source"],
        "production_band": data["production_band"],
        "annual_production_cases": data.get("annual_production_cases"),
        "buy_online": int(bool(data.get("buy_online"))),
        "ships_nationally": int(bool(data.get("ships_nationally"))),
        "shop_url": data.get("shop_url"),
        "summary": data["summary"],
        "has_image": int(bool(data.get("image"))),
    }


# =============================================================================
# 3. Writing
# =============================================================================


def connect(db_path: Path) -> sqlite3.Connection:
    """A connection with `ON DELETE CASCADE` actually switched on.

    SQLite disables foreign keys by default and the pragma is per-connection,
    not per-database. Without this line the cascade in the DDL is decorative and
    unpublishing a producer would leave its child rows behind.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def upsert_producer(conn: sqlite3.Connection, slug: str, data: dict[str, Any]) -> None:
    """Upsert the `producers` row; delete-then-insert every child table.

    Delete-then-insert is the load-bearing half (TRD.md §5). Re-approving an
    edited producer must make a removed variety *disappear* from
    `producer_varieties`, not linger beside its replacement.
    """
    columns = ("slug", *PRODUCER_SCALAR_COLUMNS)
    placeholders = ", ".join(f":{column}" for column in columns)
    updates = ", ".join(f"{column} = excluded.{column}" for column in PRODUCER_SCALAR_COLUMNS)
    conn.execute(
        f"INSERT INTO producers ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(slug) DO UPDATE SET {updates}",
        _producer_params(slug, data),
    )

    # 1:1 wide boolean tables. `practices` requires all four keys; `logistics`
    # is optional as a whole and each key defaults false (SCHEMA.md §2).
    practices = data.get("practices") or {}
    conn.execute("DELETE FROM practices WHERE slug = ?", (slug,))
    conn.execute(
        f"INSERT INTO practices (slug, {', '.join(PRACTICE_KEYS)}) "
        f"VALUES (:slug, {', '.join(f':{key}' for key in PRACTICE_KEYS)})",
        {"slug": slug, **{key: int(bool(practices.get(key))) for key in PRACTICE_KEYS}},
    )
    logistics = data.get("logistics") or {}
    conn.execute("DELETE FROM logistics WHERE slug = ?", (slug,))
    conn.execute(
        f"INSERT INTO logistics (slug, {', '.join(LOGISTICS_KEYS)}) "
        f"VALUES (:slug, {', '.join(f':{key}' for key in LOGISTICS_KEYS)})",
        {"slug": slug, **{key: int(bool(logistics.get(key))) for key in LOGISTICS_KEYS}},
    )

    # The five (slug, value) row tables.
    for field, (table, column) in ARRAY_FIELD_TABLES.items():
        conn.execute(f"DELETE FROM {table} WHERE slug = ?", (slug,))
        values = data.get(field) or []
        # sorted+set: deterministic order, and a duplicate in a hand-edited file
        # becomes one row rather than a PRIMARY KEY violation that skips the
        # producer entirely. Check 1 is what reports the duplicate.
        conn.executemany(
            f"INSERT INTO {table} (slug, {column}) VALUES (?, ?)",
            [(slug, value) for value in sorted(set(values))],
        )


def remove_producer(conn: sqlite3.Connection, slug: str) -> None:
    """Unpublish: remove every row for this slug, child tables included.

    The child rows go by `ON DELETE CASCADE`, which is why `connect()` sets the
    foreign-keys pragma.
    """
    conn.execute("DELETE FROM producers WHERE slug = ?", (slug,))


# =============================================================================
# 4. The derived JSON
#
# `site/src/data/producers.json` carries **only what pages and the search index
# need**, not a dump of the frontmatter (TRD.md §5). It is committed, because it
# is an input to the Netlify build.
#
# Read from the DB rather than from frontmatter, so the JSON cannot disagree
# with the table it is supposed to summarise. Two deliberate omissions:
#
# * **Coordinates.** There is no map and therefore no consumer (TRD.md §4.4).
#   They stay in the DB, where SCHEMA.md §3 puts them. Carrying them here would
#   recreate the reference's vestigial `venues.geojson` — written by the admin,
#   read by no page.
# * **The image path.** SCHEMA.md §3 stores `has_image` and not the path, so
#   that is what this can honestly carry. A page rendering the photograph reads
#   the frontmatter through `getCollection`, which has it.
#
# There is no GeoJSON artefact at all.
# =============================================================================


def fetch_all_producers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every producer, `ORDER BY slug`, with child rows folded in sorted."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT p.*,
               pr.wild_ferment, pr.unfined, pr.unfiltered, pr.minimal_so2
        FROM producers p
        JOIN practices pr ON pr.slug = p.slug
        ORDER BY p.slug
        """
    ).fetchall()

    children: dict[str, dict[str, list[str]]] = {}
    for field, (table, column) in ARRAY_FIELD_TABLES.items():
        for row in conn.execute(
            f"SELECT slug, {column} AS value FROM {table} ORDER BY slug, {column}"
        ):
            children.setdefault(row["slug"], {}).setdefault(field, []).append(row["value"])

    producers: list[dict[str, Any]] = []
    for row in rows:
        arrays = children.get(row["slug"], {})
        producer: dict[str, Any] = {
            "slug": row["slug"],
            "name": row["name"],
            "summary": row["summary"],
            "category": row["category"],
            "suburb": row["suburb"],
            "state": row["state"],
            "primary_region": row["primary_region"],
            "cellar_door": row["cellar_door"],
            "organic": row["organic"],
            "organic_certifier": row["organic_certifier"],
            "biodynamic": row["biodynamic"],
            "biodynamic_certifier": row["biodynamic_certifier"],
            "fruit_source": row["fruit_source"],
            "production_band": row["production_band"],
            "practices": {key: bool(row[key]) for key in PRACTICE_KEYS},
            "has_image": bool(row["has_image"]),
        }
        for field in ARRAY_FIELD_TABLES:
            producer[field] = arrays.get(field, [])
        producers.append(producer)
    return producers


def write_producers_json(producers: list[dict[str, Any]], path: Path) -> None:
    """Fixed separators, sorted keys, trailing newline (TRD.md §5)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            producers,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n",
        encoding="utf-8",
    )


# =============================================================================
# 5. The rebuild
# =============================================================================


def rebuild(
    published_dir: Path = PUBLISHED_DIR,
    db_path: Path = DB_PATH,
    json_path: Path = PRODUCERS_JSON_PATH,
) -> int:
    """Full rebuild from `_published`. There is no patch path (TRD.md §5).

    Returns the number of producers loaded. Files that failed to parse are
    logged by `iter_published` and are simply absent from the count.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    conn = connect(db_path)
    try:
        create_schema(conn)
        for slug, data in iter_published(published_dir):
            try:
                upsert_producer(conn, slug, data)
            except (sqlite3.Error, KeyError, TypeError, ValueError) as exc:
                _logger.warning("rebuild: skipping %s — %s", slug, exc)
        conn.commit()
        producers = fetch_all_producers(conn)
    finally:
        conn.close()
    write_producers_json(producers, json_path)
    return len(producers)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild directory.db and producers.json from _published MDX frontmatter."
        )
    )
    parser.add_argument("--rebuild", action="store_true", required=True)
    parser.parse_args()
    count = rebuild()
    print(f"Rebuilt {count} producer(s) -> {DB_PATH}, {PRODUCERS_JSON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
