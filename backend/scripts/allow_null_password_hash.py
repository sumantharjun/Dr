#!/usr/bin/env python3
"""
One-shot migration: allow users.password_hash to be NULL.

    cd backend
    source Dr/bin/activate
    python scripts/allow_null_password_hash.py           # dry run — reports, writes nothing
    python scripts/allow_null_password_hash.py --apply   # performs the change

A user who signs up with Google has no password at all. Storing a junk hash to
satisfy the NOT NULL would be a lie: `verify_password` would then just fail on
login instead of the code being able to detect "this account has no password"
and say something useful.

Safe to run BEFORE deploying the code — this only relaxes a constraint, so the
currently-deployed version keeps working unchanged. No rows are read or written;
existing password hashes are untouched.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

TABLE = "users"
COLUMN = "password_hash"


def _meta():
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

    meta = _meta()
    if meta is None:
        print(f"ERROR  : {TABLE}.{COLUMN} does not exist. Aborting.")
        return 1

    if meta["nullable"]:
        print(f"SKIP   : {TABLE}.{COLUMN} is already nullable — nothing to do.")
        return 0

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
    print(f"Found  : {total} user(s); column is currently NOT NULL. "
          f"No rows will be read or modified.")

    if not args.apply:
        print()
        print("DRY RUN — nothing written. Statement that would execute:")
        print(f"  ALTER TABLE {TABLE} MODIFY COLUMN {COLUMN} VARCHAR(255) NULL;")
        print()
        print("Re-run with --apply to perform the migration.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} MODIFY COLUMN {COLUMN} VARCHAR(255) NULL"))

    print(f"DONE   : {TABLE}.{COLUMN} is now nullable.")
    with engine.connect() as conn:
        without = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL")
        ).scalar_one()
    print(f"Final  : {total} user(s), {without} without a password "
          f"(expected 0 until the first Google sign-up).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
