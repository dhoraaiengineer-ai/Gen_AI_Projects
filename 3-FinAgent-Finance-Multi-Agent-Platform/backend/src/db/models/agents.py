"""Agent execution records, A2A messages, MCP tool calls, conversations, notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import (
    A2A_PRIORITIES,
    A2A_TYPES,
    AGENT_RUN_STATUSES,
    MESSAGE_ROLES,
    SEVERITIES,
    TOOL_CALL_STATUSES,
)
from src.db.base import Base, CreatedMixin, TenantScoped, TimestampMixin, in_list


class AgentRun(TenantScoped, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(in_list("status", AGENT_RUN_STATUSES), name="status"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint("tokens_in >= 0 AND tokens_out >= 0 AND cost_usd >= 0", name="usage"),
        Index("ix_agent_runs_request", "request_id"),
        Index("ix_agent_runs_agent_started", "agent", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(32))
    thread_id: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    agent: Mapped[str] = mapped_column(String(20), nullable=False)
    task: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    models_used: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(String(500))


class AgentEvent(TenantScoped, CreatedMixin, Base):
    """Timeline events (step, plan, agent_start/end, a2a, mcp, approval...) for replay and UI."""

    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_request", "request_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    agent: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class A2AMessageRow(TenantScoped, CreatedMixin, Base):
    __tablename__ = "a2a_messages"
    __table_args__ = (
        CheckConstraint(in_list("type", A2A_TYPES), name="type"),
        CheckConstraint(in_list("priority", A2A_PRIORITIES), name="priority"),
        CheckConstraint("attempt >= 1", name="attempt"),
        Index("ix_a2a_messages_request", "request_id"),
        Index("ix_a2a_messages_correlation", "correlation_id"),
    )

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(40))
    source_agent: Mapped[str] = mapped_column(String(40), nullable=False)
    target_agent: Mapped[str] = mapped_column(String(40), nullable=False)
    task: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(6), nullable=False, default="normal")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    payload_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class McpToolCall(TenantScoped, CreatedMixin, Base):
    __tablename__ = "mcp_tool_calls"
    __table_args__ = (
        CheckConstraint(in_list("status", TOOL_CALL_STATUSES), name="status"),
        Index("ix_mcp_tool_calls_request", "request_id"),
        Index("ix_mcp_tool_calls_tool_created", "tool", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(32))
    agent: Mapped[str | None] = mapped_column(String(20))
    server: Mapped[str] = mapped_column(String(20), nullable=False)
    tool: Mapped[str] = mapped_column(String(60), nullable=False)
    user_role: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(40))


class Conversation(TenantScoped, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_updated", "user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)


class Message(TenantScoped, CreatedMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(in_list("role", MESSAGE_ROLES), name="role"),
        Index("ix_messages_conversation", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class Notification(TenantScoped, CreatedMixin, Base):
    """``user_id`` NULL + ``target_role`` = broadcast to a role; both NULL = everyone."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(in_list("severity", SEVERITIES), name="severity"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    target_role: Mapped[str | None] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))


class NotificationRead(TenantScoped, Base):
    __tablename__ = "notification_reads"

    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
