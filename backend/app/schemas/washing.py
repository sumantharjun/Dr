from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WashingStart(BaseModel):
    device_id: int
    mode: str  # full_cycle, wash, deep_clean, dispense
    # Set force=true to supersede a cycle still stuck pending/running (it will
    # be marked failed with ended_reason='superseded'). Lets an app user
    # recover from a stuck state without waiting for the timeout sweep.
    force: bool = False


class DeviceWashingStart(BaseModel):
    """Device-initiated wash. device_id is derived from the API key.

    Set `force=true` to abandon any cycle that's still pending/running on this
    device (the prior cycle will be marked `failed` with a note explaining it
    was force-superseded). Use this when the firmware is recovering from a
    crash / reboot / dropped connection and knows the hardware isn't actually
    running anything anymore.
    """
    mode: str
    force: bool = False


class WashingCycleOut(BaseModel):
    id: int
    device_id: int
    mode: str
    status: str
    progress_pct: int = 0
    initiated_by: str = "app"
    ended_reason: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
