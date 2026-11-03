"""Shared enforcement for TokenGuardrail / CostGuardrail check results.

P0.6-2 (13-Jul-2026): TokenGuardrail.check() / CostGuardrail.check() have always
computed the correct allowed/blocked verdict (boundary semantics were already
right: `requested <= limit` passes, `> limit` fails), but no caller ever acted
on `allowed=False` -- ingestion.py and compressor.py logged a warning and kept
going, improver.py's cost check blocked GraphState but never wrote the
Rule 86 Section 10-mandated audit_log row (METRICS_WIRING_MATRIX.md Status D).

This module is the single place a node turns a failed check into:
  1. The documented exception (CostLimitExceeded / TokenLimitExceeded).
  2. For cost breaches only (Rule 86 Section 10): an audit_log INSERT,
     event_type="cost_limit_exceeded".

Callers catch the exception and build their own GraphState-shaped blocked
return (each node already owns a local `_trace_entry` helper with its own
node-specific extra fields -- reproducing that shape here would duplicate it).
"""
from __future__ import annotations

import logging
import uuid

from app.core.database import AsyncSessionLocal
from app.core.exceptions import CostLimitExceeded, TokenLimitExceeded
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.cost_guardrail import CostCheckResult
from app.services.token_guardrail import TokenCheckResult

logger = logging.getLogger(__name__)


def enforce_token_guardrail(check: TokenCheckResult, *, node: str, x_trace_id: str) -> None:
    """Raise TokenLimitExceeded if `check` failed. No-op (returns None) if it passed."""
    if check.allowed:
        return
    logger.error(
        "token_guardrail_enforced_block",
        extra={
            "node": node,
            "x_trace_id": x_trace_id,
            "budget_type": check.budget_type.value,
            "requested_tokens": check.requested_tokens,
            "budget_limit": check.budget_limit,
        },
    )
    raise TokenLimitExceeded(
        token_type=check.budget_type.value,
        count=check.requested_tokens,
        limit=check.budget_limit,
        context=node,
    )


async def enforce_cost_guardrail(
    check: CostCheckResult,
    *,
    node: str,
    x_trace_id: str,
    organization_id: uuid.UUID | None,
    run_id: uuid.UUID | None,
) -> None:
    """Raise CostLimitExceeded if `check` failed, after writing the audit_log
    row required by Rule 86 Section 10. No-op (returns None) if it passed.
    """
    if check.allowed:
        return
    logger.error(
        "cost_guardrail_enforced_block",
        extra={
            "node": node,
            "x_trace_id": x_trace_id,
            "budget_type": check.budget_type.value,
            "estimated_cost_usd": check.estimated_cost_usd,
            "budget_limit_usd": check.budget_limit_usd,
        },
    )
    if organization_id is not None:
        try:
            async with AsyncSessionLocal() as session:
                await AuditLogRepository(session).insert(
                    event_type="cost_limit_exceeded",
                    payload={
                        "node": node,
                        "budget_type": check.budget_type.value,
                        "cost_usd": check.estimated_cost_usd,
                        "ceiling_usd": check.budget_limit_usd,
                    },
                    organization_id=organization_id,
                    run_id=run_id,
                    trace_id=x_trace_id,
                )
                await session.commit()
        except Exception as audit_exc:  # noqa: BLE001 -- audit failure must not mask the real block
            logger.error(
                "cost_guardrail_audit_log_insert_failed",
                extra={"error": str(audit_exc), "x_trace_id": x_trace_id},
            )
    raise CostLimitExceeded(
        context=node,
        cost_usd=check.estimated_cost_usd,
        budget_usd=check.budget_limit_usd,
    )
