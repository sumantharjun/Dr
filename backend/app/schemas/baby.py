from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.utils.timezone import now_ist

VALID_GENDERS = {"male", "female"}
VALID_THEMES = {"blue", "pink"}

# Upper bound on plausible age. Generous on purpose — the device is used well
# past infancy for bottles and sterilising — but tight enough to catch a
# mistyped year, which is the common data-entry error for a date of birth.
MAX_AGE_YEARS = 10


def _validate_dob(v: date) -> date:
    today = now_ist().date()
    if v > today:
        raise ValueError("date_of_birth cannot be in the future")
    if (today - v).days > MAX_AGE_YEARS * 366:
        raise ValueError(f"date_of_birth cannot be more than {MAX_AGE_YEARS} years ago")
    return v


class BabyCreate(BaseModel):
    name: Optional[str] = None
    gender: str
    # Required on create: age drives feeding volume and interval guidance, and
    # defaulting it would produce confidently wrong recommendations.
    date_of_birth: date
    weight_kg: float
    theme_color: Optional[str] = None  # Defaults to gender-derived if omitted

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        return _validate_dob(v)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {sorted(VALID_GENDERS)}")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if not (0.5 <= v <= 30.0):
            raise ValueError("weight_kg must be between 0.5 and 30.0")
        return round(v, 2)

    @field_validator("theme_color")
    @classmethod
    def validate_theme(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_THEMES:
            raise ValueError(f"theme_color must be one of {sorted(VALID_THEMES)}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 255:
            raise ValueError("name must be 255 characters or fewer")
        return v


class BabyUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    # Optional here so an existing profile created before this field existed can
    # be backfilled from Settings without resending every other attribute.
    date_of_birth: Optional[date] = None
    weight_kg: Optional[float] = None
    theme_color: Optional[str] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        return None if v is None else _validate_dob(v)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {sorted(VALID_GENDERS)}")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.5 <= v <= 30.0):
            raise ValueError("weight_kg must be between 0.5 and 30.0")
        return None if v is None else round(v, 2)

    @field_validator("theme_color")
    @classmethod
    def validate_theme(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_THEMES:
            raise ValueError(f"theme_color must be one of {sorted(VALID_THEMES)}")
        return v


class BabyOut(BaseModel):
    id: int
    name: Optional[str]
    gender: str
    # Nullable on the way out: profiles predating this field have no DOB.
    date_of_birth: Optional[date]
    # Derived server-side from date_of_birth (Baby.age_days) so the client never
    # has to compute it and the two can't drift.
    age_days: Optional[int]
    weight_kg: float
    theme_color: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
