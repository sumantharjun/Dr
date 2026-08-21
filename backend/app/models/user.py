from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    # Nullable: a user who signed up with Google has no password at all. Storing
    # a junk hash to satisfy a NOT NULL would make `verify_password` silently
    # fail rather than letting callers detect "this account has no password".
    password_hash = Column(String(255), nullable=True)
    # Bumped on every password change/reset. Tokens carry a `pwd_at` marker of
    # this value at issue time; get_current_user rejects tokens whose marker no
    # longer matches — so a password change/reset invalidates all prior sessions.
    password_changed_at = Column(DateTime, nullable=True)
    # The parent's chosen app colour. An account-level preference, deliberately
    # not derived from the baby's gender and not stored per baby — one account
    # is one app, and with twins there is no per-baby answer.
    theme_color = Column(
        Enum("green", "blue", "pink", "lilac", "peach", "slate"),
        nullable=False,
        default="green",
        server_default="green",
    )
    # When the parent finished (or skipped) the guided tour. NULL means they
    # haven't seen it, which is what triggers it on first login. Stored on the
    # account rather than in localStorage so signing in on a second device
    # doesn't replay it.
    tour_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_ist)

    auth_identities = relationship(
        "AuthIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    babies = relationship("Baby", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="owner", cascade="all, delete")
    feeding_logs = relationship("FeedingLog", back_populates="user")
    orders = relationship("Order", back_populates="user")
