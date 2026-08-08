#!/usr/bin/env python3
"""
One-shot migration: add `babies.date_of_birth`.

Run this ONCE against the production database BEFORE deploying the code that
expects the column:

    cd backend
    source Dr/bin/activate
    python scripts/add_baby_dob_column.py           # dry run — reports, writes nothing
    python scripts/add_baby_dob_column.py --apply   # performs the change

Unlike scripts/add_milk_type_column.py there is NO backfill, deliberately. A
date of birth cannot be inferred from anything already stored, and inventing
one would feed wrong ages into feeding volume and interval guidance — worse
than having none. Existing profiles keep NULL and their parents are prompted to
fill it in from Settings.

Safety properties:
  - Idempotent: if the column exists, reports and exits 0 without writing.
  - Purely additive: a nullable column, so the currently-deployed code (which
    doesn't know about it) keeps working after this runs.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

TABLE = "babies"
COLUMN = "date_of_birth"
DDL = "DATE NULL"


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

    if COLUMN in {c["name"] for c in inspector.get_columns(TABLE)}:
        print(f"SKIP   : {TABLE}.{COLUMN} already exists — nothing to do.")
        _report()
        return 0

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
    print(f"Found  : {total} existing baby profile(s). These will keep a NULL "
          f"{COLUMN} — no value is invented.")

    if not args.apply:
        print()
        print("DRY RUN — nothing written. Statement that would execute:")
        print(f"  ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {DDL};")
        print()
        print("Re-run with --apply to perform the migration.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {DDL}"))

    print(f"DONE   : added {TABLE}.{COLUMN}.")
    _report()
    return 0


def _report() -> None:
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
        missing = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL")
        ).scalar_one()
    print(f"Profiles: {total} total, {missing} still without a date of birth.")
    if missing:
        print("          Those parents will be prompted to add it in Settings.")


if __name__ == "__main__":
    raise SystemExit(main())
