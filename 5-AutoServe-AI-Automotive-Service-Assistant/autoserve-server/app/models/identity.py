"""dealers, roles, users."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, created_at, in_list, updated_at, uuid_pk
from app.models.enums import Role, values


class Dealer(Base):
    __tablename__ = "dealers"
    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(Text)
    labour_rate: Mapped[Decimal] = mapped_column(Money)
    tax_profile: Mapped[str] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class RoleRow(Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint(in_list("name", values(Role)), name="name_valid"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)  # PII
    display_name: Mapped[str] = mapped_column(Text)  # PII
    phone: Mapped[str | None] = mapped_column(String(32))  # PII
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), index=True)
    dealer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dealers.id"), index=True)
    password_hash: Mapped[str | None] = mapped_column(Text)  # DEMO auth only
    oidc_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    role: Mapped[RoleRow] = relationship(lazy="joined")
