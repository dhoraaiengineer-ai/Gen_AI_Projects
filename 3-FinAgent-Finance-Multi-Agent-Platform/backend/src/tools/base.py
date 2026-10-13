"""Tool contract: spec, context, typed result, and the recorder port.

Every tool is defined once (``ToolSpec``) and executed through :class:`ToolRegistry`. MCP servers,
agents and tests all go through the same path, so authorization, validation, timeouts, metrics and
audit hold on every transport.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from src.core.domain import Role

ServerName = Literal["market", "finance", "risk", "research", "portfolio", "ml"]
SERVERS: tuple[ServerName, ...] = ("market", "finance", "risk", "research", "portfolio", "ml")


class ToolError(BaseModel):
    code: str  # invalid_input | unauthorized | not_found | timeout | malformed_output | ...
    message: str
    retryable: bool = False
    details: dict[str, Any] = {}


class ToolResult(BaseModel):
    """What every tool returns: never raises to the caller."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    tool: str
    data: dict[str, Any] | list[Any] | None = None
    error: ToolError | None = None
    duration_ms: float = 0.0
    source: str = ""

    @classmethod
    def failure(cls, tool: str, code: str, message: str, **kwargs: Any) -> ToolResult:
        retryable = bool(kwargs.pop("retryable", False))
        details = kwargs.pop("details", {})
        return cls(
            ok=False,
            tool=tool,
            error=ToolError(code=code, message=message, retryable=retryable, details=details),
            **kwargs,
        )


@dataclass(frozen=True)
class ToolContext:
    """Who is calling, on behalf of whom, inside which request."""

    role: Role
    tenant_id: str | None = None  # required by the registry (ADR-026)
    user_id: str | None = None
    agent: str | None = None  # None = direct (API/UI) call, no agent allow-list applies
    request_id: str | None = None
    trace_id: str | None = None

    def to_meta(self) -> dict[str, str]:
        meta = {"role": self.role.value}
        for key in ("tenant_id", "user_id", "agent", "request_id", "trace_id"):
            if value := getattr(self, key):
                meta[key] = value
        return meta

    @classmethod
    def from_meta(cls, meta: dict[str, Any] | None) -> ToolContext:
        meta = meta or {}
        try:
            role = Role(str(meta.get("role", Role.VIEWER.value)))
        except ValueError:
            role = Role.VIEWER
        return cls(
            role=role,
            tenant_id=meta.get("tenant_id"),
            user_id=meta.get("user_id"),
            agent=meta.get("agent"),
            request_id=meta.get("request_id"),
            trace_id=meta.get("trace_id"),
        )


Handler = Callable[[Any, ToolContext], Awaitable[dict[str, Any] | list[Any]]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    servers: tuple[ServerName, ...]
    description: str
    input_model: type[BaseModel]
    handler: Handler
    permission: str  # from src.security.rbac.PERMISSIONS
    timeout_seconds: float = 10.0
    source: str = "db"
    read_only: bool = True
    tags: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class ToolCallRecord:
    tool: str
    server: str
    status: str  # ok | error | denied | timeout
    duration_ms: float
    context: ToolContext
    input_summary: dict[str, Any]
    error_code: str | None = None


class ToolCallRecorder(Protocol):
    async def record(self, call: ToolCallRecord) -> None: ...

    async def audit_denied(self, call: ToolCallRecord, reason: str) -> None: ...


class NullRecorder:
    async def record(self, call: ToolCallRecord) -> None:
        return None

    async def audit_denied(self, call: ToolCallRecord, reason: str) -> None:
        return None


class InMemoryRecorder:
    """For tests and the in-process demo."""

    def __init__(self) -> None:
        self.calls: list[ToolCallRecord] = []
        self.denied: list[tuple[ToolCallRecord, str]] = []

    async def record(self, call: ToolCallRecord) -> None:
        self.calls.append(call)

    async def audit_denied(self, call: ToolCallRecord, reason: str) -> None:
        self.denied.append((call, reason))
