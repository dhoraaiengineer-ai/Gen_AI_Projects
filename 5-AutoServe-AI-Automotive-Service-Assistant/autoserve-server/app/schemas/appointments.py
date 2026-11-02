from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import StrictIn


class AppointmentIn(StrictIn):
    vehicle_id: uuid.UUID
    odometer_km: int = Field(ge=0, le=2_000_000)
    complaint_text: str = Field(min_length=3, max_length=1000)
    slot_start: datetime
    dealer_id: uuid.UUID | None = None  # default: dealer that last serviced the vehicle


class AppointmentOut(BaseModel):
    appointment_id: uuid.UUID
    ro_id: uuid.UUID
    ro_ref: str
    status: str
    slot_start: datetime
    slot_end: datetime


class SlotOut(BaseModel):
    start: datetime
    available: int


class SlotsOut(BaseModel):
    dealer_id: uuid.UUID
    slots: list[SlotOut]
    adapter: str = "DEMO"
