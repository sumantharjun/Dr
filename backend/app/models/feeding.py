from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class FeedingLog(Base):
    __tablename__ = "feeding_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feed_time = Column(DateTime, default=now_ist, index=True)
    weight_before_g = Column(Float, nullable=True)
    weight_after_g = Column(Float, nullable=True)
    milk_consumed_ml = Column(Float, nullable=True)
    method = Column(
        Enum("device", "manual", "breast", "other"), default="manual"
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_ist)

    device = relationship("Device", back_populates="feeding_logs")
    user = relationship("User", back_populates="feeding_logs")
