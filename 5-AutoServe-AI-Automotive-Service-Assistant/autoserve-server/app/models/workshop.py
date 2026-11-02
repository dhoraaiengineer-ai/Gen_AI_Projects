"""appointments, dealer_capacity, repair_orders, ro_status_history, ro_complaints, diagnostic_findings."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Hours, created_at, in_list, updated_at, uuid_pk
from app.models.enums import ROStatus, values

_STATUS_ACTORS = ("vehicle_owner", "service_advisor", "technician", "warranty_admin", "admin", "system")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_dealer_slot", "dealer_id", "slot_start"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), index=True)
    dealer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dealers.id"))
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="booked")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class DealerCapacity(Base):
    """DEMO capacity table."""

    __tablename__ = "dealer_capacity"
    __table_args__ = (
        UniqueConstraint("dealer_id", "day", "slot", name="uq_dealer_capacity_slot"),
        CheckConstraint("booked >= 0 AND booked <= capacity", name="booked_within_capacity"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    dealer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dealers.id"))
    day: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(5))  # "HH:MM"
    capacity: Mapped[int] = mapped_column(Integer)
    booked: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class RepairOrder(Base):
    __tablename__ = "repair_orders"
    __table_args__ = (
        Index("ix_repair_orders_dealer_status", "dealer_id", "status"),
        CheckConstraint(in_list("status", values(ROStatus)), name="status_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_ref: Mapped[str] = mapped_column(String(16), unique=True, server_default=text("next_ro_ref()"))
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), index=True)
    dealer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dealers.id"))
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"))
    status: Mapped[str] = mapped_column(String(32), default=ROStatus.DRAFT.value)
    odometer_in_km: Mapped[int | None] = mapped_column(Integer)
    fuel_or_charge_level: Mapped[str | None] = mapped_column(String(32))
    damage_notes: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    promised_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # advisor-set ETA only
    graph_thread_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ROStatusHistory(Base):
    __tablename__ = "ro_status_history"
    __table_args__ = (
        Index("ix_ro_status_history_ro_created", "ro_id", "created_at"),
        CheckConstraint(in_list("actor_role", _STATUS_ACTORS), name="actor_role_valid"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class ROComplaint(Base):
    __tablename__ = "ro_complaints"
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    complaint_text: Mapped[str] = mapped_column(Text)  # owner's verbatim words; PII-risk free text
    confirmed_by_advisor: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class DiagnosticFinding(Base):
    __tablename__ = "diagnostic_findings"
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    technician_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    dtcs: Mapped[list[str]] = mapped_column(ARRAY(String(5)), default=list)
    symptoms: Mapped[str | None] = mapped_column(Text)
    test_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    confirmed_hypothesis: Mapped[str | None] = mapped_column(Text)
    op_codes_performed: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    actual_hours: Mapped[Decimal | None] = mapped_column(Hours)
    parts_used: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)  # technician free text (PII-risk, never logged)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
