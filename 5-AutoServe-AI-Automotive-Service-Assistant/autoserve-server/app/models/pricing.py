"""labour_ops, parts, estimate_lines. Amounts are written only by rules/calculator.py (ADR-006)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Hours, Money, created_at, in_list, updated_at, uuid_pk


class LabourOp(Base):
    __tablename__ = "labour_ops"
    __table_args__ = (UniqueConstraint("op_code", "model_id", name="uq_labour_ops_op_model"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    op_code: Mapped[str] = mapped_column(String(32), index=True)
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicle_models.id"))
    description: Mapped[str] = mapped_column(Text)
    flat_rate_hours: Mapped[Decimal] = mapped_column(Hours)  # from labour_time_guide.csv
    source_file: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Part(Base):
    __tablename__ = "parts"
    id: Mapped[uuid.UUID] = uuid_pk()
    part_number: Mapped[str] = mapped_column(String(32), unique=True)
    description: Mapped[str] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(Money)  # from parts_price_list.csv
    component_group: Mapped[str] = mapped_column(String(64))
    source_file: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class EstimateLine(Base):
    __tablename__ = "estimate_lines"
    __table_args__ = (
        CheckConstraint(in_list("kind", ("labour", "part", "tax")), name="kind_valid"),
        CheckConstraint(in_list("pay_type", ("warranty", "recall", "customer")), name="pay_type_valid"),
        CheckConstraint(
            f"owner_decision IS NULL OR {in_list('owner_decision', ('approved', 'declined'))}", name="decision_valid"
        ),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    op_code: Mapped[str | None] = mapped_column(String(32))
    part_number: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    hours: Mapped[Decimal | None] = mapped_column(Hours)
    unit_price: Mapped[Decimal] = mapped_column(Money)
    amount: Mapped[Decimal] = mapped_column(Money)
    pay_type: Mapped[str] = mapped_column(String(16))
    owner_decision: Mapped[str | None] = mapped_column(String(16))
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
