"""A2A envelope, context and agent card (docs/a2a-protocol.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MessageType = Literal["request", "response", "error"]
Priority = Literal["low", "normal", "high"]


def new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:24]}"


class A2AContext(BaseModel):
    """Who the work is for. Travels with every envelope; never trusted from outside the process
    without JWT verification (HTTP transport)."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    trace_id: str
    tenant_id: str
    role: str
    user_id: str | None = None
    upstream: list[str] = Field(default_factory=list)


class A2AErrorBody(BaseModel):
    code: Literal["timeout", "unavailable", "invalid_request", "unauthorized", "agent_failed"]
    message: str
    retryable: bool = False


class A2AEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: str = Field(default_factory=new_message_id)
    type: MessageType = "request"
    request_id: str
    trace_id: str
    correlation_id: str | None = None
    source_agent: str
    target_agent: str
    task: str
    payload: dict[str, Any] = Field(default_factory=dict)
    context: A2AContext
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    priority: Priority = "normal"
    timeout_ms: int = Field(default=60_000, ge=100, le=600_000)
    attempt: int = Field(default=1, ge=1, le=10)
    agent_metadata: dict[str, Any] = Field(default_factory=dict)
    error: A2AErrorBody | None = None

    def reply(
        self, payload: dict[str, Any], *, metadata: dict[str, Any] | None = None
    ) -> A2AEnvelope:
        return A2AEnvelope(
            type="response",
            request_id=self.request_id,
            trace_id=self.trace_id,
            correlation_id=self.message_id,
            source_agent=self.target_agent,
            target_agent=self.source_agent,
            task=self.task,
            payload=payload,
            context=self.context,
            priority=self.priority,
            attempt=self.attempt,
            agent_metadata=metadata or {},
        )

    def fail(self, error: A2AErrorBody) -> A2AEnvelope:
        return A2AEnvelope(
            type="error",
            request_id=self.request_id,
            trace_id=self.trace_id,
            correlation_id=self.message_id,
            source_agent=self.target_agent,
            target_agent=self.source_agent,
            task=self.task,
            context=self.context,
            priority=self.priority,
            attempt=self.attempt,
            error=error,
        )


class AgentCard(BaseModel):
    """What an agent offers: published at ``/.well-known/agent-card/{agent}`` (HTTP transport)."""

    name: str
    description: str
    version: str = "0.1.0"
    tasks: list[str]
    tools: list[str] = Field(default_factory=list)
    accepts_roles: list[str] = Field(default_factory=list)  # empty = any authenticated role
