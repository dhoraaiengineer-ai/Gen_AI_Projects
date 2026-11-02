from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import StatusEvent


class ROVehicle(BaseModel):
    id: uuid.UUID
    model: str
    model_year: int
    vin_masked: str


class ROSummary(BaseModel):
    id: uuid.UUID
    ro_ref: str
    status: str
    vehicle: ROVehicle
    created_at: datetime
    updated_at: datetime


class DealerRef(BaseModel):
    id: uuid.UUID
    name: str


class ComplaintOut(BaseModel):
    text: str
    confirmed_by_advisor: bool


class CheckInOut(BaseModel):
    odometer_in_km: int | None
    fuel_or_charge_level: str | None
    damage_notes: str | None


class RODetail(BaseModel):
    id: uuid.UUID
    ro_ref: str
    status: str
    dealer: DealerRef
    vehicle: ROVehicle
    complaints: list[ComplaintOut]
    check_in: CheckInOut | None
    promised_ready_at: datetime | None
    timeline: list[StatusEvent]
