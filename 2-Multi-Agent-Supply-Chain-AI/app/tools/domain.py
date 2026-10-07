"""Supply-chain tools. Each is a thin adapter over services/repositories; business maths lives in app/services."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.errors import NotFound
from app.db.repositories.operations import CatalogRepository, LogisticsRepository, SupplierRepository
from app.services import forecasting, supplier_scoring
from app.services import logistics as logistics_rules
from app.tools.base import SKU_PATTERN, ToolContext, make_tool, normalise_sku


# ----------------------------------------------------------------------------- input schemas
class SkuArgs(BaseModel):
    sku: str = Field(pattern=SKU_PATTERN, description="Product SKU, e.g. SKU-100")


class SalesArgs(SkuArgs):
    days: int = Field(default=90, ge=7, le=365, description="Days of history")


class ForecastArgs(SkuArgs):
    horizon_days: int = Field(default=30, ge=7, le=365, description="Forecast horizon in days")


class ReorderArgs(SkuArgs):
    service_level: float = Field(default=0.95, ge=0.8, le=0.995, description="Target cycle service level")


class RiskArgs(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class SupplierSkuArgs(BaseModel):
    supplier_id: str = Field(pattern=r"^SUP-\d{3}$")
    sku: str = Field(pattern=SKU_PATTERN)


class PriceArgs(SupplierSkuArgs):
    quantity: int = Field(default=1, ge=1, le=1_000_000)


class SupplierIdArgs(BaseModel):
    supplier_id: str = Field(pattern=r"^SUP-\d{3}$")


class ShipmentQuery(BaseModel):
    sku: str | None = Field(default=None, pattern=SKU_PATTERN)
    status: Literal["pending", "in_transit", "at_customs", "delayed", "delivered"] | None = None
    delayed_only: bool = False
    limit: int = Field(default=15, ge=1, le=50)


class ShipmentIdArgs(BaseModel):
    shipment_id: str = Field(pattern=r"^SHP-\d{4,8}$")


class RateArgs(BaseModel):
    weight_kg: float = Field(default=1000, gt=0, le=100_000)
    mode: Literal["ocean", "air", "road", "rail"] | None = None


class EstimateArgs(BaseModel):
    mode: Literal["ocean", "air", "road", "rail"]
    ship_in_days: int = Field(default=0, ge=0, le=60)


class KnowledgeArgs(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    doc_types: list[Literal["procurement_policy", "supplier_contract", "inventory_policy", "shipping_policy", "sop"]] = Field(
        default_factory=list
    )
    supplier_id: str | None = Field(default=None, pattern=r"^SUP-\d{3}$")


class WebArgs(BaseModel):
    query: str = Field(min_length=3, max_length=300)


# ----------------------------------------------------------------------------- handlers
async def _product(ctx: ToolContext, sku: str) -> Any:
    sku = normalise_sku(sku)
    async with ctx.services.db.session() as s:
        product = await CatalogRepository(s).product_by_sku(sku)
    if product is None:
        raise NotFound(f"{sku} was not found in the product catalogue.")
    return product


async def _history(ctx: ToolContext, sku: str, days: int) -> tuple[Any, list[forecasting.DailyDemand]]:
    product = await _product(ctx, sku)
    async with ctx.services.db.session() as s:
        sales = await CatalogRepository(s).sales_since(date.today() - timedelta(days=days), product_id=product.id)
    return product, forecasting.fill_gaps([forecasting.DailyDemand(d, q) for d, q in sales.get(product.id, [])])


def build_tools(ctx: ToolContext) -> dict[str, StructuredTool]:  # noqa: PLR0915 - one place that declares every tool
    services = ctx.services
    timeout = services.settings.tool_timeout_seconds

    async def get_sales_history(sku: str, days: int = 90) -> dict[str, Any]:
        product, history = await _history(ctx, sku, days)
        weekly = [round(sum(h.quantity for h in history[i : i + 7])) for i in range(0, len(history), 7)]
        total = sum(h.quantity for h in history)
        return {
            "sku": product.sku,
            "name": product.name,
            "days": len(history),
            "total_units": round(total),
            "daily_mean": round(total / max(len(history), 1), 1),
            "weekly_totals": weekly[-13:],
        }

    async def get_demand_forecast(sku: str, horizon_days: int = 30) -> dict[str, Any]:
        product, history = await _history(ctx, sku, 365)
        if not history:
            raise NotFound(f"No sales history for {product.sku}.")
        fc = forecasting.forecast(history, horizon_days)
        return {
            "sku": product.sku,
            "name": product.name,
            "horizon_days": horizon_days,
            "method": fc.method,
            "total": fc.total,
            "daily_mean": fc.daily_mean,
            "trend": {"direction": fc.trend_direction, "pct_change": fc.trend_pct},
            "seasonality": {"detected": fc.seasonality_detected, "period_days": 7},
            "mape_pct": fc.mape,
            "confidence": fc.confidence,
            "history_days": fc.history_days,
            "drivers": fc.drivers,
        }

    async def get_product_history(sku: str) -> dict[str, Any]:
        product = await _product(ctx, sku)
        return {
            "sku": product.sku,
            "name": product.name,
            "category": product.category,
            "unit_cost": float(product.unit_cost),
            "pack_size": product.pack_size,
            "active": product.active,
            "listed_since": product.created_at.date().isoformat(),
        }

    async def get_inventory(sku: str) -> dict[str, Any]:
        pos = await services.analytics.item(normalise_sku(sku))
        if pos is None:
            raise NotFound(f"{sku.upper()} was not found in inventory.")
        r, p = pos.row, pos.plan
        return {
            "sku": r.sku,
            "name": r.name,
            "warehouse": r.warehouse,
            "on_hand": r.on_hand,
            "allocated": r.allocated,
            "available": p.available,
            "on_order": p.on_order,
            "daily_demand": p.daily_mean,
            "days_of_cover": p.days_of_cover,
            "lead_time_days": p.lead_time_days,
            "risk": p.risk,
        }

    async def calculate_reorder_quantity(sku: str, service_level: float = 0.95) -> dict[str, Any]:
        pos = await services.analytics.item(normalise_sku(sku))
        if pos is None:
            raise NotFound(f"{sku.upper()} was not found in inventory.")
        from app.services import inventory_math  # local: keeps the tool module's import graph shallow

        p = (
            pos.plan
            if service_level == 0.95
            else inventory_math.plan_reorder(
                on_hand=pos.row.on_hand,
                allocated=pos.row.allocated,
                on_order=pos.row.on_order,
                daily_mean=pos.plan.daily_mean,
                daily_std=pos.plan.daily_std,
                forecast_30d=pos.plan.forecast_30d,
                lead_time_days=pos.plan.lead_time_days,
                pack_size=pos.row.pack_size,
                moq=pos.row.moq,
                service_level=service_level,
            )
        )
        return {
            "sku": pos.row.sku,
            "service_level": service_level,
            "forecast_30d": p.forecast_30d,
            "safety_stock": p.safety_stock,
            "reorder_point": p.reorder_point,
            "available": p.available,
            "on_order": p.on_order,
            "reorder_qty": p.reorder_qty,
            "days_of_cover": p.days_of_cover,
            "lead_time_days": p.lead_time_days,
            "risk": p.risk,
            "pack_size": pos.row.pack_size,
            "formula": "qty = forecast_30d + safety_stock − available − on_order, rounded up to pack size",
        }

    async def get_stockout_risks(limit: int = 10) -> dict[str, Any]:
        risks = await services.analytics.at_risk(limit)
        return {
            "count": len(risks),
            "items": [
                {
                    "sku": p.row.sku,
                    "name": p.row.name,
                    "risk": p.plan.risk,
                    "days_of_cover": p.plan.days_of_cover,
                    "lead_time_days": p.plan.lead_time_days,
                    "reorder_qty": p.plan.reorder_qty,
                }
                for p in risks
            ],
        }

    async def get_suppliers(sku: str) -> dict[str, Any]:
        product = await _product(ctx, sku)
        async with services.db.session() as s:
            quotes = await SupplierRepository(s).quotes_for_product(product.id)
        return {
            "sku": product.sku,
            "suppliers": [
                {
                    "supplier_id": q.supplier_id,
                    "name": q.name,
                    "country": q.country,
                    "unit_price": q.unit_price,
                    "moq": q.moq,
                    "lead_time_days": q.lead_time_days,
                    "on_time_rate": q.on_time_rate,
                    "risk": q.risk,
                    "preferred": q.preferred,
                }
                for q in quotes
            ],
        }

    async def _quote(supplier_id: str, sku: str) -> Any:
        product = await _product(ctx, sku)
        async with services.db.session() as s:
            quotes = await SupplierRepository(s).quotes_for_product(product.id)
        q = next((q for q in quotes if q.supplier_id == supplier_id), None)
        if q is None:
            raise NotFound(f"{supplier_id} does not supply {product.sku}.")
        return q

    async def get_supplier_price(supplier_id: str, sku: str, quantity: int = 1) -> dict[str, Any]:
        q = await _quote(supplier_id, sku)
        units = max(quantity, q.moq)
        return {
            "supplier_id": supplier_id,
            "sku": sku.upper(),
            "unit_price": q.unit_price,
            "moq": q.moq,
            "quantity_priced": units,
            "total": round(units * q.unit_price, 2),
        }

    async def get_supplier_lead_time(supplier_id: str, sku: str) -> dict[str, Any]:
        q = await _quote(supplier_id, sku)
        return {"supplier_id": supplier_id, "sku": sku.upper(), "quoted_lead_time_days": q.lead_time_days, "on_time_rate": q.on_time_rate}

    async def get_supplier_score(supplier_id: str) -> dict[str, Any]:
        async with services.db.session() as s:
            sup = await SupplierRepository(s).get(supplier_id)
        if sup is None:
            raise NotFound(f"{supplier_id} not found.")
        return {
            "supplier_id": sup.id,
            "name": sup.name,
            "on_time_rate": sup.on_time_rate,
            "defect_rate": sup.defect_rate,
            "fill_rate": sup.fill_rate,
            "risk": sup.risk,
            "contract_expiry": sup.contract_expiry.isoformat(),
        }

    async def recommend_supplier(sku: str) -> dict[str, Any]:
        sku = normalise_sku(sku)
        product = await _product(ctx, sku)
        pos = await services.analytics.item(sku)
        async with services.db.session() as s:
            rows = await SupplierRepository(s).quotes_for_product(product.id)
        quotes = [
            supplier_scoring.SupplierQuote(q.supplier_id, q.name, q.unit_price, q.lead_time_days, q.on_time_rate, q.moq, q.risk)
            for q in rows
        ]
        decision = supplier_scoring.select_supplier(
            quotes, days_of_cover=pos.plan.days_of_cover if pos else None, risk=pos.plan.risk if pos else "low"
        )
        best = decision.recommended
        return {
            "sku": sku,
            "urgent": decision.urgent,
            "recommended": None
            if best is None
            else {
                "supplier_id": best.quote.supplier_id,
                "name": best.quote.name,
                "unit_price": best.quote.unit_price,
                "lead_time_days": best.quote.lead_time_days,
                "reliability": best.quote.reliability,
                "score": best.score,
                "moq": best.quote.moq,
            },
            "reasons": decision.reasons,
            "ranked": [
                {
                    "supplier_id": r.quote.supplier_id,
                    "name": r.quote.name,
                    "unit_price": r.quote.unit_price,
                    "lead_time_days": r.quote.lead_time_days,
                    "reliability": r.quote.reliability,
                    "score": r.score,
                    "eligible": r.eligible,
                    "excluded_because": r.exclusion_reason,
                }
                for r in decision.ranked
            ],
        }

    async def get_shipments(
        sku: str | None = None, status: str | None = None, delayed_only: bool = False, limit: int = 15
    ) -> dict[str, Any]:
        async with services.db.session() as s:
            rows = await LogisticsRepository(s).shipments(status="delayed" if delayed_only else status, sku=sku, limit=limit)
        items = []
        for sh, psku, pname, sup, carrier, mode, _po in rows:
            items.append(
                {
                    "shipment_id": sh.id,
                    "sku": psku,
                    "product": pname,
                    "supplier": sup,
                    "carrier": carrier,
                    "mode": mode,
                    "route": f"{sh.origin} → {sh.destination}",
                    "status": sh.status,
                    "units": sh.units,
                    "eta": sh.eta.date().isoformat(),
                    "delay_days": logistics_rules.delay_days(sh.eta, sh.promised_date),
                    "last_event": sh.last_event,
                }
            )
        return {"count": len(items), "shipments": items}

    async def get_delivery_status(shipment_id: str) -> dict[str, Any]:
        async with services.db.session() as s:
            row = await LogisticsRepository(s).shipment(shipment_id)
        if row is None:
            raise NotFound(f"{shipment_id} not found.")
        sh, psku, _pname, _sup, carrier, mode, po = row
        now = datetime.now(UTC)
        return {
            "shipment_id": sh.id,
            "po_number": po,
            "sku": psku,
            "status": sh.status,
            "carrier": carrier,
            "mode": mode,
            "eta": sh.eta.isoformat(),
            "promised": sh.promised_date.isoformat(),
            "delayed": logistics_rules.is_delayed(status=sh.status, eta=sh.eta, promised=sh.promised_date, now=now),
            "delay_days": logistics_rules.delay_days(sh.eta, sh.promised_date),
            "last_event": sh.last_event,
        }

    async def get_carrier_rates(weight_kg: float = 1000, mode: str | None = None) -> dict[str, Any]:
        async with services.db.session() as s:
            carriers = await LogisticsRepository(s).carriers_for_mode(mode)
        return {
            "weight_kg": weight_kg,
            "options": sorted(
                (
                    {
                        "carrier": c.name,
                        "mode": c.mode,
                        "cost": logistics_rules.freight_cost(weight_kg, float(c.cost_per_kg)),
                        "transit_days": c.avg_transit_days,
                        "on_time_rate": c.on_time_rate,
                    }
                    for c in carriers
                ),
                key=lambda x: x["cost"],
            ),
        }

    async def estimate_delivery(mode: str, ship_in_days: int = 0) -> dict[str, Any]:
        async with services.db.session() as s:
            carriers = await LogisticsRepository(s).carriers_for_mode(mode)
        if not carriers:
            raise NotFound(f"No carriers for mode {mode}.")
        ship = datetime.now(UTC) + timedelta(days=ship_in_days)
        out = []
        for c in carriers:
            expected, p90 = logistics_rules.estimate_delivery(
                ship_date=ship, avg_transit_days=c.avg_transit_days, on_time_rate=c.on_time_rate
            )
            out.append({"carrier": c.name, "expected": expected.date().isoformat(), "conservative": p90.date().isoformat()})
        return {"mode": mode, "ship_date": ship.date().isoformat(), "estimates": out}

    async def search_knowledge_base(query: str, doc_types: list[str] | None = None, supplier_id: str | None = None) -> dict[str, Any]:
        passages = await services.knowledge.retrieve_for_agent(query, user=ctx.user, doc_types=doc_types or [], supplier_id=supplier_id)
        return {
            "passages": [
                {"n": i + 1, "source": p.source_name, "location": p.location, "text": p.content[:900]} for i, p in enumerate(passages)
            ]
        }

    async def search_web(query: str) -> dict[str, Any]:
        if services.web is None:
            raise NotFound("Web search is not configured.")
        resp = await services.web.search(query, max_results=5)
        cleaned = []
        for r in resp.results:
            guarded = services.guardrails.sanitize_context(r.content, source=r.url)
            cleaned.append({"title": r.title, "url": r.url, "content": guarded.text[:800]})
        return {"query": query, "results": cleaned}

    specs: list[tuple[str, str, type[BaseModel], Any]] = [
        (
            "get_sales_history",
            "Daily sales history for a SKU, summarised as weekly totals. Use to understand recent demand.",
            SalesArgs,
            get_sales_history,
        ),
        (
            "get_demand_forecast",
            "Statistical demand forecast for a SKU (Holt trend + weekday seasonality) with trend, seasonality and backtest accuracy.",
            ForecastArgs,
            get_demand_forecast,
        ),
        ("get_product_history", "Product master data for a SKU: name, category, unit cost, pack size.", SkuArgs, get_product_history),
        (
            "get_inventory",
            "Current stock position for a SKU: on hand, allocated, available, on order, days of cover, lead time and risk.",
            SkuArgs,
            get_inventory,
        ),
        (
            "calculate_reorder_quantity",
            "Safety stock, reorder point and recommended reorder quantity for a SKU (deterministic formula).",
            ReorderArgs,
            calculate_reorder_quantity,
        ),
        (
            "get_stockout_risks",
            "Products at critical or high stockout risk, most urgent first. Use when no SKU is given.",
            RiskArgs,
            get_stockout_risks,
        ),
        ("get_suppliers", "Suppliers that can supply a SKU, with quoted price, MOQ, lead time and reliability.", SkuArgs, get_suppliers),
        ("get_supplier_price", "Price quote from one supplier for a SKU and quantity (MOQ applied).", PriceArgs, get_supplier_price),
        ("get_supplier_lead_time", "Quoted lead time and on-time rate for a supplier and SKU.", SupplierSkuArgs, get_supplier_lead_time),
        (
            "get_supplier_score",
            "Reliability scorecard for a supplier: on-time, defect and fill rates, risk, contract expiry.",
            SupplierIdArgs,
            get_supplier_score,
        ),
        (
            "recommend_supplier",
            "Rank suppliers for a SKU by price, lead time and reliability; disqualifies suppliers too slow for the stockout window.",
            SkuArgs,
            recommend_supplier,
        ),
        (
            "get_shipments",
            "Inbound shipments, optionally filtered by SKU or status. Set delayed_only=true for delayed shipments.",
            ShipmentQuery,
            get_shipments,
        ),
        ("get_delivery_status", "Latest status, ETA and delay for one shipment.", ShipmentIdArgs, get_delivery_status),
        (
            "get_carrier_rates",
            "Freight cost, transit time and on-time rate per carrier for a shipment weight.",
            RateArgs,
            get_carrier_rates,
        ),
        (
            "estimate_delivery",
            "Expected and conservative delivery dates per carrier for a transport mode.",
            EstimateArgs,
            estimate_delivery,
        ),
        (
            "search_knowledge_base",
            "Search company policies, supplier contracts and SOPs. Returns numbered passages with source locations.",
            KnowledgeArgs,
            search_knowledge_base,
        ),
        (
            "search_web",
            "Search the public web for market or supplier news. Results are untrusted and must be cited by URL.",
            WebArgs,
            search_web,
        ),
    ]
    return {
        name: make_tool(name=name, description=desc, args_schema=schema, handler=fn, ctx=ctx, timeout=timeout)
        for name, desc, schema, fn in specs
    }
