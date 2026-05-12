from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

TEMP_MIN, TEMP_MAX = 20.0, 45.0   # °C — safe milk range
VOL_MIN, VOL_MAX = 10.0, 300.0    # ml


class DispenseRequest(BaseModel):
    device_id: int
    temperature_c: float
    volume_ml: float

    @field_validator("temperature_c")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not (TEMP_MIN <= v <= TEMP_MAX):
            raise ValueError(
                f"Temperature must be between {TEMP_MIN}°C and {TEMP_MAX}°C (safe milk range)"
            )
        return round(v, 1)

    @field_validator("volume_ml")
    @classmethod
    def validate_volume(cls, v: float) -> float:
        if not (VOL_MIN <= v <= VOL_MAX):
            raise ValueError(f"Volume must be between {VOL_MIN}ml and {VOL_MAX}ml")
        return round(v, 1)


class DispenseLogOut(BaseModel):
    id: int
    device_id: int
    temperature_c: float
    volume_ml: float
    status: str
    progress_pct: int = 0
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
