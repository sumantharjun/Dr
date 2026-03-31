from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class FeedingLogCreate(BaseModel):
    device_id: Optional[int] = None
    feed_time: Optional[datetime] = None
    weight_before_g: Optional[float] = None
    weight_after_g: Optional[float] = None
    milk_consumed_ml: Optional[float] = None
    method: str = "manual"
    notes: Optional[str] = None


class FeedingLogOut(BaseModel):
    id: int
    device_id: Optional[int]
    feed_time: datetime
    weight_before_g: Optional[float]
    weight_after_g: Optional[float]
    milk_consumed_ml: Optional[float]
    method: str
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
