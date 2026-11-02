"""vehicle_models, vehicles, service_history, recalls, recall_vin_ranges, tsbs, maintenance_alerts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, in_list, updated_at, uuid_pk


class VehicleModel(Base):
    __tablename__ = "vehicle_models"
    __table_args__ = (
        CheckConstraint(in_list("powertrain", ("petrol", "diesel", "bev")), name="powertrain_valid"),
        CheckConstraint("char_length(vds_code) = 5", name="vds_code_len"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(32), unique=True)
    powertrain: Mapped[str] = mapped_column(String(16))
    vds_code: Mapped[str] = mapped_column(String(5), unique=True)  # VIN positions 4-8
    model_year_from: Mapped[int] = mapped_column(Integer)
    model_year_to: Mapped[int] = mapped_column(Integer)
    plant_codes: Mapped[list[str]] = mapped_column(ARRAY(String(1)))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (CheckConstraint("char_length(vin) = 17", name="vin_len"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    vin: Mapped[str] = mapped_column(String(17), unique=True)  # PII — log last 6 only
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicle_models.id"), index=True)
    model_year: Mapped[int] = mapped_column(Integer)
    plant_code: Mapped[str] = mapped_column(String(1))
    plate_number: Mapped[str | None] = mapped_column(String(16))  # PII
    in_service_date: Mapped[date | None] = mapped_column(Date)
    last_odometer_km: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ServiceHistory(Base):
    __tablename__ = "service_history"
    __table_args__ = (
        Index("ix_service_history_vehicle_date", "vehicle_id", "service_date"),
        CheckConstraint(in_list("source", ("seed", "ro")), name="source_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"))
    dealer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dealers.id"), index=True)
    service_date: Mapped[date] = mapped_column(Date)
    odometer_km: Mapped[int] = mapped_column(Integer)
    op_codes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Recall(Base):
    __tablename__ = "recalls"
    __table_args__ = (CheckConstraint(in_list("status", ("open", "closed")), name="status_valid"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    campaign_code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(Text)
    component_group: Mapped[str] = mapped_column(String(64))
    part_numbers: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    remedy_op_code: Mapped[str | None] = mapped_column(String(32))
    source_chunk_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class RecallVinRange(Base):
    __tablename__ = "recall_vin_ranges"
    __table_args__ = (Index("ix_recall_vin_ranges_model_years", "model_id", "model_year_from", "model_year_to"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    recall_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recalls.id"), index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicle_models.id"))
    model_year_from: Mapped[int] = mapped_column(Integer)
    model_year_to: Mapped[int] = mapped_column(Integer)
    vin_serial_from: Mapped[str] = mapped_column(String(6))  # inclusive
    vin_serial_to: Mapped[str] = mapped_column(String(6))  # inclusive
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Tsb(Base):
    __tablename__ = "tsbs"
    __table_args__ = (Index("ix_tsbs_model_years", "model_id", "model_year_from", "model_year_to"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    tsb_code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(Text)
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicle_models.id"))
    model_year_from: Mapped[int] = mapped_column(Integer)
    model_year_to: Mapped[int] = mapped_column(Integer)
    vin_serial_from: Mapped[str | None] = mapped_column(String(6))
    vin_serial_to: Mapped[str | None] = mapped_column(String(6))
    dtcs: Mapped[list[str]] = mapped_column(ARRAY(String(5)), default=list)
    symptom_keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    op_code: Mapped[str | None] = mapped_column(String(32))
    source_chunk_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class MaintenanceAlert(Base):
    """Optional P4-0 (predictive maintenance)."""

    __tablename__ = "maintenance_alerts"
    id: Mapped[uuid.UUID] = uuid_pk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), index=True)
    signal: Mapped[str] = mapped_column(String(64))
    evidence_window: Mapped[dict[str, object]] = mapped_column(JSONB)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    recommended_section_chunk_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
