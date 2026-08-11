from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class FeedingLog(Base):
    __tablename__ = "feeding_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Which baby this feed was for. Nullable on purpose: the device scale
    # reports a weight delta and cannot know which twin it weighed, so a report
    # arriving before anyone has set the "feeding now" baby lands here as NULL
    # rather than being guessed onto the wrong child.
    baby_id = Column(Integer, ForeignKey("babies.id"), nullable=True, index=True)
    feed_time = Column(DateTime, default=now_ist, index=True)
    weight_before_g = Column(Float, nullable=True)
    weight_after_g = Column(Float, nullable=True)
    milk_consumed_ml = Column(Float, nullable=True)
    method = Column(
        Enum("device", "manual", "breast", "other"), default="manual"
    )
    # What was actually fed, as distinct from `method` (how it was delivered) —
    # a bottle feed can hold breast milk or formula, and the two are not
    # interchangeable clinically. Nullable because the device scale reports a
    # weight difference without knowing the contents; NULL reads as "unknown"
    # rather than being silently recorded as breast milk.
    milk_type = Column(
        Enum("breast_milk", "formula", "cow_milk", "mixed", "other"), nullable=True
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_ist)

    baby = relationship("Baby", back_populates="feeding_logs")
    device = relationship("Device", back_populates="feeding_logs")
    user = relationship("User", back_populates="feeding_logs")
