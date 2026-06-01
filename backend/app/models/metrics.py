from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class DeviceMetrics(Base):
    __tablename__ = "device_metrics"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    # Per wash cycle metrics
    cycle_id = Column(Integer, ForeignKey("washing_cycles.id"), nullable=True)
    # Nullable: this firmware has no flow/energy meters, so these are usually
    # not reported. Kept on the model in case real meters arrive later.
    power_kwh = Column(Float, nullable=True, default=0.0)
    water_liters = Column(Float, nullable=True, default=0.0)
    recorded_at = Column(DateTime, default=now_ist)

    device = relationship("Device", back_populates="metrics")
