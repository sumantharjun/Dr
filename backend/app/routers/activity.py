from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.activity import DeviceActivityLog
from app.models.device import Device
from app.models.user import User
from app.utils.dependencies import get_current_user, get_device_by_api_key

router = APIRouter(prefix="/activity", tags=["activity"])

# Closed set of event types — mirror of EVENT_META in
# frontend/src/pages/ActivityPage.tsx. Keep in sync.
VALID_EVENT_TYPES = frozenset({
    "wash_started",
    "wash_completed",
    "wash_failed",
    "dispense_started",
    "dispense_completed",
    "dispense_failed",
    "alert_triggered",
    "network_reconnected",
    "device_online",
    "device_offline",
    "feeding_logged",
})


class ActivityOut(BaseModel):
    id: int
    device_id: int
    event_type: str
    description: str | None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class ActivityCreate(BaseModel):
    device_id: int
    event_type: str
    description: str | None = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of: {sorted(VALID_EVENT_TYPES)}"
            )
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("description must be 500 characters or fewer")
        return v


@router.post("/", response_model=ActivityOut, status_code=201)
def log_activity(
    body: ActivityCreate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Device firmware calls this to log events (e.g. wash_started, network_reconnected)."""
    if device.id != body.device_id:
        raise HTTPException(status_code=403, detail="API key does not match device_id")
    log = DeviceActivityLog(
        device_id=body.device_id,
        event_type=body.event_type,
        description=body.description,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/{device_id}", response_model=List[ActivityOut])
def get_activity(
    device_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return (
        db.query(DeviceActivityLog)
        .filter(DeviceActivityLog.device_id == device_id)
        .order_by(DeviceActivityLog.recorded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
