from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.rag.answer import Citation
from app.schemas.chat import RecallNotice
from app.schemas.common import StrictIn
from app.schemas.vehicles import DecodedVinOut


class ServiceRecordOut(BaseModel):
    date: date
    odometer_km: int
    op_codes: list[str]
    dealer_name: str


class MaintenanceDueOut(BaseModel):
    status: Literal["ok", "overdue", "unknown"]
    based_on: str
    due_at_km: int | None
    due_at_date: date | None
    overdue_by_km: int | None
    overdue_by_days: int | None
    current_km: int | None
    source: Citation | None


class TsbMatchOut(BaseModel):
    tsb_code: str
    title: str
    op_code: str | None
    match_reason: Literal["dtc", "keyword"]
    matched_terms: list[str]
    source: Citation | None


class CoverageOut(BaseModel):
    coverage: str
    status: Literal["active", "expired", "unknown"]
    end_date: date | None
    km_limit: int
    km_remaining: int | None
    source: Citation | None


class RiskFlagOut(BaseModel):
    id: uuid.UUID
    detector_id: str
    severity: str
    evidence: dict[str, Any]
    explanation: str  # always "indicator for review" wording
    status: str


class VehicleContextOut(BaseModel):
    vehicle_id: uuid.UUID
    model: str
    model_year: int
    decoded: DecodedVinOut | None
    in_service_date: date | None
    service_history: list[ServiceRecordOut]
    maintenance_due: MaintenanceDueOut | None
    open_recalls: list[RecallNotice]
    applicable_tsbs: list[TsbMatchOut]
    warranty_coverage: list[CoverageOut]
    risk_flags: list[RiskFlagOut]


class CheckInIn(StrictIn):
    odometer_in_km: int = Field(ge=0, le=2_000_000)
    fuel_or_charge_level: str = Field(min_length=1, max_length=32)
    damage_notes: str = Field(default="", max_length=2000)
    complaint_confirmed: bool
    complaint_clarification: str | None = Field(default=None, max_length=1000)  # advisor note; owner's words kept


class CheckInResult(BaseModel):
    ro_id: uuid.UUID
    ro_ref: str
    status: str
    vehicle_context: VehicleContextOut
    replayed: bool = False


class BoardItem(BaseModel):
    appointment_id: uuid.UUID
    ro_id: uuid.UUID
    ro_ref: str
    ro_status: str
    slot_start: datetime
    vehicle_id: uuid.UUID
    model: str
    model_year: int
    vin_masked: str
    owner_display_name: str
    complaint_text: str
