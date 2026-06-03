from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # bcrypt's hard limit; we already truncate at hash-time


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(
                f"password must be {MAX_PASSWORD_LENGTH} characters or fewer"
            )
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("full_name must not be empty")
        if len(v) > 255:
            raise ValueError("full_name must be 255 characters or fewer")
        return v.strip()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"new_password must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"new_password must be {MAX_PASSWORD_LENGTH} characters or fewer")
        return v


class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"new_password must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"new_password must be {MAX_PASSWORD_LENGTH} characters or fewer")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
