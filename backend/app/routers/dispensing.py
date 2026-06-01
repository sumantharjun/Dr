from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from fastapi.responses import JSONResponse

TERMINAL_STATUSES = ("completed", "failed")

from app.database import get_db
from app.models.device import Device
from app.models.dispensing import MilkDispenseLog
from app.models.user import User
from app.schemas.dispensing import DeviceDispenseRequest, DispenseLogOut, DispenseRequest
from app.services.commands import dispatch_command
from app.services.dispensing_ops import apply_dispense_progress
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.utils.locks import device_start_lock
from app.utils.timezone import now_ist
from app.websocket.manager import manager

router = APIRouter(prefix="/dispensing", tags=["dispensing"])

VALID_DISPENSE_STATUSES = {"pending", "dispensing", "completed", "failed"}


class DispenseProgressUpdate(BaseModel):
    log_id: int
    status: str
    progress_pct: int  # 0–100


def _active_dispense(db: Session, device_id: int):
    # order_by(id desc) — newest wins deterministically if a corrupt
    # double-active state ever exists.
    return (
        db.query(MilkDispenseLog)
        .filter(
            MilkDispenseLog.device_id == device_id,
            MilkDispenseLog.status.in_(["pending", "dispensing"]),
        )
        .order_by(MilkDispenseLog.id.desc())
        .first()
    )


def _has_active_dispense(db: Session, device_id: int) -> bool:
    return _active_dispense(db, device_id) is not None


def _force_fail_active_dispense(db: Session, device_id: int, reason: str = "superseded"):
    # Atomic + lost-update safe — see washing._force_fail_active for rationale.
    active = _active_dispense(db, device_id)
    if not active:
        return None
    result = db.execute(
        update(MilkDispenseLog)
        .where(
            MilkDispenseLog.id == active.id,
            MilkDispenseLog.status.notin_(TERMINAL_STATUSES),
        )
        .values(status="failed", ended_reason=reason, completed_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return active.id if result.rowcount == 1 else None


def _active_dispense_409(active: MilkDispenseLog, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": message,
            "active_log_id": active.id,
            "active_log_created_at": (
                active.created_at.isoformat() if active.created_at else None
            ),
            "active_log_initiated_by": active.initiated_by,
            "active_log_status": active.status,
            "active_log_temperature_c": active.temperature_c,
            "active_log_volume_ml": active.volume_ml,
            "active_log_scoop_number": active.scoop_number,
        },
    )


@router.post("/", response_model=DispenseLogOut, status_code=201)
async def dispense_milk(
    body: DispenseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(
        Device.id == body.device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    superseded_id = None
    with device_start_lock(db, body.device_id):
        active = _active_dispense(db, body.device_id)
        if active and not body.force:
            return _active_dispense_409(
                active,
                "A dispense is already active on this device. Wait for it to "
                "finish, cancel it, or resend with `force: true` to supersede it.",
            )
        if active:
            superseded_id = _force_fail_active_dispense(
                db, body.device_id, reason="superseded"
            )

        log = MilkDispenseLog(
            device_id=body.device_id,
            temperature_c=body.temperature_c,
            volume_ml=body.volume_ml,
            scoop_number=body.scoop_number,
            status="pending",
            initiated_by="app",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

    if superseded_id is not None:
        # Explicit stop for the OLD dispense so a mid-operation REST device
        # halts on its next poll (rather than only learning via a 409).
        await dispatch_command(
            db,
            body.device_id,
            {"type": "command", "command": "stop_dispense", "log_id": superseded_id},
        )
        await manager.broadcast_to_device(
            str(body.device_id),
            {
                "type": "dispense_progress",
                "log_id": log.id,
                "status": "pending",
                "progress_pct": 0,
                "initiated_by": "app",
                "temperature_c": log.temperature_c,
                "volume_ml": log.volume_ml,
                "superseded_log_id": superseded_id,
            },
        )

    await dispatch_command(
        db,
        body.device_id,
        {
            "type": "command",
            "command": "dispense",
            "temperature_c": body.temperature_c,
            "volume_ml": body.volume_ml,
            "scoop_number": body.scoop_number,
            "log_id": log.id,
        },
    )
    return log


@router.post("/device-start", response_model=DispenseLogOut, status_code=201)
async def device_start_dispense(
    body: DeviceDispenseRequest,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """
    Called by the device firmware when a user starts a dispense from the
    physical controls (dialed temperature + volume on the device). Creates a
    server-side log row so the device has a `log_id` to use in subsequent
    /dispensing/progress calls, and notifies any app clients.

    Returns 409 if a prior dispense is stuck in pending/dispensing — unless
    `force=true` is sent, in which case the stuck log is marked failed and a
    fresh one is created.
    """
    superseded_id = None
    with device_start_lock(db, device.id):
        active = _active_dispense(db, device.id)
        if active and not body.force:
            return _active_dispense_409(
                active,
                "A dispense is already active on this device. "
                "If it's stale, resend with `force: true`; if it just started "
                "(see active_log_created_at), adopt its `active_log_id` for "
                "subsequent progress packets.",
            )
        if active:
            superseded_id = _force_fail_active_dispense(db, device.id)

        log = MilkDispenseLog(
            device_id=device.id,
            temperature_c=body.temperature_c,
            volume_ml=body.volume_ml,
            scoop_number=body.scoop_number,
            status="pending",
            initiated_by="device",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

    broadcast: dict = {
        "type": "dispense_progress",
        "log_id": log.id,
        "status": "pending",
        "progress_pct": 0,
        "initiated_by": "device",
        "scoop_number": log.scoop_number,
        "temperature_c": log.temperature_c,
        "volume_ml": log.volume_ml,
    }
    if superseded_id is not None:
        broadcast["superseded_log_id"] = superseded_id
    await manager.broadcast_to_device(str(device.id), broadcast)
    return log


@router.post("/progress", response_model=DispenseLogOut)
async def update_dispense_progress(
    body: DispenseProgressUpdate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Device firmware calls this to report milk dispense progress."""
    log = apply_dispense_progress(
        db=db,
        device=device,
        log_id=body.log_id,
        status=body.status,
        progress_pct=body.progress_pct,
    )

    await manager.broadcast_to_device(
        str(device.id),
        {
            "type": "dispense_progress",
            "log_id": log.id,
            "status": log.status,
            "progress_pct": log.progress_pct,
        },
    )
    return log


@router.patch("/{log_id}/cancel", response_model=DispenseLogOut)
async def cancel_dispense(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    App-side reset for a stuck dispense. Directly clears the active row so the
    device is unblocked, and fires a stop_dispense command. Idempotent on
    already-terminal logs.
    """
    log = (
        db.query(MilkDispenseLog)
        .join(Device, MilkDispenseLog.device_id == Device.id)
        .filter(MilkDispenseLog.id == log_id, Device.user_id == current_user.id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Dispense log not found")

    # Atomic cancel — see washing.cancel_wash_cycle for rationale.
    result = db.execute(
        update(MilkDispenseLog)
        .where(
            MilkDispenseLog.id == log.id,
            MilkDispenseLog.status.notin_(TERMINAL_STATUSES),
        )
        .values(status="failed", ended_reason="cancelled", completed_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(log)

    if result.rowcount == 0:
        return log  # already terminal (double-tap or finished concurrently)

    await dispatch_command(
        db, log.device_id,
        {"type": "command", "command": "stop_dispense", "log_id": log.id},
    )
    await manager.broadcast_to_device(
        str(log.device_id),
        {
            "type": "dispense_progress",
            "log_id": log.id,
            "status": "failed",
            "progress_pct": log.progress_pct,
            "ended_reason": "cancelled",
        },
    )
    return log


@router.get("/history", response_model=List[DispenseLogOut])
def dispense_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(MilkDispenseLog)
        .join(Device, MilkDispenseLog.device_id == Device.id)
        .filter(Device.user_id == current_user.id)
        .order_by(MilkDispenseLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
