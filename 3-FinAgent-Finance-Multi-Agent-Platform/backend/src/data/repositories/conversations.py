"""Conversations and messages (long-term chat history, per user, tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from src.core.errors import NotFound
from src.db.models import Conversation, Message
from src.db.session import Database


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def ensure(self, conversation_id: str | None, user_id: str, title: str) -> str:
        """Return an existing conversation owned by this user, or create one."""
        uid = _uuid(user_id)
        if uid is None:
            raise NotFound("conversation owner unknown")
        async with self.db.session() as session:
            cid = _uuid(conversation_id)
            if cid is not None:
                row = await session.scalar(
                    select(Conversation).where(Conversation.id == cid, Conversation.user_id == uid)
                )
                if row is not None:
                    return str(row.id)
            row = Conversation(user_id=uid, title=title[:200] or "Conversation")
            session.add(row)
            await session.flush()
            return str(row.id)

    async def add(
        self,
        conversation_id: str,
        role: str,
        content: str,
        request_id: str | None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        cid = _uuid(conversation_id)
        async with self.db.session() as session:
            session.add(
                Message(
                    conversation_id=cid,
                    role=role,
                    content=content,
                    request_id=request_id,
                    meta=meta or {},
                )
            )
            convo = await session.get(Conversation, cid)
            if convo is not None:
                convo.updated_at = datetime.now(UTC)

    async def recent(self, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
        async with self.db.sessions() as session:
            rows = await session.scalars(
                select(Conversation)
                .where(Conversation.user_id == _uuid(user_id))
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
            )
            return [
                {
                    "conversationId": str(r.id),
                    "title": r.title,
                    "createdAt": r.created_at,
                    "updatedAt": r.updated_at,
                }
                for r in rows
            ]

    async def messages(self, conversation_id: str, user_id: str) -> list[dict[str, Any]]:
        async with self.db.sessions() as session:
            owner = await session.scalar(
                select(Conversation.id).where(
                    Conversation.id == _uuid(conversation_id),
                    Conversation.user_id == _uuid(user_id),
                )
            )
            if owner is None:
                raise NotFound("conversation not found")
            rows = await session.scalars(
                select(Message).where(Message.conversation_id == owner).order_by(Message.id)
            )
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "requestId": m.request_id,
                    "meta": m.meta,
                    "createdAt": m.created_at,
                }
                for m in rows
            ]
