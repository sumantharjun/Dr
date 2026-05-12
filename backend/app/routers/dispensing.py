from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.dispensing import MilkDispenseLog
from app.models.user import User
from app.schemas.dispensing import DispenseLogOut, DispenseRequest
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.utils.timezone import now_ist
from app.websocket.manager import manager

router = APIRouter(prefix="/dispensing", tags=["dispensing"])

VALID_DISPENSE_STATUSES = {"pending", "dispensing", "completed", "failed"}


class DispenseProgressUpdate(BaseModel):
    log_id: int
    status: str
    progress_pct: int  # 0–100


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

    log = MilkDispenseLog(
        device_id=body.device_id,
        temperature_c=body.temperature_c,
        volume_ml=body.volume_ml,
        status="pending",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    await manager.broadcast_to_device(
        str(body.device_id),
        {
            "type": "command",
            "command": "dispense",
            "temperature_c": body.temperature_c,
            "volume_ml": body.volume_ml,
            "log_id": log.id,
        },
    )
    return log


@router.post("/progress", response_model=DispenseLogOut)
async def update_dispense_progress(
    body: DispenseProgressUpdate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Device firmware calls this to report milk dispense progress."""
    if body.status not in VALID_DISPENSE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {sorted(VALID_DISPENSE_STATUSES)}")
    if not (0 <= body.progress_pct <= 100):
        raise HTTPException(status_code=400, detail="progress_pct must be 0–100")

    log = db.query(MilkDispenseLog).filter(
        MilkDispenseLog.id == body.log_id,
        MilkDispenseLog.device_id == device.id,
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Dispense log not found")

    log.status = body.status
    log.progress_pct = body.progress_pct
    if body.status == "completed":
        log.completed_at = now_ist()
        log.progress_pct = 100

    db.commit()
    db.refresh(log)

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
