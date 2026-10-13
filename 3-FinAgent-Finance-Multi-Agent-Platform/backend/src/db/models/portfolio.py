"""Portfolios, holdings snapshots, trades, risk limits, draft orders and approvals."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import (
    APPROVAL_STATUSES,
    CURRENCIES,
    LIMIT_SEVERITIES,
    LIMIT_TYPES,
    ORDER_STATUSES,
    TRADE_SIDES,
)
from src.db.base import Base, CreatedMixin, TenantScoped, TimestampMixin, in_list
from src.db.models.reference import MONEY, PRICE

QTY = Numeric(20, 6)


class Portfolio(TenantScoped, TimestampMixin, Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        CheckConstraint("code ~ '^PF-[A-Z0-9\\-]{1,20}$'", name="code_format"),
        CheckConstraint(in_list("base_currency", CURRENCIES), name="base_currency"),
        CheckConstraint("cash >= 0", name="cash_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    strategy: Mapped[str] = mapped_column(String(300), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    benchmark_id: Mapped[int | None] = mapped_column(
        ForeignKey("benchmarks.id", ondelete="SET NULL")
    )
    cash: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    inception_date: Mapped[date] = mapped_column(Date, nullable=False)
    manager_name: Mapped[str | None] = mapped_column(String(120))


class Holding(TenantScoped, Base):
    """Holdings snapshot per date; the latest ``as_of_date`` is the current portfolio."""

    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("avg_cost > 0", name="avg_cost_positive"),
        Index("ix_holdings_portfolio_date", "portfolio_id", "as_of_date"),
    )

    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), primary_key=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(PRICE, nullable=False)


class Trade(TenantScoped, CreatedMixin, Base):
    """Executed portfolio trades (history). Agents never write here."""

    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint(in_list("side", TRADE_SIDES), name="side"),
        CheckConstraint("quantity > 0 AND price > 0 AND fees >= 0", name="amounts"),
        Index("ix_trades_portfolio_date", "portfolio_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    fees: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)


class RiskLimit(TenantScoped, TimestampMixin, Base):
    """Policy limits. ``portfolio_id`` NULL = applies to every portfolio."""

    __tablename__ = "risk_limits"
    __table_args__ = (
        CheckConstraint(in_list("limit_type", LIMIT_TYPES), name="limit_type"),
        CheckConstraint(in_list("severity", LIMIT_SEVERITIES), name="severity"),
        CheckConstraint("threshold >= 0", name="threshold_nonneg"),
        UniqueConstraint("tenant_id", "portfolio_id", "limit_type", "scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int | None] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    limit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(60))
    threshold: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="hard")
    policy_reference: Mapped[str | None] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(nullable=False, default=True)


class Approval(TenantScoped, TimestampMixin, Base):
    """Human-in-the-loop approval request. Idempotent per run + proposal."""

    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint(in_list("status", APPROVAL_STATUSES), name="status"),
        CheckConstraint(
            "(status = 'pending') = (decided_at IS NULL) OR status = 'expired'",
            name="decision_consistency",
        ),
        Index("ix_approvals_status_expires", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_id: Mapped[int | None] = mapped_column(
        ForeignKey("portfolios.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    proposal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    total_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now() + interval '24 hours'")
    )


class Order(TenantScoped, TimestampMixin, Base):
    """Draft orders. Never executed by the system; created only after an approval."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(in_list("status", ORDER_STATUSES), name="status"),
        CheckConstraint(in_list("side", TRADE_SIDES), name="side"),
        CheckConstraint("quantity > 0 AND est_price > 0 AND est_value >= 0", name="amounts"),
        Index("ix_orders_portfolio_status", "portfolio_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"), index=True
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    est_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    est_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    rationale: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
