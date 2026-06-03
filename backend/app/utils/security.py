import hashlib
from datetime import timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.utils.timezone import now_ist

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
    expire = now_ist() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
