"""ORM model — users table (belongs to organization; roles: admin, viewer).

Mirrors migrations 0002 (table + uq_users_org_email + ck_users_role) and
0003 (indexes). email is unique only *within* an org (composite), not
globally — matching the as-built schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
        CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_email", "email"),
        Index("ix_users_deleted_at", "deleted_at"),
        Index("ix_users_org_email", "organization_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="viewer",
        # values: admin | viewer
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # soft-delete

    # Relationships
    organization: Mapped[Organization] = relationship(back_populates=None)  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
