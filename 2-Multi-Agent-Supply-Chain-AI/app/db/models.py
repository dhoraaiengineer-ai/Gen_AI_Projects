"""SQLAlchemy models. SQL lives only in `app/db/` — agents and tools go through repositories."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIMENSIONS = 1536


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ----------------------------------------------------------------------------- operational data
class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pack_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    inventory: Mapped[list[Inventory]] = relationship(back_populates="product")

    __table_args__ = (
        CheckConstraint("unit_cost >= 0", name="ck_products_unit_cost"),
        CheckConstraint("pack_size > 0", name="ck_products_pack_size"),
    )


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    warehouse: Mapped[str] = mapped_column(String(80), nullable=False)
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    on_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avg_age_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    product: Mapped[Product] = relationship(back_populates="inventory")

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse", name="uq_inventory_product_warehouse"),
        CheckConstraint("on_hand >= 0 AND allocated >= 0 AND on_order >= 0", name="ck_inventory_non_negative"),
        CheckConstraint("allocated <= on_hand", name="ck_inventory_allocated"),
    )


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("product_id", "sale_date", name="uq_sales_product_date"),
        CheckConstraint("quantity >= 0", name="ck_sales_quantity"),
        Index("ix_sales_product_date", "product_id", "sale_date"),
    )


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    region: Mapped[str] = mapped_column(String(16), nullable=False)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False)
    defect_rate: Mapped[float] = mapped_column(Float, nullable=False)
    fill_rate: Mapped[float] = mapped_column(Float, nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False, server_default="low")
    contract_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, server_default="{}")
    spend_ytd: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint(
            "on_time_rate BETWEEN 0 AND 1 AND defect_rate BETWEEN 0 AND 1 AND fill_rate BETWEEN 0 AND 1", name="ck_suppliers_rates"
        ),
        CheckConstraint("risk IN ('low','medium','high','critical')", name="ck_suppliers_risk"),
    )


class SupplierProduct(TimestampMixin, Base):
    __tablename__ = "supplier_products"

    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    moq: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        CheckConstraint("unit_price > 0 AND moq > 0 AND lead_time_days > 0", name="ck_supplier_products_positive"),
        Index("ix_supplier_products_product", "product_id"),
    )


class Carrier(TimestampMixin, Base):
    __tablename__ = "carriers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_transit_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_per_kg: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (CheckConstraint("mode IN ('ocean','air','road','rail')", name="ck_carriers_mode"),)


class PurchaseOrder(TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("quantity > 0 AND unit_price > 0", name="ck_po_positive"),
        CheckConstraint("status IN ('draft','approved','sent','received','cancelled')", name="ck_po_status"),
        Index("ix_po_supplier_status", "supplier_id", "status"),
        Index("ix_po_product", "product_id"),
    )


class Shipment(TimestampMixin, Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    po_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="SET NULL"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    carrier_id: Mapped[int] = mapped_column(ForeignKey("carriers.id", ondelete="RESTRICT"), nullable=False)
    origin: Mapped[str] = mapped_column(String(80), nullable=False)
    destination: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    promised_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('pending','in_transit','at_customs','delayed','delivered')", name="ck_shipments_status"),
        CheckConstraint("units > 0", name="ck_shipments_units"),
        Index("ix_shipments_status", "status"),
        Index("ix_shipments_product", "product_id"),
    )


# ----------------------------------------------------------------------------- workflow / audit data
class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sku: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)
    po_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','expired')", name="ck_approvals_status"),
        Index("ix_approvals_status", "status"),
    )


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, server_default="success")
    user_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (Index("ix_agent_events_ts", "ts"), Index("ix_agent_events_agent_ts", "agent", "ts"))


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    href: Mapped[str | None] = mapped_column(String(300))
    dedupe_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationRead(Base):
    __tablename__ = "notification_reads"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        Index("ix_messages_conversation", "conversation_id", "created_at"),
    )


# ----------------------------------------------------------------------------- knowledge base
class KbSource(TimestampMixin, Base):
    """Hash registry: one row per uploaded document, used for incremental upsert."""

    __tablename__ = "kb_sources"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    collection: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(300), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_ids: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    uploaded_by: Mapped[str] = mapped_column(String(120), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        UniqueConstraint("collection", "source_key", name="uq_kb_sources_collection_key"),
        CheckConstraint("status IN ('indexed','processing','failed')", name="ck_kb_sources_status"),
        CheckConstraint("classification IN ('public','internal','restricted')", name="ck_kb_sources_classification"),
    )


class KbChunk(Base):
    """A retrievable chunk with its embedding, full-text vector and filterable metadata columns."""

    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # hash(source + strategy + content)
    collection: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("kb_sources.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(64))
    is_parent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(String(16))
    skus: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, server_default="{}")
    region: Mapped[str | None] = mapped_column(String(16))
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_kb_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_kb_chunks_skus", "skus", postgresql_using="gin"),
        Index("ix_kb_chunks_filters", "collection", "classification", "doc_type"),
        Index("ix_kb_chunks_source", "source_id"),
        Index(
            "ix_kb_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class KbState(Base):
    """Knowledge-base version, bumped on every upload/update/delete; part of the answer-cache key."""

    __tablename__ = "kb_state"

    collection: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
