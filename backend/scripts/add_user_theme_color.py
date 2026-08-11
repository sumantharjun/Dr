#!/usr/bin/env python3
"""
One-shot migration: move the app colour from the baby to the user.

    cd backend
    source Dr/bin/activate
    python scripts/add_user_theme_color.py           # dry run — reports, writes nothing
    python scripts/add_user_theme_color.py --apply   # performs the change

The colour used to be derived from the baby's gender and stored on
babies.theme_color. It is now a free choice belonging to the account, so it
moves to users.theme_color with a default of pastel green.

Existing users are backfilled from their baby's current colour rather than being
reset to the default — nobody's app should change appearance because of a
deploy. Users with no baby, or a colour outside the new set, get green.

babies.theme_color is deliberately LEFT IN PLACE. Dropping a column is
destructive and buys nothing; it is simply unused from here on and can be
removed in a later cleanup once this path has proven itself.

Run BEFORE deploying the code — the new code selects users.theme_color on every
authenticated request, so without the column every request would 500.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

TABLE = "users"
COLUMN = "theme_color"
THEMES = ("green", "blue", "pink", "lilac", "peach", "slate")
DEFAULT = "green"
# repr() gives 'green' — single quotes, which is what MySQL wants for ENUM values.
DDL = f"ENUM({','.join(repr(t) for t in THEMES)}) NOT NULL DEFAULT '{DEFAULT}'"


def _has_column() -> bool:
    return COLUMN in {c["name"] for c in inspect(engine).get_columns(TABLE)}


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

    if _has_column():
        print(f"SKIP   : {TABLE}.{COLUMN} already exists — nothing to do.")
        _report()
        return 0

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one()
        # How many users will inherit a colour from their baby vs. take the default.
        inheritable = conn.execute(text(
            "SELECT COUNT(*) FROM users u JOIN babies b ON b.user_id = u.id "
            "WHERE b.theme_color IN ('blue','pink')"
        )).scalar_one()
    print(f"Found  : {total} user(s); {inheritable} will inherit their baby's "
          f"current colour, {total - inheritable} will get '{DEFAULT}'.")

    if not args.apply:
        print()
        print("DRY RUN — nothing written. Statements that would execute:")
        print(f"  ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {DDL};")
        print(f"  UPDATE {TABLE} u JOIN babies b ON b.user_id = u.id")
        print(f"    SET u.{COLUMN} = b.theme_color WHERE b.theme_color IN ('blue','pink');")
        print()
        print("Re-run with --apply to perform the migration.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {DDL}"))
    print(f"DONE   : added {TABLE}.{COLUMN} (default '{DEFAULT}').")

    # Separate transaction: MySQL commits implicitly on DDL anyway, so the
    # backfill cannot share one with the ALTER. If this half fails the column
    # still exists and everyone simply has the default — re-running is safe.
    with engine.begin() as conn:
        result = conn.execute(text(
            f"UPDATE {TABLE} u JOIN babies b ON b.user_id = u.id "
            f"SET u.{COLUMN} = b.theme_color WHERE b.theme_color IN ('blue','pink')"
        ))
    print(f"DONE   : carried over {result.rowcount} user(s) existing colour.")
    _report()
    return 0


def _report() -> None:
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT {COLUMN}, COUNT(*) FROM {TABLE} GROUP BY {COLUMN} ORDER BY COUNT(*) DESC"
        )).all()
    print("Distribution:")
    for theme, n in rows:
        print(f"  {theme:<8} {n}")


if __name__ == "__main__":
    raise SystemExit(main())
