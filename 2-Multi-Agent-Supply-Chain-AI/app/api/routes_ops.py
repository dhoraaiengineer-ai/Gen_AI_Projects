"""Operational read APIs: dashboard, inventory, demand, suppliers, logistics, analytics."""

from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_services, require_analyst, require_user
from app.container import Services
from app.core.rbac import User
from app.models import schemas as s
from app.services.analytics_report import analytics_report

router = APIRouter(prefix="/api", tags=["operations"])
SKU = Path(pattern=r"^[Ss][Kk][Uu]-\d{3,6}$")

_overview_cache: dict[str, Any] = {}


@router.get("/dashboard/overview")
async def overview(_: User = Depends(require_user), services: Services = Depends(get_services)) -> dict[str, Any]:
    cached = _overview_cache.get("v")
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]  # type: ignore[no-any-return]
    data = await services.dashboard.overview(await services.dashboard.recommendations())
    data["supplyDemand"] = await services.dashboard.supply_demand()
    _overview_cache["v"] = (time.monotonic(), data)
    return data


@router.get("/inventory/summary", response_model=s.InventorySummary, response_model_by_alias=True)
async def inventory_summary(_: User = Depends(require_user), services: Services = Depends(get_services)) -> s.InventorySummary:
    return await services.analytics.summary()


@router.get("/inventory", response_model=s.Page, response_model_by_alias=True)
async def inventory(
    search: str | None = Query(default=None, max_length=80),
    risk: Literal["all", "critical", "high", "medium", "low"] = "all",
    category: str | None = Query(default=None, max_length=80),
    sort: str = Query(default="risk", pattern=r"^[a-zA-Z0-9]{2,20}$"),
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=25, ge=1, le=100),
    _: User = Depends(require_user),
    services: Services = Depends(get_services),
) -> s.Page:
    result = await services.dashboard.inventory_page(
        search=search, risk=risk, category=category, sort=sort, order=order, page=page, page_size=page_size
    )
    result.items = [i.model_dump(by_alias=True) for i in result.items]
    return result


@router.get("/inventory/{sku}", response_model=s.InventoryItem, response_model_by_alias=True)
async def inventory_item(sku: str = SKU, _: User = Depends(require_user), services: Services = Depends(get_services)) -> s.InventoryItem:
    return await services.dashboard.inventory_item(sku)


@router.get("/demand/skus")
async def demand_skus(_: User = Depends(require_user), services: Services = Depends(get_services)) -> list[dict[str, str]]:
    return await services.dashboard.forecastable_skus()


@router.get("/demand/{sku}", response_model=s.DemandForecast, response_model_by_alias=True)
async def demand(
    sku: str = SKU,
    horizon: Literal["7d", "30d", "90d", "6m", "1y"] = "30d",
    _: User = Depends(require_user),
    services: Services = Depends(get_services),
) -> s.DemandForecast:
    return await services.dashboard.demand(sku, horizon)


@router.get("/suppliers", response_model=list[s.SupplierOut], response_model_by_alias=True)
async def suppliers(
    sort: Literal["price", "leadTime", "reliability", "risk", "score"] = "score",
    sku: str | None = Query(default=None, pattern=r"^[Ss][Kk][Uu]-\d{3,6}$"),
    _: User = Depends(require_analyst),
    services: Services = Depends(get_services),
) -> list[s.SupplierOut]:
    return await services.dashboard.suppliers(sort, sku)


@router.get("/suppliers/recommendation", response_model=s.SupplierRecommendation, response_model_by_alias=True)
async def supplier_recommendation(
    sku: str = Query(pattern=r"^[Ss][Kk][Uu]-\d{3,6}$"), _: User = Depends(require_analyst), services: Services = Depends(get_services)
) -> s.SupplierRecommendation:
    return await services.dashboard.supplier_recommendation(sku)


@router.get("/shipments", response_model=list[s.ShipmentOut], response_model_by_alias=True)
async def shipments(
    status: Literal["all", "pending", "in_transit", "at_customs", "delayed", "delivered"] = "all",
    search: str | None = Query(default=None, max_length=80),
    _: User = Depends(require_user),
    services: Services = Depends(get_services),
) -> list[s.ShipmentOut]:
    return await services.dashboard.shipments(status, search)


@router.get("/logistics/summary", response_model=s.LogisticsSummary, response_model_by_alias=True)
async def logistics_summary(_: User = Depends(require_user), services: Services = Depends(get_services)) -> s.LogisticsSummary:
    return await services.dashboard.logistics_summary()


@router.get("/analytics")
async def analytics(_: User = Depends(require_user), services: Services = Depends(get_services)) -> dict[str, Any]:
    return await analytics_report(services.db, services.analytics)
