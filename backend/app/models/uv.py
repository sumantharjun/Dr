from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class UvCycle(Base):
    __tablename__ = "uv_cycles"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    # Simple discrete states: started (active) → completed | failed (terminal).
    status = Column(Enum("started", "completed", "failed"), nullable=False, default="started")
    # app via /uv/start, or device via /uv/device-start (physical button).
    initiated_by = Column(Enum("app", "device"), nullable=False, default="app")
    # Why it ended (mirrors WashingCycle.ended_reason); NULL while still started.
    ended_reason = Column(
        Enum("completed", "cancelled", "timed_out", "superseded", "failed"),
        nullable=True,
    )
    started_at = Column(DateTime, default=now_ist)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="uv_cycles")
