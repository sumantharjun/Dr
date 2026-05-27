from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class Baby(Base):
    """One-to-one with User: parent's baby profile."""
    __tablename__ = "babies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    gender = Column(Enum("male", "female"), nullable=False)
    weight_kg = Column(Float, nullable=False)
    # User-selectable theme; defaults to gender-derived value on creation.
    theme_color = Column(Enum("blue", "pink"), nullable=False, default="blue")
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    user = relationship("User", backref="baby")
