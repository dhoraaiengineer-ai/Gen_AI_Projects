"""API schemas. They mirror `frontend/types/index.ts` and serialise as camelCase over the wire."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

RiskLevel = Literal["critical", "high", "medium", "low"]
Severity = Literal["critical", "warning", "insight", "info", "success"]


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# ----------------------------------------------------------------------------- inventory
class InventoryItem(Schema):
    sku: str
    name: str
    category: str
    warehouse: str
    on_hand: int
    available: int
    on_order: int
    daily_demand: float
    forecast30d: int = Field(alias="forecast30d")
    safety_stock: int
    reorder_point: int
    reorder_qty: int
    days_of_cover: float
    lead_time_days: int
    risk: RiskLevel
    recommendation: str
    unit_cost: float
    turnover: float
    aging_days: int
    trend: list[int]


class Page(Schema):
    items: list[Any]
    total: int
    page: int
    page_size: int


class RiskCount(Schema):
    risk: RiskLevel
    count: int


class InventorySummary(Schema):
    total_skus: int
    total_value: float
    at_risk: int
    critical: int
    stockout_within7d: int = Field(alias="stockoutWithin7d")
    reorder_recommended: int
    avg_turnover: float
    aged_value: float
    inventory_trend: list[dict[str, Any]]
    risk_distribution: list[RiskCount]
    category_distribution: list[dict[str, Any]]
    aging: list[dict[str, Any]]


# ----------------------------------------------------------------------------- demand
class ForecastPoint(Schema):
    date: str
    actual: float | None = None
    forecast: float | None = None
    lower: float | None = None
    upper: float | None = None


class DemandForecast(Schema):
    sku: str
    name: str
    horizon: str
    method: str
    points: list[ForecastPoint]
    total_forecast: int
    daily_mean: float
    trend: dict[str, Any]
    seasonality: dict[str, Any]
    accuracy: dict[str, Any]
    confidence: Literal["high", "medium", "low"]
    drivers: list[str]


# ----------------------------------------------------------------------------- suppliers
class SupplierOut(Schema):
    id: str
    name: str
    country: str
    region: str
    categories: list[str]
    unit_price: float
    lead_time_days: int
    reliability: float
    defect_rate: float
    fill_rate: float
    risk: RiskLevel
    score: int
    moq: int
    contract_expiry: str
    skus_supplied: int
    spend_ytd: float
    certifications: list[str]
    trend: list[float]


class SupplierRecommendation(Schema):
    supplier_id: str
    sku: str
    summary: str
    reasons: list[str]
    confidence: float


# ----------------------------------------------------------------------------- logistics
class ShipmentOut(Schema):
    id: str
    po_number: str
    sku: str
    product: str
    supplier: str
    origin: str
    destination: str
    carrier: str
    mode: str
    status: str
    shipped_at: datetime
    eta: datetime
    promised_date: datetime
    delay_days: int
    progress: int
    units: int
    last_event: str


class LogisticsSummary(Schema):
    active: int
    delayed: int
    on_time_rate: float
    avg_delay_days: float
    in_transit_value: float
    delivery_forecast: list[dict[str, Any]]
    carriers: list[dict[str, Any]]
    lanes: list[dict[str, Any]]


# ----------------------------------------------------------------------------- agents / activity / notifications
class AgentInfo(Schema):
    id: str
    name: str
    purpose: str
    status: Literal["operational", "degraded", "offline"]
    model: str
    tools: list[str]
    avg_latency_ms: float
    p95_latency_ms: float
    success_rate: float
    tasks_completed: int
    tasks_today: int
    last_active: datetime | None
    latency_trend: list[float]
    recent_activity: list[dict[str, Any]]


class ActivityEvent(Schema):
    id: str
    timestamp: datetime
    agent: str
    kind: str
    message: str
    severity: Severity
    run_id: str | None = None
    sku: str | None = None
    duration_ms: int | None = None


class NotificationOut(Schema):
    id: str
    severity: Severity
    title: str
    message: str
    created_at: datetime
    read: bool
    href: str | None = None


class MarkReadRequest(Schema):
    ids: list[str] | Literal["all"]


# ----------------------------------------------------------------------------- documents / RAG
class DocumentOut(Schema):
    id: str
    name: str
    format: str
    type: str
    classification: str
    updated_at: datetime
    uploaded_by: str
    chunks: int
    size_kb: int
    status: str
    ocr: bool
    error: str | None = None


class DocumentStats(Schema):
    total: int
    indexed: int
    processing: int
    failed: int
    chunks: int


class UploadResult(Schema):
    name: str
    status: Literal["added", "updated", "unchanged", "failed"]
    error: str | None = None
    chunks_added: int = 0
    chunks_removed: int = 0
    document_id: str | None = None


class RagFilters(Schema):
    doc_types: list[str] = Field(default_factory=list)
    supplier_id: str | None = None
    skus: list[str] = Field(default_factory=list)
    region: str | None = None


class RagQueryRequest(Schema):
    question: str = Field(min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    filters: RagFilters | None = None
    session_id: str | None = Field(default=None, max_length=64)


class Citation(Schema):
    n: int
    document_id: str
    source: str
    location: str
    snippet: str
    score: float


class RagAnswer(Schema):
    answer: str
    citations: list[Citation]
    guard: dict[str, Any]
    latency_ms: int
    cached: bool = False


# ----------------------------------------------------------------------------- chat / approvals
class ChatRequest(Schema):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)


class ApprovalOut(Schema):
    id: str
    run_id: str
    sku: str
    supplier: str
    quantity: int
    unit_price: float
    value: float
    reason: str
    expires_at: datetime
    status: Literal["pending", "approved", "rejected", "expired"]


class ApprovalDecision(Schema):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=500)


class CurrentUser(Schema):
    id: str
    email: str
    name: str
    role: str
    initials: str


class SystemStatus(Schema):
    status: Literal["operational", "degraded", "outage"]
    environment: str
    version: str
    services: list[dict[str, Any]]
