from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

TEMP_MIN, TEMP_MAX = 20.0, 45.0   # °C — safe milk range
VOL_MIN, VOL_MAX = 10.0, 300.0    # ml
SCOOP_MIN, SCOOP_MAX = 0, 20      # formula scoops


class DispenseRequest(BaseModel):
    device_id: int
    temperature_c: float
    volume_ml: float
    # Number of formula scoops (optional — firmware/app may send it alongside
    # temperature and volume).
    scoop_number: Optional[int] = None
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

    @field_validator("scoop_number")
    @classmethod
    def validate_scoops(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if not (SCOOP_MIN <= v <= SCOOP_MAX):
            raise ValueError(f"scoop_number must be between {SCOOP_MIN} and {SCOOP_MAX}")
        return v


class DeviceDispenseRequest(BaseModel):
    """Device-initiated dispense. device_id is derived from the API key.

    Set `force=true` to abandon any dispense that's still pending/dispensing
    on this device (the prior log will be marked `failed` with a note
    explaining it was force-superseded).
    """
    temperature_c: float
    volume_ml: float
    scoop_number: Optional[int] = None
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

    @field_validator("scoop_number")
    @classmethod
    def validate_scoops(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if not (SCOOP_MIN <= v <= SCOOP_MAX):
            raise ValueError(f"scoop_number must be between {SCOOP_MIN} and {SCOOP_MAX}")
        return v


class DispenseLogOut(BaseModel):
    id: int
    device_id: int
    temperature_c: float
    volume_ml: float
    scoop_number: Optional[int] = None
    status: str
    progress_pct: int = 0
    initiated_by: str = "app"
    ended_reason: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
