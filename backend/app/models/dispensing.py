from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class MilkDispenseLog(Base):
    __tablename__ = "milk_dispense_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    temperature_c = Column(Float, nullable=False)
    volume_ml = Column(Float, nullable=False)
    status = Column(
        Enum("pending", "dispensing", "completed", "failed"), default="pending"
    )
    progress_pct = Column(Integer, default=0)  # 0–100
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="dispense_logs")
