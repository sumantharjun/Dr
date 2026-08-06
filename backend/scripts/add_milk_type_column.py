#!/usr/bin/env python3
"""
One-shot migration: add `feeding_logs.milk_type` and backfill existing rows.

Run this ONCE, against the production database, BEFORE deploying the code that
expects the column:

    cd backend
    source Dr/bin/activate
    python scripts/add_milk_type_column.py           # dry run — reports, writes nothing
    python scripts/add_milk_type_column.py --apply   # performs the change

Why this is a script and not a boot migration like the ones in app/main.py:
the backfill writes clinical data ('breast_milk') to every pre-existing feeding
log. That is a judgement call about historical records, made once, deliberately
— not something a process restart should be able to re-attempt.

Safety properties:
  - Idempotent. If the column already exists the script reports and exits 0
    without touching a single row.
  - The ALTER and the backfill share one transaction, so a failure part-way
    cannot leave the column added but the rows unbackfilled.
  - The backfill only ever targets rows where milk_type IS NULL, and only in
    the run that creates the column, so it cannot overwrite real data later.
"""
import argparse
import sys
from pathlib import Path

# Allow `python scripts/add_milk_type_column.py` from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

TABLE = "feeding_logs"
COLUMN = "milk_type"
ENUM_DDL = "ENUM('breast_milk','formula','cow_milk','mixed','other') NULL"
BACKFILL_VALUE = "breast_milk"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the migration. Without this flag the script only reports.",
    )
    args = parser.parse_args()

    url = engine.url
    print(f"Target : {url.host}:{url.port}/{url.database} (dialect: {engine.dialect.name})")

    if engine.dialect.name != "mysql":
        print(f"ERROR  : expected a MySQL database, got '{engine.dialect.name}'. Aborting.")
        return 1

    inspector = inspect(engine)
    if TABLE not in inspector.get_table_names():
        print(f"ERROR  : table '{TABLE}' does not exist. Aborting.")
        return 1

    columns = {c["name"] for c in inspector.get_columns(TABLE)}
    if COLUMN in columns:
        print(f"SKIP   : {TABLE}.{COLUMN} already exists — nothing to do.")
        _report_distribution()
        return 0

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
    print(f"Found  : {total} existing row(s) in {TABLE}, all of which will be set "
          f"to '{BACKFILL_VALUE}'.")

    if not args.apply:
        print()
        print("DRY RUN — nothing written. Statements that would execute:")
        print(f"  ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {ENUM_DDL};")
        print(f"  UPDATE {TABLE} SET {COLUMN} = '{BACKFILL_VALUE}' WHERE {COLUMN} IS NULL;")
        print()
        print("Re-run with --apply to perform the migration.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {ENUM_DDL}"))
        result = conn.execute(
            text(f"UPDATE {TABLE} SET {COLUMN} = :v WHERE {COLUMN} IS NULL"),
            {"v": BACKFILL_VALUE},
        )
        backfilled = result.rowcount

    print(f"DONE   : added {TABLE}.{COLUMN}; backfilled {backfilled} row(s) "
          f"to '{BACKFILL_VALUE}'.")
    if backfilled != total:
        print(f"WARNING: expected to backfill {total} row(s) but wrote {backfilled}. "
              f"Inspect the table before deploying.")
    _report_distribution()
    return 0


def _report_distribution() -> None:
    """Print the milk_type breakdown so the result is visible, not assumed."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT COALESCE({COLUMN}, '<null>') AS t, COUNT(*) AS n "
            f"FROM {TABLE} GROUP BY {COLUMN} ORDER BY n DESC"
        )).all()
    print("Current distribution:")
    if not rows:
        print("  (table is empty)")
    for t, n in rows:
        print(f"  {t:<12} {n}")


if __name__ == "__main__":
    raise SystemExit(main())
