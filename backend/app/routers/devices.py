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

from app.services.commands import dispatch_command
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.utils.security import decode_token, hash_api_key
from app.utils.timezone import now_ist
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])

VALID_COMMANDS = {"start_wash", "stop_wash", "dispense", "stop_dispense", "reboot", "status"}
ALLOWED_WS_EVENT_TYPES = {"wash_progress", "dispense_progress", "alert", "status", "metric", "weight_report"}
WS_IDLE_TIMEOUT = 300  # 5 min — device must send something or server pings


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

            await manager.broadcast_to_device(str(device_id), event)

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
