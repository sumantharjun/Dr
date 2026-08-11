#!/usr/bin/env python3
"""
One-shot migration: allow more than one baby per account, and attribute feeding
data to a specific baby.

    cd backend
    source Dr/bin/activate
    python scripts/enable_multi_baby.py           # dry run — reports, writes nothing
    python scripts/enable_multi_baby.py --apply   # performs the change

Steps, in this order:
  1. feeding_logs.baby_id      — add (nullable FK)
  2. BACKFILL feeding_logs     — attribute every existing log to its owner's baby
  3. device_alerts.baby_id     — add (nullable FK), scopes duplicate suppression
  4. devices.active_baby_id    — add (nullable FK), the "feeding now" pointer
  5. babies: DROP the UNIQUE index on user_id, replace with a plain index

**Step 2 must happen before step 5.** Right now every account has exactly one
baby, because the unique constraint guarantees it — so "this user's logs belong
to this user's baby" is provably correct. The moment that constraint is dropped
a second baby can appear and the mapping stops being provable. Ordering is the
whole reason this is one script rather than several.

Run BEFORE deploying the code: the new code selects feeding_logs.baby_id on
every feeding query, so without the column those endpoints would 500.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import engine  # noqa: E402

# The non-unique index that takes over from the UNIQUE one. A distinct name is
# required: it must be created while the old index still exists (see step 5).
REPLACEMENT_INDEX = "ix_babies_user_id_multi"


def _columns(table: str) -> set:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _unique_user_index() -> str | None:
    """Name of the UNIQUE index on babies.user_id, or None if already dropped."""
    for ix in inspect(engine).get_indexes("babies"):
        if ix.get("unique") and ix.get("column_names") == ["user_id"]:
            return ix["name"]
    return None


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

    need_log_col = "baby_id" not in _columns("feeding_logs")
    need_alert_col = "baby_id" not in _columns("device_alerts")
    need_active = "active_baby_id" not in _columns("devices")
    unique_ix = _unique_user_index()

    with engine.connect() as conn:
        logs = conn.execute(text("SELECT COUNT(*) FROM feeding_logs")).scalar_one()
        babies = conn.execute(text("SELECT COUNT(*) FROM babies")).scalar_one()
        attributable = conn.execute(text(
            "SELECT COUNT(*) FROM feeding_logs fl JOIN babies b ON b.user_id = fl.user_id"
        )).scalar_one()
        multi = conn.execute(text(
            "SELECT COUNT(*) FROM (SELECT user_id FROM babies GROUP BY user_id "
            "HAVING COUNT(*) > 1) x"
        )).scalar_one()

    print(f"Found  : {logs} feeding log(s), {babies} baby profile(s).")
    print(f"         {attributable} log(s) can be attributed; "
          f"{logs - attributable} have no baby on the account and stay NULL.")
    print(f"Pending: feeding_logs.baby_id={'ADD' if need_log_col else 'present'}  "
          f"device_alerts.baby_id={'ADD' if need_alert_col else 'present'}  "
          f"devices.active_baby_id={'ADD' if need_active else 'present'}  "
          f"babies unique index={'DROP ' + unique_ix if unique_ix else 'already dropped'}")

    if multi:
        # Only possible if a previous run already dropped the constraint. The
        # backfill would then be a guess, so refuse rather than mis-assign.
        print(f"ABORT  : {multi} user(s) already have more than one baby — the "
              f"backfill can no longer be proven correct. Inspect manually.")
        return 1

    if not (need_log_col or need_alert_col or need_active or unique_ix):
        print("SKIP   : nothing to do.")
        _report()
        return 0

    if not args.apply:
        print("\nDRY RUN — nothing written. Statements that would execute:")
        if need_log_col:
            print("  ALTER TABLE feeding_logs ADD COLUMN baby_id INT NULL,")
            print("    ADD CONSTRAINT fk_feeding_logs_baby FOREIGN KEY (baby_id) REFERENCES babies(id);")
            print("  CREATE INDEX ix_feeding_logs_baby_id ON feeding_logs (baby_id);")
            print("  UPDATE feeding_logs fl JOIN babies b ON b.user_id = fl.user_id")
            print("    SET fl.baby_id = b.id WHERE fl.baby_id IS NULL;")
        if need_alert_col:
            print("  ALTER TABLE device_alerts ADD COLUMN baby_id INT NULL,")
            print("    ADD CONSTRAINT fk_device_alerts_baby FOREIGN KEY (baby_id) REFERENCES babies(id);")
        if need_active:
            print("  ALTER TABLE devices ADD COLUMN active_baby_id INT NULL,")
            print("    ADD CONSTRAINT fk_devices_active_baby FOREIGN KEY (active_baby_id) REFERENCES babies(id);")
        if unique_ix:
            print(f"  CREATE INDEX {REPLACEMENT_INDEX} ON babies (user_id);")
            print(f"  ALTER TABLE babies DROP INDEX {unique_ix};   -- after, or errno 1553")
        print("\nRe-run with --apply to perform the migration.")
        return 0

    # 1 + 2 — the column, then the backfill, before the constraint goes.
    if need_log_col:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE feeding_logs ADD COLUMN baby_id INT NULL"))
            conn.execute(text(
                "ALTER TABLE feeding_logs ADD CONSTRAINT fk_feeding_logs_baby "
                "FOREIGN KEY (baby_id) REFERENCES babies(id)"))
            conn.execute(text("CREATE INDEX ix_feeding_logs_baby_id ON feeding_logs (baby_id)"))
        print("DONE   : added feeding_logs.baby_id.")

    with engine.begin() as conn:
        res = conn.execute(text(
            "UPDATE feeding_logs fl JOIN babies b ON b.user_id = fl.user_id "
            "SET fl.baby_id = b.id WHERE fl.baby_id IS NULL"))
    print(f"DONE   : attributed {res.rowcount} existing feeding log(s).")

    if need_alert_col:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE device_alerts ADD COLUMN baby_id INT NULL"))
            conn.execute(text(
                "ALTER TABLE device_alerts ADD CONSTRAINT fk_device_alerts_baby "
                "FOREIGN KEY (baby_id) REFERENCES babies(id)"))
            conn.execute(text("CREATE INDEX ix_device_alerts_baby_id ON device_alerts (baby_id)"))
        print("DONE   : added device_alerts.baby_id.")

    if need_active:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE devices ADD COLUMN active_baby_id INT NULL"))
            conn.execute(text(
                "ALTER TABLE devices ADD CONSTRAINT fk_devices_active_baby "
                "FOREIGN KEY (active_baby_id) REFERENCES babies(id)"))
        print("DONE   : added devices.active_baby_id.")

    # 5 — last, so the backfill above was provably correct.
    #
    # Order matters here too: babies.user_id carries a foreign key, and MySQL
    # requires an index on an FK column. Dropping the unique index first fails
    # with errno 1553 ("needed in a foreign key constraint"), so the plain
    # replacement has to exist BEFORE the unique one goes.
    ix = _unique_user_index()
    if ix:
        with engine.begin() as conn:
            existing = {i["name"] for i in inspect(engine).get_indexes("babies")}
            if REPLACEMENT_INDEX not in existing:
                conn.execute(text(
                    f"CREATE INDEX {REPLACEMENT_INDEX} ON babies (user_id)"))
            conn.execute(text(f"ALTER TABLE babies DROP INDEX {ix}"))
        print(f"DONE   : added {REPLACEMENT_INDEX}, dropped UNIQUE index {ix}; "
              f"multiple babies per account are now allowed.")

    _report()
    return 0


def _report() -> None:
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM feeding_logs")).scalar_one()
        unattributed = conn.execute(text(
            "SELECT COUNT(*) FROM feeding_logs WHERE baby_id IS NULL")).scalar_one()
    print(f"Final  : {total} feeding log(s), {unattributed} still unattributed "
          f"(expected: only logs whose account has no baby).")
    print(f"         babies unique index: "
          f"{'STILL PRESENT' if _unique_user_index() else 'dropped'}")


if __name__ == "__main__":
    raise SystemExit(main())
