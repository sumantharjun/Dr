from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class WashingCycle(Base):
    __tablename__ = "washing_cycles"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    # Allowed wash modes (matches VALID_MODES in routers/washing.py). The old
    # modes wash/deep_clean/dispense were removed per the firmware spec.
    mode = Column(
        Enum("full_cycle", "steam_dry", "dry"),
        nullable=False,
    )
    status = Column(
        Enum("pending", "running", "completed", "failed"), default="pending"
    )
    progress_pct = Column(Integer, default=0)  # 0–100
    # Who initiated the cycle — app user via /washing/start, or the device
    # itself via /washing/device-start (physical button on the machine).
    initiated_by = Column(Enum("app", "device"), nullable=False, default="app")
    # Why the cycle reached a terminal state. NULL while still pending/running.
    # Disambiguates the overloaded `failed` status: a real hardware failure, a
    # user/app cancel, the timeout sweep giving up, or a force-supersede all
    # used to be indistinguishable.
    ended_reason = Column(
        Enum("completed", "cancelled", "timed_out", "superseded", "failed"),
        nullable=True,
    )
    started_at = Column(DateTime, default=now_ist)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="washing_cycles")
