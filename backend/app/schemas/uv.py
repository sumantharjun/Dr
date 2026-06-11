from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UvStart(BaseModel):
    """App-initiated UV sterilization. Set force=true to supersede a stuck cycle."""
    device_id: int
    force: bool = False


class DeviceUvStart(BaseModel):
    """Device-initiated UV (physical button). device_id derived from the API key."""
    force: bool = False


class UvProgressUpdate(BaseModel):
    uv_cycle_id: int
    status: str  # started | completed | failed


class UvCycleOut(BaseModel):
    id: int
    device_id: int
    status: str
    initiated_by: str = "app"
    ended_reason: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
