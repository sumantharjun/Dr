from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.metrics import DeviceMetrics
from app.models.user import User
from app.schemas.metrics import MetricsCreate, MetricsOut, MetricsSummary
from app.utils.dependencies import get_current_user, get_device_by_api_key

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Baseline: a standard bottle sterilizer uses ~1.0 kWh and ~5L per cycle
BASELINE_POWER_KWH = 1.0
BASELINE_WATER_LITERS = 5.0


@router.post("/", response_model=MetricsOut, status_code=201)
def submit_metrics(
    body: MetricsCreate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Called by device firmware after each wash cycle to report actual consumption."""
    if device.id != body.device_id:
        raise HTTPException(status_code=403, detail="API key does not match device_id")
    record = DeviceMetrics(
        device_id=body.device_id,
        cycle_id=body.cycle_id,
        power_kwh=body.power_kwh,
        water_liters=body.water_liters,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/history", response_model=List[MetricsOut])
def metrics_history(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = [
        d.id for d in db.query(Device).filter(Device.user_id == current_user.id).all()
    ]
    return (
        db.query(DeviceMetrics)
        .filter(DeviceMetrics.device_id.in_(device_ids))
        .order_by(DeviceMetrics.recorded_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/summary", response_model=MetricsSummary)
def metrics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = [
        d.id for d in db.query(Device).filter(Device.user_id == current_user.id).all()
    ]
    row = db.query(
        func.count(DeviceMetrics.id).label("total_cycles"),
        func.coalesce(func.sum(DeviceMetrics.power_kwh), 0).label("total_power"),
        func.coalesce(func.sum(DeviceMetrics.water_liters), 0).label("total_water"),
    ).filter(DeviceMetrics.device_id.in_(device_ids)).one()

    total_cycles = row.total_cycles
    total_power = float(row.total_power)
    total_water = float(row.total_water)

    return MetricsSummary(
        total_cycles=total_cycles,
        total_power_kwh=round(total_power, 3),
        total_water_liters=round(total_water, 2),
        power_saved_kwh=round(max(0.0, total_cycles * BASELINE_POWER_KWH - total_power), 3),
        water_saved_liters=round(max(0.0, total_cycles * BASELINE_WATER_LITERS - total_water), 2),
    )
