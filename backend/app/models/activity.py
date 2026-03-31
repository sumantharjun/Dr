from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DeviceActivityLog(Base):
    __tablename__ = "device_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    event_type = Column(String(100), nullable=False)  # wash_started, dispense_completed, alert_triggered, etc.
    description = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    device = relationship("Device")
