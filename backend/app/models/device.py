from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_name = Column(String(255), nullable=False)
    mac_address = Column(String(17), unique=True, nullable=False)
    wifi_ssid = Column(String(255), nullable=True)
    status = Column(
        Enum("online", "offline", "pairing", "error"), default="offline"
    )
    # ── API key storage ────────────────────────────────────────────────────
    # Legacy plaintext column — kept nullable during the rollout so the startup
    # migration can backfill `api_key_hash` from it, then null it out. New
    # registrations never populate this column.
    api_key = Column(String(64), unique=True, index=True, nullable=True)
    # SHA-256 hex (64 chars) of the device's plaintext API key. This is what
    # the auth dependency looks up. Plaintext is returned once at registration
    # / rotation and is never persisted afterwards.
    api_key_hash = Column(String(64), unique=True, index=True, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_ist)

    owner = relationship("User", back_populates="devices")
    feeding_logs = relationship("FeedingLog", back_populates="device", cascade="all, delete")
    washing_cycles = relationship("WashingCycle", back_populates="device", cascade="all, delete")
    dispense_logs = relationship("MilkDispenseLog", back_populates="device", cascade="all, delete")
    alerts = relationship("DeviceAlert", back_populates="device", cascade="all, delete")
    metrics = relationship("DeviceMetrics", back_populates="device", cascade="all, delete")
    activity_logs = relationship("DeviceActivityLog", back_populates="device", cascade="all, delete")
    pending_commands = relationship("PendingCommand", back_populates="device", cascade="all, delete")
