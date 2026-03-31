from datetime import datetime
from pydantic import BaseModel


class AlertCreate(BaseModel):
    device_id: int
    alert_type: str
    message: str
    severity: str = "warning"


class AlertOut(BaseModel):
    id: int
    device_id: int
    alert_type: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
