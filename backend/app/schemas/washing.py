from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WashingStart(BaseModel):
    device_id: int
    mode: str  # full_cycle, wash, deep_clean, dispense


class WashingCycleOut(BaseModel):
    id: int
    device_id: int
    mode: str
    status: str
    progress_pct: int = 0
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
