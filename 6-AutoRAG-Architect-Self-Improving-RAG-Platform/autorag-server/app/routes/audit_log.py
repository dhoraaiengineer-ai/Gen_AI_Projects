"""GET /api/v1/audit-log — Fetch immutable audit events.

INSERT ONLY table — no POST/PUT/DELETE routes ever exposed here.
Owner: Team 10 (D-4)
Spec: .claude/specs/database.md § audit_log table
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_organization_id, get_trace_id
from app.db.session import get_db
from app.models.audit_log import APPROVED_EVENT_TYPES
from app.repositories.audit_log_repository import AuditLogRepository

router = APIRouter(tags=["Audit Log"])

_MAX_LIMIT = 500


@router.get("")
async def list_audit_log(
    event_type: str | None = Query(default=None, description="Filter by approved event type"),
    run_id: str | None = Query(default=None, description="Filter by LangGraph run ID"),
    limit: int = Query(default=50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    trace_id: str = Depends(get_trace_id),
    organization_id: str = Depends(get_organization_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return paginated audit log entries scoped to the caller's organization.

    INSERT ONLY — this endpoint is read-only. No write operations are exposed.
    Approved event_types: pipeline_created, pipeline_updated, ingest_started,
    ingest_completed, eval_started, eval_completed, deploy_started,
    deploy_completed, rollback_triggered, hitl_approved, hitl_rejected,
    cost_limit_exceeded.

    Owner: Team 10 (D-4)
    """
    if event_type is not None and event_type not in APPROVED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_EVENT_TYPE",
                "message": f"'{event_type}' is not an approved event_type.",
                "valid_values": sorted(APPROVED_EVENT_TYPES),
            },
        )

    run_uuid: uuid.UUID | None = None
    if run_id is not None:
        try:
            run_uuid = uuid.UUID(run_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_RUN_ID", "message": "run_id must be a valid UUID."},
            ) from exc

    org_uuid: uuid.UUID
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ORG_ID", "message": "X-Organization-ID must be a valid UUID."},
        ) from exc

    repo = AuditLogRepository(db)
    entries = await repo.list_by_org(
        organization_id=org_uuid,
        event_type=event_type,
        run_id=run_uuid,
        limit=limit,
        offset=offset,
    )

    return {
        "status": "ok",
        "data": {
            "items": [
                {
                    "id": str(entry.id),
                    "event_type": entry.event_type,
                    "run_id": str(entry.run_id) if entry.run_id else None,
                    "organization_id": str(entry.organization_id) if entry.organization_id else None,
                    "x_trace_id": entry.x_trace_id,
                    "payload": entry.payload,
                    "created_at": entry.created_at.isoformat(),
                }
                for entry in entries
            ],
            "limit": limit,
            "offset": offset,
            "count": len(entries),
        },
        "error": None,
        "request_id": trace_id,
    }
