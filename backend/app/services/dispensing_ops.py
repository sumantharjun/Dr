"""Shared persistence helper for dispense progress updates.
Used by both POST /dispensing/progress and the WS `dispense_progress` event."""
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.dispensing import MilkDispenseLog
from app.utils.timezone import now_ist

VALID_STATUSES = {"pending", "dispensing", "completed", "failed"}
TERMINAL_STATUSES = ("completed", "failed")


def apply_dispense_progress(
    db: Session,
    device: Device,
    log_id: int,
    status: str,
    progress_pct: int,
) -> MilkDispenseLog:
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

    # Atomic terminal-state guard (lost-update safe) — see
    # washing_ops.apply_wash_progress for the full rationale. A single
    # conditional UPDATE closes the read-then-write gap so a concurrent
    # cancel/sweep/supersede can't be silently overwritten.
    values = {"status": status, "progress_pct": progress_pct}
    if status == "completed":
        values["progress_pct"] = 100
        values["completed_at"] = now_ist()
        values["ended_reason"] = "completed"
    elif status == "failed":
        values["completed_at"] = now_ist()
        values["ended_reason"] = "failed"

    result = db.execute(
        update(MilkDispenseLog)
        .where(
            MilkDispenseLog.id == log_id,
            MilkDispenseLog.device_id == device.id,
            MilkDispenseLog.status.notin_(TERMINAL_STATUSES),
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    db.commit()

    if result.rowcount == 1:
        return (
            db.query(MilkDispenseLog)
            .filter(MilkDispenseLog.id == log_id, MilkDispenseLog.device_id == device.id)
            .first()
        )

    log = (
        db.query(MilkDispenseLog)
        .filter(MilkDispenseLog.id == log_id, MilkDispenseLog.device_id == device.id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Dispense log not found")
    if log.status == status:
        return log  # idempotent ack
    raise HTTPException(
        status_code=409,
        detail=(
            f"Dispense {log.id} is already '{log.status}' and cannot "
            f"transition to '{status}'. It was likely recovered "
            "(timeout/cancel/supersede) while the device was offline — "
            "start a new dispense instead of reporting on this one."
        ),
    )
