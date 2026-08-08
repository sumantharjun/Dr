import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_api_key(plaintext: str) -> str:
    """
    Hash a device API key for storage. Device keys are high-entropy random
    tokens (256 bits) so a fast hash (SHA-256) is appropriate — slow hashes
    like bcrypt aren't needed since the keyspace is already brute-force-proof,
    and per-request bcrypt would add unacceptable latency to every device call.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def password_marker(changed_at) -> str:
    """Token claim that pins a session to the password version at issue time.
    Empty string when the password has never been changed (legacy/new users) so
    pre-existing tokens stay valid; once changed, old tokens stop matching."""
    return changed_at.isoformat() if changed_at else ""


def hash_token(plaintext: str) -> str:
    """SHA-256 of a high-entropy reset token. Same rationale as hash_api_key —
    the token is random and long, so a fast hash is appropriate and we never
    store the plaintext (it lives only in the emailed link)."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # `exp` must be UTC: RFC 7519 defines it as seconds since the UTC epoch, and
    # jose validates it against a real UTC clock on decode. Building it from
    # now_ist() — a NAIVE IST datetime — made jose read IST wall-clock as UTC,
    # so every token silently outlived its configured lifetime by the 5h30m IST
    # offset (a "60 minute" session really lasted ~6.5 hours).
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Sliding sessions ────────────────────────────────────────────────────────
# "Remember me" is carried in the token itself (the `rmb` claim) rather than
# looked up per request, so a renewal knows which lifetime to re-issue with
# without touching the database.
REMEMBER_CLAIM = "rmb"


def session_lifetime(remember: bool) -> timedelta:
    minutes = (
        settings.REMEMBER_ME_EXPIRE_MINUTES
        if remember
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return timedelta(minutes=minutes)


def _now_as_encoded_timestamp() -> int:
    """'Now' on the same UTC-epoch scale the `exp` claim is stored on."""
    return int(datetime.now(timezone.utc).timestamp())


def renew_if_stale(payload: dict) -> Optional[str]:
    """
    Return a freshly-issued token if this one is past the halfway point of its
    lifetime, else None.

    Halfway (rather than "nearly expired") means a user who opens the app once
    a fortnight still keeps a 30-day session alive, while a token is renewed at
    most a handful of times over its life instead of on every request.
    """
    exp = payload.get("exp")
    if not exp:
        return None

    remember = bool(payload.get(REMEMBER_CLAIM))
    lifetime = session_lifetime(remember)
    remaining = int(exp) - _now_as_encoded_timestamp()
    if remaining > lifetime.total_seconds() / 2:
        return None

    return create_access_token(
        {
            "sub": payload["sub"],
            "pwd_at": payload.get("pwd_at", ""),
            REMEMBER_CLAIM: remember,
        },
        expires_delta=lifetime,
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
