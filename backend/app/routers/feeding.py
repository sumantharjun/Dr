from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.baby import Baby
from app.models.device import Device
from app.models.feeding import FeedingLog
from app.models.user import User
from app.schemas.feeding import (
    VALID_MILK_TYPES,
    FeedingAnalytics,
    FeedingLogCreate,
    FeedingLogOut,
    FeedingSchedule,
)
from app.services.feeding_analyzer import analyze_and_alert
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.utils.timezone import now_ist
from app.websocket.manager import manager

router = APIRouter(prefix="/feeding", tags=["feeding"])

WEIGHT_TO_ML_FACTOR = 0.97  # 100g ≈ 97ml per BRD spec


def _owned_baby(baby_id: int, user: User, db: Session) -> Baby:
    """404 unless this baby belongs to the caller. Scoped by user_id as well as
    id so a guessed id from another account looks the same as a missing one."""
    baby = db.query(Baby).filter(Baby.id == baby_id, Baby.user_id == user.id).first()
    if not baby:
        raise HTTPException(status_code=404, detail="Baby not found")
    return baby


@router.get("/logs", response_model=List[FeedingLogOut])
def get_feeding_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    baby_id: Optional[int] = Query(None, description="Restrict to one baby"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Feeding history. Omit `baby_id` for every baby on the account (which is
    also what a single-baby client gets by not sending it)."""
    q = db.query(FeedingLog).filter(FeedingLog.user_id == current_user.id)
    if baby_id is not None:
        _owned_baby(baby_id, current_user, db)
        q = q.filter(FeedingLog.baby_id == baby_id)
    return (
        q.order_by(FeedingLog.feed_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/logs", response_model=FeedingLogOut, status_code=201)
async def create_feeding_log(
    body: FeedingLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # If a device is referenced, it must belong to the caller. Otherwise a user
    # could attach feeding logs to (and trigger alerts on) another user's
    # device by guessing its id. device_id stays optional for manual feeds.
    _owned_baby(body.baby_id, current_user, db)

    if body.device_id is not None:
        device = db.query(Device).filter(
            Device.id == body.device_id, Device.user_id == current_user.id
        ).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

    milk_ml = body.milk_consumed_ml

    if milk_ml is None and body.weight_before_g is not None and body.weight_after_g is not None:
        weight_diff = body.weight_before_g - body.weight_after_g
        if weight_diff < 0:
            raise HTTPException(
                status_code=400,
                detail="weight_before_g must be greater than weight_after_g",
            )
        milk_ml = round(weight_diff * WEIGHT_TO_ML_FACTOR, 1)

    log = FeedingLog(
        user_id=current_user.id,
        device_id=body.device_id,
        baby_id=body.baby_id,
        feed_time=body.feed_time or now_ist(),
        weight_before_g=body.weight_before_g,
        weight_after_g=body.weight_after_g,
        milk_consumed_ml=milk_ml,
        method=body.method,
        milk_type=body.milk_type,
        notes=body.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    await analyze_and_alert(
        user_id=current_user.id, baby_id=log.baby_id, device_id=log.device_id, db=db
    )

    return log


class DeviceFeedReport(BaseModel):
    weight_before_g: float
    weight_after_g: float
    feed_time: Optional[datetime] = None
    # Optional: the scale measures a weight delta and can't tell what's in the
    # bottle. Firmware that does know (e.g. the feed followed a formula
    # dispense) should send it; otherwise the log stays untyped rather than
    # guessing.
    milk_type: Optional[str] = None

    @field_validator("milk_type")
    @classmethod
    def validate_milk_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_MILK_TYPES:
            raise ValueError(f"Milk type must be one of: {sorted(VALID_MILK_TYPES)}")
        return v


@router.post("/device-report", response_model=FeedingLogOut, status_code=201)
async def device_feed_report(
    body: DeviceFeedReport,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """
    Device scale POSTs weight readings after each feeding session.
    Requires X-Device-Api-Key header. Milk consumed is calculated from weight diff.
    """
    if body.weight_before_g < body.weight_after_g:
        raise HTTPException(
            status_code=400,
            detail="weight_before_g must be greater than or equal to weight_after_g",
        )
    if body.weight_before_g < 0 or body.weight_after_g < 0:
        raise HTTPException(status_code=400, detail="Weight values must be non-negative")

    weight_diff = body.weight_before_g - body.weight_after_g
    milk_ml = round(weight_diff * WEIGHT_TO_ML_FACTOR, 1)

    log = FeedingLog(
        user_id=device.user_id,
        device_id=device.id,
        # The scale cannot know which baby it weighed, so we attribute to
        # whichever the app last marked as "feeding now". NULL when unset —
        # unattributed is honest, guessing is not.
        baby_id=device.active_baby_id,
        feed_time=body.feed_time or now_ist(),
        weight_before_g=body.weight_before_g,
        weight_after_g=body.weight_after_g,
        milk_consumed_ml=milk_ml,
        method="device",
        milk_type=body.milk_type,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    await analyze_and_alert(
        user_id=device.user_id, baby_id=log.baby_id, device_id=device.id, db=db
    )

    # Notify connected app clients so they can refresh the feeding page in real time
    await manager.broadcast_to_device(
        str(device.id),
        {"type": "feeding_logged", "log_id": log.id, "milk_consumed_ml": milk_ml},
    )

    return log


@router.get("/analytics", response_model=List[FeedingAnalytics])
def get_analytics(
    days: int = Query(7, ge=1, le=30),
    baby_id: Optional[int] = Query(None, description="Restrict to one baby"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Daily intake and feed counts. Pass `baby_id` for one baby — without it
    the totals combine every baby on the account, which is only meaningful when
    there is one."""
    since = now_ist() - timedelta(days=days)
    q = (
        db.query(
            func.date(FeedingLog.feed_time).label("date"),
            func.coalesce(func.sum(FeedingLog.milk_consumed_ml), 0).label("total_ml"),
            func.count(FeedingLog.id).label("feed_count"),
        )
        .filter(FeedingLog.user_id == current_user.id, FeedingLog.feed_time >= since)
    )
    if baby_id is not None:
        _owned_baby(baby_id, current_user, db)
        q = q.filter(FeedingLog.baby_id == baby_id)
    rows = (
        q.group_by(func.date(FeedingLog.feed_time))
        .order_by(func.date(FeedingLog.feed_time))
        .all()
    )
    return [
        FeedingAnalytics(date=str(r.date), total_ml=float(r.total_ml), feed_count=r.feed_count)
        for r in rows
    ]


@router.get("/schedule", response_model=FeedingSchedule)
def get_schedule(
    baby_id: Optional[int] = Query(None, description="Whose schedule to compute"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Last feed, elapsed time and next due.

    `baby_id` matters most here: twins are on two independent schedules, and a
    combined "next feed due" describes neither of them. Without it the answer
    spans every baby on the account.
    """
    q = db.query(FeedingLog).filter(FeedingLog.user_id == current_user.id)
    if baby_id is not None:
        _owned_baby(baby_id, current_user, db)
        q = q.filter(FeedingLog.baby_id == baby_id)
    last = q.order_by(FeedingLog.feed_time.desc()).first()
    if not last:
        return FeedingSchedule(
            last_feed_time=None,
            minutes_since_last_feed=None,
            next_feed_due=None,
        )
    now = now_ist()
    minutes_since = int((now - last.feed_time).total_seconds() / 60)
    next_due = last.feed_time + timedelta(hours=3)
    return FeedingSchedule(
        last_feed_time=last.feed_time,
        minutes_since_last_feed=minutes_since,
        next_feed_due=next_due,
    )
