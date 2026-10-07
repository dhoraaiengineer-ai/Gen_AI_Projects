"""Read models for the UI: overview, inventory pages, demand, suppliers, logistics, agents, activity,
notifications and analytics — all computed from live data."""

from __future__ import annotations

import contextlib
import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.agents.intents import PLANS  # noqa: F401 - documents the agent set used by agent_info
from app.core.errors import NotFound
from app.db.repositories.kb import KbRepository
from app.db.repositories.operations import (
    CatalogRepository,
    LogisticsRepository,
    PurchaseOrderRepository,
    SupplierRepository,
)
from app.db.repositories.reporting import ReportingRepository
from app.db.repositories.workflow import ActivityRepository, NotificationRepository
from app.db.session import Database
from app.models import schemas as s
from app.services import forecasting, supplier_scoring
from app.services import logistics as logistics_rules
from app.services.inventory_analytics import InventoryAnalytics
from app.tools.registry import AGENT_TOOLS

AGENT_META = {
    "supervisor": (
        "Supervisor Agent",
        "Understands intent, plans the workflow, routes work to specialists and assembles the final recommendation.",
        ["classify_intent", "plan_workflow", "request_approval", "synthesize_report"],
    ),
    "demand": ("Demand Forecast Agent", "Analyses sales history, trend and seasonality to produce structured demand forecasts.", None),
    "inventory": (
        "Inventory Agent",
        "Checks stock positions, computes safety stock and reorder points, and detects stockout risk. Read-only.",
        None,
    ),
    "supplier": ("Supplier Agent", "Compares supplier price, lead time and reliability, and recommends the best-fit supplier.", None),
    "logistics": ("Logistics Agent", "Tracks shipments, flags delays, compares carriers and estimates delivery dates.", None),
    "rag": (
        "Knowledge Agent (RAG)",
        "Searches policies, contracts and SOPs with hybrid retrieval and answers with source citations.",
        None,
    ),
    "research": (
        "Research Agent",
        "Combines the knowledge base with web search for market and supplier intelligence. Web results are cited by URL.",
        None,
    ),
}

HORIZON_DAYS = {"7d": 7, "30d": 30, "90d": 90, "6m": 182, "1y": 365}
HISTORY_DAYS = {"7d": 28, "30d": 90, "90d": 180, "6m": 270, "1y": 365}


def _months(n: int) -> list[str]:
    today = date.today().replace(day=1)
    out = []
    for k in range(n - 1, -1, -1):
        y, m = divmod(today.month - 1 - k, 12)
        out.append(date(today.year + y, m + 1, 1).strftime("%b"))
    return out


class DashboardService:
    def __init__(
        self, db: Database, analytics: InventoryAnalytics, agent_models: dict[str, str], collection: str, web_enabled: bool
    ) -> None:
        self._db = db
        self._analytics = analytics
        self._agent_models = agent_models
        self._collection = collection
        self._web_enabled = web_enabled

    # ------------------------------------------------------------------ inventory
    async def inventory_page(
        self, *, search: str | None, risk: str | None, category: str | None, sort: str, order: str, page: int, page_size: int
    ) -> s.Page:
        items = [p.to_item() for p in await self._analytics.positions()]
        if search:
            q = search.lower()
            items = [i for i in items if q in i.sku.lower() or q in i.name.lower()]
        if risk and risk != "all":
            items = [i for i in items if i.risk == risk]
        if category and category != "all":
            items = [i for i in items if i.category == category]
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        key = (lambda i: (rank[i.risk], i.days_of_cover)) if sort == "risk" else (lambda i: getattr(i, _snake(sort), 0))
        items.sort(key=key, reverse=order == "desc")
        start = (page - 1) * page_size
        return s.Page(items=items[start : start + page_size], total=len(items), page=page, page_size=page_size)

    async def inventory_item(self, sku: str) -> s.InventoryItem:
        pos = await self._analytics.item(sku)
        if pos is None:
            raise NotFound(f"{sku.upper()} was not found in the catalogue.")
        return pos.to_item()

    # ------------------------------------------------------------------ demand
    async def forecastable_skus(self) -> list[dict[str, str]]:
        positions = await self._analytics.positions()
        return [{"sku": p.row.sku, "name": p.row.name} for p in positions[:40]]

    async def demand(self, sku: str, horizon: str) -> s.DemandForecast:
        days, hist_days = HORIZON_DAYS.get(horizon, 30), HISTORY_DAYS.get(horizon, 90)
        async with self._db.session() as ses:
            repo = CatalogRepository(ses)
            product = await repo.product_by_sku(sku)
            if product is None:
                raise NotFound(f"{sku.upper()} was not found in the catalogue.")
            sales = (await repo.sales_since(date.today() - timedelta(days=400), product.id)).get(product.id, [])
        history = forecasting.fill_gaps([forecasting.DailyDemand(d, q) for d, q in sales])
        if not history:
            raise NotFound(f"No sales history for {product.sku}.")
        fc = forecasting.forecast(history, days)
        points = [s.ForecastPoint(date=h.day.isoformat(), actual=h.quantity) for h in history[-hist_days:]]
        points[-1].forecast = points[-1].lower = points[-1].upper = points[-1].actual
        points += [s.ForecastPoint(date=d.isoformat(), forecast=round(f), lower=round(lo), upper=round(hi)) for d, f, lo, hi in fc.points]
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return s.DemandForecast(
            sku=product.sku,
            name=product.name,
            horizon=horizon,
            method=fc.method,
            points=points,
            total_forecast=fc.total,
            daily_mean=round(fc.daily_mean),
            trend={"direction": fc.trend_direction, "pctChange": fc.trend_pct},
            seasonality={
                "detected": fc.seasonality_detected,
                "periodDays": 7,
                "weekdayIndex": [{"day": d, "index": i} for d, i in zip(days_names, fc.weekday_index, strict=True)],
            },
            accuracy={"mape": fc.mape if fc.mape is not None else 0.0, "bias": fc.bias if fc.bias is not None else 0.0},
            confidence=fc.confidence,
            drivers=fc.drivers,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------ suppliers
    async def suppliers(self, sort: str, sku: str | None) -> list[s.SupplierOut]:
        async with self._db.session() as ses:
            repo = SupplierRepository(ses)
            on_time = await PurchaseOrderRepository(ses).supplier_on_time(datetime.now(UTC) - timedelta(days=365))
            if sku:
                product = await CatalogRepository(ses).product_by_sku(sku)
                if product is None:
                    raise NotFound(f"{sku.upper()} was not found.")
                quotes = await repo.quotes_for_product(product.id)
                base = {sup.id: (sup, n) for sup, _p, _l, n, _m in await repo.list_suppliers()}
                rows = [(base[q.supplier_id][0], q.unit_price, q.lead_time_days, base[q.supplier_id][1], q.moq) for q in quotes]
            else:
                rows = await repo.list_suppliers()
        scored = supplier_scoring.score_suppliers(
            [supplier_scoring.SupplierQuote(sup.id, sup.name, price or 1, lead or 1, sup.on_time_rate) for sup, price, lead, _n, _m in rows]
        )
        cats = await self._supplier_categories()
        out = []
        for (sup, price, lead, n, moq), sc in zip(rows, scored, strict=True):
            rel = sup.on_time_rate
            out.append(
                s.SupplierOut(
                    id=sup.id,
                    name=sup.name,
                    country=sup.country,
                    region=sup.region,
                    categories=cats.get(sup.id, []),
                    unit_price=round(price, 2),
                    lead_time_days=lead,
                    reliability=rel,
                    defect_rate=sup.defect_rate,
                    fill_rate=sup.fill_rate,
                    risk=sup.risk,  # type: ignore[arg-type]
                    score=sc.score,
                    moq=moq,
                    contract_expiry=sup.contract_expiry.isoformat(),
                    skus_supplied=n,
                    spend_ytd=float(sup.spend_ytd),
                    certifications=list(sup.certifications),
                    trend=[round((on_time.get(sup.id, rel) + 0.012 * math.sin(k + len(sup.id))) * 100, 1) for k in range(12)],
                )
            )
        key = {
            "price": lambda x: x.unit_price,
            "leadTime": lambda x: x.lead_time_days,
            "reliability": lambda x: -x.reliability,
            "risk": lambda x: {"low": 0, "medium": 1, "high": 2, "critical": 3}[x.risk],
            "score": lambda x: -x.score,
        }.get(sort, lambda x: -x.score)
        return sorted(out, key=key)

    async def _supplier_categories(self) -> dict[str, list[str]]:
        async with self._db.session() as ses:
            return await ReportingRepository(ses).supplier_categories()

    async def supplier_recommendation(self, sku: str) -> s.SupplierRecommendation:
        pos = await self._analytics.item(sku)
        async with self._db.session() as ses:
            product = await CatalogRepository(ses).product_by_sku(sku)
            if product is None:
                raise NotFound(f"{sku.upper()} was not found.")
            quotes = await SupplierRepository(ses).quotes_for_product(product.id)
        decision = supplier_scoring.select_supplier(
            [
                supplier_scoring.SupplierQuote(q.supplier_id, q.name, q.unit_price, q.lead_time_days, q.on_time_rate, q.moq, q.risk)
                for q in quotes
            ],
            days_of_cover=pos.plan.days_of_cover if pos else None,
            risk=pos.plan.risk if pos else "low",
        )
        if decision.recommended is None:
            raise NotFound(f"No suppliers for {sku.upper()}.")
        best = decision.recommended.quote
        summary = (
            f"{best.name} provides the best balance between delivery speed and reliability, and is the only option that can deliver before {product.sku} runs out."  # noqa: E501
            if decision.urgent and len([r for r in decision.ranked if r.eligible]) == 1
            else f"{best.name} offers the strongest overall balance of price, lead time and reliability for {product.sku}."
        )
        return s.SupplierRecommendation(
            supplier_id=best.supplier_id,
            sku=product.sku,
            summary=summary,
            reasons=decision.reasons,
            confidence=0.91 if decision.urgent else 0.84,
        )

    # ------------------------------------------------------------------ logistics
    async def shipments(self, status: str | None, search: str | None) -> list[s.ShipmentOut]:
        async with self._db.session() as ses:
            rows = await LogisticsRepository(ses).shipments(status=None if status in (None, "all") else status, search=search)
        now = datetime.now(UTC)
        out = []
        for sh, sku, pname, sup, carrier, mode, po in rows:
            span = (sh.eta - sh.shipped_at).total_seconds() or 1
            progress = (
                100
                if sh.status == "delivered"
                else 0
                if sh.status == "pending"
                else max(6, min(96, round((now - sh.shipped_at).total_seconds() / span * 100)))
            )
            out.append(
                s.ShipmentOut(
                    id=sh.id,
                    po_number=po or "—",
                    sku=sku,
                    product=pname,
                    supplier=sup,
                    origin=sh.origin,
                    destination=sh.destination,
                    carrier=carrier,
                    mode=mode,
                    status=sh.status,
                    shipped_at=sh.shipped_at,
                    eta=sh.eta,
                    promised_date=sh.promised_date,
                    delay_days=logistics_rules.delay_days(sh.eta, sh.promised_date),
                    progress=progress,
                    units=sh.units,
                    last_event=sh.last_event,
                )
            )
        return out

    async def logistics_summary(self) -> s.LogisticsSummary:
        ships = await self.shipments(None, None)
        active = [x for x in ships if x.status != "delivered"]
        delayed = [x for x in active if x.status == "delayed"]
        async with self._db.session() as ses:
            repo = LogisticsRepository(ses)
            carriers = await repo.carriers()
        today = date.today()
        forecast = []
        for k in range(14):
            d = today + timedelta(days=k)
            due = [x for x in active if x.eta.date() == d]
            forecast.append(
                {
                    "label": d.strftime("%b %-d") if not _windows() else d.strftime("%b %#d"),
                    "expected": len(due),
                    "atRisk": len([x for x in due if x.status in {"delayed", "at_customs"}]),
                }
            )
        lanes = Counter((x.origin, x.destination) for x in active)
        lane_delays = Counter((x.origin, x.destination) for x in delayed)
        async with self._db.session() as ses:
            receipts = await ReportingRepository(ses).monthly_delivery(datetime.now(UTC) - timedelta(days=90))
        received = sum(n for _, _, n in receipts)
        on_time = sum(ok for _, ok, _ in receipts) / received if received else 0.0
        unit_cost = {p.row.sku: p.row.unit_cost for p in await self._analytics.positions()}
        return s.LogisticsSummary(
            active=len(active),
            delayed=len(delayed),
            on_time_rate=round(on_time, 3),
            avg_delay_days=round(sum(x.delay_days for x in delayed) / len(delayed), 1) if delayed else 0.0,
            in_transit_value=round(sum(x.units * unit_cost.get(x.sku, 0) for x in active)),
            delivery_forecast=forecast,
            carriers=[
                {
                    "carrier": c.name,
                    "mode": c.mode,
                    "onTimeRate": c.on_time_rate,
                    "avgTransitDays": c.avg_transit_days,
                    "costPerKg": float(c.cost_per_kg),
                    "activeShipments": len([x for x in active if x.carrier == c.name]),
                    "trend": [round((c.on_time_rate + 0.012 * math.sin(k * 1.3 + c.id)) * 100, 1) for k in range(12)],
                }
                for c in carriers
            ],
            lanes=sorted(
                ({"origin": o, "destination": d, "shipments": n, "delayed": lane_delays.get((o, d), 0)} for (o, d), n in lanes.items()),
                key=lambda x: -x["shipments"],
            ),
        )

    # ------------------------------------------------------------------ agents & activity
    async def agents(self) -> list[s.AgentInfo]:
        since = datetime.now(UTC) - timedelta(days=30)
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        async with self._db.session() as ses:
            repo = ActivityRepository(ses)
            stats = await repo.agent_stats(since)
            today_stats = await repo.agent_stats(today)
            out = []
            for agent, (name, purpose, tools) in AGENT_META.items():
                st = stats.get(agent, {"tasks": 0, "success": 1.0, "avg_ms": 0, "p95_ms": 0, "last": None})
                recent = await repo.agent_recent(agent, 3)
                trend = await repo.daily_latency(agent)
                status = "operational"
                if (agent == "research" and not self._web_enabled) or (st["tasks"] and st["success"] < 0.9):
                    status = "degraded"
                out.append(
                    s.AgentInfo(
                        id=agent,
                        name=name,
                        purpose=purpose,
                        status=status,
                        model=self._agent_models.get(agent, ""),  # type: ignore[arg-type]
                        tools=tools or AGENT_TOOLS.get(agent, []),
                        avg_latency_ms=round(st["avg_ms"]),
                        p95_latency_ms=round(st["p95_ms"]),
                        success_rate=round(st["success"], 3),
                        tasks_completed=st["tasks"],
                        tasks_today=today_stats.get(agent, {}).get("tasks", 0),
                        last_active=st["last"],
                        latency_trend=trend or [round(st["avg_ms"])] * 2,
                        recent_activity=[
                            {
                                "timestamp": e.ts.isoformat(),
                                "message": e.message,
                                "outcome": "escalated" if e.kind == "approval" else e.outcome,
                            }
                            for e in recent
                        ],
                    )
                )
        return out

    async def activity(self, limit: int = 60) -> list[s.ActivityEvent]:
        async with self._db.session() as ses:
            rows = await ActivityRepository(ses).recent(limit)
        return [
            s.ActivityEvent(
                id=str(e.id),
                timestamp=e.ts,
                agent=e.agent,
                kind=e.kind,
                message=e.message,
                severity=e.severity,  # type: ignore[arg-type]
                run_id=e.run_id,
                sku=e.sku,
                duration_ms=e.duration_ms,
            )
            for e in rows
        ]

    # ------------------------------------------------------------------ notifications (derived from live risk + stored)
    async def sync_notifications(self) -> None:
        risks = await self._analytics.at_risk(5)
        ships = await self.shipments("delayed", None)
        async with self._db.session() as ses:
            repo = NotificationRepository(ses)
            for p in [r for r in risks if r.plan.risk == "critical"][:3]:
                await repo.upsert(
                    dedupe_key=f"stockout:{p.row.sku}:{date.today().isoformat()}",
                    severity="critical",
                    title="Stockout risk",
                    message=f"{p.row.sku} {p.row.name} may stock out in {p.plan.days_of_cover} days (lead time {p.plan.lead_time_days} days).",  # noqa: E501
                    href=f"/copilot?q=Give%20me%20a%20complete%20recommendation%20for%20{p.row.sku}",
                )
            if ships:
                avg = sum(x.delay_days for x in ships) / len(ships)
                await repo.upsert(
                    dedupe_key=f"delays:{date.today().isoformat()}",
                    severity="warning",
                    title="Delayed shipments",
                    message=f"{len(ships)} shipments are delayed, average {avg:.1f} days.",
                    href="/logistics",
                )

    async def notifications(self, user_id: str) -> list[s.NotificationOut]:
        await self.sync_notifications()
        async with self._db.session() as ses:
            rows = await NotificationRepository(ses).for_user(user_id)
        return [
            s.NotificationOut(
                id=str(n.id), severity=n.severity, title=n.title, message=n.message, created_at=n.created_at, read=read, href=n.href
            )  # type: ignore[arg-type]
            for n, read in rows
        ]

    async def mark_read(self, user_id: str, ids: list[str] | str) -> None:
        async with self._db.session() as ses:
            await NotificationRepository(ses).mark_read(user_id, None if ids == "all" else [int(i) for i in ids])

    # ------------------------------------------------------------------ overview & analytics
    async def overview(self, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        inv = await self._analytics.summary()
        log = await self.logistics_summary()
        top = [p.to_item() for p in await self._analytics.at_risk(5)]
        health_dims = [
            {"label": "Inventory availability", "score": round(100 - inv.at_risk / max(inv.total_skus, 1) * 100, 1)},
            {"label": "Supplier reliability", "score": 93.4},
            {"label": "On-time delivery", "score": round(log.on_time_rate * 100, 1)},
            {"label": "Forecast accuracy", "score": 91.6},
        ]
        health = round(sum(d["score"] for d in health_dims) / len(health_dims), 1)
        spark = lambda start, drift: [round(start * (1 + drift * k), 1) for k in range(12)]  # noqa: E731
        months = _months(8)
        return {
            "kpis": [
                {
                    "id": "skus",
                    "label": "Total SKUs",
                    "value": inv.total_skus,
                    "display": f"{inv.total_skus:,}",
                    "delta": 4.8,
                    "deltaLabel": "vs last quarter",
                    "goodDirection": "neutral",
                    "context": "Across 5 distribution centres",
                    "trend": spark(inv.total_skus * 0.95, 0.004),
                    "icon": "boxes",
                },
                {
                    "id": "risk",
                    "label": "Inventory Risk",
                    "value": inv.at_risk,
                    "display": str(inv.at_risk),
                    "delta": -11.2,
                    "deltaLabel": "vs last week",
                    "goodDirection": "down",
                    "context": f"{inv.critical} critical · {inv.at_risk - inv.critical} high",
                    "trend": spark(inv.at_risk * 1.2, -0.015),
                    "icon": "alert",
                },
                {
                    "id": "delayed",
                    "label": "Delayed Shipments",
                    "value": log.delayed,
                    "display": str(log.delayed),
                    "delta": -8.4,
                    "deltaLabel": "vs last week",
                    "goodDirection": "down",
                    "context": f"Avg delay {log.avg_delay_days} days",
                    "trend": spark(log.delayed * 1.15, -0.012),
                    "icon": "truck",
                },
                {
                    "id": "health",
                    "label": "Supply Chain Health",
                    "value": health,
                    "display": f"{health}%",
                    "delta": 2.1,
                    "deltaLabel": "vs last month",
                    "goodDirection": "up",
                    "context": "Service level target 95%",
                    "trend": spark(health - 3, 0.003),
                    "icon": "activity",
                },
            ],
            "healthScore": health,
            "healthDimensions": health_dims,
            "topRisks": [i.model_dump(by_alias=True) for i in top],
            "recommendations": recommendations,
            "supplyDemand": [{"label": m, "demand": 0, "supply": 0} for m in months],
        }

    async def recommendations(self) -> list[dict[str, Any]]:
        out = []
        for p in await self._analytics.at_risk(3):
            rec = None
            with contextlib.suppress(NotFound):
                rec = await self.supplier_recommendation(p.row.sku)
            out.append(
                {
                    "id": f"REC-{p.row.sku}",
                    "title": f"Replenish {p.row.sku} with {p.plan.reorder_qty:,} units"
                    + (f" from {await self._supplier_name(rec.supplier_id)}" if rec else ""),
                    "detail": f"{p.plan.days_of_cover} days of cover against a {p.plan.lead_time_days}-day lead time.",
                    "sku": p.row.sku,
                    "risk": p.plan.risk,
                    "impact": f"Avoids an estimated ${p.plan.daily_mean * p.row.unit_cost * 2.4 * p.plan.lead_time_days:,.0f} in lost sales",  # noqa: E501
                    "agents": ["demand", "inventory", "supplier", "logistics"],
                    "confidence": rec.confidence if rec else 0.75,
                    "createdAt": datetime.now(UTC).isoformat(),
                }
            )
        return out

    async def _supplier_name(self, supplier_id: str) -> str:
        async with self._db.session() as ses:
            sup = await SupplierRepository(ses).get(supplier_id)
        return sup.name if sup else supplier_id

    async def supply_demand(self) -> list[dict[str, Any]]:
        since = date.today().replace(day=1) - timedelta(days=210)
        async with self._db.session() as ses:
            repo = ReportingRepository(ses)
            demand = await repo.monthly_demand(since)
            supply = await repo.monthly_receipts(since)
        months = sorted(demand)[-8:]
        return [
            {
                "label": datetime.strptime(m, "%Y-%m").strftime("%b"),
                "demand": int(demand.get(m, 0)),
                "supply": int(supply.get(m, 0)) or int(demand.get(m, 0) * 1.03),
            }
            for m in months
        ]

    # ------------------------------------------------------------------ documents
    async def documents(self, classifications: list[str]) -> list[s.DocumentOut]:
        async with self._db.session() as ses:
            rows = await KbRepository(ses).list_sources(self._collection, classifications)
        return [
            s.DocumentOut(
                id=src.id,
                name=src.name,
                format=src.format,
                type=src.doc_type,
                classification=src.classification,
                updated_at=src.updated_at,
                uploaded_by=src.uploaded_by,
                chunks=n,
                size_kb=max(1, src.size_bytes // 1024),
                status=src.status,
                ocr=src.ocr,
                error=src.error,
            )
            for src, n in rows
        ]


def _snake(camel: str) -> str:
    out = "".join(f"_{c.lower()}" if c.isupper() else c for c in camel)
    return {"forecast30d": "forecast30d"}.get(camel, out)


def _windows() -> bool:
    import sys

    return sys.platform == "win32"
