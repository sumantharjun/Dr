from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import DeviceAlert
from app.models.device import Device
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertOut
from app.services.alerts_catalog import default_severity_for
from app.utils.dependencies import get_current_user, get_device_by_api_key
from app.websocket.manager import manager

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _owned_device_ids(user: User, db: Session) -> list[int]:
    return [d.id for d in db.query(Device).filter(Device.user_id == user.id).all()]


@router.get("/", response_model=List[AlertOut])
def get_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = _owned_device_ids(current_user, db)
    return (
        db.query(DeviceAlert)
        .filter(DeviceAlert.device_id.in_(device_ids))
        .order_by(DeviceAlert.is_read.asc(), DeviceAlert.created_at.desc())
        .all()
    )


@router.post("/", response_model=AlertOut, status_code=201)
async def create_alert(
    body: AlertCreate,
    device: Device = Depends(get_device_by_api_key),
    db: Session = Depends(get_db),
):
    """Called by device/firmware to push safety alerts. Requires X-Device-Api-Key header.

    Valid alert_type values: overheating, malfunction, washing_error, low_detergent.
    If severity is omitted, the catalog default for that alert_type is used.
    """
    if device.id != body.device_id:
        raise HTTPException(status_code=403, detail="API key does not match device_id")
    severity = body.severity or default_severity_for(body.alert_type)
    alert = DeviceAlert(
        device_id=body.device_id,
        alert_type=body.alert_type,
        message=body.message,
        severity=severity,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    await manager.broadcast_to_device(
        str(body.device_id),
        {"type": "alert", "alert_type": body.alert_type, "message": body.message, "severity": severity},
    )
    return alert


@router.put("/{alert_id}/read", response_model=AlertOut)
def mark_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = _owned_device_ids(current_user, db)
    alert = db.query(DeviceAlert).filter(
        DeviceAlert.id == alert_id,
        DeviceAlert.device_id.in_(device_ids),
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device_ids = _owned_device_ids(current_user, db)
    alert = db.query(DeviceAlert).filter(
        DeviceAlert.id == alert_id,
        DeviceAlert.device_id.in_(device_ids),
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
