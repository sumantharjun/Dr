"""Shared helper for creating a device-emitted safety alert.
Used by POST /alerts/ and the WebSocket `alert` event."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.alert import DeviceAlert
from app.models.device import Device
from app.services.alerts_catalog import VALID_DEVICE_ALERT_TYPES, default_severity_for

VALID_SEVERITIES = {"info", "warning", "error", "critical"}


def create_device_alert(
    db: Session,
    device: Device,
    alert_type: str,
    message: str,
    severity: Optional[str] = None,
    body_device_id: Optional[int] = None,
) -> DeviceAlert:
    if body_device_id is not None and body_device_id != device.id:
        raise HTTPException(status_code=403, detail="API key does not match device_id")
    if alert_type not in VALID_DEVICE_ALERT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                "alert_type must be one of: "
                f"{sorted(VALID_DEVICE_ALERT_TYPES)} "
                "(server-generated types are not accepted from devices)"
            ),
        )
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")
    if len(message) > 500:
        raise HTTPException(status_code=422, detail="message must be 500 characters or fewer")
    if severity is not None and severity not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=422,
            detail=f"severity must be one of: {sorted(VALID_SEVERITIES)}",
        )

    severity = severity or default_severity_for(alert_type)
    alert = DeviceAlert(
        device_id=device.id,
        alert_type=alert_type,
        message=message.strip(),
        severity=severity,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
