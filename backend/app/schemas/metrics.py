from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MetricsCreate(BaseModel):
    device_id: int
    cycle_id: Optional[int] = None
    power_kwh: float
    water_liters: float


class MetricsOut(BaseModel):
    id: int
    device_id: int
    cycle_id: Optional[int]
    power_kwh: float
    water_liters: float
    recorded_at: datetime

    model_config = {"from_attributes": True}


class MetricsSummary(BaseModel):
    total_cycles: int
    total_power_kwh: float
    total_water_liters: float
    # Savings vs baseline (standard machine uses ~1.0 kWh and 5L per cycle)
    power_saved_kwh: float
    water_saved_liters: float
