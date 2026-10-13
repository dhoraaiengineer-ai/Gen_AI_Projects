"""Portfolios, holdings snapshots, trades and risk limits (read-only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Float, cast, func, or_, select

from src.db.models import Holding, Instrument, Portfolio, RiskLimit, Trade
from src.db.session import Database
from src.services.concentration import Limit


@dataclass(frozen=True)
class PortfolioInfo:
    id: int
    code: str
    name: str
    strategy: str
    base_currency: str
    cash: float
    inception_date: date
    manager_name: str | None


@dataclass(frozen=True)
class HoldingRow:
    ticker: str
    name: str
    sector: str
    asset_class: str
    quantity: float
    avg_cost: float


@dataclass(frozen=True)
class TradeRow:
    trade_date: date
    ticker: str
    side: str
    quantity: float
    price: float
    fees: float


def _portfolio(row: Portfolio) -> PortfolioInfo:
    return PortfolioInfo(
        row.id,
        row.code,
        row.name,
        row.strategy,
        row.base_currency,
        float(row.cash),
        row.inception_date,
        row.manager_name,
    )


class PortfolioRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def list_all(self) -> list[PortfolioInfo]:
        async with self.db.sessions() as session:
            return [
                _portfolio(r)
                for r in await session.scalars(select(Portfolio).order_by(Portfolio.code))
            ]

    async def get(self, code: str) -> PortfolioInfo | None:
        async with self.db.sessions() as session:
            row = await session.scalar(select(Portfolio).where(Portfolio.code == code))
            return _portfolio(row) if row else None

    async def snapshot_dates(self, portfolio_id: int) -> list[date]:
        stmt = (
            select(Holding.as_of_date.label("as_of_date"))
            .where(Holding.portfolio_id == portfolio_id)
            .group_by(Holding.as_of_date)
            .order_by(Holding.as_of_date)
        )
        async with self.db.sessions() as session:
            return list(await session.scalars(stmt))

    async def holdings(
        self, portfolio_id: int, as_of: date | None = None
    ) -> tuple[date | None, list[HoldingRow]]:
        """Holdings at the latest snapshot on or before ``as_of`` (default: latest)."""
        latest = select(func.max(Holding.as_of_date)).where(Holding.portfolio_id == portfolio_id)
        if as_of:
            latest = latest.where(Holding.as_of_date <= as_of)
        stmt = (
            select(
                Instrument.ticker.label("ticker"),
                Instrument.name.label("name"),
                Instrument.sector.label("sector"),
                Instrument.asset_class.label("asset_class"),
                cast(Holding.quantity, Float).label("quantity"),
                cast(Holding.avg_cost, Float).label("avg_cost"),
                Holding.as_of_date.label("as_of_date"),
            )
            .join(Instrument, Instrument.id == Holding.instrument_id)
            .where(
                Holding.portfolio_id == portfolio_id, Holding.as_of_date == latest.scalar_subquery()
            )
            .order_by(Instrument.ticker)
        )
        async with self.db.sessions() as session:
            rows = (await session.execute(stmt)).all()
        snapshot = rows[0].as_of_date if rows else None
        return snapshot, [
            HoldingRow(r.ticker, r.name, r.sector, r.asset_class, r.quantity, r.avg_cost)
            for r in rows
        ]

    async def trades(
        self, portfolio_id: int, *, since: date | None = None, limit: int = 100
    ) -> list[TradeRow]:
        stmt = (
            select(
                Trade.trade_date.label("trade_date"),
                Instrument.ticker.label("ticker"),
                Trade.side.label("side"),
                cast(Trade.quantity, Float).label("quantity"),
                cast(Trade.price, Float).label("price"),
                cast(Trade.fees, Float).label("fees"),
            )
            .join(Instrument, Instrument.id == Trade.instrument_id)
            .where(Trade.portfolio_id == portfolio_id)
            .order_by(Trade.trade_date.desc(), Instrument.ticker)
            .limit(limit)
        )
        if since:
            stmt = stmt.where(Trade.trade_date >= since)
        async with self.db.sessions() as session:
            return [TradeRow(*r) for r in (await session.execute(stmt)).all()]

    async def limits(self, portfolio_id: int) -> list[Limit]:
        """Active limits for the portfolio; portfolio-specific limits override global ones."""
        stmt = select(RiskLimit).where(
            RiskLimit.active.is_(True),
            or_(RiskLimit.portfolio_id.is_(None), RiskLimit.portfolio_id == portfolio_id),
        )
        async with self.db.sessions() as session:
            rows = list(await session.scalars(stmt))
        chosen: dict[tuple[str, str | None], RiskLimit] = {}
        for r in sorted(rows, key=lambda x: x.portfolio_id is not None):  # specific last → wins
            chosen[(r.limit_type, r.scope)] = r
        return [
            Limit(r.limit_type, float(r.threshold), r.severity, r.scope, r.policy_reference)
            for r in chosen.values()
        ]
