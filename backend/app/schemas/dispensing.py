from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DispenseRequest(BaseModel):
    device_id: int
    temperature_c: float
    volume_ml: float


class DispenseLogOut(BaseModel):
    id: int
    device_id: int
    temperature_c: float
    volume_ml: float
    status: str
    progress_pct: int = 0
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
