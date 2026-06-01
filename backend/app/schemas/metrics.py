from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MetricsCreate(BaseModel):
    # Optional — derived from the X-Device-Api-Key. If supplied it must match
    # the key's device (else 403); kept for backward compatibility.
    device_id: Optional[int] = None
    cycle_id: Optional[int] = None
    # Optional — firmware without flow/energy meters won't send these.
    power_kwh: Optional[float] = None
    water_liters: Optional[float] = None


class MetricsOut(BaseModel):
    id: int
    device_id: int
    cycle_id: Optional[int]
    power_kwh: Optional[float] = None
    water_liters: Optional[float] = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class MetricsSummary(BaseModel):
    total_cycles: int
    total_power_kwh: float
    total_water_liters: float
    # Savings vs baseline (standard machine uses ~1.0 kWh and 5L per cycle)
    power_saved_kwh: float
    water_saved_liters: float
