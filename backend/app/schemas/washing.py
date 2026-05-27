from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WashingStart(BaseModel):
    device_id: int
    mode: str  # full_cycle, wash, deep_clean, dispense


class DeviceWashingStart(BaseModel):
    """Device-initiated wash. device_id is derived from the API key."""
    mode: str


class WashingCycleOut(BaseModel):
    id: int
    device_id: int
    mode: str
    status: str
    progress_pct: int = 0
    initiated_by: str = "app"
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
