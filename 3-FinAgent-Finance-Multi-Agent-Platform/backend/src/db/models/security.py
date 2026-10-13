"""Users (profiles keyed by the Supabase auth id), roles, permissions, audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import Role
from src.db.base import Base, CreatedMixin, TenantScoped, TimestampMixin, in_list

ROLE_VALUES = tuple(r.value for r in Role)


class RoleRow(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint(in_list("name", ROLE_VALUES), name="name"),)

    name: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"
    __table_args__ = (CheckConstraint("name ~ '^[a-z_]+:[a-z_*]+$'", name="name_format"),)

    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role: Mapped[str] = mapped_column(
        ForeignKey("roles.name", ondelete="CASCADE"), primary_key=True
    )
    permission: Mapped[str] = mapped_column(
        ForeignKey("permissions.name", ondelete="CASCADE"), primary_key=True
    )


class User(TenantScoped, TimestampMixin, Base):
    """Application profile. Authentication lives in Supabase; no passwords stored here."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(
        ForeignKey("roles.name", ondelete="RESTRICT"), nullable=False, default="viewer"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(TenantScoped, CreatedMixin, Base):
    """Append-only audit trail: decisions and reasons, never secrets or raw sensitive data."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_request", "request_id"),
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(32))
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    user_role: Mapped[str | None] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(120))
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="allow")
    reason: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
