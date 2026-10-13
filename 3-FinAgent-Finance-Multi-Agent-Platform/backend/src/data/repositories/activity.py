"""Read models over execution records: one request trace, agent statistics, recent activity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Integer, case, func, select

from src.db.models import A2AMessageRow, AgentRun, Approval, AuditLog, McpToolCall
from src.db.session import Database


class ActivityRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def request_trace(self, request_id: str) -> dict[str, Any]:
        """Audit entries, agent runs, A2A envelopes and MCP tool calls of one request."""
        async with self.db.sessions() as session:
            audit = list(
                await session.scalars(
                    select(AuditLog).where(AuditLog.request_id == request_id).order_by(AuditLog.id)
                )
            )
            runs = list(
                await session.scalars(
                    select(AgentRun)
                    .where(AgentRun.request_id == request_id)
                    .order_by(AgentRun.started_at)
                )
            )
            messages = list(
                await session.scalars(
                    select(A2AMessageRow)
                    .where(A2AMessageRow.request_id == request_id)
                    .order_by(A2AMessageRow.created_at)
                )
            )
            tools = list(
                await session.scalars(
                    select(McpToolCall)
                    .where(McpToolCall.request_id == request_id)
                    .order_by(McpToolCall.id)
                )
            )
        return {
            "requestId": request_id,
            "audit": [
                {
                    "at": a.created_at,
                    "action": a.action,
                    "decision": a.decision,
                    "reason": a.reason,
                    "userRole": a.user_role,
                    "resource": a.resource,
                    "details": a.details,
                }
                for a in audit
            ],
            "agentRuns": [
                {
                    "agent": r.agent,
                    "task": r.task,
                    "status": r.status,
                    "startedAt": r.started_at,
                    "durationMs": r.duration_ms,
                    "confidence": r.confidence,
                    "toolCalls": r.tool_calls,
                    "error": r.error,
                }
                for r in runs
            ],
            "a2aMessages": [
                {
                    "messageId": m.message_id,
                    "type": m.type,
                    "source": m.source_agent,
                    "target": m.target_agent,
                    "task": m.task,
                    "attempt": m.attempt,
                    "latencyMs": m.latency_ms,
                    "correlationId": m.correlation_id,
                    "error": m.error,
                    "at": m.created_at,
                }
                for m in messages
            ],
            "toolCalls": [
                {
                    "tool": t.tool,
                    "server": t.server,
                    "agent": t.agent,
                    "status": t.status,
                    "durationMs": t.duration_ms,
                    "errorCode": t.error_code,
                    "at": t.created_at,
                }
                for t in tools
            ],
        }

    async def agent_stats(self, days: int = 7) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)
        failed = func.sum(case((AgentRun.status == "failed", 1), else_=0)).cast(Integer)
        stmt = (
            select(
                AgentRun.agent.label("agent"),
                func.count().label("runs"),
                func.avg(AgentRun.duration_ms).label("avg_ms"),
                func.avg(AgentRun.confidence).label("avg_conf"),
                failed.label("failed"),
                func.max(AgentRun.started_at).label("last"),
            )
            .where(AgentRun.started_at >= since)
            .group_by(AgentRun.agent)
        )
        async with self.db.sessions() as session:
            rows = (await session.execute(stmt)).all()
        return [
            {
                "agent": r.agent,
                "runs": int(r.runs),
                "avgDurationMs": round(float(r.avg_ms or 0), 1),
                "avgConfidence": round(float(r.avg_conf), 3) if r.avg_conf is not None else None,
                "failed": int(r.failed or 0),
                "lastRunAt": r.last,
            }
            for r in rows
        ]

    async def recent_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self.db.sessions() as session:
            rows = await session.scalars(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            )
            return [
                {
                    "at": a.created_at,
                    "requestId": a.request_id,
                    "action": a.action,
                    "decision": a.decision,
                    "reason": a.reason,
                    "userRole": a.user_role,
                }
                for a in rows
            ]

    async def pending_approvals(self) -> int:
        async with self.db.sessions() as session:
            count = await session.scalar(
                select(func.count()).select_from(Approval).where(Approval.status == "pending")
            )
        return int(count or 0)
