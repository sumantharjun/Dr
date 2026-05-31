import logging
import logging.config
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import *  # noqa: F401,F403 — registers all ORM models with Base
from app.routers import auth, devices, feeding, washing, dispensing, alerts, orders, metrics, activity, baby
from app.utils.timezone import now_ist

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)


def _migrate_device_api_key_hash() -> None:
    """
    One-shot schema + data migration for device API key hashing.

    - Adds `api_key_hash VARCHAR(64)` to `devices` if missing.
    - Backfills the hash for any device that still has the legacy plaintext
      `api_key`, then nulls the plaintext column so no key is ever at rest.
    Idempotent — safe to run on every boot.
    """
    from sqlalchemy import inspect, text
    from app.utils.security import hash_api_key

    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("devices")}

    with engine.begin() as conn:
        if "api_key_hash" not in columns:
            conn.execute(text("ALTER TABLE devices ADD COLUMN api_key_hash VARCHAR(64) NULL"))
            try:
                conn.execute(text(
                    "CREATE UNIQUE INDEX ix_devices_api_key_hash ON devices(api_key_hash)"
                ))
            except Exception:
                # MySQL may complain if the index already exists; ignore.
                pass
            logger.info("Added api_key_hash column to devices table")

        rows = conn.execute(text(
            "SELECT id, api_key FROM devices WHERE api_key IS NOT NULL AND api_key_hash IS NULL"
        )).fetchall()
        for row in rows:
            digest = hash_api_key(row.api_key)
            conn.execute(
                text("UPDATE devices SET api_key_hash=:h, api_key=NULL WHERE id=:i"),
                {"h": digest, "i": row.id},
            )
        if rows:
            logger.info("Backfilled api_key_hash for %d device(s) and cleared plaintext", len(rows))


try:
    _migrate_device_api_key_hash()
except Exception:
    logging.getLogger(__name__).exception("Device API key hash migration failed")


def _migrate_initiated_by() -> None:
    """
    Idempotent: add `initiated_by` ENUM('app','device') column to both
    washing_cycles and milk_dispense_logs, defaulting to 'app' for any
    rows that pre-date the device-initiated endpoints.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    for table in ("washing_cycles", "milk_dispense_logs"):
        columns = {c["name"] for c in inspector.get_columns(table)}
        if "initiated_by" in columns:
            continue
        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {table} "
                f"ADD COLUMN initiated_by ENUM('app','device') NOT NULL DEFAULT 'app'"
            ))
        logger.info("Added initiated_by column to %s", table)


try:
    _migrate_initiated_by()
except Exception:
    logging.getLogger(__name__).exception("initiated_by migration failed")


def _migrate_ended_reason() -> None:
    """
    Idempotent: add a nullable `ended_reason` ENUM column to both
    washing_cycles and milk_dispense_logs. Disambiguates the overloaded
    `failed` status (real failure vs. cancel vs. timeout vs. force-supersede).
    Existing rows are left NULL — we can't retroactively know why they ended.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    for table in ("washing_cycles", "milk_dispense_logs"):
        columns = {c["name"] for c in inspector.get_columns(table)}
        if "ended_reason" in columns:
            continue
        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN ended_reason "
                f"ENUM('completed','cancelled','timed_out','superseded','failed') NULL"
            ))
        logger.info("Added ended_reason column to %s", table)


try:
    _migrate_ended_reason()
except Exception:
    logging.getLogger(__name__).exception("ended_reason migration failed")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Smart Baby Feeding API",
    description="Backend API for the Smart Baby Feeding & Bottle Care Monitoring System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Api-Key"],
)


# ---------------------------------------------------------------------------
# Security headers (set at the app layer so they apply regardless of which
# reverse proxy is in front of us).
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    return response

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(feeding.router)
app.include_router(washing.router)
app.include_router(dispensing.router)
app.include_router(alerts.router)
app.include_router(orders.router)
app.include_router(metrics.router)
app.include_router(activity.router)
app.include_router(baby.router)

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


# ---------------------------------------------------------------------------
# Scheduled job: feeding reminders (every 5 minutes)
# Creates a reminder alert when a user's feed is overdue (> 3 h).
# Deduplicates by skipping if an unread reminder already exists for the device.
# ---------------------------------------------------------------------------
async def check_feeding_reminders() -> None:
    from app.models.alert import DeviceAlert
    from app.models.device import Device
    from app.models.feeding import FeedingLog
    from app.websocket.manager import manager

    db = SessionLocal()
    try:
        now = now_ist()
        user_ids = [r[0] for r in db.query(FeedingLog.user_id).distinct().all()]

        for user_id in user_ids:
            last = (
                db.query(FeedingLog)
                .filter(FeedingLog.user_id == user_id)
                .order_by(FeedingLog.feed_time.desc())
                .first()
            )
            if not last:
                continue
            if (now - last.feed_time) < timedelta(hours=3):
                continue

            user_devices = db.query(Device).filter(Device.user_id == user_id).all()
            if not user_devices:
                continue

            minutes_elapsed = int((now - last.feed_time).total_seconds() / 60)
            msg = (
                f"Feeding reminder: {minutes_elapsed} minutes since last feed. "
                "Please feed the baby soon."
            )

            for device in user_devices:
                # Skip if an unread reminder already exists — avoid spamming
                already_unread = (
                    db.query(DeviceAlert)
                    .filter(
                        DeviceAlert.device_id == device.id,
                        DeviceAlert.alert_type == "feeding_reminder",
                        DeviceAlert.is_read == False,  # noqa: E712
                    )
                    .first()
                )
                if already_unread:
                    continue

                alert = DeviceAlert(
                    device_id=device.id,
                    alert_type="feeding_reminder",
                    message=msg,
                    severity="warning",
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)

                await manager.broadcast_to_device(
                    str(device.id),
                    {
                        "type": "alert",
                        "alert_type": "feeding_reminder",
                        "message": msg,
                        "severity": "warning",
                    },
                )
                logger.info("Feeding reminder sent for user %s, device %s", user_id, device.id)

    except Exception:
        logger.exception("Error in check_feeding_reminders job")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduled job: auto-fail stale wash cycles + dispenses (every 5 minutes)
#
# Prevents the "stuck pending/running" state — if firmware crashes mid-cycle
# or never sends a completion packet, the row would otherwise block the 409
# concurrency guard on /washing/device-start indefinitely. After the timeout
# the row is force-flipped to `failed` so the next device-start call can
# proceed without `force=true`.
# ---------------------------------------------------------------------------
WASH_STALE_TIMEOUT_MIN = 60     # wash cycles longer than this are presumed stuck
DISPENSE_STALE_TIMEOUT_MIN = 15  # dispense ops are short — much tighter window


def auto_fail_stale_operations() -> None:
    from sqlalchemy import update
    from app.models.washing import WashingCycle
    from app.models.dispensing import MilkDispenseLog

    db = SessionLocal()
    try:
        now = now_ist()
        wash_cutoff = now - timedelta(minutes=WASH_STALE_TIMEOUT_MIN)
        disp_cutoff = now - timedelta(minutes=DISPENSE_STALE_TIMEOUT_MIN)

        # SELECT first purely for per-row logging, then recover with a single
        # atomic conditional UPDATE. The UPDATE re-checks the status filter at
        # write time, so any row a concurrent progress packet drove terminal
        # between this SELECT and the UPDATE is excluded (no lost update).
        stale_cycles = (
            db.query(WashingCycle.id, WashingCycle.started_at)
            .filter(
                WashingCycle.status.in_(["pending", "running"]),
                WashingCycle.started_at < wash_cutoff,
            )
            .all()
        )
        for cid, started_at in stale_cycles:
            logger.info("Auto-failing stale wash cycle id=%s (started_at=%s)", cid, started_at)

        wash_result = db.execute(
            update(WashingCycle)
            .where(
                WashingCycle.status.in_(["pending", "running"]),
                WashingCycle.started_at < wash_cutoff,
            )
            .values(status="failed", ended_reason="timed_out", completed_at=now)
            .execution_options(synchronize_session=False)
        )

        stale_dispenses = (
            db.query(MilkDispenseLog.id, MilkDispenseLog.created_at)
            .filter(
                MilkDispenseLog.status.in_(["pending", "dispensing"]),
                MilkDispenseLog.created_at < disp_cutoff,
            )
            .all()
        )
        for did, created_at in stale_dispenses:
            logger.info("Auto-failing stale dispense log id=%s (created_at=%s)", did, created_at)

        disp_result = db.execute(
            update(MilkDispenseLog)
            .where(
                MilkDispenseLog.status.in_(["pending", "dispensing"]),
                MilkDispenseLog.created_at < disp_cutoff,
            )
            .values(status="failed", ended_reason="timed_out", completed_at=now)
            .execution_options(synchronize_session=False)
        )

        db.commit()
        if wash_result.rowcount or disp_result.rowcount:
            logger.info(
                "Auto-fail sweep: %s wash cycle(s), %s dispense(s) recovered",
                wash_result.rowcount, disp_result.rowcount,
            )
    except Exception:
        logger.exception("auto_fail_stale_operations failed")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduled job: order auto-progression (every 2 minutes)
# pending → confirmed  at  2 min from creation
# confirmed → shipped  at 10 min from creation
# shipped → delivered  at 30 min from creation
# ---------------------------------------------------------------------------
def progress_orders() -> None:
    from app.models.order import Order

    db = SessionLocal()
    try:
        now = now_ist()

        pending = db.query(Order).filter(Order.status == "pending").all()
        for order in pending:
            if (now - order.created_at) >= timedelta(minutes=2):
                order.status = "confirmed"
                logger.info("Order %s confirmed", order.id)

        confirmed = db.query(Order).filter(Order.status == "confirmed").all()
        for order in confirmed:
            if (now - order.created_at) >= timedelta(minutes=10):
                order.status = "shipped"
                logger.info("Order %s shipped", order.id)

        shipped = db.query(Order).filter(Order.status == "shipped").all()
        for order in shipped:
            if (now - order.created_at) >= timedelta(minutes=30):
                order.status = "delivered"
                logger.info("Order %s delivered", order.id)

        db.commit()
    except Exception:
        logger.exception("Error in progress_orders job")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
def seed_products():
    db = SessionLocal()
    try:
        from app.models.order import Product
        if db.query(Product).count() == 0:
            products = [
                Product(name="Baby Bottle Cleaning Liquid 500ml", description="Specially formulated cleaning liquid for baby bottles.", price=299.0, category="cleaning", stock=100),
                Product(name="Baby Bottle Cleaning Liquid 1L", description="Economy size cleaning liquid for baby bottles.", price=499.0, category="cleaning", stock=50),
                Product(name="Baby Bottle 240ml (Pack of 3)", description="BPA-free wide-neck baby bottles.", price=699.0, category="bottles", stock=80),
                Product(name="Bottle Brush Set", description="Soft-bristle brush set for manual cleaning.", price=249.0, category="accessories", stock=60),
                Product(name="Sterilization Pods (50 pack)", description="Effervescent sterilization pods.", price=349.0, category="cleaning", stock=120),
                Product(name="Baby Bottle Nipples Size M (4 pack)", description="Medium-flow silicone nipples.", price=199.0, category="accessories", stock=90),
            ]
            db.add_all(products)
            db.commit()
            logger.info("Seeded %d products", len(products))
    except Exception:
        logger.exception("Failed to seed products")
    finally:
        db.close()


@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(
        check_feeding_reminders, "interval", minutes=5,
        id="feeding_reminders", replace_existing=True,
    )
    scheduler.add_job(
        progress_orders, "interval", minutes=2,
        id="order_progression", replace_existing=True,
    )
    scheduler.add_job(
        auto_fail_stale_operations, "interval", minutes=2,
        id="auto_fail_stale_ops", replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


@app.on_event("shutdown")
async def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/health/scheduler", tags=["health"])
def scheduler_health():
    jobs = scheduler.get_jobs()
    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": [{"id": j.id, "next_run": str(j.next_run_time)} for j in jobs],
    }
