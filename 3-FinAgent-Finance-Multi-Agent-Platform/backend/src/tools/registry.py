"""Tool registry: the single execution path for every tool call."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from src.core.errors import AppError
from src.core.metrics import TOOL_CALLS, TOOL_LATENCY
from src.core.tenancy import tenant_scope
from src.core.tracing import set_attributes, span
from src.security.rbac import has_permission
from src.tools.base import (
    NullRecorder,
    ToolCallRecord,
    ToolCallRecorder,
    ToolContext,
    ToolResult,
    ToolSpec,
)
from src.tools.permissions import agent_may_call

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = ("customer", "account", "email", "phone", "name")


def summarise_input(args: dict[str, Any]) -> dict[str, Any]:
    """Small, PII-free summary of tool arguments for records and audit."""
    out: dict[str, Any] = {}
    for key, value in list(args.items())[:12]:
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            out[key] = "***"
        elif isinstance(value, str | int | float | bool) or value is None:
            out[key] = value if not isinstance(value, str) else value[:80]
        elif isinstance(value, list):
            out[key] = f"list[{len(value)}]"
        else:
            out[key] = type(value).__name__
    return out


class ToolRegistry:
    def __init__(self, recorder: ToolCallRecorder | None = None) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self.recorder: ToolCallRecorder = recorder or NullRecorder()

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"tool {spec.name!r} registered twice")
        self._specs[spec.name] = spec

    def register_all(self, specs: Iterable[ToolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def specs(self, server: str | None = None) -> list[ToolSpec]:
        return [s for s in self._specs.values() if server is None or server in s.servers]

    def names(self) -> list[str]:
        return sorted(self._specs)

    async def execute(
        self, name: str, args: dict[str, Any] | None, ctx: ToolContext, *, server: str | None = None
    ) -> ToolResult:
        """Authorize → validate → run with timeout → check output → record. Never raises."""
        with span(f"tool {name}", tool=name, agent=ctx.agent, mcp_server=server):
            result = await self._execute(name, args, ctx, server=server)
            set_attributes(ok=result.ok, error_code=result.error.code if result.error else None)
            return result

    async def _execute(
        self, name: str, args: dict[str, Any] | None, ctx: ToolContext, *, server: str | None
    ) -> ToolResult:
        started = time.perf_counter()
        args = args or {}
        spec = self._specs.get(name)
        server_name = server or (spec.servers[0] if spec else "unknown")

        def done(result: ToolResult, status: str) -> ToolResult:
            elapsed = (time.perf_counter() - started) * 1000
            TOOL_CALLS.labels(tool=name, status=status).inc()
            TOOL_LATENCY.labels(tool=name).observe(elapsed / 1000)
            return result.model_copy(update={"duration_ms": round(elapsed, 1)})

        if spec is None:
            return done(ToolResult.failure(name, "not_found", f"unknown tool {name!r}"), "error")

        record = ToolCallRecord(name, server_name, "ok", 0.0, ctx, summarise_input(args))
        denial = self._authorize(spec, ctx)
        if denial:
            record = _with(record, status="denied", error_code="unauthorized")
            await self._safe(self.recorder.audit_denied(record, denial))
            await self._safe(self.recorder.record(record))
            logger.warning(
                "tool denied",
                extra={"tool": name, "agent": ctx.agent, "role": ctx.role.value, "reason": denial},
            )
            return done(
                ToolResult.failure(name, "unauthorized", denial, source=spec.source), "denied"
            )

        try:
            parsed = spec.input_model.model_validate(args)
        except ValidationError as exc:
            errors = [
                {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
                for e in exc.errors()
            ]
            await self._safe(
                self.recorder.record(_with(record, status="error", error_code="invalid_input"))
            )
            return done(
                ToolResult.failure(
                    name,
                    "invalid_input",
                    "invalid tool arguments",
                    details={"errors": errors},
                    source=spec.source,
                ),
                "error",
            )

        status, result = await self._run(spec, parsed, ctx)
        elapsed = (time.perf_counter() - started) * 1000
        await self._safe(
            self.recorder.record(
                _with(
                    record,
                    status=status,
                    duration_ms=elapsed,
                    error_code=result.error.code if result.error else None,
                )
            )
        )
        return done(result, status)

    def _authorize(self, spec: ToolSpec, ctx: ToolContext) -> str | None:
        if not ctx.tenant_id:
            return "no tenant in tool context"
        if ctx.agent is not None and not agent_may_call(ctx.agent, spec.name):
            return f"agent {ctx.agent!r} is not allowed to call {spec.name!r}"
        if not has_permission(ctx.role, spec.permission):
            return f"role {ctx.role.value!r} lacks permission {spec.permission!r}"
        return None

    async def _run(  # noqa: PLR0911 - one return per failure class keeps the mapping explicit
        self, spec: ToolSpec, parsed: Any, ctx: ToolContext
    ) -> tuple[str, ToolResult]:
        try:
            with tenant_scope(str(ctx.tenant_id)):  # repositories filter by this tenant
                data: Any = await asyncio.wait_for(
                    spec.handler(parsed, ctx), timeout=spec.timeout_seconds
                )
        except TimeoutError:
            return "timeout", ToolResult.failure(
                spec.name,
                "timeout",
                f"{spec.name} exceeded {spec.timeout_seconds}s",
                retryable=True,
                source=spec.source,
            )
        except AppError as exc:
            return "error", ToolResult.failure(
                spec.name,
                exc.code,
                exc.message,
                retryable=exc.retryable,
                details=exc.details,
                source=spec.source,
            )
        except (ValueError, KeyError, LookupError) as exc:
            # Domain validation (e.g. not enough history) — reported to the model as data errors.
            return "error", ToolResult.failure(
                spec.name, "invalid_request", str(exc), source=spec.source
            )
        except Exception:
            logger.exception("tool crashed", extra={"tool": spec.name})
            return "error", ToolResult.failure(
                spec.name, "internal_error", "tool failed", source=spec.source
            )
        if not isinstance(data, dict | list):
            return "error", ToolResult.failure(
                spec.name,
                "malformed_output",
                f"expected dict or list, got {type(data).__name__}",
                source=spec.source,
            )
        try:
            safe = json.loads(json.dumps(data, default=_json_default, allow_nan=False))
        except (TypeError, ValueError) as exc:
            return "error", ToolResult.failure(
                spec.name, "malformed_output", str(exc), source=spec.source
            )
        return "ok", ToolResult(ok=True, tool=spec.name, data=safe, source=spec.source)

    @staticmethod
    async def _safe(coro: Any) -> None:
        """Recording must never break a tool call; failures are logged, not swallowed silently."""
        try:
            await coro
        except Exception:
            logger.exception("tool call recording failed")


def _with(record: ToolCallRecord, **changes: Any) -> ToolCallRecord:
    from dataclasses import replace  # noqa: PLC0415

    return replace(record, **changes)


def _json_default(value: Any) -> Any:
    from datetime import date, datetime  # noqa: PLC0415
    from decimal import Decimal  # noqa: PLC0415

    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item") and callable(value.item):  # NumPy scalars
        return value.item()
    if hasattr(value, "tolist") and callable(value.tolist):  # NumPy arrays
        return value.tolist()
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")
