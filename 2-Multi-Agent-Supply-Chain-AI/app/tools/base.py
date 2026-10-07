"""Tool infrastructure: typed results, timeouts, metrics and the per-request context tools run with."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError

from app.core.errors import AppError, NotFound
from app.core.metrics import TOOL_LATENCY
from app.core.rbac import User

logger = logging.getLogger(__name__)

SKU_PATTERN = r"^SKU-\d{3,6}$"
SKU_RE = re.compile(SKU_PATTERN, re.I)


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error_code: str | None = None
    message: str | None = None

    def to_llm(self) -> str:
        """Compact JSON for the model. Errors carry a safe message, never internals."""
        payload = {"ok": True, "data": self.data} if self.ok else {"ok": False, "error": self.error_code, "message": self.message}
        return json.dumps(payload, default=str, separators=(",", ":"))


@dataclass
class ToolContext:
    """Everything a tool may touch for one request. Built by the container; tools never import providers."""

    user: User
    services: Any  # app.container.Services (typed loosely to avoid an import cycle)
    run_id: str = ""
    calls: list[dict[str, Any]] = field(default_factory=list)  # audit trail of tool calls in this run


def normalise_sku(sku: str) -> str:
    sku = sku.strip().upper()
    if not SKU_RE.match(sku):
        raise NotFound(f"{sku} is not a valid SKU (expected format SKU-123).")
    return sku


async def run_tool(name: str, fn: Callable[[], Awaitable[Any]], timeout_seconds: float, ctx: ToolContext) -> ToolResult:
    started = time.perf_counter()
    outcome = "ok"
    try:
        data = await asyncio.wait_for(fn(), timeout=timeout_seconds)
        result = ToolResult(ok=True, data=data)
    except TimeoutError:
        outcome = "timeout"
        result = ToolResult(ok=False, error_code="timeout", message=f"{name} timed out after {timeout_seconds:.0f}s")
    except NotFound as exc:
        outcome = "not_found"
        result = ToolResult(ok=False, error_code="not_found", message=exc.message)
    except AppError as exc:
        outcome = exc.code
        result = ToolResult(ok=False, error_code=exc.code, message=exc.message)
    except ValidationError as exc:
        outcome = "invalid_input"
        result = ToolResult(ok=False, error_code="invalid_input", message=str(exc.errors()[0].get("msg", "invalid input")))
    except Exception:
        outcome = "error"
        logger.exception("tool failed", extra={"tool": name})
        result = ToolResult(ok=False, error_code="tool_error", message=f"{name} failed unexpectedly")
    elapsed = time.perf_counter() - started
    TOOL_LATENCY.labels(name, outcome).observe(elapsed)
    ctx.calls.append({"tool": name, "outcome": outcome, "ms": round(elapsed * 1000)})
    return result


def make_tool(
    *,
    name: str,
    description: str,
    args_schema: type[BaseModel],
    handler: Callable[..., Awaitable[Any]],
    ctx: ToolContext,
    timeout: float,
) -> StructuredTool:
    """Wrap an async handler as a LangChain tool returning a JSON ToolResult string."""

    async def _call(**kwargs: Any) -> str:
        result = await run_tool(name, lambda: handler(**kwargs), timeout, ctx)
        return result.to_llm()

    return StructuredTool.from_function(coroutine=_call, name=name, description=description, args_schema=args_schema)
