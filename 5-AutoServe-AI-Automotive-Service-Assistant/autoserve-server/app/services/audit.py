"""Append-only, hash-chained audit log (rules/30, NFR-012).

hash_n = sha256(hash_{n-1} || canonical_json(record_n)); genesis prev_hash = 64 zeros.
Inserts are serialised with a transaction-scoped advisory lock so the chain never forks.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import mask_mapping
from app.core.security import Actor
from app.models import AuditLog

GENESIS_HASH = "0" * 64
_LOCK_KEY = 0x4155_4449_54  # arbitrary constant ("AUDIT")


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def record_material(
    *,
    occurred_at: datetime,
    actor_id: uuid.UUID | None,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "occurred_at": occurred_at.astimezone(UTC).isoformat(),
        "actor_id": str(actor_id) if actor_id else None,
        "actor_role": actor_role,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "payload": payload,
    }


def chain_hash(prev_hash: str, material: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(material)).encode()).hexdigest()


@dataclass(frozen=True)
class ChainCheck:
    intact: bool
    checked: int
    first_broken_seq: int | None


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        actor: Actor,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append one event inside the caller's transaction (the caller commits)."""
        await self.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
        prev = await self.session.scalar(select(AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1))
        occurred_at = datetime.now(UTC)
        masked = json.loads(canonical_json(mask_mapping(payload or {})))
        material = record_material(
            occurred_at=occurred_at,
            actor_id=actor.user_id,
            actor_role=actor.role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=masked,
        )
        prev_hash = prev or GENESIS_HASH
        row = AuditLog(
            occurred_at=occurred_at,
            actor_id=actor.user_id,
            actor_role=actor.role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=masked,
            prev_hash=prev_hash,
            hash=chain_hash(prev_hash, material),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def verify_chain(self, batch_size: int = 1000) -> ChainCheck:
        expected_prev = GENESIS_HASH
        checked = 0
        last_seq = 0
        while True:
            rows = (
                await self.session.scalars(
                    select(AuditLog).where(AuditLog.seq > last_seq).order_by(AuditLog.seq).limit(batch_size)
                )
            ).all()
            if not rows:
                return ChainCheck(intact=True, checked=checked, first_broken_seq=None)
            for row in rows:
                material = record_material(
                    occurred_at=row.occurred_at,
                    actor_id=row.actor_id,
                    actor_role=row.actor_role,
                    action=row.action,
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    payload=row.payload,
                )
                if row.prev_hash != expected_prev or row.hash != chain_hash(row.prev_hash, material):
                    return ChainCheck(intact=False, checked=checked, first_broken_seq=row.seq)
                expected_prev = row.hash
                checked += 1
                last_seq = row.seq
