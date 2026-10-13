"""Tool registry: the single execution path (authorization, validation, timeout, output checks)."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest
from pydantic import Field

from src.core.domain import Role
from src.core.errors import NotFound
from src.core.tenancy import current_tenant
from src.tools.base import InMemoryRecorder, ToolContext, ToolSpec
from src.tools.inputs import PortfolioInput, ToolInput
from src.tools.registry import ToolRegistry, summarise_input

TENANT = "0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a01"


class SleepInput(ToolInput):
    seconds: float = Field(ge=0, le=5)


async def echo(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
    return {
        "portfolio": args.portfolio_id,
        "tenant": str(current_tenant()),
        "weight": np.float64(0.31),
        "breached": np.bool_(True),
    }


async def slow(args: SleepInput, ctx: ToolContext) -> dict[str, Any]:
    await asyncio.sleep(args.seconds)
    return {}


async def not_found(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
    raise NotFound("portfolio PF-ZZ not found")


async def crash(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
    raise RuntimeError("secret internal detail")


async def bad_output(args: PortfolioInput, ctx: ToolContext) -> Any:
    return "not a dict"


async def nan_output(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
    return {"value": float("nan")}


@pytest.fixture
def recorder() -> InMemoryRecorder:
    return InMemoryRecorder()


@pytest.fixture
def registry(recorder: InMemoryRecorder) -> ToolRegistry:
    reg = ToolRegistry(recorder)
    reg.register(ToolSpec("calculate_var", ("risk",), "VaR", PortfolioInput, echo, "risk:analyze"))
    reg.register(
        ToolSpec(
            "stress_test", ("risk",), "slow", SleepInput, slow, "risk:analyze", timeout_seconds=0.05
        )
    )
    reg.register(
        ToolSpec("check_policy_limits", ("risk",), "nf", PortfolioInput, not_found, "risk:analyze")
    )
    reg.register(
        ToolSpec("calculate_beta", ("risk",), "crash", PortfolioInput, crash, "risk:analyze")
    )
    reg.register(
        ToolSpec("calculate_cvar", ("risk",), "bad", PortfolioInput, bad_output, "risk:analyze")
    )
    reg.register(
        ToolSpec(
            "calculate_volatility", ("risk",), "nan", PortfolioInput, nan_output, "risk:analyze"
        )
    )
    return reg


def ctx(
    role: Role = Role.RISK_MANAGER, agent: str | None = "risk", tenant: str | None = TENANT
) -> ToolContext:
    return ToolContext(role=role, tenant_id=tenant, agent=agent, request_id="req_test")


async def test_valid_call_runs_in_tenant_scope_and_encodes_numpy(
    registry: ToolRegistry, recorder: InMemoryRecorder
) -> None:
    result = await registry.execute("calculate_var", {"portfolio_id": "pf-a"}, ctx())
    assert result.ok
    assert result.data == {"portfolio": "PF-A", "tenant": TENANT, "weight": 0.31, "breached": True}
    assert recorder.calls[-1].status == "ok"
    assert current_tenant() is None  # scope does not leak out of the call


@pytest.mark.parametrize(
    "args", [{}, {"portfolio_id": "NOT-A-PF"}, {"portfolio_id": "PF-A", "extra": 1}]
)
async def test_invalid_input_is_reported_not_raised(
    registry: ToolRegistry, args: dict[str, Any]
) -> None:
    result = await registry.execute("calculate_var", args, ctx())
    assert not result.ok
    assert result.error is not None and result.error.code == "invalid_input"
    assert result.error.details["errors"]


async def test_role_without_permission_is_denied_and_audited(
    registry: ToolRegistry, recorder: InMemoryRecorder
) -> None:
    result = await registry.execute(
        "calculate_var", {"portfolio_id": "PF-A"}, ctx(role=Role.VIEWER, agent=None)
    )
    assert result.error is not None and result.error.code == "unauthorized"
    assert "risk:analyze" in result.error.message
    assert recorder.denied and recorder.denied[-1][0].status == "denied"


async def test_agent_allow_list_is_enforced(
    registry: ToolRegistry, recorder: InMemoryRecorder
) -> None:
    result = await registry.execute("calculate_var", {"portfolio_id": "PF-A"}, ctx(agent="fraud"))
    assert result.error is not None and result.error.code == "unauthorized"
    assert "agent 'fraud'" in result.error.message
    assert len(recorder.denied) == 1


async def test_missing_tenant_is_denied(registry: ToolRegistry) -> None:
    result = await registry.execute("calculate_var", {"portfolio_id": "PF-A"}, ctx(tenant=None))
    assert result.error is not None and result.error.code == "unauthorized"
    assert "tenant" in result.error.message


async def test_timeout_is_retryable_error(registry: ToolRegistry) -> None:
    result = await registry.execute("stress_test", {"seconds": 1}, ctx())
    assert result.error is not None and result.error.code == "timeout"
    assert result.error.retryable


async def test_app_error_maps_to_code(registry: ToolRegistry) -> None:
    result = await registry.execute("check_policy_limits", {"portfolio_id": "PF-ZZ"}, ctx())
    assert result.error is not None and result.error.code == "not_found"


async def test_crash_is_internal_error_without_details(registry: ToolRegistry) -> None:
    result = await registry.execute("calculate_beta", {"portfolio_id": "PF-A"}, ctx())
    assert result.error is not None and result.error.code == "internal_error"
    assert "secret" not in result.error.message


@pytest.mark.parametrize("tool", ["calculate_cvar", "calculate_volatility"])
async def test_malformed_output_is_caught(registry: ToolRegistry, tool: str) -> None:
    result = await registry.execute(tool, {"portfolio_id": "PF-A"}, ctx())
    assert result.error is not None and result.error.code == "malformed_output"


async def test_unknown_tool(registry: ToolRegistry) -> None:
    result = await registry.execute("launch_rockets", {}, ctx())
    assert result.error is not None and result.error.code == "not_found"


def test_duplicate_registration_rejected(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="twice"):
        registry.register(
            ToolSpec("calculate_var", ("risk",), "", PortfolioInput, echo, "risk:analyze")
        )


def test_input_summary_masks_customer_fields() -> None:
    summary = summarise_input(
        {"customer_id": "CU-000001", "portfolio_id": "PF-A", "tickers": ["A", "B"]}
    )
    assert summary == {"customer_id": "***", "portfolio_id": "PF-A", "tickers": "list[2]"}


def test_tool_context_meta_round_trip() -> None:
    original = ctx()
    assert ToolContext.from_meta(original.to_meta()) == original
    assert (
        ToolContext.from_meta({"role": "superuser"}).role is Role.VIEWER
    )  # unknown role → least privilege
