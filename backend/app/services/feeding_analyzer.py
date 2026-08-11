"""
Checks feeding logs for abnormal patterns and auto-creates DeviceAlerts.

Rules (based on standard newborn guidelines):
  1. OVERDUE     — gap since last feed > 6 hours
  2. LOW_INTAKE  — milk consumed < 50 ml per feed (for device/bottle feeds)
  3. FREQUENT    — more than 5 feeds in the last 3 hours

All three are evaluated PER BABY. They used to run across the whole account,
which was fine with one baby and actively dangerous with twins: a well-fed twin
kept the pooled "last feed" recent, so a genuinely overdue sibling never
triggered an alert. Alert messages name the baby for the same reason — with two
babies, "no feeding recorded for over 6 hours" is not actionable on its own.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.utils.timezone import now_ist

from app.models.alert import DeviceAlert
from app.models.baby import Baby
from app.models.feeding import FeedingLog
from app.websocket.manager import manager


async def analyze_and_alert(
    user_id: int, device_id: int | None, db: Session, baby_id: int | None = None
) -> None:
    """
    Evaluate the feeding rules for one baby and raise alerts.

    `baby_id` is None only for feeds we could not attribute (a device report
    before "feeding now" was set). Analysing those against the whole account
    would reintroduce the pooling bug, so they are skipped — an unattributed
    feed can't tell us anything reliable about any particular baby.
    """
    if baby_id is None:
        return

    now = now_ist()
    baby = db.query(Baby).filter(Baby.id == baby_id).first()
    who = baby.name if baby else "your baby"

    # -- Rule 1: Overdue feed --
    last = (
        db.query(FeedingLog)
        .filter(FeedingLog.user_id == user_id, FeedingLog.baby_id == baby_id)
        .order_by(FeedingLog.feed_time.desc())
        .first()
    )
    if last and (now - last.feed_time) > timedelta(hours=6):
        await _create_alert(
            db=db,
            device_id=device_id,
            baby_id=baby_id,
            alert_type="overdue_feed",
            message=f"{who}: no feeding recorded for over 6 hours. Last feed: {last.feed_time.strftime('%H:%M')}.",
            severity="warning",
        )

    # -- Rule 2: Low intake on the most recent feed --
    if last and last.milk_consumed_ml is not None and last.method in ("device", "manual"):
        if last.milk_consumed_ml < 50:
            await _create_alert(
                db=db,
                device_id=device_id,
                baby_id=baby_id,
                alert_type="low_intake",
                message=f"{who}: low milk intake detected — {last.milk_consumed_ml:.0f} ml (expected ≥50 ml).",
                severity="warning",
            )

    # -- Rule 3: Too-frequent feeding --
    three_hours_ago = now - timedelta(hours=3)
    recent_count = (
        db.query(FeedingLog)
        .filter(
            FeedingLog.user_id == user_id,
            FeedingLog.baby_id == baby_id,
            FeedingLog.feed_time >= three_hours_ago,
        )
        .count()
    )
    if recent_count > 5:
        await _create_alert(
            db=db,
            device_id=device_id,
            baby_id=baby_id,
            alert_type="frequent_feeding",
            message=f"{who}: {recent_count} feeds in the last 3 hours — unusually frequent. Please consult a paediatrician.",
            severity="error",
        )


async def _create_alert(
    db: Session,
    device_id: int | None,
    alert_type: str,
    message: str,
    severity: str,
    baby_id: int | None = None,
) -> None:
    if device_id is None:
        return  # Can't create device alert without a device

    # Avoid duplicate alerts of the same type within the last 2 hours — scoped
    # per baby, so one twin's alert can no longer suppress the other's inside
    # that window. alert_type itself stays a plain catalog key, because both
    # alerts_catalog.py and the frontend's alertMeta() look it up exactly.
    two_hours_ago = now_ist() - timedelta(hours=2)
    existing = (
        db.query(DeviceAlert)
        .filter(
            DeviceAlert.device_id == device_id,
            DeviceAlert.alert_type == alert_type,
            DeviceAlert.baby_id == baby_id,
            DeviceAlert.created_at >= two_hours_ago,
        )
        .first()
    )
    if existing:
        return

    alert = DeviceAlert(
        device_id=device_id,
        baby_id=baby_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    await manager.broadcast_to_device(
        str(device_id),
        {
            "type": "alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
        },
    )
