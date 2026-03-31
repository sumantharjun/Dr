import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceCommand, DeviceCreate, DeviceOut, DeviceWithKeyOut
from app.utils.dependencies import get_current_user
from app.websocket.manager import manager

router = APIRouter(prefix="/devices", tags=["devices"])


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
    existing = db.query(Device).filter(Device.mac_address == body.mac_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device already registered")
    device = Device(
        user_id=current_user.id,
        device_name=body.device_name,
        mac_address=body.mac_address,
        wifi_ssid=body.wifi_ssid,
        status="pairing",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
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
    """Regenerate the device API key. Returns new key — store it in device firmware."""
    import secrets
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.api_key = secrets.token_hex(32)
    db.commit()
    db.refresh(device)
    return device


@router.post("/{device_id}/command")
async def send_command(
    device_id: int,
    body: DeviceCommand,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(
        Device.id == device_id, Device.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await manager.broadcast_to_device(
        str(device_id),
        {"type": "command", "command": body.command, "payload": body.payload},
    )
    return {"status": "command_sent"}


@router.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str, db: Session = Depends(get_db)):
    await manager.connect(websocket, device_id)
    device = db.query(Device).filter(Device.id == int(device_id)).first()
    if device:
        device.status = "online"
        device.last_seen = datetime.utcnow()
        db.commit()
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            # Update device last_seen on any event
            if device:
                device.last_seen = datetime.utcnow()
                db.commit()
            # Broadcast event to all listeners on this device channel
            await manager.broadcast_to_device(device_id, event)
    except WebSocketDisconnect:
        manager.disconnect(websocket, device_id)
        if device:
            device.status = "offline"
            db.commit()
