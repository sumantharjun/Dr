from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

VALID_METHODS = {"device", "manual", "breast", "other"}
VALID_MILK_TYPES = {"breast_milk", "formula", "cow_milk", "mixed", "other"}


class FeedingLogCreate(BaseModel):
    device_id: Optional[int] = None
    feed_time: Optional[datetime] = None
    weight_before_g: Optional[float] = None
    weight_after_g: Optional[float] = None
    milk_consumed_ml: Optional[float] = None
    method: str = "manual"
    # Required with no default: what the baby was fed is the point of the log,
    # and defaulting it would quietly attribute every unlabelled feed to one
    # type. Device-reported feeds go through DeviceFeedReport, which may omit it.
    milk_type: str
    notes: Optional[str] = None

    @field_validator("weight_before_g", "weight_after_g")
    @classmethod
    def validate_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 2000):
            raise ValueError("Weight must be between 0 and 2000 grams")
        return v

    @field_validator("milk_consumed_ml")
    @classmethod
    def validate_milk(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 500):
            raise ValueError("Milk volume must be between 0 and 500 ml")
        return v

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"Method must be one of: {sorted(VALID_METHODS)}")
        return v

    @field_validator("milk_type")
    @classmethod
    def validate_milk_type(cls, v: str) -> str:
        if v not in VALID_MILK_TYPES:
            raise ValueError(f"Milk type must be one of: {sorted(VALID_MILK_TYPES)}")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 500:
            raise ValueError("Notes must be 500 characters or fewer")
        return v


class FeedingLogOut(BaseModel):
    id: int
    device_id: Optional[int]
    feed_time: datetime
    weight_before_g: Optional[float]
    weight_after_g: Optional[float]
    milk_consumed_ml: Optional[float]
    method: str
    # Optional on the way out: rows predating this field and device-reported
    # feeds can legitimately have no milk type.
    milk_type: Optional[str]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedingAnalytics(BaseModel):
    date: str
    total_ml: float
    feed_count: int


class FeedingSchedule(BaseModel):
    last_feed_time: Optional[datetime]
    minutes_since_last_feed: Optional[int]
    recommended_interval_hours: int = 3
    next_feed_due: Optional[datetime]
