"""Aggregate queries for dashboards and executive analytics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentEvent, Product, PurchaseOrder, Sale, Supplier, SupplierProduct

_ON_TIME = func.sum(func.cast(PurchaseOrder.received_at <= PurchaseOrder.expected_at, Integer))


class ReportingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def supplier_categories(self) -> dict[str, list[str]]:
        stmt = select(SupplierProduct.supplier_id, Product.category).join(Product, Product.id == SupplierProduct.product_id).distinct()
        cats: dict[str, list[str]] = {}
        for sid, cat in (await self.s.execute(stmt)).all():
            cats.setdefault(sid, []).append(cat)
        return {k: sorted(v) for k, v in cats.items()}

    async def monthly_demand(self, since: date) -> dict[str, int]:
        month = func.to_char(Sale.sale_date, "YYYY-MM")
        stmt = select(month, func.sum(Sale.quantity)).where(Sale.sale_date >= since).group_by(month)
        return {m: int(q) for m, q in (await self.s.execute(stmt)).all()}

    async def monthly_receipts(self, since: date) -> dict[str, int]:
        month = func.to_char(PurchaseOrder.received_at, "YYYY-MM")
        stmt = select(month, func.sum(PurchaseOrder.quantity)).where(PurchaseOrder.received_at >= since).group_by(month)
        return {m: int(q) for m, q in (await self.s.execute(stmt)).all() if m}

    async def monthly_delivery(self, since: datetime) -> list[tuple[str, int, int]]:
        """(YYYY-MM, on-time receipts, total receipts)."""
        month = func.to_char(PurchaseOrder.received_at, "YYYY-MM")
        stmt = (
            select(month, _ON_TIME, func.count())
            .where(PurchaseOrder.status == "received", PurchaseOrder.received_at >= since)
            .group_by(month)
            .order_by(month)
        )
        return [(m, int(ok or 0), int(n)) for m, ok, n in (await self.s.execute(stmt)).all()]

    async def supplier_performance(self, since: datetime) -> list[tuple[str, int, int, float]]:
        """(supplier name, on-time receipts, total receipts, defect rate), best on-time first."""
        stmt = (
            select(Supplier.name, _ON_TIME, func.count(), Supplier.defect_rate)
            .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
            .where(PurchaseOrder.status == "received", PurchaseOrder.received_at >= since)
            .group_by(Supplier.id)
            .order_by(func.avg(func.cast(PurchaseOrder.received_at <= PurchaseOrder.expected_at, Integer)).desc())
        )
        return [(name, int(ok or 0), int(n), float(defect)) for name, ok, n, defect in (await self.s.execute(stmt)).all()]

    async def monthly_workflows(self) -> list[tuple[str, int, int]]:
        """(YYYY-MM, supervisor workflows, workflows escalated to approval)."""
        month = func.to_char(AgentEvent.ts, "YYYY-MM")
        stmt = (
            select(month, func.count(), func.sum(func.cast(AgentEvent.kind == "approval", Integer)))
            .where(AgentEvent.agent == "supervisor")
            .group_by(month)
            .order_by(month)
        )
        return [(m, int(n), int(esc or 0)) for m, n, esc in (await self.s.execute(stmt)).all()]


def as_dict(rows: list[tuple[Any, ...]]) -> dict[Any, Any]:
    return {r[0]: r[1:] for r in rows}
