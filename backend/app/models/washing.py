from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class WashingCycle(Base):
    __tablename__ = "washing_cycles"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    mode = Column(
        Enum("full_cycle", "wash", "deep_clean", "dispense"), nullable=False
    )
    status = Column(
        Enum("pending", "running", "completed", "failed"), default="pending"
    )
    progress_pct = Column(Integer, default=0)  # 0–100
    # Who initiated the cycle — app user via /washing/start, or the device
    # itself via /washing/device-start (physical button on the machine).
    initiated_by = Column(Enum("app", "device"), nullable=False, default="app")
    started_at = Column(DateTime, default=now_ist)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="washing_cycles")
