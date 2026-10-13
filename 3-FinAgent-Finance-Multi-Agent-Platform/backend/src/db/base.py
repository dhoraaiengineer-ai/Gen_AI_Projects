"""Declarative base, naming convention and shared column helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

EMBEDDING_DIMENSIONS = 1536


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TenantScoped:
    """Rows owned by one tenant (ADR-026). Queries are filtered automatically by the session."""

    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805 - SQLAlchemy declared_attr convention
        return mapped_column(
            Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
        )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CreatedMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


def in_list(column: str, values: tuple[str, ...]) -> str:
    """SQL text for a CHECK constraint restricting ``column`` to ``values``."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
