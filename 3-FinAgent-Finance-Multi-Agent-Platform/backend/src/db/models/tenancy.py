"""Tenants (ADR-026): one row per asset-management firm using the platform."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, in_list

TENANT_STATUSES = ("active", "suspended")
TENANT_PLANS = ("demo", "standard", "enterprise")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,40}$'", name="slug_format"),
        CheckConstraint(in_list("status", TENANT_STATUSES), name="status"),
        CheckConstraint(in_list("plan", TENANT_PLANS), name="plan"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(42), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    plan: Mapped[str] = mapped_column(String(12), nullable=False, default="standard")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
