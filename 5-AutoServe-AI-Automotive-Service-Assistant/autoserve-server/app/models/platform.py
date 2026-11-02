"""llm_usage, audit_log (append-only, hash-chained), idempotency_keys, config_versions."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, in_list, updated_at, uuid_pk


class LlmUsage(Base):
    __tablename__ = "llm_usage"
    __table_args__ = (CheckConstraint(in_list("chain", ("agent", "answer", "embedding")), name="chain_valid"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    request_id: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(32))
    ro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"), index=True)
    node: Mapped[str | None] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(64))
    chain: Mapped[str] = mapped_column(String(16))
    fallback_index: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))  # null when price unknown (never guessed)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = created_at()


class AuditLog(Base):
    """INSERT-only. DB trigger rejects UPDATE/DELETE/TRUNCATE. hash = sha256(prev_hash || canonical payload)."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # masked
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(64), unique=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    route: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = created_at()


class ConfigVersion(Base):
    __tablename__ = "config_versions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_config_versions_name_version"),
        Index("uq_config_versions_active", "name", unique=True, postgresql_where="active"),
        CheckConstraint(
            in_list("name", ("rules", "document_checklists", "intents", "safety_keywords")), name="name_valid"
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    yaml_content: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class GraphNodeRun(Base):
    """Per-node idempotency for the service graph (rules/60): (ro_id, node, input_hash) → stored output."""

    __tablename__ = "graph_node_runs"
    __table_args__ = (UniqueConstraint("ro_id", "node", "input_hash", name="uq_graph_node_runs_key"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    ro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repair_orders.id"))
    node: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64))
    output: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()
