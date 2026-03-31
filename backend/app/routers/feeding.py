from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feeding import FeedingLog
from app.models.user import User
from app.schemas.feeding import FeedingAnalytics, FeedingLogCreate, FeedingLogOut, FeedingSchedule
from app.services.feeding_analyzer import analyze_and_alert
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/feeding", tags=["feeding"])

WEIGHT_TO_ML_FACTOR = 0.97  # 100g ≈ 97ml


@router.get("/logs", response_model=List[FeedingLogOut])
def get_feeding_logs(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(FeedingLog)
        .filter(FeedingLog.user_id == current_user.id)
        .order_by(FeedingLog.feed_time.desc())
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
    milk_ml = body.milk_consumed_ml
    if milk_ml is None and body.weight_before_g is not None and body.weight_after_g is not None:
        weight_diff = body.weight_before_g - body.weight_after_g
        milk_ml = round(weight_diff * WEIGHT_TO_ML_FACTOR, 1)

    log = FeedingLog(
        user_id=current_user.id,
        device_id=body.device_id,
        feed_time=body.feed_time or datetime.utcnow(),
        weight_before_g=body.weight_before_g,
        weight_after_g=body.weight_after_g,
        milk_consumed_ml=milk_ml,
        method=body.method,
        notes=body.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # Run pattern analysis and auto-generate alerts if needed
    await analyze_and_alert(user_id=current_user.id, device_id=log.device_id, db=db)

    return log


@router.get("/analytics", response_model=List[FeedingAnalytics])
def get_analytics(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(FeedingLog.feed_time).label("date"),
            func.coalesce(func.sum(FeedingLog.milk_consumed_ml), 0).label("total_ml"),
            func.count(FeedingLog.id).label("feed_count"),
        )
        .filter(FeedingLog.user_id == current_user.id, FeedingLog.feed_time >= since)
        .group_by(func.date(FeedingLog.feed_time))
        .order_by(func.date(FeedingLog.feed_time))
        .all()
    )
    return [
        FeedingAnalytics(date=str(r.date), total_ml=float(r.total_ml), feed_count=r.feed_count)
        for r in rows
    ]


@router.get("/schedule", response_model=FeedingSchedule)
def get_schedule(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    last = (
        db.query(FeedingLog)
        .filter(FeedingLog.user_id == current_user.id)
        .order_by(FeedingLog.feed_time.desc())
        .first()
    )
    if not last:
        return FeedingSchedule(
            last_feed_time=None,
            minutes_since_last_feed=None,
            next_feed_due=None,
        )
    now = datetime.utcnow()
    minutes_since = int((now - last.feed_time).total_seconds() / 60)
    next_due = last.feed_time + timedelta(hours=3)
    return FeedingSchedule(
        last_feed_time=last.feed_time,
        minutes_since_last_feed=minutes_since,
        next_feed_due=next_due,
    )
