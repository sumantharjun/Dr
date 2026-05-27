from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.utils.timezone import now_ist
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.washing import WashingCycle
from app.models.user import User
from app.schemas.washing import DeviceWashingStart, WashingCycleOut, WashingStart
from app.services.commands import dispatch_command
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.websocket.manager import manager

router = APIRouter(prefix="/washing", tags=["washing"])

VALID_MODES = {"full_cycle", "wash", "deep_clean", "dispense"}
VALID_STATUSES = {"pending", "running", "completed", "failed"}


class WashProgressUpdate(BaseModel):
    cycle_id: int
    status: str
    progress_pct: int  # 0–100


def _has_active_cycle(db: Session, device_id: int) -> bool:
    return (
        db.query(WashingCycle)
        .filter(
            WashingCycle.device_id == device_id,
            WashingCycle.status.in_(["pending", "running"]),
        )
        .first()
        is not None
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

    if _has_active_cycle(db, body.device_id):
        raise HTTPException(
            status_code=409,
            detail="A wash cycle is already active on this device. Finish or fail it before starting another.",
        )

    cycle = WashingCycle(
        device_id=body.device_id, mode=body.mode, status="pending", initiated_by="app"
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

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
    """
    if body.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Choose from: {sorted(VALID_MODES)}")

    if _has_active_cycle(db, device.id):
        raise HTTPException(
            status_code=409,
            detail="A wash cycle is already active on this device. Finish or fail it before starting another.",
        )

    cycle = WashingCycle(
        device_id=device.id, mode=body.mode, status="pending", initiated_by="device"
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    # Tell the app clients a device-initiated cycle just began.
    await manager.broadcast_to_device(
        str(device.id),
        {
            "type": "wash_progress",
            "cycle_id": cycle.id,
            "status": "pending",
            "progress_pct": 0,
            "initiated_by": "device",
            "mode": cycle.mode,
        },
    )
    return cycle


@router.post("/progress", response_model=WashingCycleOut)
async def update_wash_progress(
    body: WashProgressUpdate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Device firmware calls this to report wash cycle progress."""
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {sorted(VALID_STATUSES)}")
    if not (0 <= body.progress_pct <= 100):
        raise HTTPException(status_code=400, detail="progress_pct must be 0–100")

    cycle = db.query(WashingCycle).filter(
        WashingCycle.id == body.cycle_id,
        WashingCycle.device_id == device.id,
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    cycle.status = body.status
    cycle.progress_pct = body.progress_pct
    if body.status == "completed":
        cycle.completed_at = now_ist()
        cycle.progress_pct = 100

    db.commit()
    db.refresh(cycle)

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
