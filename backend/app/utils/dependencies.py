from fastapi import Depends, Header, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import (
    REMEMBER_CLAIM,
    decode_token,
    hash_api_key,
    password_marker,
    renew_if_stale,
)

bearer_scheme = HTTPBearer()

# Response header carrying a slid-forward session token. Must also be listed in
# the CORS middleware's expose_headers, or the browser will withhold it from
# JavaScript on cross-origin calls and sessions will silently never renew.
RENEWED_TOKEN_HEADER = "X-Renewed-Token"


def get_current_user(
    response: Response,
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
    # Reject tokens issued before the user's most recent password change/reset.
    if payload.get("pwd_at", "") != password_marker(user.password_changed_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again.",
        )
    # Slide the session forward. Only reached once the token is fully valid, so
    # an expired or password-invalidated token can never renew itself.
    renewed = renew_if_stale(payload)
    if renewed:
        response.headers[RENEWED_TOKEN_HEADER] = renewed
    return user


def get_session_is_remembered(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> bool:
    """
    Whether the caller's session was opened with "Remember me".

    Used when re-issuing a token mid-session (e.g. after a password change) so
    the replacement keeps the same lifetime the user originally chose, instead
    of silently downgrading a 30-day session to a 12-hour one.
    """
    payload = decode_token(credentials.credentials) or {}
    return bool(payload.get(REMEMBER_CLAIM))


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
