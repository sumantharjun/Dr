"""Shared persistence helper for wash progress updates.
Called by both the HTTP /washing/progress route and the WebSocket
`wash_progress` event handler so the two transports stay in lockstep."""
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.washing import WashingCycle
from app.utils.timezone import now_ist

VALID_STATUSES = {"pending", "running", "completed", "failed"}
TERMINAL_STATUSES = ("completed", "failed")


def apply_wash_progress(
    db: Session,
    device: Device,
    cycle_id: int,
    status: str,
    progress_pct: int,
) -> WashingCycle:
    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Choose from: {sorted(VALID_STATUSES)}",
        )
    try:
        progress_pct = int(progress_pct)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="progress_pct must be an integer 0–100")
    if not (0 <= progress_pct <= 100):
        raise HTTPException(status_code=400, detail="progress_pct must be 0–100")

    # ── Atomic terminal-state guard (lost-update safe) ──────────────────────
    # A completed/failed cycle must never come back to life. Checking status
    # in Python and then writing leaves a read-then-write gap: a concurrent
    # cancel / timeout-sweep / force-supersede can commit *between* our read
    # and our write, and our blind write would silently revive the row. So we
    # make the transition a single conditional UPDATE — the DB evaluates
    # "is this row still non-terminal?" atomically at write time. rowcount
    # then tells us what happened.
    values = {"status": status, "progress_pct": progress_pct}
    if status == "completed":
        values["progress_pct"] = 100
        values["completed_at"] = now_ist()
        values["ended_reason"] = "completed"
    elif status == "failed":
        values["completed_at"] = now_ist()
        values["ended_reason"] = "failed"

    result = db.execute(
        update(WashingCycle)
        .where(
            WashingCycle.id == cycle_id,
            WashingCycle.device_id == device.id,
            WashingCycle.status.notin_(TERMINAL_STATUSES),
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    db.commit()

    if result.rowcount == 1:
        return (
            db.query(WashingCycle)
            .filter(WashingCycle.id == cycle_id, WashingCycle.device_id == device.id)
            .first()
        )

    # rowcount == 0 — the row was not updated. Find out why.
    cycle = (
        db.query(WashingCycle)
        .filter(WashingCycle.id == cycle_id, WashingCycle.device_id == device.id)
        .first()
    )
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status == status:
        return cycle  # idempotent ack — firmware retrying its final packet
    raise HTTPException(
        status_code=409,
        detail=(
            f"Cycle {cycle.id} is already '{cycle.status}' and cannot "
            f"transition to '{status}'. It was likely recovered "
            "(timeout/cancel/supersede) while the device was offline — "
            "start a new cycle instead of reporting on this one."
        ),
    )
