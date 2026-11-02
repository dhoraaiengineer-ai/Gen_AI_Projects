from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class VehicleSummary(BaseModel):
    id: uuid.UUID
    vin_masked: str
    model: str
    model_year: int
    plate_masked: str | None
    last_odometer_km: int | None


class DecodedVinOut(BaseModel):
    wmi: str
    model: str
    model_year: int
    plant: str
    serial: str


class VehicleDetail(BaseModel):
    id: uuid.UUID
    vin: str  # full VIN only reaches the owner and in-scope staff (scope enforced by the repository)
    decoded: DecodedVinOut | None
    model: str
    model_year: int
    in_service_date: date | None
    last_odometer_km: int | None
    plate_number: str | None
