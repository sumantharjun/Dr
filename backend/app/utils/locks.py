"""
Per-device MySQL advisory locks used to serialize the check-then-insert
pattern on the wash/dispense start handlers, closing the TOCTOU race where
two concurrent start requests could both pass the "is there an active cycle?"
check before either committed and end up inserting two pending rows.

MySQL's GET_LOCK is *connection*-scoped. The handlers commit one or more times
inside the locked section (e.g. _force_fail_active, then the insert), and a
SQLAlchemy Session returns its pooled connection on every commit — so the
session's connection is NOT stable across the locked block. Acquiring the lock
on the session connection therefore risks RELEASE_LOCK running on a different
pooled connection than GET_LOCK did, leaking the lock and (under concurrent
same-device starts, e.g. a device retry-storm) reopening the TOCTOU race and
poisoning pooled connections with a never-released lock.

To avoid that, we hold the lock on a DEDICATED connection checked out from the
pool for the entire `with` block, independent of the session's commit cycle.
GET_LOCK/RELEASE_LOCK are not transactional, so commits/rollbacks on the
session connection don't affect it. The lock auto-releases if the dedicated
connection is dropped, so we never wedge a device forever.
"""
from contextlib import contextmanager
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@contextmanager
def device_start_lock(db: Session, device_id: int, timeout_seconds: int = 5):
    """
    Acquire a MySQL named lock scoped to a single device_id on a dedicated
    connection. Raises 503 if the lock can't be acquired within
    `timeout_seconds`. Releases the lock and returns the connection when the
    `with` block exits.
    """
    lock_name = f"sbf_start_{device_id}"
    lock_conn = db.get_bind().connect()  # dedicated connection, held for the whole block
    try:
        result = lock_conn.execute(
            text("SELECT GET_LOCK(:n, :t)"),
            {"n": lock_name, "t": timeout_seconds},
        ).scalar()

        if result != 1:
            # 0 = timed out waiting; None = internal error
            raise HTTPException(
                status_code=503,
                detail=(
                    "Server is busy processing another start request for this "
                    "device. Please retry in a moment."
                ),
            )

        try:
            yield
        finally:
            try:
                lock_conn.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": lock_name})
            except Exception:
                # Non-fatal: the lock auto-releases when lock_conn is closed
                # below (or if the connection is dropped by the server).
                logger.warning("Failed to release device lock %s", lock_name, exc_info=True)
    finally:
        lock_conn.close()
