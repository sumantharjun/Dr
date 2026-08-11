from typing import Optional

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class Baby(Base):
    """A baby profile. A user may have several — twins are the motivating case."""
    __tablename__ = "babies"

    id = Column(Integer, primary_key=True, index=True)
    # Indexed but NOT unique: this was one-to-one until multi-baby support.
    # Dropping that constraint is what allows twins on a single account.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Required: the app greets and labels by name throughout, and a blank one
    # degrades every one of those into generic copy. Rows predating this rule
    # were backfilled to 'Baby' by scripts/backfill_baby_name.py, which also
    # applied the NOT NULL constraint.
    name = Column(String(255), nullable=False)
    gender = Column(Enum("male", "female"), nullable=False)
    # Required for new profiles (see schemas/baby.py) but nullable in the
    # column: profiles created before this field existed have no date of birth
    # and one cannot be inferred. Those parents are prompted in Settings.
    date_of_birth = Column(Date, nullable=True)
    weight_kg = Column(Float, nullable=False)
    # User-selectable theme; defaults to gender-derived value on creation.
    theme_color = Column(Enum("blue", "pink"), nullable=False, default="blue")
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)

    user = relationship("User", back_populates="babies")
    feeding_logs = relationship("FeedingLog", back_populates="baby")

    @property
    def age_days(self) -> Optional[int]:
        """
        Age in whole days, or None if no date of birth is recorded.

        Derived here rather than in the client so age-based feeding guidance and
        the UI can never disagree about how old the baby is. Serialised onto
        BabyOut via `from_attributes`.
        """
        if not self.date_of_birth:
            return None
        return (now_ist().date() - self.date_of_birth).days
