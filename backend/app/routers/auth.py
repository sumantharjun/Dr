import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth_identity import AuthIdentity
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.user import (
    ChangePassword,
    ForgotPasswordRequest,
    GoogleSignIn,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
    UserPreferences,
)
from app.services import oauth_google
from app.utils.dependencies import get_current_user, get_session_is_remembered
from app.utils.email import send_password_reset_email
from app.utils.rate_limiter import login_limiter, oauth_limiter, register_limiter, reset_limiter
from app.utils.security import (
    REMEMBER_CLAIM,
    create_access_token,
    hash_password,
    hash_token,
    password_marker,
    session_lifetime,
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
    # A just-registered user is treated as a remembered session: they've only
    # this second chosen a password, and dropping them at the login screen when
    # they close the tab would be a poor first impression.
    token = create_access_token(
        {
            "sub": str(user.id),
            "pwd_at": password_marker(user.password_changed_at),
            REMEMBER_CLAIM: True,
        },
        expires_delta=session_lifetime(True),
    )
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
    # `not user.password_hash` short-circuits before verify_password, which
    # would raise on a None hash. A Google-only account must fail here the same
    # way a wrong password does — saying "this account has no password" would
    # confirm the address exists to anyone probing.
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(
        {
            "sub": str(user.id),
            "pwd_at": password_marker(user.password_changed_at),
            REMEMBER_CLAIM: body.remember_me,
        },
        expires_delta=session_lifetime(body.remember_me),
    )
    return Token(access_token=token, user=UserOut.model_validate(user))


def _resolve_google_user(claims: dict, db: Session) -> User:
    """
    Map verified Google claims onto a user, creating or linking as needed.

    Order matters:
      1. Known identity (`sub`) — the only reliable match, and works even after
         the parent changes their Google email address.
      2. Existing account with the same email — link it. Safe *only* because
         verify_id_token already refused anything without email_verified.
      3. Neither — create a new user with no password.
    """
    sub = claims["sub"]
    email = claims["email"]

    identity = (
        db.query(AuthIdentity)
        .filter(AuthIdentity.provider == "google", AuthIdentity.provider_user_id == sub)
        .first()
    )
    if identity:
        return identity.user

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            # full_name is NOT NULL and Google occasionally omits `name`
            # (and Apple usually will), so fall back to the email local-part
            # rather than assuming it's present.
            full_name=(claims.get("name") or email.split("@")[0]).strip()[:255],
            password_hash=None,  # no password — this account signs in with Google
        )
        db.add(user)
        db.flush()

    db.add(AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_user_id=sub,
        email_at_link=email,
    ))
    return user


@router.post("/google", response_model=Token)
def google_sign_in(body: GoogleSignIn, request: Request, db: Session = Depends(get_db)):
    """
    Exchange a Google ID token for one of our session tokens.

    The Google token is used exactly once, here, to establish identity; the
    caller then uses the returned token like any other session, so sliding
    renewal and Remember Me behave identically to a password login.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured.",
        )

    client_ip = request.client.host if request.client else "unknown"
    if not oauth_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Please wait a minute and try again.",
        )

    try:
        claims = oauth_google.verify_id_token(body.credential)
    except oauth_google.GoogleAuthError as exc:
        # 401, not 500 — an unacceptable token is a client-side problem.
        raise HTTPException(status_code=401, detail=str(exc))

    user = _resolve_google_user(claims, db)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        {
            "sub": str(user.id),
            "pwd_at": password_marker(user.password_changed_at),
            REMEMBER_CLAIM: body.remember_me,
        },
        expires_delta=session_lifetime(body.remember_me),
    )
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me/preferences", response_model=UserOut)
def update_preferences(
    body: UserPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update account-level display preferences (currently just the theme)."""
    if body.theme_color is not None:
        current_user.theme_color = body.theme_color
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePassword,
    current_user: User = Depends(get_current_user),
    remembered: bool = Depends(get_session_is_remembered),
    db: Session = Depends(get_db),
):
    """Change the logged-in user's password after verifying the current one."""
    # A Google-only account has no password to verify against. Point the parent
    # at the reset flow, which is how they'd add one.
    if not current_user.password_hash:
        raise HTTPException(
            status_code=400,
            detail=(
                "This account signs in with Google and has no password. "
                "Use “Forgot password” to set one."
            ),
        )
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
    # Keep the lifetime the user originally chose — a password change shouldn't
    # quietly demote a remembered session to a short one.
    token = create_access_token(
        {
            "sub": str(current_user.id),
            "pwd_at": password_marker(current_user.password_changed_at),
            REMEMBER_CLAIM: remembered,
        },
        expires_delta=session_lifetime(remembered),
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
