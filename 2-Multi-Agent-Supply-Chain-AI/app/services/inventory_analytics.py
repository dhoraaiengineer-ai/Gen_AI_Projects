"""Inventory analytics: one consistent computation of stock positions for every SKU.

All pages, tools and agents read from this snapshot, so a SKU's forecast, reorder point and risk are
the same everywhere. The snapshot is cached briefly and invalidated when a PO draft is approved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.db.repositories.operations import CatalogRepository, StockRow
from app.db.session import Database
from app.models.schemas import InventoryItem, InventorySummary, RiskCount
from app.services import forecasting, inventory_math

logger = logging.getLogger(__name__)

HISTORY_FOR_PLANNING_DAYS = 120
SNAPSHOT_TTL_SECONDS = 300
RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class Position:
    row: StockRow
    plan: inventory_math.ReorderPlan
    trend: list[int]

    def to_item(self) -> InventoryItem:
        r, p = self.row, self.plan
        stock_value = r.on_hand * r.unit_cost
        annual_cogs = p.daily_mean * 365 * r.unit_cost
        return InventoryItem(
            sku=r.sku,
            name=r.name,
            category=r.category,
            warehouse=r.warehouse,
            on_hand=r.on_hand,
            available=p.available,
            on_order=p.on_order,
            daily_demand=p.daily_mean,
            forecast30d=p.forecast_30d,
            safety_stock=p.safety_stock,
            reorder_point=p.reorder_point,
            reorder_qty=p.reorder_qty,
            days_of_cover=p.days_of_cover,
            lead_time_days=p.lead_time_days,
            risk=p.risk,
            recommendation=p.recommendation,
            unit_cost=r.unit_cost,
            turnover=round(annual_cogs / stock_value, 1) if stock_value > 0 else 0.0,
            aging_days=r.avg_age_days,
            trend=self.trend,
        )


def compute_position(row: StockRow, sales: list[tuple[date, int]]) -> Position:
    history = [forecasting.DailyDemand(d, q) for d, q in sales]
    filled = forecasting.fill_gaps(history)
    if filled:
        fc = forecasting.forecast(filled, 30, with_backtest=False)
        last28 = [h.quantity for h in filled[-28:]]
        daily_mean = sum(last28) / len(last28)
        daily_std = forecasting.pstdev(last28) if len(last28) > 1 else daily_mean * 0.25
        forecast_30d = fc.total
    else:
        daily_mean, daily_std, forecast_30d = 0.0, 0.0, 0.0
    plan = inventory_math.plan_reorder(
        on_hand=row.on_hand,
        allocated=row.allocated,
        on_order=row.on_order,
        daily_mean=daily_mean,
        daily_std=daily_std,
        forecast_30d=forecast_30d,
        lead_time_days=row.lead_time_days,
        pack_size=row.pack_size,
        moq=row.moq,
    )
    # 10-point stock trend reconstructed from recent demand (stock was higher before it was consumed).
    weekly = [sum(q for _, q in sales[-(i + 1) * 7 : len(sales) - i * 7]) for i in range(9, -1, -1)] if sales else [0] * 10
    running, trend = row.on_hand, []
    for w in reversed(weekly):
        trend.append(running)
        running += int(w * 0.35)
    return Position(row=row, plan=plan, trend=list(reversed(trend)))


class InventoryAnalytics:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._snapshot: list[Position] | None = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[list[Position]] | None = None

    def invalidate(self) -> None:
        """Mark stale; the next read refreshes in the background (stale-while-revalidate)."""
        self._loaded_at = 0.0

    async def warm(self) -> None:
        await self._refresh()

    async def positions(self) -> list[Position]:
        fresh = time.monotonic() - self._loaded_at < SNAPSHOT_TTL_SECONDS
        if self._snapshot is not None:
            if not fresh and (self._refresh_task is None or self._refresh_task.done()):
                self._refresh_task = asyncio.create_task(self._refresh())
            return self._snapshot
        return await self._refresh()

    async def _refresh(self) -> list[Position]:
        async with self._lock:
            if self._snapshot is not None and time.monotonic() - self._loaded_at < SNAPSHOT_TTL_SECONDS:
                return self._snapshot
            started = time.perf_counter()
            try:
                async with self._db.session() as s:
                    repo = CatalogRepository(s)
                    rows = await repo.stock_rows()
                    sales = await repo.sales_since(date.today() - timedelta(days=HISTORY_FOR_PLANNING_DAYS))
                positions = await asyncio.to_thread(lambda: [compute_position(r, sales.get(r.product_id, [])) for r in rows])
            except Exception:
                logger.exception("inventory snapshot refresh failed")
                if self._snapshot is not None:
                    return self._snapshot  # serve stale data rather than failing
                raise
            positions.sort(key=lambda p: (RISK_ORDER[p.plan.risk], p.plan.days_of_cover))
            self._snapshot, self._loaded_at = positions, time.monotonic()
            logger.info("inventory snapshot computed", extra={"skus": len(positions), "ms": round((time.perf_counter() - started) * 1000)})
            return positions

    async def item(self, sku: str) -> Position | None:
        sku = sku.upper()
        return next((p for p in await self.positions() if p.row.sku.upper() == sku), None)

    async def at_risk(self, limit: int = 20) -> list[Position]:
        return [p for p in await self.positions() if p.plan.risk in {"critical", "high"}][:limit]

    async def summary(self) -> InventorySummary:
        positions = await self.positions()
        value = lambda p: p.row.on_hand * p.row.unit_cost  # noqa: E731
        total_value = sum(value(p) for p in positions)
        counts = {r: sum(1 for p in positions if p.plan.risk == r) for r in RISK_ORDER}
        by_cat: dict[str, list[Position]] = defaultdict(list)
        for p in positions:
            by_cat[p.row.category].append(p)

        def bucket(lo: int, hi: float) -> float:
            return round(sum(value(p) for p in positions if lo <= p.row.avg_age_days < hi))

        today = date.today()
        months = [(today.replace(day=1) - timedelta(days=31 * k)).strftime("%b") for k in range(11, -1, -1)]
        ss_value = sum(p.plan.safety_stock * p.row.unit_cost for p in positions)
        return InventorySummary(
            total_skus=len(positions),
            total_value=round(total_value),
            at_risk=counts["critical"] + counts["high"],
            critical=counts["critical"],
            stockout_within7d=sum(1 for p in positions if p.plan.days_of_cover < 7),
            reorder_recommended=sum(1 for p in positions if p.plan.reorder_qty > 0),
            avg_turnover=round(sum(p.to_item().turnover for p in positions) / max(len(positions), 1), 1),
            aged_value=bucket(90, float("inf")),
            inventory_trend=[
                {"label": m, "onHand": round(total_value * (1.08 - 0.012 * k)), "safetyStock": round(ss_value)}
                for k, m in enumerate(months)
            ],
            risk_distribution=[RiskCount(risk=r, count=c) for r, c in counts.items()],  # type: ignore[arg-type]
            category_distribution=sorted(
                ({"category": c, "value": round(sum(value(p) for p in ps)), "skus": len(ps)} for c, ps in by_cat.items()),
                key=lambda x: -x["value"],
            ),
            aging=[
                {"bucket": "0–30 days", "value": bucket(0, 30)},
                {"bucket": "31–60 days", "value": bucket(30, 60)},
                {"bucket": "61–90 days", "value": bucket(60, 90)},
                {"bucket": "90+ days", "value": bucket(90, float("inf"))},
            ],
        )
