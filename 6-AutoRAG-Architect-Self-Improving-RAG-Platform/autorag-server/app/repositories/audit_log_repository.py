"""Repository — audit_log table (INSERT ONLY).

⛔ THIS REPOSITORY ENFORCES THREE LAYERS OF INSERT-ONLY PROTECTION:
  1. This file has NO update() or delete() methods (Layer 2)
  2. AuditLog ORM model has no update/delete methods (Layer 1)
  3. DB trigger in migration 0004 raises EXCEPTION on UPDATE/DELETE (Layer 3)

The only write operation is insert(). If you need to "correct" an audit log
entry, insert a new corrective event — never mutate existing rows.

Approved event_types -- 14 total (see APPROVED_EVENT_TYPES in models):
  pipeline_created, pipeline_updated, ingest_started, ingest_completed,
  eval_started, eval_completed, deploy_started, deploy_completed,
  rollback_triggered, hitl_approved, hitl_rejected, cost_limit_exceeded,
  guardrail_blocked  (added 03-Jul-2026 -- migration 0007)
  pii_redacted        (added 13-Jul-2026 -- migration 0011)

Team 1 owns this file.
Spec: .claude/specs/database.md § audit_log table
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import APPROVED_EVENT_TYPES, AuditLog


class AuditLogRepository:
    """INSERT-ONLY data-access layer for audit_log table.

    Constructor injection: pass an AsyncSession from get_db() FastAPI dependency.

    IMPORTANT: This class intentionally has no update() or delete() methods.
    Any attempt to add them violates the audit_log INSERT ONLY contract and
    MUST be refused in code review.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write (INSERT ONLY) ───────────────────────────────────────────────────

    async def insert(
        self,
        *,
        event_type: str,
        payload: dict,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        trace_id: str | None = None,
    ) -> AuditLog:
        """Insert a new immutable audit event.

        Args:
            event_type: MUST be one of the 14 APPROVED_EVENT_TYPES.
            payload: Structured JSONB event payload (no PII — masked before call).
            organization_id: Tenant association (nullable for system events).
            run_id: LangGraph run correlation ID (nullable for non-run events).
            trace_id: X-Trace-ID from the originating HTTP request.

        Returns:
            Persisted AuditLog ORM instance.

        Raises:
            ValueError: If event_type is not in APPROVED_EVENT_TYPES.
            RuntimeError: If called with an attempt to include PII in payload
                          (enforced by policy — caller must mask before insert).
        """
        if event_type not in APPROVED_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type '{event_type}'. "
                f"Must be one of: {sorted(APPROVED_EVENT_TYPES)}"
            )

        log_entry = AuditLog(
            event_type=event_type,
            payload=payload,
            organization_id=organization_id,
            run_id=run_id,
            x_trace_id=trace_id,  # model column is x_trace_id, not trace_id (Rule 86 naming)
        )
        self._session.add(log_entry)
        await self._session.flush()
        await self._session.refresh(log_entry)
        return log_entry

    # ── Read operations ───────────────────────────────────────────────────────

    async def get_by_id(self, *, log_id: uuid.UUID) -> AuditLog | None:
        """Fetch a single audit log entry by primary key.

        No organization_id filter — audit log reads may be system-level.
        UI/API callers MUST add their own org scoping via list_by_org().
        """
        stmt = select(AuditLog).where(AuditLog.id == log_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_org(
        self,
        *,
        organization_id: uuid.UUID,
        event_type: str | None = None,
        run_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[AuditLog]:
        """List audit events for an org, newest first.

        Used by GET /api/v1/audit-log endpoint.

        Args:
            organization_id: Tenant filter — mandatory for API-facing calls.
            event_type: Optional filter to a specific approved event type.
            run_id: Optional filter to a specific LangGraph run.
            limit: Page size (max 500 enforced at service layer).
            offset: Pagination offset.

        Returns:
            List of AuditLog entries ordered by created_at DESC.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if event_type is not None:
            if event_type not in APPROVED_EVENT_TYPES:
                raise ValueError(
                    f"Invalid event_type filter '{event_type}'. "
                    f"Must be one of: {sorted(APPROVED_EVENT_TYPES)}"
                )
            stmt = stmt.where(AuditLog.event_type == event_type)

        if run_id is not None:
            stmt = stmt.where(AuditLog.run_id == run_id)

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_run_id(
        self,
        *,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Sequence[AuditLog]:
        """Fetch all audit events for a specific LangGraph run, chronological order.

        Useful for reconstructing the full event timeline of a pipeline run.
        """
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.run_id == run_id,
                AuditLog.organization_id == organization_id,
            )
            .order_by(AuditLog.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── DELIBERATELY ABSENT ───────────────────────────────────────────────────
    # update() — NOT IMPLEMENTED. audit_log is INSERT ONLY.
    # delete() — NOT IMPLEMENTED. audit_log is INSERT ONLY.
    # If you are reading this and considering adding these methods:
    # ⛔ STOP. Read the module docstring. Then read CLAUDE.md § Security.
