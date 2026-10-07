"""Read/write access to operational data: catalog, inventory, sales, suppliers, logistics, purchase orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Integer, Select, and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Carrier,
    Inventory,
    Product,
    PurchaseOrder,
    Sale,
    Shipment,
    Supplier,
    SupplierProduct,
)


@dataclass(frozen=True)
class StockRow:
    product_id: int
    sku: str
    name: str
    category: str
    unit_cost: float
    pack_size: int
    warehouse: str
    on_hand: int
    allocated: int
    on_order: int
    avg_age_days: int
    lead_time_days: int
    moq: int


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def stock_rows(self) -> list[StockRow]:
        """Every active product with its inventory and preferred-supplier lead time (one row per product)."""
        preferred = (
            select(
                SupplierProduct.product_id,
                func.min(SupplierProduct.lead_time_days).filter(SupplierProduct.preferred).label("pref_lt"),
                func.min(SupplierProduct.lead_time_days).label("min_lt"),
                func.min(SupplierProduct.moq).label("moq"),
            )
            .group_by(SupplierProduct.product_id)
            .subquery()
        )
        stmt = (
            select(
                Product.id,
                Product.sku,
                Product.name,
                Product.category,
                Product.unit_cost,
                Product.pack_size,
                func.min(Inventory.warehouse),
                func.sum(Inventory.on_hand),
                func.sum(Inventory.allocated),
                func.sum(Inventory.on_order),
                func.max(Inventory.avg_age_days),
                func.coalesce(func.max(preferred.c.pref_lt), func.max(preferred.c.min_lt), 14),
                func.coalesce(func.max(preferred.c.moq), 1),
            )
            .join(Inventory, Inventory.product_id == Product.id)
            .outerjoin(preferred, preferred.c.product_id == Product.id)
            .where(Product.active.is_(True))
            .group_by(Product.id)
        )
        rows = (await self.s.execute(stmt)).all()
        return [
            StockRow(
                r[0], r[1], r[2], r[3], float(r[4]), int(r[5]), r[6], int(r[7]), int(r[8]), int(r[9]), int(r[10]), int(r[11]), int(r[12])
            )
            for r in rows
        ]

    async def product_by_sku(self, sku: str) -> Product | None:
        return (await self.s.execute(select(Product).where(func.upper(Product.sku) == sku.upper()))).scalar_one_or_none()

    async def sales_since(self, since: date, product_id: int | None = None) -> dict[int, list[tuple[date, int]]]:
        """Daily sales per product, aggregated into arrays in Postgres (one row per product, not per day)."""
        stmt = (
            select(
                Sale.product_id,
                func.array_agg(aggregate_order_by(Sale.sale_date, Sale.sale_date)),
                func.array_agg(aggregate_order_by(Sale.quantity, Sale.sale_date)),
            )
            .where(Sale.sale_date >= since)
            .group_by(Sale.product_id)
        )
        if product_id is not None:
            stmt = stmt.where(Sale.product_id == product_id)
        return {pid: list(zip(days, (int(q) for q in qtys), strict=True)) for pid, days, qtys in (await self.s.execute(stmt)).all()}

    async def _sales_rows(self, since: date, product_id: int | None = None) -> dict[int, list[tuple[date, int]]]:
        stmt = select(Sale.product_id, Sale.sale_date, Sale.quantity).where(Sale.sale_date >= since)
        if product_id is not None:
            stmt = stmt.where(Sale.product_id == product_id)
        out: dict[int, list[tuple[date, int]]] = {}
        for pid, d, q in (await self.s.execute(stmt.order_by(Sale.sale_date))).all():
            out.setdefault(pid, []).append((d, int(q)))
        return out

    async def search_products(self, term: str, limit: int = 10) -> list[tuple[str, str]]:
        like = f"%{term}%"
        stmt = (
            select(Product.sku, Product.name)
            .where(or_(Product.sku.ilike(like), Product.name.ilike(like)))
            .order_by(Product.sku)
            .limit(limit)
        )
        return [(r[0], r[1]) for r in (await self.s.execute(stmt)).all()]

    async def count_products(self) -> int:
        return int((await self.s.execute(select(func.count(Product.id)))).scalar_one())


@dataclass(frozen=True)
class QuoteRow:
    supplier_id: str
    name: str
    country: str
    region: str
    unit_price: float
    moq: int
    lead_time_days: int
    on_time_rate: float
    defect_rate: float
    fill_rate: float
    risk: str
    contract_expiry: date
    certifications: list[str]
    preferred: bool


class SupplierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def list_suppliers(self) -> list[tuple[Supplier, float, int, int]]:
        """Suppliers with their average unit price, average lead time and number of SKUs supplied."""
        stmt = (
            select(
                Supplier,
                func.avg(SupplierProduct.unit_price),
                func.avg(SupplierProduct.lead_time_days),
                func.count(SupplierProduct.product_id),
                func.min(SupplierProduct.moq),
            )
            .outerjoin(SupplierProduct, SupplierProduct.supplier_id == Supplier.id)
            .where(Supplier.active.is_(True))
            .group_by(Supplier.id)
        )
        return [(r[0], float(r[1] or 0), round(float(r[2] or 0)), int(r[3]), int(r[4] or 1)) for r in (await self.s.execute(stmt)).all()]

    async def quotes_for_product(self, product_id: int) -> list[QuoteRow]:
        stmt = (
            select(Supplier, SupplierProduct)
            .join(SupplierProduct, SupplierProduct.supplier_id == Supplier.id)
            .where(SupplierProduct.product_id == product_id, Supplier.active.is_(True))
            .order_by(SupplierProduct.unit_price)
        )
        return [
            QuoteRow(
                s.id,
                s.name,
                s.country,
                s.region,
                float(sp.unit_price),
                sp.moq,
                sp.lead_time_days,
                s.on_time_rate,
                s.defect_rate,
                s.fill_rate,
                s.risk,
                s.contract_expiry,
                list(s.certifications),
                sp.preferred,
            )
            for s, sp in (await self.s.execute(stmt)).all()
        ]

    async def get(self, supplier_id: str) -> Supplier | None:
        return await self.s.get(Supplier, supplier_id)


class LogisticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    def _base(self) -> Select[Any]:
        return (
            select(Shipment, Product.sku, Product.name, Supplier.name, Carrier.name, Carrier.mode, PurchaseOrder.po_number)
            .join(Product, Product.id == Shipment.product_id)
            .join(Supplier, Supplier.id == Shipment.supplier_id)
            .join(Carrier, Carrier.id == Shipment.carrier_id)
            .outerjoin(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        )

    async def shipments(
        self, *, status: str | None = None, sku: str | None = None, search: str | None = None, limit: int = 500
    ) -> list[tuple[Any, ...]]:
        stmt = self._base()
        conds = []
        if status:
            conds.append(Shipment.status == status)
        if sku:
            conds.append(func.upper(Product.sku) == sku.upper())
        if search:
            like = f"%{search}%"
            conds.append(
                or_(
                    Shipment.id.ilike(like),
                    Product.sku.ilike(like),
                    Carrier.name.ilike(like),
                    Shipment.origin.ilike(like),
                    Shipment.destination.ilike(like),
                )
            )
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by((Shipment.status == "delayed").desc(), Shipment.eta).limit(limit)
        return [tuple(r) for r in (await self.s.execute(stmt)).all()]

    async def shipment(self, shipment_id: str) -> tuple[Any, ...] | None:
        row = (await self.s.execute(self._base().where(Shipment.id == shipment_id))).first()
        return tuple(row) if row else None

    async def carriers(self) -> list[Carrier]:
        return list((await self.s.execute(select(Carrier).order_by(Carrier.name))).scalars())

    async def carriers_for_mode(self, mode: str | None) -> list[Carrier]:
        stmt = select(Carrier)
        if mode:
            stmt = stmt.where(Carrier.mode == mode)
        return list((await self.s.execute(stmt)).scalars())

    async def active_counts_by_carrier(self) -> dict[int, int]:
        stmt = select(Shipment.carrier_id, func.count()).where(Shipment.status != "delivered").group_by(Shipment.carrier_id)
        return {int(cid): int(n) for cid, n in (await self.s.execute(stmt)).all()}


class PurchaseOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create_draft(
        self, *, product_id: int, supplier_id: str, quantity: int, unit_price: float, created_by: str, approved_by: str | None
    ) -> PurchaseOrder:
        next_no = int((await self.s.execute(select(func.coalesce(func.max(PurchaseOrder.id), 0)))).scalar_one()) + 1
        po = PurchaseOrder(
            po_number=f"PO-D{next_no:06d}",
            product_id=product_id,
            supplier_id=supplier_id,
            quantity=quantity,
            unit_price=unit_price,
            status="draft",
            created_by=created_by,
            approved_by=approved_by,
        )
        self.s.add(po)
        await self.s.flush()
        return po

    async def mark_on_order(self, product_id: int, quantity: int) -> None:
        """Approved drafts count as inbound stock for planning (the PO itself is still a draft)."""
        await self.s.execute(update(Inventory).where(Inventory.product_id == product_id).values(on_order=Inventory.on_order + quantity))

    async def supplier_on_time(self, since: datetime) -> dict[str, float]:
        """Share of received POs delivered by their expected date, per supplier."""
        on_time = func.sum(func.cast(PurchaseOrder.received_at <= PurchaseOrder.expected_at, Integer))
        stmt = (
            select(PurchaseOrder.supplier_id, on_time, func.count())
            .where(PurchaseOrder.status == "received", PurchaseOrder.received_at >= since)
            .group_by(PurchaseOrder.supplier_id)
        )
        return {sid: (float(ok or 0) / n if n else 0.0) for sid, ok, n in (await self.s.execute(stmt)).all()}
