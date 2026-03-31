from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
        raise HTTPException(status_code=400, detail=f"Invalid mode. Choose from: {VALID_MODES}")

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
    cycle = db.query(WashingCycle).filter(
        WashingCycle.id == body.cycle_id,
        WashingCycle.device_id == device.id,
    ).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    cycle.status = body.status
    cycle.progress_pct = body.progress_pct
    if body.status == "completed":
        cycle.completed_at = datetime.utcnow()
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
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = [
        d.id for d in db.query(Device).filter(Device.user_id == current_user.id).all()
    ]
    return (
        db.query(WashingCycle)
        .filter(WashingCycle.device_id.in_(device_ids))
        .order_by(WashingCycle.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
