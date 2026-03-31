from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.dispensing import MilkDispenseLog
from app.models.user import User
from app.schemas.dispensing import DispenseLogOut, DispenseRequest
from app.utils.dependencies import get_current_user
from app.websocket.manager import manager

router = APIRouter(prefix="/dispensing", tags=["dispensing"])


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


@router.get("/history", response_model=List[DispenseLogOut])
def dispense_history(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = [
        d.id for d in db.query(Device).filter(Device.user_id == current_user.id).all()
    ]
    return (
        db.query(MilkDispenseLog)
        .filter(MilkDispenseLog.device_id.in_(device_ids))
        .order_by(MilkDispenseLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
