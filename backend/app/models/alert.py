from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class DeviceAlert(Base):
    __tablename__ = "device_alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    # Which baby the alert concerns, for feeding alerts. NULL for device-level
    # alerts (wash, UV, connectivity) which aren't about a baby at all. Used to
    # scope duplicate suppression so one twin's alert can't mute the other's.
    baby_id = Column(Integer, ForeignKey("babies.id"), nullable=True, index=True)
    alert_type = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(Enum("info", "warning", "error", "critical"), default="warning")
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=now_ist, index=True)

    device = relationship("Device", back_populates="alerts")
