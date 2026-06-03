from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Bumped on every password change/reset. Tokens carry a `pwd_at` marker of
    # this value at issue time; get_current_user rejects tokens whose marker no
    # longer matches — so a password change/reset invalidates all prior sessions.
    password_changed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_ist)

    devices = relationship("Device", back_populates="owner", cascade="all, delete")
    feeding_logs = relationship("FeedingLog", back_populates="user")
    orders = relationship("Order", back_populates="user")
