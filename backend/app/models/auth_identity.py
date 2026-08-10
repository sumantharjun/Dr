from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.timezone import now_ist


class AuthIdentity(Base):
    """
    A third-party login attached to a user (Google today, Apple later).

    Separate table rather than columns on `users` so a parent can have more than
    one provider on the same account, and so adding Apple needs no schema change
    at all.
    """
    __tablename__ = "auth_identities"
    __table_args__ = (
        # One provider account maps to exactly one user. The DB constraint is
        # what actually prevents two users claiming the same Google account if
        # two sign-ins race.
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_identity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(Enum("google", "apple"), nullable=False)
    # The provider's stable subject id (`sub`). This — never the email — is the
    # identity: an email can be changed by its owner, `sub` cannot, and Apple's
    # "Hide My Email" relay addresses make email matching outright unreliable.
    provider_user_id = Column(String(255), nullable=False)
    # The email the provider asserted when the link was made. Informational
    # only (support, auditing); never used for matching.
    email_at_link = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=now_ist)

    user = relationship("User", back_populates="auth_identities")
