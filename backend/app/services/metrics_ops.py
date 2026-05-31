"""Shared helper for inserting a DeviceMetrics row.
Used by POST /metrics/ and the WebSocket `metric` event."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.metrics import DeviceMetrics


def record_metric(
    db: Session,
    device: Device,
    power_kwh: float,
    water_liters: float,
    cycle_id: Optional[int] = None,
    body_device_id: Optional[int] = None,
) -> DeviceMetrics:
    if body_device_id is not None and body_device_id != device.id:
        raise HTTPException(status_code=403, detail="API key does not match device_id")
    try:
        power_kwh = float(power_kwh)
        water_liters = float(water_liters)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="power_kwh and water_liters must be numeric")
    if power_kwh < 0 or water_liters < 0:
        raise HTTPException(status_code=400, detail="Metric values must be non-negative")

    record = DeviceMetrics(
        device_id=device.id,
        cycle_id=cycle_id,
        power_kwh=power_kwh,
        water_liters=water_liters,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
