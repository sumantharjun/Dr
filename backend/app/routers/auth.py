import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.user import (
    ChangePassword,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.utils.dependencies import get_current_user
from app.utils.email import send_password_reset_email
from app.utils.rate_limiter import login_limiter, register_limiter, reset_limiter
from app.utils.security import (
    create_access_token,
    hash_password,
    hash_token,
    password_marker,
    verify_password,
)
from app.utils.timezone import now_ist

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not register_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait before trying again.",
        )
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id), "pwd_at": password_marker(user.password_changed_at)})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(body: UserLogin, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not login_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait 1 minute before trying again.",
        )
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "pwd_at": password_marker(user.password_changed_at)})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the logged-in user's password after verifying the current one."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password must be different from the current one"
        )
    current_user.password_hash = hash_password(body.new_password)
    current_user.password_changed_at = now_ist()
    db.commit()
    db.refresh(current_user)
    # Bumping password_changed_at invalidates all prior tokens (incl. the one
    # used for this request). Return a fresh token so the CURRENT session keeps
    # working while any other/old sessions are logged out.
    token = create_access_token(
        {"sub": str(current_user.id), "pwd_at": password_marker(current_user.password_changed_at)}
    )
    return {"status": "password_changed", "access_token": token}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Email a single-use, time-limited password-reset LINK (never a password).

    Always returns the same response whether or not the email is registered, so
    the endpoint can't be used to enumerate accounts. The email is sent in the
    background so the response time doesn't reveal whether the address exists
    (and so the caller isn't blocked on SMTP). Rate-limited per IP.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not reset_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset requests. Please wait a few minutes and try again.",
        )

    user = db.query(User).filter(User.email == body.email).first()
    if user:
        # Invalidate any prior unused tokens so only the newest link works.
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).update({PasswordResetToken.used_at: now_ist()})

        plaintext = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(plaintext),
            expires_at=now_ist() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        ))
        db.commit()

        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={plaintext}"
        background.add_task(
            send_password_reset_email,
            user.email,
            reset_url,
            settings.PASSWORD_RESET_EXPIRE_MINUTES,
        )

    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Consume a reset token and set the new password. Single use + 1h expiry."""
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_token(body.token))
        .first()
    )
    now = now_ist()
    if not row or row.used_at is not None or row.expires_at < now:
        raise HTTPException(
            status_code=400,
            detail="This reset link is invalid or has expired. Please request a new one.",
        )

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = now  # invalidates any existing sessions
    row.used_at = now
    db.commit()
    return {"message": "Password has been reset. You can now sign in."}
