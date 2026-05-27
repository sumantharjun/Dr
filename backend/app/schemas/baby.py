from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

VALID_GENDERS = {"male", "female"}
VALID_THEMES = {"blue", "pink"}


class BabyCreate(BaseModel):
    name: Optional[str] = None
    gender: str
    weight_kg: float
    theme_color: Optional[str] = None  # Defaults to gender-derived if omitted

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
    weight_kg: Optional[float] = None
    theme_color: Optional[str] = None

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
    weight_kg: float
    theme_color: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
