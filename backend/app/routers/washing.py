from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.utils.locks import device_start_lock
from app.utils.timezone import now_ist
from sqlalchemy import update
from sqlalchemy.orm import Session

TERMINAL_STATUSES = ("completed", "failed")

from app.database import get_db
from app.models.device import Device
from app.models.washing import WashingCycle
from app.models.user import User
from app.schemas.washing import DeviceWashingStart, WashingCycleOut, WashingStart
from app.services.commands import dispatch_command
from app.services.washing_ops import apply_wash_progress
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.websocket.manager import manager

router = APIRouter(prefix="/washing", tags=["washing"])

VALID_MODES = {"full_cycle", "steam_dry", "dry"}
VALID_STATUSES = {"pending", "running", "completed", "failed"}


class WashProgressUpdate(BaseModel):
    cycle_id: int
    status: str
    progress_pct: int  # 0–100


def _active_cycle(db: Session, device_id: int) -> Optional[WashingCycle]:
    # order_by(id desc) so that if a corrupt double-active state ever exists,
    # the newest cycle is returned deterministically rather than arbitrarily.
    return (
        db.query(WashingCycle)
        .filter(
            WashingCycle.device_id == device_id,
            WashingCycle.status.in_(["pending", "running"]),
        )
        .order_by(WashingCycle.id.desc())
        .first()
    )


def _has_active_cycle(db: Session, device_id: int) -> bool:
    return _active_cycle(db, device_id) is not None


def _force_fail_active(db: Session, device_id: int, reason: str = "superseded") -> Optional[int]:
    """Atomically mark the currently-active cycle as failed. Returns its id if
    we actually superseded one, else None.

    `reason` is recorded in ended_reason so the terminal row is auditable
    (defaults to 'superseded'). The conditional UPDATE makes this lost-update
    safe: if a concurrent progress packet drove the cycle terminal between our
    read and our write, rowcount is 0 and we report no supersede (so we don't
    queue a stop for a cycle that finished on its own)."""
    active = _active_cycle(db, device_id)
    if not active:
        return None
    result = db.execute(
        update(WashingCycle)
        .where(
            WashingCycle.id == active.id,
            WashingCycle.status.notin_(TERMINAL_STATUSES),
        )
        .values(status="failed", ended_reason=reason, completed_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return active.id if result.rowcount == 1 else None


def _active_cycle_409(active: WashingCycle, message: str) -> JSONResponse:
    """
    Build the 409 response body, surfacing enough info about the in-flight
    cycle that callers can decide between "adopt" and "force-retry" without
    a second round-trip.
    """
    return JSONResponse(
        status_code=409,
        content={
            "detail": message,
            "active_cycle_id": active.id,
            "active_cycle_started_at": (
                active.started_at.isoformat() if active.started_at else None
            ),
            "active_cycle_initiated_by": active.initiated_by,
            "active_cycle_status": active.status,
            "active_cycle_mode": active.mode,
        },
    )


@router.post("/start", response_model=WashingCycleOut, status_code=201)
async def start_washing(
    body: WashingStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Choose from: {sorted(VALID_MODES)}")

    device = db.query(Device).filter(
        Device.id == body.device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    superseded_id = None
    with device_start_lock(db, body.device_id):
        active = _active_cycle(db, body.device_id)
        if active and not body.force:
            return _active_cycle_409(
                active,
                "A wash cycle is already active on this device. Finish it, "
                "cancel it, or resend with `force: true` to supersede it.",
            )
        if active:
            superseded_id = _force_fail_active(
                db, body.device_id, reason="superseded"
            )

        cycle = WashingCycle(
            device_id=body.device_id, mode=body.mode, status="pending", initiated_by="app"
        )
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

    # If we superseded a stuck cycle: enqueue an explicit stop for the OLD
    # cycle so a mid-cycle REST-polling device halts it on its next poll
    # (it would otherwise only learn the old id is dead via a 409 on its next
    # progress post), and tell app clients to drop state pinned to the old id.
    if superseded_id is not None:
        await dispatch_command(
            db,
            body.device_id,
            {"type": "command", "command": "stop_wash", "cycle_id": superseded_id},
        )
        await manager.broadcast_to_device(
            str(body.device_id),
            {
                "type": "wash_progress",
                "cycle_id": cycle.id,
                "status": "pending",
                "progress_pct": 0,
                "initiated_by": "app",
                "mode": cycle.mode,
                "superseded_cycle_id": superseded_id,
            },
        )

    await dispatch_command(
        db,
        body.device_id,
        {"type": "command", "command": "start_wash", "mode": body.mode, "cycle_id": cycle.id},
    )
    return cycle


@router.post("/device-start", response_model=WashingCycleOut, status_code=201)
async def device_start_washing(
    body: DeviceWashingStart,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """
    Called by the device firmware when a user starts a wash from the physical
    controls on the machine itself (not from the app). Creates a server-side
    cycle row so the device has a `cycle_id` to use in subsequent
    /washing/progress calls, and notifies any app clients listening on the
    device's WebSocket room.

    If a prior cycle is stuck in pending/running (e.g. firmware crashed
    mid-cycle, lost the network, or never sent its completion packet) the
    request returns 409 unless `force=true` is sent — in which case the
    stuck cycle is marked failed and a fresh one is created.
    """
    if body.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Choose from: {sorted(VALID_MODES)}")

    superseded_id = None
    with device_start_lock(db, device.id):
        active = _active_cycle(db, device.id)
        if active and not body.force:
            return _active_cycle_409(
                active,
                "A wash cycle is already active on this device. "
                "If it's stale, resend with `force: true`; if it just started "
                "(see active_cycle_started_at), adopt its `active_cycle_id` for "
                "subsequent progress packets.",
            )
        if active:
            superseded_id = _force_fail_active(
                db, device.id,
                reason="Force-superseded by a new device-initiated wash.",
            )

        cycle = WashingCycle(
            device_id=device.id, mode=body.mode, status="pending", initiated_by="device"
        )
        db.add(cycle)
        db.commit()
        db.refresh(cycle)

    # Tell the app clients a device-initiated cycle just began. If we
    # force-superseded an older cycle, send its id too so the app can clean
    # up any in-memory state pinned to that cycle.
    broadcast: dict = {
        "type": "wash_progress",
        "cycle_id": cycle.id,
        "status": "pending",
        "progress_pct": 0,
        "initiated_by": "device",
        "mode": cycle.mode,
    }
    if superseded_id is not None:
        broadcast["superseded_cycle_id"] = superseded_id
    await manager.broadcast_to_device(str(device.id), broadcast)
    return cycle


@router.post("/progress", response_model=WashingCycleOut)
async def update_wash_progress(
    body: WashProgressUpdate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Device firmware calls this to report wash cycle progress."""
    cycle = apply_wash_progress(
        db=db,
        device=device,
        cycle_id=body.cycle_id,
        status=body.status,
        progress_pct=body.progress_pct,
    )

    await manager.broadcast_to_device(
        str(device.id),
        {
            "type": "wash_progress",
            "cycle_id": cycle.id,
            "status": cycle.status,
            "progress_pct": cycle.progress_pct,
        },
    )
    return cycle


@router.patch("/{cycle_id}/cancel", response_model=WashingCycleOut)
async def cancel_wash_cycle(
    cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    App-side reset for a stuck cycle. Unlike the old Stop button (which only
    queued a `stop_wash` command and left the DB row untouched when the device
    was offline), this directly clears the active row so the device is no
    longer blocked, AND fires the stop command so an online device halts too.

    Idempotent on already-terminal cycles. Only pending/running cycles are
    mutated.
    """
    cycle = (
        db.query(WashingCycle)
        .join(Device, WashingCycle.device_id == Device.id)
        .filter(WashingCycle.id == cycle_id, Device.user_id == current_user.id)
        .first()
    )
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    # Atomic cancel: only transition a still-active row. If a concurrent
    # progress packet drove it terminal first, rowcount is 0 and we just
    # return the final state (the cancel is moot — it already finished) rather
    # than overwriting it or sending a spurious stop.
    result = db.execute(
        update(WashingCycle)
        .where(
            WashingCycle.id == cycle.id,
            WashingCycle.status.notin_(TERMINAL_STATUSES),
        )
        .values(status="failed", ended_reason="cancelled", completed_at=now_ist())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(cycle)

    if result.rowcount == 0:
        # Already terminal (double-tap, or finished concurrently) — nothing to do.
        return cycle

    # We won the cancel: stop the device (queued for REST pollers, pushed on WS).
    await dispatch_command(
        db, cycle.device_id,
        {"type": "command", "command": "stop_wash", "cycle_id": cycle.id},
    )
    await manager.broadcast_to_device(
        str(cycle.device_id),
        {
            "type": "wash_progress",
            "cycle_id": cycle.id,
            "status": "failed",
            "progress_pct": cycle.progress_pct,
            "ended_reason": "cancelled",
        },
    )
    return cycle


@router.get("/history", response_model=List[WashingCycleOut])
def washing_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(WashingCycle)
        .join(Device, WashingCycle.device_id == Device.id)
        .filter(Device.user_id == current_user.id)
        .order_by(WashingCycle.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
