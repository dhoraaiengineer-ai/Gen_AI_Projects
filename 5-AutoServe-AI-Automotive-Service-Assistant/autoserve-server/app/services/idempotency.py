"""Idempotency-Key store (rules/10): same key + same request → stored response; same key + different request → 409."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import IdempotencyConflict
from app.core.security import Actor
from app.models import IdempotencyKey

TTL = timedelta(hours=24)


def request_hash(route: str, body: dict[str, Any]) -> str:
    return hashlib.sha256(f"{route}\x1f{json.dumps(body, sort_keys=True, default=str)}".encode()).hexdigest()


async def replay(
    session: AsyncSession, actor: Actor, key: str, route: str, body: dict[str, Any]
) -> dict[str, Any] | None:
    row = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    if row is None or row.expires_at < datetime.now(UTC):
        return None
    if row.actor_id != actor.user_id or row.route != route or row.request_hash != request_hash(route, body):
        raise IdempotencyConflict()
    return dict(row.response)


async def remember(
    session: AsyncSession, actor: Actor, key: str, route: str, body: dict[str, Any], response: dict[str, Any]
) -> None:
    if actor.user_id is None:
        return
    session.add(
        IdempotencyKey(
            key=key,
            actor_id=actor.user_id,
            route=route,
            request_hash=request_hash(route, body),
            response=response,
            expires_at=datetime.now(UTC) + TTL,
        )
    )
    await session.flush()
