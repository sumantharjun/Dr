from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import decode_token, hash_api_key

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_device_by_api_key(
    x_device_api_key: str = Header(..., alias="X-Device-Api-Key"),
    db: Session = Depends(get_db),
):
    """
    Authenticate a device by its API key.

    Looks up the device by SHA-256 hash of the incoming key. During the
    rollout window, if a device row still has a legacy plaintext `api_key`
    and no hash yet, we accept that match too — the startup migration will
    backfill the hash and null out the plaintext on the next boot.
    """
    from app.models.device import Device

    digest = hash_api_key(x_device_api_key)
    device = (
        db.query(Device)
        .filter(
            or_(
                Device.api_key_hash == digest,
                # Legacy fallback — removed once startup migration completes.
                Device.api_key == x_device_api_key,
            )
        )
        .first()
    )
    if not device:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid device API key")
    return device
