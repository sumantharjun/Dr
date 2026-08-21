#!/usr/bin/env python3
"""
One-shot migration: add `users.tour_completed_at`.

    cd backend
    source Dr/bin/activate
    python scripts/add_user_tour_completed.py           # dry run — reports, writes nothing
    python scripts/add_user_tour_completed.py --apply   # performs the change

Tracks whether a parent has seen the guided tour. NULL means "not yet", which
is what triggers it on first login.

Existing users are STAMPED AS COMPLETED rather than left NULL. They already know
their way around, and a tour ambushing established accounts on their next login
would be worse than not shipping one. Only accounts created from here on get it.

Run BEFORE deploying the code — the new code selects this column on every
authenticated request, so without it those endpoints would 500.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

TABLE = "users"
COLUMN = "tour_completed_at"


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

    if COLUMN in {c["name"] for c in inspect(engine).get_columns(TABLE)}:
        print(f"SKIP   : {TABLE}.{COLUMN} already exists — nothing to do.")
        _report()
        return 0

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
    print(f"Found  : {total} existing user(s). All will be marked as having "
          f"already seen the tour, so it only runs for new sign-ups.")

    if not args.apply:
        print()
        print("DRY RUN — nothing written. Statements that would execute:")
        print(f"  ALTER TABLE {TABLE} ADD COLUMN {COLUMN} DATETIME NULL;")
        print(f"  UPDATE {TABLE} SET {COLUMN} = UTC_TIMESTAMP() WHERE {COLUMN} IS NULL;")
        print()
        print("Re-run with --apply to perform the migration.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} DATETIME NULL"))
    print(f"DONE   : added {TABLE}.{COLUMN}.")

    # Separate transaction: MySQL commits implicitly on DDL, so this can't share
    # one with the ALTER. Confined to the run that creates the column, so a
    # later re-run can't stamp genuinely-new users who haven't toured yet.
    with engine.begin() as conn:
        res = conn.execute(text(
            f"UPDATE {TABLE} SET {COLUMN} = UTC_TIMESTAMP() WHERE {COLUMN} IS NULL"))
    print(f"DONE   : marked {res.rowcount} existing user(s) as already toured.")
    _report()
    return 0


def _report() -> None:
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
        pending = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL")).scalar_one()
    print(f"Final  : {total} user(s), {pending} who would still be shown the tour.")


if __name__ == "__main__":
    raise SystemExit(main())
