from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class PendingCommand(Base):
    __tablename__ = "pending_commands"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    command = Column(String(50), nullable=False)
    payload = Column(Text, nullable=False)  # JSON-encoded command frame
    created_at = Column(DateTime, default=now_ist, index=True)
    fetched_at = Column(DateTime, nullable=True, index=True)

    device = relationship("Device", back_populates="pending_commands")
