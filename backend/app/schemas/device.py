from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DeviceCreate(BaseModel):
    device_name: str
    mac_address: str
    wifi_ssid: Optional[str] = None


class DeviceOut(BaseModel):
    id: int
    device_name: str
    mac_address: str
    wifi_ssid: Optional[str]
    status: str
    last_seen: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceWithKeyOut(DeviceOut):
    """Returned only at registration time — includes api_key."""
    api_key: str


class DeviceCommand(BaseModel):
    command: str
    payload: Optional[dict] = None
