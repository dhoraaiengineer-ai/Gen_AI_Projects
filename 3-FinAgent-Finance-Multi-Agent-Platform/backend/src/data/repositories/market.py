"""Instruments, prices, benchmark and financial statements (read-only).

Price history is aggregated in SQL (one row per instrument with ``array_agg`` ordered by date)
instead of loading one row per day per instrument.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
from sqlalchemy import ColumnElement, Float, Select, cast, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from src.db.models import Benchmark, FinancialStatement, Instrument, MarketData
from src.db.session import Database
from src.services.fundamentals import Statement


@dataclass(frozen=True)
class InstrumentInfo:
    id: int
    ticker: str
    name: str
    asset_class: str
    sector: str
    industry: str | None
    currency: str
    exchange: str | None
    market_cap_usd: float | None


@dataclass(frozen=True)
class PriceSeries:
    ticker: str
    dates: list[date]
    close: np.ndarray
    volume: np.ndarray

    @property
    def last(self) -> float:
        return float(self.close[-1])

    @property
    def last_date(self) -> date:
        return self.dates[-1]


def _info(row: Instrument) -> InstrumentInfo:
    return InstrumentInfo(
        row.id,
        row.ticker,
        row.name,
        row.asset_class,
        row.sector,
        row.industry,
        row.currency,
        row.exchange,
        float(row.market_cap_usd) if row.market_cap_usd is not None else None,
    )


class MarketRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def instruments(self, tickers: Sequence[str]) -> dict[str, InstrumentInfo]:
        async with self.db.sessions() as session:
            rows = await session.scalars(select(Instrument).where(Instrument.ticker.in_(tickers)))
            return {r.ticker: _info(r) for r in rows}

    async def search_instruments(self, text: str, limit: int = 10) -> list[InstrumentInfo]:
        pattern = f"%{text}%"
        stmt = (
            select(Instrument)
            .where((Instrument.ticker.ilike(pattern)) | (Instrument.name.ilike(pattern)))
            .order_by(Instrument.ticker)
            .limit(limit)
        )
        async with self.db.sessions() as session:
            return [_info(r) for r in await session.scalars(stmt)]

    def _history_stmt(
        self, tickers: Sequence[str], start: date | None, end: date | None
    ) -> Select[Any, Any, Any, Any]:
        conditions: list[ColumnElement[bool]] = [Instrument.ticker.in_(tickers)]
        if start:
            conditions.append(MarketData.trade_date >= start)
        if end:
            conditions.append(MarketData.trade_date <= end)
        return (
            select(
                Instrument.ticker.label("ticker"),
                func.array_agg(
                    aggregate_order_by(MarketData.trade_date, MarketData.trade_date)
                ).label("dates"),
                func.array_agg(
                    aggregate_order_by(cast(MarketData.close, Float), MarketData.trade_date)
                ).label("close"),
                func.array_agg(aggregate_order_by(MarketData.volume, MarketData.trade_date)).label(
                    "volume"
                ),
            )
            .join(MarketData, MarketData.instrument_id == Instrument.id)
            .where(*conditions)
            .group_by(Instrument.ticker)
        )

    async def price_history(
        self, tickers: Sequence[str], start: date | None = None, end: date | None = None
    ) -> dict[str, PriceSeries]:
        async with self.db.sessions() as session:
            rows = (await session.execute(self._history_stmt(tickers, start, end))).all()
        return {
            r.ticker: PriceSeries(
                r.ticker,
                list(r.dates),
                np.asarray(r.close, dtype=np.float64),
                np.asarray(r.volume, dtype=np.int64),
            )
            for r in rows
        }

    async def last_prices(
        self, tickers: Sequence[str], as_of: date | None = None
    ) -> dict[str, tuple[date, float]]:
        latest = (
            select(
                MarketData.instrument_id.label("instrument_id"),
                func.max(MarketData.trade_date).label("trade_date"),
            )
            .join(Instrument, Instrument.id == MarketData.instrument_id)
            .where(Instrument.ticker.in_(tickers))
        )
        if as_of:
            latest = latest.where(MarketData.trade_date <= as_of)
        latest_sq = latest.group_by(MarketData.instrument_id).subquery()
        stmt = (
            select(
                Instrument.ticker.label("ticker"),
                MarketData.trade_date.label("trade_date"),
                cast(MarketData.close, Float).label("close"),
            )
            .join(
                latest_sq,
                (latest_sq.c.instrument_id == MarketData.instrument_id)
                & (latest_sq.c.trade_date == MarketData.trade_date),
            )
            .join(Instrument, Instrument.id == MarketData.instrument_id)
        )
        async with self.db.sessions() as session:
            return {
                r.ticker: (r.trade_date, float(r.close))
                for r in (await session.execute(stmt)).all()
            }

    async def benchmark(self, code: str | None = None) -> InstrumentInfo | None:
        stmt = select(Instrument).join(Benchmark, Benchmark.instrument_id == Instrument.id)
        if code:
            stmt = stmt.where(Benchmark.code == code)
        async with self.db.sessions() as session:
            row = (await session.scalars(stmt.limit(1))).first()
            return _info(row) if row else None

    async def latest_trade_date(self) -> date | None:
        async with self.db.sessions() as session:
            return await session.scalar(select(func.max(MarketData.trade_date).label("d")))

    async def statements(self, ticker: str) -> list[Statement]:
        stmt = (
            select(FinancialStatement)
            .join(Instrument, Instrument.id == FinancialStatement.instrument_id)
            .where(Instrument.ticker == ticker)
            .order_by(FinancialStatement.period_end)
        )
        async with self.db.sessions() as session:
            rows = list(await session.scalars(stmt))

        def f(v: Decimal) -> float:
            return float(v)

        return [
            Statement(
                r.fiscal_year,
                r.fiscal_period,
                f(r.revenue),
                f(r.gross_profit),
                f(r.operating_income),
                f(r.net_income),
                f(r.ebitda),
                f(r.interest_expense),
                f(r.total_assets),
                f(r.total_liabilities),
                f(r.total_equity),
                f(r.current_assets),
                f(r.current_liabilities),
                f(r.total_debt),
                f(r.cash),
                f(r.operating_cash_flow),
                f(r.capex),
                f(r.shares_outstanding),
            )
            for r in rows
        ]


async def all_instruments(db: Database) -> list[InstrumentInfo]:
    """Every instrument (500 rows; used by the market summary)."""
    async with db.sessions() as session:
        return [
            _info(r) for r in await session.scalars(select(Instrument).order_by(Instrument.ticker))
        ]
