"""Reference and market data: instruments, daily prices, benchmarks, financial statements."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import ASSET_CLASSES, CURRENCIES, FISCAL_PERIODS
from src.db.base import Base, TimestampMixin, in_list

PRICE = Numeric(18, 6)
MONEY = Numeric(20, 2)


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint(in_list("asset_class", ASSET_CLASSES), name="asset_class"),
        CheckConstraint(in_list("currency", CURRENCIES), name="currency"),
        CheckConstraint("ticker ~ '^[A-Z][A-Z0-9.\\-]{0,9}$'", name="ticker_format"),
        Index("ix_instruments_sector", "sector"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)
    sector: Mapped[str] = mapped_column(String(60), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    exchange: Mapped[str | None] = mapped_column(String(20))
    cusip: Mapped[str | None] = mapped_column(String(9), unique=True)
    market_cap_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MarketData(Base):
    """Daily OHLCV (the Build spec's ``prices``)."""

    __tablename__ = "market_data"
    __table_args__ = (
        CheckConstraint("open > 0 AND high > 0 AND low > 0 AND close > 0", name="positive_prices"),
        CheckConstraint("high >= low", name="high_ge_low"),
        CheckConstraint("volume >= 0", name="volume_nonneg"),
        Index("ix_market_data_trade_date", "trade_date"),
    )

    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    high: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    low: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    adj_close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Benchmark(TimestampMixin, Base):
    __tablename__ = "benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False, unique=True
    )


class FinancialStatement(TimestampMixin, Base):
    """One row per instrument and fiscal period with the main line items (USD)."""

    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint("instrument_id", "fiscal_year", "fiscal_period"),
        CheckConstraint(in_list("fiscal_period", FISCAL_PERIODS), name="fiscal_period"),
        CheckConstraint("fiscal_year BETWEEN 1990 AND 2100", name="fiscal_year"),
        CheckConstraint("revenue >= 0", name="revenue_nonneg"),
        CheckConstraint("total_assets >= 0", name="assets_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(2), nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    revenue: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cost_of_revenue: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    operating_income: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_income: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    ebitda: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    interest_expense: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_assets: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_liabilities: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_equity: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    current_assets: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    current_liabilities: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_debt: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cash: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    operating_cash_flow: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    capex: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    shares_outstanding: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
