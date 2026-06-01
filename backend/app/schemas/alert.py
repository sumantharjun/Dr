from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.services.alerts_catalog import VALID_DEVICE_ALERT_TYPES

VALID_SEVERITIES = {"info", "warning", "error", "critical"}


class AlertCreate(BaseModel):
    # Optional — derived from the X-Device-Api-Key. Validated against the key's
    # device if supplied (403 on mismatch); kept for backward compatibility.
    device_id: Optional[int] = None
    alert_type: str
    message: str
    severity: Optional[str] = None  # If None, server fills from catalog default

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        if v not in VALID_DEVICE_ALERT_TYPES:
            raise ValueError(
                "alert_type must be one of: "
                f"{sorted(VALID_DEVICE_ALERT_TYPES)} "
                "(server-generated types like 'feeding_reminder' are not accepted from devices)"
            )
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of: {sorted(VALID_SEVERITIES)}")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message must not be empty")
        if len(v) > 500:
            raise ValueError("message must be 500 characters or fewer")
        return v.strip()


class AlertOut(BaseModel):
    id: int
    device_id: int
    alert_type: str
    message: str
    severity: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
