import logging
import logging.config
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import *  # noqa: F401,F403 — registers all ORM models with Base
from app.routers import auth, devices, feeding, washing, dispensing, alerts, orders, metrics, activity
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

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(feeding.router)
app.include_router(washing.router)
app.include_router(dispensing.router)
app.include_router(alerts.router)
app.include_router(orders.router)
app.include_router(metrics.router)
app.include_router(activity.router)

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
                Product(name="Sterilization Tablets (50 pack)", description="Effervescent sterilization tablets.", price=349.0, category="cleaning", stock=120),
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
