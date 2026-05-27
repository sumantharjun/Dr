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
