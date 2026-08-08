#!/usr/bin/env python3
"""
One-shot migration: give every baby a name, then require one.

    cd backend
    source Dr/bin/activate
    python scripts/backfill_baby_name.py           # dry run — reports, writes nothing
    python scripts/backfill_baby_name.py --apply   # performs the change

Two steps:
  1. Backfill NULL / whitespace-only names to 'Baby'. The app greets and labels
     by name throughout, so a blank name turned every one of those into generic
     copy. 'Baby' is a neutral placeholder the parent can edit in Settings.
  2. MODIFY the column to NOT NULL, so the same gap can't reappear. The API
     also rejects blank names (schemas/baby.py), but the constraint is what
     makes that guarantee durable.

Run this BEFORE deploying the code that expects a non-null name.

MySQL note: DDL causes an implicit commit, so the backfill and the constraint
cannot share a transaction. The backfill runs and commits first — if the ALTER
then fails, the data is still correct and the script can simply be re-run.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

TABLE = "babies"
COLUMN = "name"
PLACEHOLDER = "Baby"
BLANK_PREDICATE = f"{COLUMN} IS NULL OR TRIM({COLUMN}) = ''"


def _column_meta():
    return next(
        (c for c in inspect(engine).get_columns(TABLE) if c["name"] == COLUMN), None
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually perform the migration. Without this flag the script only reports.")
    args = parser.parse_args()

    url = engine.url
    print(f"Target : {url.host}:{url.port}/{url.database} (dialect: {engine.dialect.name})")

    if engine.dialect.name != "mysql":
        print(f"ERROR  : expected a MySQL database, got '{engine.dialect.name}'. Aborting.")
        return 1

    meta = _column_meta()
    if meta is None:
        print(f"ERROR  : {TABLE}.{COLUMN} does not exist. Aborting.")
        return 1

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
        blank = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {BLANK_PREDICATE}")
        ).scalar_one()

    already_not_null = not meta["nullable"]
    print(f"Found  : {total} profile(s); {blank} with a blank name; "
          f"column is currently {'NOT NULL' if already_not_null else 'NULLABLE'}.")

    if blank == 0 and already_not_null:
        print("SKIP   : nothing to do — every profile has a name and the column is already NOT NULL.")
        return 0

    if not args.apply:
        print()
        print("DRY RUN — nothing written. Statements that would execute:")
        if blank:
            print(f"  UPDATE {TABLE} SET {COLUMN} = '{PLACEHOLDER}' WHERE {BLANK_PREDICATE};")
        if not already_not_null:
            print(f"  ALTER TABLE {TABLE} MODIFY COLUMN {COLUMN} VARCHAR(255) NOT NULL;")
        print()
        print("Re-run with --apply to perform the migration.")
        return 0

    # Step 1 — backfill, committed on its own.
    if blank:
        with engine.begin() as conn:
            result = conn.execute(
                text(f"UPDATE {TABLE} SET {COLUMN} = :v WHERE {BLANK_PREDICATE}"),
                {"v": PLACEHOLDER},
            )
        print(f"DONE   : named {result.rowcount} profile(s) '{PLACEHOLDER}'.")

    # Step 2 — the constraint. Re-check for blanks first: MySQL would silently
    # coerce a remaining NULL to '' rather than refusing, which would leave a
    # blank name behind a NOT NULL column.
    if not already_not_null:
        with engine.connect() as conn:
            remaining = conn.execute(
                text(f"SELECT COUNT(*) FROM {TABLE} WHERE {BLANK_PREDICATE}")
            ).scalar_one()
        if remaining:
            print(f"ABORT  : {remaining} profile(s) still blank — not applying NOT NULL. "
                  f"Re-run the script.")
            return 1
        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {TABLE} MODIFY COLUMN {COLUMN} VARCHAR(255) NOT NULL"
            ))
        print(f"DONE   : {TABLE}.{COLUMN} is now NOT NULL.")

    _report()
    return 0


def _report() -> None:
    meta = _column_meta()
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
        blank = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {BLANK_PREDICATE}")
        ).scalar_one()
        placeholders = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} = :v"), {"v": PLACEHOLDER}
        ).scalar_one()
    print(f"Final  : {total} profile(s), {blank} blank, {placeholders} named "
          f"'{PLACEHOLDER}', column nullable={meta['nullable']}.")
    if placeholders:
        print(f"         Those parents can rename from Settings.")


if __name__ == "__main__":
    raise SystemExit(main())
