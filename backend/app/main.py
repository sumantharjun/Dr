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


def _migrate_firmware_spec() -> None:
    """
    Idempotent migrations for the firmware-team spec changes:
      - washing_cycles.mode ENUM widened to the superset (adds steam_dry, dry;
        keeps legacy wash/deep_clean/dispense so historical rows stay valid).
      - milk_dispense_logs.scoop_number INT NULL added.
      - device_metrics power_kwh / water_liters made nullable (firmware has no
        flow/energy meters, so the API no longer requires them).
    Each step is guarded so it only runs when needed. No-ops on SQLite (which
    lacks MODIFY COLUMN / ENUM) are caught per-step.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    is_mysql = engine.dialect.name == "mysql"

    # 1) Update washing_cycles.mode ENUM to the allowed set {full_cycle,
    #    steam_dry, dry}, dropping the removed modes (wash, deep_clean,
    #    dispense). MySQL-only — ENUM/MODIFY are MySQL syntax; on SQLite the
    #    column is created from the model definition, so nothing to do.
    #    NOTE: narrowing the ENUM is destructive — any existing rows still on a
    #    removed mode (wash/deep_clean/dispense) will be set to '' by MySQL.
    if is_mysql:
        try:
            mode_col = next(
                (c for c in inspector.get_columns("washing_cycles") if c["name"] == "mode"),
                None,
            )
            type_str = str(mode_col["type"]).lower() if mode_col else ""
            needs = mode_col is not None and (
                "steam_dry" not in type_str   # pre-firmware enum: add new modes
                or "deep_clean" in type_str   # still carries removed modes
                or "dispense" in type_str
                or "wash" in type_str
            )
            if needs:
                with engine.begin() as conn:
                    conn.execute(text(
                        "ALTER TABLE washing_cycles MODIFY COLUMN mode "
                        "ENUM('full_cycle','steam_dry','dry') NOT NULL"
                    ))
                logger.info("Updated washing_cycles.mode ENUM to {full_cycle, steam_dry, dry}")
        except Exception:
            logger.exception("mode ENUM migration failed/skipped")

    # 2) Add milk_dispense_logs.scoop_number (portable ADD COLUMN).
    try:
        cols = {c["name"] for c in inspector.get_columns("milk_dispense_logs")}
        if "scoop_number" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE milk_dispense_logs ADD COLUMN scoop_number INT NULL"))
            logger.info("Added scoop_number column to milk_dispense_logs")
    except Exception:
        logger.exception("scoop_number migration failed/skipped")

    # 3) Make device_metrics power_kwh / water_liters nullable (MySQL-only;
    #    MODIFY COLUMN is MySQL syntax).
    if is_mysql:
        try:
            for col in ("power_kwh", "water_liters"):
                meta = next(
                    (c for c in inspector.get_columns("device_metrics") if c["name"] == col),
                    None,
                )
                if meta is not None and not meta["nullable"]:
                    with engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE device_metrics MODIFY COLUMN {col} FLOAT NULL"))
                    logger.info("Made device_metrics.%s nullable", col)
        except Exception:
            logger.exception("device_metrics nullable migration failed/skipped")


try:
    _migrate_firmware_spec()
except Exception:
    logging.getLogger(__name__).exception("firmware_spec migration failed")

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
    """
    Sync the product catalog (upsert by name) on startup.

    PLACEHOLDER CATALOG: the client's real product images and costs haven't
    been received yet. Prices are realistic current Indian-market figures
    (INR) used as placeholders, and images are local bundled SVG placeholders
    under frontend/public/products/. Replace both when the real catalog lands.

    Upsert (rather than insert-only) so updated prices/images also apply to a
    DB that was already seeded with the old values; existing stock is preserved.
    """
    db = SessionLocal()
    try:
        from app.models.order import Product, OrderItem

        # Renamed products: upsert-by-name can't see a rename, so map any
        # superseded name to its current one and fix it up first. We rename the
        # existing row in place (preserving its id + order history) rather than
        # leaving a stale duplicate behind.
        renames = {"Sterilization Tablets (50 pack)": "Sterilization Pods (50 pack)"}
        for old_name, new_name in renames.items():
            old = db.query(Product).filter(Product.name == old_name).first()
            if not old:
                continue
            if db.query(Product).filter(Product.name == new_name).first() is None:
                old.name = new_name  # rename in place
            elif not db.query(OrderItem).filter(OrderItem.product_id == old.id).first():
                db.delete(old)        # a duplicate already exists & old one is unused
            db.flush()

        catalog = [
            {"name": "Baby Bottle Cleaning Liquid 500ml", "description": "Specially formulated liquid cleanser for baby bottles, teats & accessories.", "price": 275.0, "category": "cleaning", "stock": 100, "image_url": "/products/cleaning-liquid-500ml.svg"},
            {"name": "Baby Bottle Cleaning Liquid 1L", "description": "Economy 1L bottle & accessory cleanser.", "price": 485.0, "category": "cleaning", "stock": 50, "image_url": "/products/cleaning-liquid-1l.svg"},
            {"name": "Baby Bottle 240ml (Pack of 3)", "description": "BPA-free wide-neck baby feeding bottles, 240ml.", "price": 599.0, "category": "bottles", "stock": 80, "image_url": "/products/baby_bottle.png"},
            {"name": "Bottle Brush Set", "description": "Soft-bristle bottle & nipple brush set for manual cleaning.", "price": 249.0, "category": "accessories", "stock": 60, "image_url": "/products/bottle-brush-set.svg"},
            {"name": "Sterilization Pods (50 pack)", "description": "Effervescent sterilizing pods, 50 pack.", "price": 399.0, "category": "cleaning", "stock": 120, "image_url": "/products/sterilization-pods.svg"},
            {"name": "Baby Bottle Nipples Size M (4 pack)", "description": "Medium-flow anti-colic silicone nipples, 4 pack.", "price": 349.0, "category": "accessories", "stock": 90, "image_url": "/products/nipples-m-4pack.svg"},
        ]
        for item in catalog:
            existing = db.query(Product).filter(Product.name == item["name"]).first()
            if existing:
                # Refresh catalog fields; leave on-hand stock untouched.
                existing.description = item["description"]
                existing.price = item["price"]
                existing.category = item["category"]
                existing.image_url = item["image_url"]
            else:
                db.add(Product(**item))
        db.commit()
        logger.info("Synced %d catalog products", len(catalog))
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
