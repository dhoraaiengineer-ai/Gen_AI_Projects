"""Unit tests for app.services.guardrail_enforcement (P0.6-2, 13-Jul-2026).

TokenGuardrail/CostGuardrail.check() already had correct boundary semantics
(requested <= limit passes, > limit fails) -- these tests cover the part that
was previously missing: turning a failed check into an actual raised
exception, plus (cost only, Rule 86 Section 10) a real audit_log write.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import CostLimitExceeded, TokenLimitExceeded
from app.services.cost_guardrail import CostBudgetType, CostCheckResult
from app.services.guardrail_enforcement import (
    enforce_cost_guardrail,
    enforce_token_guardrail,
)
from app.services.token_guardrail import TokenBudgetType, TokenCheckResult


def _token_result(*, requested: int, limit: int) -> TokenCheckResult:
    return TokenCheckResult(
        allowed=requested <= limit,
        budget_type=TokenBudgetType.PROMPT,
        requested_tokens=requested,
        budget_limit=limit,
        reason="within token budget" if requested <= limit else "exceeds limit",
    )


def _cost_result(*, cost: float, limit: float) -> CostCheckResult:
    return CostCheckResult(
        allowed=cost <= limit,
        budget_type=CostBudgetType.PIPELINE_BUILD,
        estimated_cost_usd=cost,
        budget_limit_usd=limit,
        reason="within budget" if cost <= limit else "exceeds limit",
    )


@pytest.fixture
def mock_db() -> MagicMock:
    """Same double used by test_observer.py: AsyncSessionLocal() as an async context manager."""
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock()

    return MagicMock(return_value=mock_ctx)


class TestEnforceTokenGuardrailBoundaries:
    def test_token_below_limit_passes(self) -> None:
        check = _token_result(requested=999, limit=1000)
        enforce_token_guardrail(check, node="ingestion", x_trace_id="t-1")  # must not raise

    def test_token_at_exact_limit_passes(self) -> None:
        check = _token_result(requested=1000, limit=1000)
        enforce_token_guardrail(check, node="ingestion", x_trace_id="t-2")  # must not raise

    def test_token_above_limit_raises_token_limit_exceeded(self) -> None:
        check = _token_result(requested=1001, limit=1000)
        with pytest.raises(TokenLimitExceeded) as exc_info:
            enforce_token_guardrail(check, node="compressor", x_trace_id="t-3")
        assert exc_info.value.count == 1001
        assert exc_info.value.limit == 1000
        assert exc_info.value.token_type == TokenBudgetType.PROMPT.value

    def test_raised_exception_message_includes_node_context(self) -> None:
        check = _token_result(requested=50_000, limit=32_000)
        with pytest.raises(TokenLimitExceeded) as exc_info:
            enforce_token_guardrail(check, node="improver", x_trace_id="t-4")
        assert "improver" in str(exc_info.value)


class TestEnforceCostGuardrailBoundaries:
    @pytest.mark.asyncio
    async def test_cost_below_budget_passes(self, mock_db: MagicMock) -> None:
        check = _cost_result(cost=0.0089, limit=0.009)
        with patch("app.services.guardrail_enforcement.AsyncSessionLocal", new=mock_db):
            await enforce_cost_guardrail(
                check,
                node="improver",
                x_trace_id="t-5",
                organization_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
            )  # must not raise

    @pytest.mark.asyncio
    async def test_cost_at_exact_budget_passes(self, mock_db: MagicMock) -> None:
        check = _cost_result(cost=0.009, limit=0.009)
        with patch("app.services.guardrail_enforcement.AsyncSessionLocal", new=mock_db):
            await enforce_cost_guardrail(
                check,
                node="improver",
                x_trace_id="t-6",
                organization_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
            )  # must not raise

    @pytest.mark.asyncio
    async def test_cost_above_budget_raises_cost_limit_exceeded(self, mock_db: MagicMock) -> None:
        check = _cost_result(cost=0.010, limit=0.009)
        with (
            patch("app.services.guardrail_enforcement.AsyncSessionLocal", new=mock_db),
            pytest.raises(CostLimitExceeded) as exc_info,
        ):
            await enforce_cost_guardrail(
                check,
                node="improver",
                x_trace_id="t-7",
                organization_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
            )
        assert exc_info.value.cost_usd == 0.010
        assert exc_info.value.budget_usd == 0.009

    @pytest.mark.asyncio
    async def test_cost_breach_writes_audit_log_event(self, mock_db: MagicMock) -> None:
        """Rule 86 Section 10: cost limit violations MUST be written to audit_log."""
        check = _cost_result(cost=5.00, limit=2.00)
        org_id = uuid.uuid4()
        run_id = uuid.uuid4()
        with (
            patch("app.services.guardrail_enforcement.AsyncSessionLocal", new=mock_db),
            patch(
                "app.services.guardrail_enforcement.AuditLogRepository.insert",
                new_callable=AsyncMock,
            ) as mock_insert,
            pytest.raises(CostLimitExceeded),
        ):
            await enforce_cost_guardrail(
                check,
                node="improver",
                x_trace_id="t-8",
                organization_id=org_id,
                run_id=run_id,
            )
        mock_insert.assert_awaited_once()
        _, kwargs = mock_insert.call_args
        assert kwargs["event_type"] == "cost_limit_exceeded"
        assert kwargs["organization_id"] == org_id
        assert kwargs["run_id"] == run_id
        assert kwargs["payload"]["cost_usd"] == 5.00
        assert kwargs["payload"]["ceiling_usd"] == 2.00

    @pytest.mark.asyncio
    async def test_cost_breach_without_organization_id_still_raises_no_audit(
        self, mock_db: MagicMock
    ) -> None:
        """System-level calls with no organization_id must still block -- just skip the audit write."""
        check = _cost_result(cost=5.00, limit=2.00)
        with (
            patch("app.services.guardrail_enforcement.AsyncSessionLocal", new=mock_db),
            patch(
                "app.services.guardrail_enforcement.AuditLogRepository.insert",
                new_callable=AsyncMock,
            ) as mock_insert,
            pytest.raises(CostLimitExceeded),
        ):
            await enforce_cost_guardrail(
                check,
                node="improver",
                x_trace_id="t-9",
                organization_id=None,
                run_id=None,
            )
        mock_insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_audit_log_failure_does_not_mask_the_real_block(self, mock_db: MagicMock) -> None:
        """If the audit_log insert itself fails, CostLimitExceeded must still be raised
        (fail closed on the guardrail, not fail open because telemetry broke)."""
        check = _cost_result(cost=5.00, limit=2.00)
        with (
            patch("app.services.guardrail_enforcement.AsyncSessionLocal", new=mock_db),
            patch(
                "app.services.guardrail_enforcement.AuditLogRepository.insert",
                new_callable=AsyncMock,
                side_effect=RuntimeError("db unavailable"),
            ),
            pytest.raises(CostLimitExceeded),
        ):
            await enforce_cost_guardrail(
                check,
                node="improver",
                x_trace_id="t-10",
                organization_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
            )
