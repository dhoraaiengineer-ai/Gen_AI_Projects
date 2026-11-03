"""ORM model — organizations table (root tenant; all tables scope to this).

Mirrors migrations 0002 (table) + 0003 (indexes). The slug carries BOTH a
unique constraint (uq_organizations_slug) and a plain lookup index
(ix_organizations_slug), exactly as the DB was built.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("name", name="uq_organizations_name"),
        UniqueConstraint("slug", name="uq_organizations_slug"),
        Index("ix_organizations_slug", "slug"),
        Index("ix_organizations_deleted_at", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, server_default="free")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Soft-delete: NULL = active, non-NULL = deleted
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug}>"
