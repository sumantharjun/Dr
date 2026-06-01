from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class MilkDispenseLog(Base):
    __tablename__ = "milk_dispense_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    temperature_c = Column(Float, nullable=False)
    volume_ml = Column(Float, nullable=False)
    # Number of formula scoops for this dispense. Optional — older rows and
    # clients that don't send it stay NULL.
    scoop_number = Column(Integer, nullable=True)
    status = Column(
        Enum("pending", "dispensing", "completed", "failed"), default="pending"
    )
    progress_pct = Column(Integer, default=0)  # 0–100
    # Who initiated the dispense — app user via /dispensing/, or the device
    # itself via /dispensing/device-start (physical controls on the machine).
    initiated_by = Column(Enum("app", "device"), nullable=False, default="app")
    # Why the dispense reached a terminal state. NULL while still
    # pending/dispensing. See WashingCycle.ended_reason for rationale.
    ended_reason = Column(
        Enum("completed", "cancelled", "timed_out", "superseded", "failed"),
        nullable=True,
    )
    created_at = Column(DateTime, default=now_ist)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="dispense_logs")
