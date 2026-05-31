from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

TEMP_MIN, TEMP_MAX = 20.0, 45.0   # °C — safe milk range
VOL_MIN, VOL_MAX = 10.0, 300.0    # ml


class DispenseRequest(BaseModel):
    device_id: int
    temperature_c: float
    volume_ml: float
    # Set force=true to supersede a dispense still stuck pending/dispensing
    # (marked failed with ended_reason='superseded'). App-side recovery path.
    force: bool = False

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


class DeviceDispenseRequest(BaseModel):
    """Device-initiated dispense. device_id is derived from the API key.

    Set `force=true` to abandon any dispense that's still pending/dispensing
    on this device (the prior log will be marked `failed` with a note
    explaining it was force-superseded).
    """
    temperature_c: float
    volume_ml: float
    force: bool = False

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
    initiated_by: str = "app"
    ended_reason: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
