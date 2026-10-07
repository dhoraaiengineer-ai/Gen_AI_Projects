"""Workflow data: approvals, agent activity, notifications, conversation memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Integer, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentEvent, Approval, Conversation, Message, Notification, NotificationRead


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def upsert_pending(self, **fields: Any) -> Approval:
        """Idempotent on thread_id: a resumed graph re-running the approval node never creates duplicates."""
        stmt = insert(Approval).values(**fields).on_conflict_do_nothing(index_elements=["thread_id"])
        await self.s.execute(stmt)
        approval = (await self.s.execute(select(Approval).where(Approval.thread_id == fields["thread_id"]))).scalar_one()
        return approval

    async def get(self, approval_id: str) -> Approval | None:
        return await self.s.get(Approval, approval_id)

    async def list(self, status: str | None = None, limit: int = 50) -> list[Approval]:
        await self.expire_overdue()
        stmt = select(Approval).order_by(Approval.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Approval.status == status)
        return list((await self.s.execute(stmt)).scalars())

    async def decide(self, approval_id: str, *, status: str, decided_by: str, comment: str | None) -> Approval | None:
        """Atomic transition pending → decided. Returns None if it was not pending (already decided/expired)."""
        stmt = (
            update(Approval)
            .where(Approval.id == approval_id, Approval.status == "pending", Approval.expires_at > func.now())
            .values(status=status, decided_by=decided_by, decided_at=func.now(), comment=comment)
            .returning(Approval)
        )
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def attach_po(self, approval_id: str, po_id: int) -> None:
        await self.s.execute(update(Approval).where(Approval.id == approval_id).values(po_id=po_id))

    async def expire_overdue(self) -> None:
        await self.s.execute(
            update(Approval).where(Approval.status == "pending", Approval.expires_at <= func.now()).values(status="expired")
        )


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def add(self, **fields: Any) -> None:
        self.s.add(AgentEvent(**fields))

    async def recent(self, limit: int = 60) -> list[AgentEvent]:
        return list((await self.s.execute(select(AgentEvent).order_by(AgentEvent.ts.desc()).limit(limit))).scalars())

    async def agent_stats(self, since: datetime) -> dict[str, dict[str, Any]]:
        """Per-agent task counts, success rate and latency percentiles from recorded events."""
        stmt = (
            select(
                AgentEvent.agent,
                func.count(),
                func.sum(func.cast(AgentEvent.outcome == "success", Integer)),
                func.avg(AgentEvent.duration_ms),
                func.percentile_cont(0.95).within_group(AgentEvent.duration_ms),
                func.max(AgentEvent.ts),
            )
            .where(AgentEvent.ts >= since, AgentEvent.duration_ms.is_not(None))
            .group_by(AgentEvent.agent)
        )
        out: dict[str, dict[str, Any]] = {}
        for agent, n, ok, avg, p95, last in (await self.s.execute(stmt)).all():
            out[agent] = {
                "tasks": int(n),
                "success": (float(ok or 0) / n) if n else 1.0,
                "avg_ms": float(avg or 0),
                "p95_ms": float(p95 or 0),
                "last": last,
            }
        return out

    async def agent_recent(self, agent: str, limit: int = 3) -> list[AgentEvent]:
        stmt = select(AgentEvent).where(AgentEvent.agent == agent).order_by(AgentEvent.ts.desc()).limit(limit)
        return list((await self.s.execute(stmt)).scalars())

    async def daily_latency(self, agent: str, hours: int = 24) -> list[float]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        bucket = func.date_trunc("hour", AgentEvent.ts)
        stmt = (
            select(bucket, func.avg(AgentEvent.duration_ms))
            .where(AgentEvent.agent == agent, AgentEvent.ts >= since, AgentEvent.duration_ms.is_not(None))
            .group_by(bucket)
            .order_by(bucket)
        )
        return [float(v or 0) for _, v in (await self.s.execute(stmt)).all()]

    async def count_since(self, since: datetime) -> int:
        return int((await self.s.execute(select(func.count()).select_from(AgentEvent).where(AgentEvent.ts >= since))).scalar_one())


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def upsert(self, *, dedupe_key: str, **fields: Any) -> None:
        stmt = insert(Notification).values(dedupe_key=dedupe_key, **fields)
        stmt = stmt.on_conflict_do_update(
            index_elements=["dedupe_key"], set_={"message": stmt.excluded.message, "title": stmt.excluded.title}
        )
        await self.s.execute(stmt)

    async def for_user(self, user_id: str, limit: int = 30) -> list[tuple[Notification, bool]]:
        stmt = (
            select(Notification, NotificationRead.user_id.is_not(None))
            .outerjoin(NotificationRead, and_(NotificationRead.notification_id == Notification.id, NotificationRead.user_id == user_id))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return [(n, bool(read)) for n, read in (await self.s.execute(stmt)).all()]

    async def mark_read(self, user_id: str, ids: list[int] | None) -> None:
        target_ids = ids if ids is not None else list((await self.s.execute(select(Notification.id))).scalars())
        if not target_ids:
            return
        stmt = insert(NotificationRead).values([{"user_id": user_id, "notification_id": i} for i in target_ids]).on_conflict_do_nothing()
        await self.s.execute(stmt)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def ensure(self, conversation_id: str, user_id: str, title: str) -> Conversation:
        conv = await self.s.get(Conversation, conversation_id)
        if conv is None:
            conv = Conversation(id=conversation_id, user_id=user_id, title=title[:200])
            self.s.add(conv)
            await self.s.flush()
        elif conv.user_id != user_id:
            raise PermissionError("conversation belongs to another user")
        return conv

    async def add_message(self, conversation_id: str, role: str, content: str, meta: dict[str, Any] | None = None) -> None:
        self.s.add(Message(conversation_id=conversation_id, role=role, content=content, meta=meta or {}))

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[Conversation]:
        stmt = select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).limit(limit)
        return list((await self.s.execute(stmt)).scalars())

    async def messages(self, conversation_id: str, user_id: str, limit: int = 100) -> list[Message]:
        conv = await self.s.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user_id:
            return []
        stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at).limit(limit)
        return list((await self.s.execute(stmt)).scalars())
