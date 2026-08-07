"""validate_derived.py — `/validate` check 3. Gate 2.

**Derived-data freshness.** Two questions, both about `data/directory.db` and
`site/src/data/producers.json`:

1. *Are the committed artefacts what `_published` would produce right now?*
   Rebuild to a temp location and diff. Drift means somebody edited published
   content without re-running approve or rebuild, and the site would then build
   from a JSON file that no longer describes the MDX beside it.

2. *Is the rebuild idempotent?* Rebuild twice and compare bytes. A
   non-idempotent rebuild fails **even when the diff against the committed
   artefacts is clean**, because it makes question 1 unanswerable: every deploy
   would show a diff and the real drift would hide in the noise. The usual
   cause is an insert-only child-table rebuild (TRD.md §5).

**The self-test pattern** (`.claude/commands/validate.md`). No pytest, no CI:
the validator carries its own fixtures and runs them every time the real check
runs, so the regression fails the same command. `_selftest()` here does more
work than most because the thing it guards is a *writer*, and a writer can only
be verified by writing. It exercises, on fixtures in a temp directory:

* a clean rebuild, twice, byte-identical;
* the drift comparator actually reporting a difference when there is one;
* **delete-then-insert on the child tables** — the named regression: a variety
  removed from frontmatter and re-upserted into an existing DB must disappear;
* `ON DELETE CASCADE` reaching every child table on unpublish, which is only
  true because `connect()` sets the foreign-keys pragma;
* a corrupted `_published` file being skipped rather than taking the rebuild
  down with it.

Nothing here writes to the real tree. Every fixture lives under a
`TemporaryDirectory`.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import DB_PATH, PRODUCERS_JSON_PATH, PUBLISHED_DIR  # noqa: E402
from admin.pipeline import data_store  # noqa: E402


def _rebuild_into(directory: Path, published_dir: Path = PUBLISHED_DIR) -> tuple[Path, Path]:
    """Rebuild to a scratch directory. Returns (db path, json path)."""
    db_path = directory / "directory.db"
    json_path = directory / "producers.json"
    data_store.rebuild(published_dir=published_dir, db_path=db_path, json_path=json_path)
    return db_path, json_path


def _diff(label: str, expected: Path, actual: Path) -> str | None:
    """Byte comparison with a message that says what to do about it."""
    if not expected.is_file():
        return (
            f"{label}: {expected} is missing. It is a committed artefact "
            f"(TRD.md §5) — run `python -m admin.pipeline.data_store --rebuild`."
        )
    if expected.read_bytes() != actual.read_bytes():
        return (
            f"{label}: committed artefact does not match a fresh rebuild from "
            f"_published. Published content was edited without re-running "
            f"approve or rebuild. Run "
            f"`python -m admin.pipeline.data_store --rebuild` and commit."
        )
    return None


def check_3_derived() -> list[str]:
    """Freshness against the committed artefacts, then idempotency."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="wm-derived-") as tmp:
        root = Path(tmp)

        first_db, first_json = _rebuild_into(root / "first")
        for label, committed, fresh in (
            ("directory.db", DB_PATH, first_db),
            ("producers.json", PRODUCERS_JSON_PATH, first_json),
        ):
            message = _diff(label, committed, fresh)
            if message:
                errors.append(message)

        # Idempotency, independently of whether the diff above was clean.
        second_db, second_json = _rebuild_into(root / "second")
        for label, one, two in (
            ("directory.db", first_db, second_db),
            ("producers.json", first_json, second_json),
        ):
            if one.read_bytes() != two.read_bytes():
                errors.append(
                    f"{label}: two consecutive rebuilds differ. The rebuild is "
                    f"not deterministic — usually an insert-only child-table "
                    f"rebuild, a timestamp in the output, or an unordered read."
                )
    return errors


# =============================================================================
# The self-test
# =============================================================================

#: A complete, valid producer, as a frontmatter dict. Written to MDX by
#: `_write_fixture` so the self-test exercises the real parse path rather than
#: handing `upsert_producer` a dict the parser never saw.
_FIXTURE: dict[str, Any] = {
    "name": "Selftest Wines",
    "parent_company": None,
    "ownership_source": {
        "source": "https://example.invalid/about",
        "method": "producer_statement",
        "date": "2026-08-07",
    },
    "category": "garagiste",
    "website": "https://example.invalid",
    "location": {"suburb": "Basket Range", "state": "SA"},
    "regions": ["adelaide-hills"],
    "primary_region": "adelaide-hills",
    "cellar_door": "none",
    "organic": "none",
    "biodynamic": "none",
    "fruit_source": "purchased",
    "practices": {key: False for key in data_store.PRACTICE_KEYS},
    "varieties": ["chardonnay", "gamay", "pinot-noir"],
    "wine_styles": ["red", "white"],
    "vessels": ["stainless", "amphora"],
    "production_band": "unknown",
    "buy_online": False,
    "ships_nationally": False,
    "summary": "A self-test fixture.",
    "drafted": "2026-08-07",
    "verified": "2026-08-07",
    "source_url": "https://example.invalid/about",
}


def _write_fixture(directory: Path, slug: str, data: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}.mdx"
    path.write_text(
        "---\n"
        + yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        + "---\n\nA fixture body.\n",
        encoding="utf-8",
    )
    return path


def _child_values(db_path: Path, table: str, column: str) -> list[str]:
    conn = data_store.connect(db_path)
    try:
        return [row[0] for row in conn.execute(f"SELECT {column} FROM {table} ORDER BY {column}")]
    finally:
        conn.close()


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="wm-derived-selftest-") as tmp:
        root = Path(tmp)
        published = root / "_published"
        _write_fixture(published, "selftest-wines", _FIXTURE)

        # 1. A clean rebuild is idempotent, byte for byte, DB and JSON.
        one_db, one_json = _rebuild_into(root / "one", published)
        two_db, two_json = _rebuild_into(root / "two", published)
        if one_db.read_bytes() != two_db.read_bytes():
            errors.append("selftest: two rebuilds of a clean fixture produced different DBs")
        if one_json.read_bytes() != two_json.read_bytes():
            errors.append("selftest: two rebuilds of a clean fixture produced different JSON")

        # 2. The drift comparator must BITE. Edit the fixture, rebuild, and
        #    confirm the comparison against the earlier artefacts reports it.
        #    A comparator nobody has watched fail has not been verified.
        drifted = {**_FIXTURE, "summary": "An edited self-test fixture."}
        _write_fixture(published, "selftest-wines", drifted)
        three_db, three_json = _rebuild_into(root / "three", published)
        if _diff("selftest db", one_db, three_db) is None:
            errors.append("selftest: the DB drift comparator did NOT catch an edited fixture")
        if _diff("selftest json", one_json, three_json) is None:
            errors.append("selftest: the JSON drift comparator did NOT catch an edited fixture")
        _write_fixture(published, "selftest-wines", _FIXTURE)

        # 3. Delete-then-insert on the child tables. THE named regression: an
        #    insert-only child rebuild leaves a removed variety lingering. This
        #    upserts into an EXISTING DB rather than doing a full rebuild,
        #    because a full rebuild drops the file and would hide the bug.
        db_path = root / "child.db"
        reupserted = True
        conn = data_store.connect(db_path)
        try:
            data_store.create_schema(conn)
            data_store.upsert_producer(conn, "selftest-wines", _FIXTURE)
            shrunk = {**_FIXTURE, "varieties": ["chardonnay", "gamay"]}
            data_store.upsert_producer(conn, "selftest-wines", shrunk)
            conn.commit()
        except sqlite3.Error as exc:
            # An insert-only child rebuild trips a PRIMARY KEY violation on the
            # first unchanged array member long before it reaches the assertion
            # below. Report it as this check's own failure rather than letting
            # it escape as a traceback, which would skip the rest of the suite.
            reupserted = False
            errors.append(
                f"selftest: re-upserting an edited producer raised {exc!r}. The "
                f"child rebuild is not delete-then-insert (TRD.md §5)."
            )
        finally:
            conn.close()
        if reupserted:
            varieties = _child_values(db_path, "producer_varieties", "variety")
            if varieties != ["chardonnay", "gamay"]:
                errors.append(
                    f"selftest: child rebuild is not delete-then-insert — after removing "
                    f"pinot-noir, producer_varieties holds {varieties}"
                )

        # 4. ON DELETE CASCADE reaches every child table on unpublish. True only
        #    because connect() sets the per-connection foreign-keys pragma.
        conn = data_store.connect(db_path)
        try:
            data_store.remove_producer(conn, "selftest-wines")
            conn.commit()
            for table in (
                "practices",
                "logistics",
                *(table for table, _ in data_store.ARRAY_FIELD_TABLES.values()),
            ):
                left = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if left:
                    errors.append(
                        f"selftest: unpublish left {left} row(s) in {table} — "
                        f"ON DELETE CASCADE is not in force (PRAGMA foreign_keys)"
                    )
        except sqlite3.Error as exc:
            errors.append(f"selftest: unpublish raised {exc}")
        finally:
            conn.close()

        # 5. A corrupted file is skipped and logged, not fatal. One bad file
        #    must not cost the other 299 (TRD.md §5).
        (published / "broken-wines.mdx").write_text(
            "---\nname: Broken\nthis is: not: valid: yaml\n---\n\nBody.\n",
            encoding="utf-8",
        )
        (published / "headless-wines.mdx").write_text("No frontmatter here.\n", encoding="utf-8")
        logging.disable(logging.WARNING)  # the skip warnings are expected here
        try:
            four_db, _ = _rebuild_into(root / "four", published)
        except Exception as exc:  # noqa: BLE001 — any raise at all is the failure
            errors.append(f"selftest: a corrupted _published file was fatal to the rebuild: {exc}")
            four_db = None
        finally:
            logging.disable(logging.NOTSET)

        if four_db is not None:
            conn = data_store.connect(four_db)
            try:
                slugs = [row[0] for row in conn.execute("SELECT slug FROM producers")]
            finally:
                conn.close()
            if slugs != ["selftest-wines"]:
                errors.append(
                    f"selftest: rebuild past two corrupted files loaded {slugs}, "
                    f"expected the one good producer"
                )

    return errors


def main() -> int:
    errors = _selftest() + check_3_derived()
    if errors:
        print(f"VALIDATE 3 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    print(
        "VALIDATE 3 PASS — selftest ok; committed directory.db and producers.json "
        "match a fresh rebuild, and the rebuild is byte-identical twice"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
