"""Shared persistence helper for UV sterilization status updates.
Used by both POST /uv/progress and the WebSocket `uv_progress` event."""
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.uv import UvCycle
from app.utils.timezone import now_ist

VALID_STATUSES = {"started", "completed", "failed"}
TERMINAL_STATUSES = ("completed", "failed")


def apply_uv_progress(db: Session, device: Device, uv_cycle_id: int, status: str) -> UvCycle:
    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Choose from: {sorted(VALID_STATUSES)}",
        )

    # Atomic terminal-state guard (lost-update safe) — see washing_ops for the
    # full rationale. A completed/failed UV cycle can't be revived; an
    # idempotent repeat of the same terminal status is a no-op ack.
    values = {"status": status}
    if status in TERMINAL_STATUSES:
        values["completed_at"] = now_ist()
        values["ended_reason"] = status  # 'completed' or 'failed'

    result = db.execute(
        update(UvCycle)
        .where(
            UvCycle.id == uv_cycle_id,
            UvCycle.device_id == device.id,
            UvCycle.status.notin_(TERMINAL_STATUSES),
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    db.commit()

    if result.rowcount == 1:
        return db.query(UvCycle).filter(UvCycle.id == uv_cycle_id, UvCycle.device_id == device.id).first()

    cycle = db.query(UvCycle).filter(UvCycle.id == uv_cycle_id, UvCycle.device_id == device.id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="UV cycle not found")
    if cycle.status == status:
        return cycle  # idempotent ack
    raise HTTPException(
        status_code=409,
        detail=(
            f"UV cycle {cycle.id} is already '{cycle.status}' and cannot transition "
            f"to '{status}'. Start a new UV cycle instead of reporting on this one."
        ),
    )
