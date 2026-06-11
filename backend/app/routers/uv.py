from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.user import User
from app.models.uv import UvCycle
from app.schemas.uv import DeviceUvStart, UvCycleOut, UvProgressUpdate, UvStart
from app.services.commands import dispatch_command
from app.services.uv_ops import apply_uv_progress
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.utils.locks import device_start_lock
from app.utils.timezone import now_ist
from app.websocket.manager import manager

router = APIRouter(prefix="/uv", tags=["uv"])

TERMINAL_STATUSES = ("completed", "failed")


def _active_uv(db: Session, device_id: int) -> Optional[UvCycle]:
    # Newest active cycle, deterministically (defends against any double-active).
    return (
        db.query(UvCycle)
        .filter(UvCycle.device_id == device_id, UvCycle.status == "started")
        .order_by(UvCycle.id.desc())
        .first()
    )


def _force_fail_active(db: Session, device_id: int, reason: str = "superseded") -> Optional[int]:
    active = _active_uv(db, device_id)
    if not active:
        return None
    result = db.execute(
        update(UvCycle)
        .where(UvCycle.id == active.id, UvCycle.status.notin_(TERMINAL_STATUSES))
        .values(status="failed", ended_reason=reason, completed_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return active.id if result.rowcount == 1 else None


def _active_uv_409(active: UvCycle, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": message,
            "active_uv_cycle_id": active.id,
            "active_uv_started_at": active.started_at.isoformat() if active.started_at else None,
            "active_uv_initiated_by": active.initiated_by,
            "active_uv_status": active.status,
        },
    )


@router.post("/start", response_model=UvCycleOut, status_code=201)
async def start_uv(
    body: UvStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start UV sterilization from the app. Dispatches a `uv_start` command
    carrying the new `uv_cycle_id`, which the device echoes in /uv/progress."""
    device = db.query(Device).filter(
        Device.id == body.device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    superseded_id = None
    with device_start_lock(db, body.device_id):
        active = _active_uv(db, body.device_id)
        if active and not body.force:
            return _active_uv_409(
                active,
                "A UV cycle is already active on this device. Wait for it to "
                "finish, cancel it, or resend with `force: true` to supersede it.",
            )
        if active:
            superseded_id = _force_fail_active(db, body.device_id, reason="superseded")

        cycle = UvCycle(device_id=body.device_id, status="started", initiated_by="app")
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

    if superseded_id is not None:
        await dispatch_command(db, body.device_id, {"type": "command", "command": "uv_stop", "uv_cycle_id": superseded_id})
        await manager.broadcast_to_device(
            str(body.device_id),
            {"type": "uv_progress", "uv_cycle_id": cycle.id, "status": "started",
             "initiated_by": "app", "superseded_uv_cycle_id": superseded_id},
        )

    await dispatch_command(db, body.device_id, {"type": "command", "command": "uv_start", "uv_cycle_id": cycle.id})
    return cycle


@router.post("/device-start", response_model=UvCycleOut, status_code=201)
async def device_start_uv(
    body: DeviceUvStart,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Called by firmware when UV is started from the device's physical controls."""
    superseded_id = None
    with device_start_lock(db, device.id):
        active = _active_uv(db, device.id)
        if active and not body.force:
            return _active_uv_409(
                active,
                "A UV cycle is already active on this device. If it's stale, "
                "resend with `force: true`; otherwise adopt its `active_uv_cycle_id`.",
            )
        if active:
            superseded_id = _force_fail_active(db, device.id)

        cycle = UvCycle(device_id=device.id, status="started", initiated_by="device")
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

    broadcast: dict = {"type": "uv_progress", "uv_cycle_id": cycle.id, "status": "started", "initiated_by": "device"}
    if superseded_id is not None:
        broadcast["superseded_uv_cycle_id"] = superseded_id
    await manager.broadcast_to_device(str(device.id), broadcast)
    return cycle


@router.post("/progress", response_model=UvCycleOut)
async def update_uv_progress(
    body: UvProgressUpdate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Device reports UV status: started → completed | failed."""
    cycle = apply_uv_progress(db=db, device=device, uv_cycle_id=body.uv_cycle_id, status=body.status)
    await manager.broadcast_to_device(
        str(device.id),
        {"type": "uv_progress", "uv_cycle_id": cycle.id, "status": cycle.status, "ended_reason": cycle.ended_reason},
    )
    return cycle


@router.patch("/{uv_cycle_id}/cancel", response_model=UvCycleOut)
async def cancel_uv(
    uv_cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """App-side reset for a stuck UV cycle; also sends a `uv_stop` command."""
    cycle = (
        db.query(UvCycle)
        .join(Device, UvCycle.device_id == Device.id)
        .filter(UvCycle.id == uv_cycle_id, Device.user_id == current_user.id)
        .first()
    )
    if not cycle:
        raise HTTPException(status_code=404, detail="UV cycle not found")

    result = db.execute(
        update(UvCycle)
        .where(UvCycle.id == cycle.id, UvCycle.status.notin_(TERMINAL_STATUSES))
        .values(status="failed", ended_reason="cancelled", completed_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(cycle)
    if result.rowcount == 0:
        return cycle  # already terminal — nothing to do

    await dispatch_command(db, cycle.device_id, {"type": "command", "command": "uv_stop", "uv_cycle_id": cycle.id})
    await manager.broadcast_to_device(
        str(cycle.device_id),
        {"type": "uv_progress", "uv_cycle_id": cycle.id, "status": "failed", "ended_reason": "cancelled"},
    )
    return cycle


@router.get("/history", response_model=List[UvCycleOut])
def uv_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(UvCycle)
        .join(Device, UvCycle.device_id == Device.id)
        .filter(Device.user_id == current_user.id)
        .order_by(UvCycle.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
