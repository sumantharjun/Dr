import secrets
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_name = Column(String(255), nullable=False)
    mac_address = Column(String(17), unique=True, nullable=False)
    wifi_ssid = Column(String(255), nullable=True)
    status = Column(
        Enum("online", "offline", "pairing", "error"), default="offline"
    )
    api_key = Column(String(64), unique=True, index=True, default=lambda: secrets.token_hex(32))
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="devices")
    feeding_logs = relationship("FeedingLog", back_populates="device", cascade="all, delete")
    washing_cycles = relationship("WashingCycle", back_populates="device", cascade="all, delete")
    dispense_logs = relationship("MilkDispenseLog", back_populates="device", cascade="all, delete")
    alerts = relationship("DeviceAlert", back_populates="device", cascade="all, delete")
