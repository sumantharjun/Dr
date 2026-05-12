from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.utils.timezone import now_ist
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.washing import WashingCycle
from app.models.user import User
from app.schemas.washing import WashingCycleOut, WashingStart
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.websocket.manager import manager

router = APIRouter(prefix="/washing", tags=["washing"])

VALID_MODES = {"full_cycle", "wash", "deep_clean", "dispense"}
VALID_STATUSES = {"pending", "running", "completed", "failed"}


class WashProgressUpdate(BaseModel):
    cycle_id: int
    status: str
    progress_pct: int  # 0–100


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

    cycle = WashingCycle(device_id=body.device_id, mode=body.mode, status="pending")
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    await manager.broadcast_to_device(
        str(body.device_id),
        {"type": "command", "command": "start_wash", "mode": body.mode, "cycle_id": cycle.id},
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
