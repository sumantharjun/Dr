from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class WashingCycle(Base):
    __tablename__ = "washing_cycles"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    mode = Column(
        Enum("full_cycle", "wash", "deep_clean", "dispense"), nullable=False
    )
    status = Column(
        Enum("pending", "running", "completed", "failed"), default="pending"
    )
    progress_pct = Column(Integer, default=0)  # 0–100
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="washing_cycles")
