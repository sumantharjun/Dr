from pydantic import field_validator
from pydantic_settings import BaseSettings

_WEAK_DEFAULT = "your-super-secret-key-change-in-production"


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://appuser:apppassword@localhost:3306/baby_feeding"
    SECRET_KEY: str = _WEAK_DEFAULT
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Comma-separated list of allowed CORS origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

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
