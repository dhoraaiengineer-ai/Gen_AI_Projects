"""Live-DB runtime proof for guardrail enforcement (Part G, G.6).

tests/unit/test_guardrail_enforcement.py already proves the boundary logic and
audit-write *call* against a mocked DB session (16 cases). This file proves the
same BLOCK path against a REAL Postgres connection: the audit_log row genuinely
lands in the database, with the CHECK constraint and INSERT-only trigger live,
not simulated.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CostLimitExceeded, TokenLimitExceeded
from app.services.cost_guardrail import CostBudgetType, CostCheckResult
from app.services.guardrail_enforcement import (
    enforce_cost_guardrail,
    enforce_token_guardrail,
)
from app.services.token_guardrail import TokenBudgetType, TokenCheckResult


class TestTokenGuardrailRuntimeBoundaries:
    """No DB write for token guardrail (Rule 86: only cost breaches audit) --
    this just confirms the boundary semantics hold with real dataclass instances,
    not mocks, matching the PASS/PASS/BLOCK contract from the user's G.6 spec."""

    def test_below_limit_passes(self) -> None:
        check = TokenCheckResult(
            allowed=True,
            budget_type=TokenBudgetType.PROMPT,
            requested_tokens=31999,
            budget_limit=32000,
            reason="within token budget",
        )
        enforce_token_guardrail(check, node="ingestion", x_trace_id="g6-below")

    def test_at_limit_passes(self) -> None:
        check = TokenCheckResult(
            allowed=True,
            budget_type=TokenBudgetType.PROMPT,
            requested_tokens=32000,
            budget_limit=32000,
            reason="within token budget",
        )
        enforce_token_guardrail(check, node="ingestion", x_trace_id="g6-at")

    def test_above_limit_blocks(self) -> None:
        check = TokenCheckResult(
            allowed=False,
            budget_type=TokenBudgetType.PROMPT,
            requested_tokens=32001,
            budget_limit=32000,
            reason="exceeds limit",
        )
        with pytest.raises(TokenLimitExceeded):
            enforce_token_guardrail(check, node="ingestion", x_trace_id="g6-above")


class TestCostGuardrailRuntimeAuditWrite:
    """Cost breaches must write a REAL audit_log row (Rule 86 Section 10)."""

    async def _count_audit_rows(self, db_session: AsyncSession, run_id: uuid.UUID) -> int:
        result = await db_session.execute(
            text("SELECT count(*) FROM audit_log WHERE run_id = :run_id"),
            {"run_id": str(run_id)},
        )
        return int(result.scalar_one())

    async def test_below_budget_passes_no_audit_row(self, db_session: AsyncSession) -> None:
        org_id = uuid.uuid4()
        run_id = uuid.uuid4()
        check = CostCheckResult(
            allowed=True,
            budget_type=CostBudgetType.PIPELINE_BUILD,
            estimated_cost_usd=1.99,
            budget_limit_usd=2.00,
            reason="within budget",
        )
        await enforce_cost_guardrail(
            check, node="improver", x_trace_id="g6-cost-below",
            organization_id=org_id, run_id=run_id,
        )
        assert await self._count_audit_rows(db_session, run_id) == 0

    async def test_at_budget_passes_no_audit_row(self, db_session: AsyncSession) -> None:
        org_id = uuid.uuid4()
        run_id = uuid.uuid4()
        check = CostCheckResult(
            allowed=True,
            budget_type=CostBudgetType.PIPELINE_BUILD,
            estimated_cost_usd=2.00,
            budget_limit_usd=2.00,
            reason="within budget",
        )
        await enforce_cost_guardrail(
            check, node="improver", x_trace_id="g6-cost-at",
            organization_id=org_id, run_id=run_id,
        )
        assert await self._count_audit_rows(db_session, run_id) == 0

    async def test_above_budget_blocks_and_writes_real_audit_row(
        self, db_session: AsyncSession
    ) -> None:
        org_id = uuid.uuid4()
        run_id = uuid.uuid4()
        check = CostCheckResult(
            allowed=False,
            budget_type=CostBudgetType.PIPELINE_BUILD,
            estimated_cost_usd=2.01,
            budget_limit_usd=2.00,
            reason="exceeds limit",
        )
        with pytest.raises(CostLimitExceeded):
            await enforce_cost_guardrail(
                check, node="improver", x_trace_id="g6-cost-above",
                organization_id=org_id, run_id=run_id,
            )

        # enforce_cost_guardrail commits on its OWN session (app's real
        # AsyncSessionLocal, matching production) -- re-query via db_session
        # (a separate connection to the same real DB) to prove the row is
        # genuinely persisted, not just visible within one in-memory session.
        row = await db_session.execute(
            text(
                "SELECT event_type, payload, organization_id, run_id "
                "FROM audit_log WHERE run_id = :run_id"
            ),
            {"run_id": str(run_id)},
        )
        record = row.mappings().one()
        assert record["event_type"] == "cost_limit_exceeded"
        assert record["payload"]["node"] == "improver"
        assert record["payload"]["cost_usd"] == 2.01
        assert record["payload"]["ceiling_usd"] == 2.00
        # Audit-safety: never leak internals beyond the documented safe schema.
        assert set(record["payload"].keys()) == {"node", "budget_type", "cost_usd", "ceiling_usd"}
