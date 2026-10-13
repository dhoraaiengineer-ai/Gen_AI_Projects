"""Audit log persistence (tenant stamped by the ORM hook)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.db.models import AuditLog
from src.db.session import Database
from src.security.audit import AuditEvent


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


class AuditRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, event: AuditEvent) -> None:
        async with self.db.session() as session:
            session.add(
                AuditLog(
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                    user_id=_uuid(event.user_id),
                    user_role=event.user_role,
                    action=event.action[:60],
                    resource=(event.resource or "")[:120] or None,
                    decision=event.decision[:20],
                    reason=(event.reason or "")[:500] or None,
                    details=event.details,
                )
            )

    async def recent(
        self, *, limit: int = 100, action: str | None = None, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if since:
            stmt = stmt.where(AuditLog.created_at >= since)
        async with self.db.sessions() as session:
            rows = list(await session.scalars(stmt))
        return [
            {
                "id": r.id,
                "at": r.created_at,
                "requestId": r.request_id,
                "userId": str(r.user_id) if r.user_id else None,
                "userRole": r.user_role,
                "action": r.action,
                "resource": r.resource,
                "decision": r.decision,
                "reason": r.reason,
                "details": r.details,
            }
            for r in rows
        ]
