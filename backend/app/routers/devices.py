import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.pending_command import PendingCommand
from app.models.user import User
from app.schemas.device import DeviceCommand, DeviceCreate, DeviceOut, DeviceWithKeyOut
from sqlalchemy import or_

from app.services.alerts_ops import create_device_alert
from app.services.commands import dispatch_command
from app.services.dispensing_ops import apply_dispense_progress
from app.services.metrics_ops import record_metric
from app.services.uv_ops import apply_uv_progress
from app.services.washing_ops import apply_wash_progress
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.utils.security import decode_token, hash_api_key
from app.utils.timezone import now_ist
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])

VALID_COMMANDS = {"start_wash", "stop_wash", "dispense", "stop_dispense", "uv_start", "uv_stop", "reboot", "status"}
ALLOWED_WS_EVENT_TYPES = {"wash_progress", "dispense_progress", "uv_progress", "alert", "status", "metric", "weight_report"}
# Subset of ALLOWED_WS_EVENT_TYPES that persists to the database. Anything not
# in this set is treated as ephemeral (live-only) and only broadcast.
PERSISTABLE_WS_EVENT_TYPES = {"wash_progress", "dispense_progress", "uv_progress", "alert", "metric"}
WS_IDLE_TIMEOUT = 300  # 5 min — device must send something or server pings


def _persist_ws_event(
    db: Session,
    device: Device,
    event: dict,
) -> tuple[bool, Optional[dict]]:
    """
    Persist a device-originated WebSocket event using the same helpers that
    back the HTTP routes. Returns (ok, error_frame).

    - ok=True, error_frame=None  → caller should broadcast the event
    - ok=False, error_frame=dict → caller should send the error frame back to
      the originating socket and SKIP the broadcast (don't propagate
      garbage to app clients)
    - For event types not in PERSISTABLE_WS_EVENT_TYPES, always returns
      (True, None) — they're ephemeral and only need broadcasting.
    """
    etype = event.get("type")
    if etype not in PERSISTABLE_WS_EVENT_TYPES:
        return True, None

    try:
        if etype == "wash_progress":
            apply_wash_progress(
                db=db,
                device=device,
                cycle_id=event.get("cycle_id"),
                status=event.get("status"),
                progress_pct=event.get("progress_pct"),
            )
        elif etype == "dispense_progress":
            apply_dispense_progress(
                db=db,
                device=device,
                log_id=event.get("log_id"),
                status=event.get("status"),
                progress_pct=event.get("progress_pct"),
            )
        elif etype == "uv_progress":
            apply_uv_progress(
                db=db,
                device=device,
                uv_cycle_id=event.get("uv_cycle_id"),
                status=event.get("status"),
            )
        elif etype == "alert":
            # Accept either flat fields (preferred) or nested under "payload"
            # for backward compatibility with the original WS spec.
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            alert_type = event.get("alert_type") or payload.get("alert_type")
            message = event.get("message") or payload.get("message")
            severity = event.get("severity") or payload.get("severity")
            if not alert_type:
                raise HTTPException(
                    status_code=422,
                    detail="alert_type is required (see DEVICE_API.md §4e for the closed set)",
                )
            create_device_alert(
                db=db,
                device=device,
                alert_type=alert_type,
                message=message or "",
                severity=severity,
            )
        elif etype == "metric":
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            # power/water are optional — this firmware has no flow/energy
            # meters. record_metric treats missing values as 0.0.
            power_kwh = event.get("power_kwh") if event.get("power_kwh") is not None else payload.get("power_kwh")
            water_liters = event.get("water_liters") if event.get("water_liters") is not None else payload.get("water_liters")
            cycle_id = event.get("cycle_id") if event.get("cycle_id") is not None else payload.get("cycle_id")
            record_metric(
                db=db,
                device=device,
                power_kwh=power_kwh,
                water_liters=water_liters,
                cycle_id=cycle_id,
            )
        return True, None
    except HTTPException as e:
        return False, {
            "type": "error",
            "for": etype,
            "status_code": e.status_code,
            "detail": e.detail,
            "original": event,
        }
    except Exception as e:
        logger.exception("WS persistence failed for event type %s", etype)
        return False, {
            "type": "error",
            "for": etype,
            "status_code": 500,
            "detail": f"Internal error while processing {etype}",
            "original": event,
        }


@router.get("/commands/pending")
def fetch_pending_commands(
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """
    Device firmware polls this endpoint to retrieve queued commands.
    Each command is delivered once — the row is marked as fetched on read.
    Polling also marks the device as online and updates last_seen.

    Auth: X-Device-Api-Key header.

    Response: list of commands, oldest first. Each item has:
      - id           int          row id (use for diagnostics)
      - command      string       command name (start_wash, dispense, stop_wash, ...)
      - payload      object       full command frame (mirrors the WebSocket frame)
      - created_at   ISO datetime when the command was enqueued

    Recommended poll interval: 5 s when idle, 1–2 s while waiting for the user
    to start an operation. Once a wash/dispense is running, the device already
    streams progress so polling can slow back down.
    """
    rows = (
        db.query(PendingCommand)
        .filter(
            PendingCommand.device_id == device.id,
            PendingCommand.fetched_at.is_(None),
        )
        .order_by(PendingCommand.created_at.asc())
        .all()
    )

    now = now_ist()
    out = []
    for r in rows:
        r.fetched_at = now
        try:
            payload = json.loads(r.payload)
        except (json.JSONDecodeError, ValueError):
            payload = {}
        out.append({
            "id": r.id,
            "command": r.command,
            "payload": payload,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    device.last_seen = now
    device.status = "online"
    db.commit()
    return out


@router.get("/me", response_model=DeviceOut)
def get_my_device(
    device: Device = Depends(get_device_by_api_key),
):
    """
    Return the device associated with the supplied `X-Device-Api-Key`.

    Lets firmware fetch its own `device_id`/identity from the key alone, with no
    app login. (Declared before `/{device_id}` so "me" isn't parsed as an id.)
    """
    return device


@router.get("/", response_model=List[DeviceOut])
def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Device).filter(Device.user_id == current_user.id).all()


@router.post("/", response_model=DeviceWithKeyOut, status_code=201)
def register_device(
    body: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import secrets

    existing = db.query(Device).filter(Device.mac_address == body.mac_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device already registered")
    plaintext_key = secrets.token_hex(32)
    device = Device(
        user_id=current_user.id,
        device_name=body.device_name,
        mac_address=body.mac_address,
        wifi_ssid=body.wifi_ssid,
        status="pairing",
        api_key=None,                       # never store plaintext
        api_key_hash=hash_api_key(plaintext_key),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    # Surface the plaintext on the response object once — this is the only
    # time the caller can read it.
    device.api_key = plaintext_key
    return device


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()


@router.post("/{device_id}/rotate-key", response_model=DeviceWithKeyOut)
def rotate_api_key(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate the device API key. Flash the new key to device firmware immediately."""
    import secrets

    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    plaintext_key = secrets.token_hex(32)
    device.api_key = None
    device.api_key_hash = hash_api_key(plaintext_key)
    db.commit()
    db.refresh(device)
    device.api_key = plaintext_key  # transient — returned once, never stored
    return device


@router.post("/{device_id}/command")
async def send_command(
    device_id: int,
    body: DeviceCommand,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.command not in VALID_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid command '{body.command}'. Allowed: {sorted(VALID_COMMANDS)}",
        )
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await dispatch_command(
        db,
        device_id,
        {"type": "command", "command": body.command, "payload": body.payload or {}},
    )
    return {"status": "command_sent"}


@router.websocket("/ws/{device_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: int,
    token: Optional[str] = Query(default=None),    # App clients use JWT
    api_key: Optional[str] = Query(default=None),  # Device firmware uses API key
    db: Session = Depends(get_db),
):
    """
    Accepts connections from two client types:
      - Mobile/web app:      ?token=<JWT>
      - Device firmware:     ?api_key=<device_api_key>
    """
    device: Optional[Device] = None

    if api_key:
        # ── Device firmware auth via API key ──────────────────────────────
        # Look up by SHA-256 hash (post-migration); fall back to plaintext
        # for any device row still on the legacy schema. Mirrors
        # get_device_by_api_key in app/utils/dependencies.py.
        digest = hash_api_key(api_key)
        device = (
            db.query(Device)
            .filter(
                Device.id == device_id,
                or_(Device.api_key_hash == digest, Device.api_key == api_key),
            )
            .first()
        )
        if not device:
            await websocket.close(code=4003)
            return

    elif token:
        # ── App client auth via JWT ───────────────────────────────────────
        payload = decode_token(token)
        if payload is None:
            await websocket.close(code=4001)
            return
        try:
            user_id = int(payload["sub"])
        except (KeyError, ValueError):
            await websocket.close(code=4001)
            return
        device = db.query(Device).filter(
            Device.id == device_id, Device.user_id == user_id
        ).first()
        if not device:
            await websocket.close(code=4003)
            return

    else:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, str(device_id))
    device.status = "online"
    device.last_seen = now_ist()
    db.commit()
    logger.info("WebSocket connected: device %s (auth=%s)", device_id, "api_key" if api_key else "jwt")

    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(WS_IDLE_TIMEOUT),
                )
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                continue

            try:
                event = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Malformed JSON from device %s — ignored", device_id)
                continue

            if not isinstance(event, dict) or "type" not in event:
                logger.warning("Invalid event structure from device %s — ignored", device_id)
                continue

            if event["type"] not in ALLOWED_WS_EVENT_TYPES:
                logger.warning(
                    "Unknown event type '%s' from device %s — ignored",
                    event.get("type"), device_id,
                )
                continue

            device.last_seen = now_ist()
            db.commit()

            # Persist state-changing events through the same helpers the HTTP
            # routes use, so WS and HTTP transports stay in lockstep. Ephemeral
            # events (weight_report, status) skip persistence.
            ok, error_frame = _persist_ws_event(db, device, event)

            if not ok and error_frame is not None:
                # Validation/lookup failure: tell the sender, don't fan out
                # broken state to the app.
                try:
                    await websocket.send_text(json.dumps(error_frame))
                except Exception:
                    pass
                continue

            # Fan the event out to OTHER clients in this device's room (e.g.
            # the user's app). The originating socket is excluded so the
            # device doesn't see its own event echoed back.
            await manager.broadcast_to_device(str(device_id), event, exclude=websocket)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error for device %s: %s", device_id, e)
    finally:
        manager.disconnect(websocket, str(device_id))
        try:
            device.status = "offline"
            db.commit()
        except Exception:
            pass
        logger.info("WebSocket disconnected: device %s", device_id)
