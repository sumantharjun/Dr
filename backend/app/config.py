from pydantic import field_validator
from pydantic_settings import BaseSettings

_WEAK_DEFAULT = "your-super-secret-key-change-in-production"


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://appuser:apppassword@localhost:3306/baby_feeding"
    SECRET_KEY: str = _WEAK_DEFAULT
    ALGORITHM: str = "HS256"
    # ── Session lifetimes ───────────────────────────────────────────────────
    # Both are SLIDING: any authenticated request made past the halfway point
    # of a token's life gets a freshly-issued token back in the X-Renewed-Token
    # response header (see utils/dependencies.py). An active user therefore
    # never hits the expiry at all — only real inactivity ends a session.
    #
    # Without "Remember me": long enough to cover a day's use, but the token
    # lives in sessionStorage so closing the browser signs the user out.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours
    # With "Remember me": persists in localStorage across browser restarts.
    REMEMBER_ME_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    # Comma-separated list of allowed CORS origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ── Password reset ──────────────────────────────────────────────────────
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60
    # Base URL of the frontend, used to build the reset link in the email.
    FRONTEND_URL: str = "https://unova-api.vsngroups.com"

    # ── Outbound email ──────────────────────────────────────────────────────
    # Preferred: set RESEND_API_KEY to send via Resend's HTTPS API (port 443 —
    # immune to the SMTP port blocking many networks impose).
    # Fallback: set SMTP_HOST to send via SMTP. If neither is set (dev/test),
    # emails are logged / captured in an in-memory outbox instead of being sent.
    RESEND_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: str = "UNOVA <no-reply@unova.local>"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if v == _WEAK_DEFAULT:
            raise ValueError(
                "SECRET_KEY is set to the insecure default. "
                "Generate a strong key with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters (256 bits).")
        return v

    class Config:
        env_file = ".env"


settings = Settings()
