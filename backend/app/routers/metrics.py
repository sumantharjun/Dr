from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.metrics import DeviceMetrics
from app.models.washing import WashingCycle
from app.models.user import User
from app.schemas.metrics import MetricsCreate, MetricsOut, MetricsSummary
from app.services.metrics_ops import record_metric
from app.utils.dependencies import get_current_user, get_device_by_api_key

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Savings are ESTIMATED from completed-cycle count, because the firmware has no
# flow/energy meters to report actual consumption. Per completed cycle we assume
# a standard machine uses BASELINE_* while the smart device uses DEVICE_EST_*;
# the difference is the per-cycle saving. These are assumptions — tune here.
BASELINE_POWER_KWH = 1.0       # standard machine, per cycle
BASELINE_WATER_LITERS = 5.0
DEVICE_EST_POWER_KWH = 0.6     # smart device estimate, per cycle
DEVICE_EST_WATER_LITERS = 3.0
POWER_SAVED_PER_CYCLE = max(0.0, BASELINE_POWER_KWH - DEVICE_EST_POWER_KWH)
WATER_SAVED_PER_CYCLE = max(0.0, BASELINE_WATER_LITERS - DEVICE_EST_WATER_LITERS)


@router.post("/", response_model=MetricsOut, status_code=201)
def submit_metrics(
    body: MetricsCreate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Called by device firmware after each wash cycle to report actual consumption."""
    return record_metric(
        db=db,
        device=device,
        power_kwh=body.power_kwh,
        water_liters=body.water_liters,
        cycle_id=body.cycle_id,
        body_device_id=body.device_id,
    )


@router.get("/history", response_model=List[MetricsOut])
def metrics_history(
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(DeviceMetrics)
        .join(Device, DeviceMetrics.device_id == Device.id)
        .filter(Device.user_id == current_user.id)
        .order_by(DeviceMetrics.recorded_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/summary", response_model=MetricsSummary)
def metrics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = [d.id for d in db.query(Device).filter(Device.user_id == current_user.id).all()]

    # Estimate from the number of COMPLETED wash cycles — the firmware can't
    # report actual power/water consumption (no meters). Each completed cycle
    # contributes the assumed per-cycle consumption and saving.
    total_cycles = (
        db.query(func.count(WashingCycle.id))
        .filter(
            WashingCycle.device_id.in_(device_ids),
            WashingCycle.status == "completed",
        )
        .scalar()
        or 0
    )

    return MetricsSummary(
        total_cycles=total_cycles,
        total_power_kwh=round(total_cycles * DEVICE_EST_POWER_KWH, 3),
        total_water_liters=round(total_cycles * DEVICE_EST_WATER_LITERS, 2),
        power_saved_kwh=round(total_cycles * POWER_SAVED_PER_CYCLE, 3),
        water_saved_liters=round(total_cycles * WATER_SAVED_PER_CYCLE, 2),
    )
