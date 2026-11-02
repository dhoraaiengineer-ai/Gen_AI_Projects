"""DEMO adapters (no real OEM / SMS / email). Everything they produce is labelled DEMO and SYNTHETIC.

DemoOemAdapter.submit() is called ONLY after a `submit_to_oem` decision recorded by a warranty_admin (agent spec 09).
It writes the claim as a JSON file to the outbox and returns a fake acknowledgement.
Notifications are stored in `notifications` (payload may hold PII) and logged without PII.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, RoleRow, User

log = structlog.get_logger(__name__)
OUTBOX = Path(os.environ.get("DEMO_OEM_OUTBOX", Path(__file__).resolve().parents[2] / "var" / "oem_outbox"))


class DemoOemAdapter:
    def __init__(self, outbox: Path = OUTBOX) -> None:
        self.outbox = outbox

    def submit(self, claim: dict[str, Any]) -> dict[str, Any]:
        self.outbox.mkdir(parents=True, exist_ok=True)
        ack = {
            "adapter": "DEMO",
            "ack_id": f"DEMO-ACK-{uuid.uuid4().hex[:10].upper()}",
            "received_at": datetime.now(UTC).isoformat(),
            "status": "RECEIVED",
        }
        path = self.outbox / f"{claim['claim_ref']}.json"
        path.write_text(
            json.dumps({"claim": claim, "ack": ack, "label": "SYNTHETIC DEMO CLAIM"}, indent=2, default=str),
            encoding="utf-8",
        )
        log.info("demo_oem_submitted", claim_ref=claim["claim_ref"], ack_id=ack["ack_id"])
        return ack


async def notify(
    session: AsyncSession, user_ids: list[uuid.UUID], template: str, payload: dict[str, Any], channel: str = "in_app"
) -> list[str]:
    """Queue DEMO notifications; the DEMO adapter 'sends' immediately (status=sent). Returns notification ids."""
    ids = []
    for uid in dict.fromkeys(user_ids):
        n = Notification(
            user_id=uid, channel=channel, template=template, payload=payload, status="sent", adapter="DEMO"
        )
        session.add(n)
        await session.flush()
        ids.append(str(n.id))
    log.info("demo_notifications_sent", template=template, count=len(ids), channel=channel)
    return ids


async def dealer_staff(session: AsyncSession, dealer_id: uuid.UUID, role: str) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(User.id)
            .join(RoleRow, RoleRow.id == User.role_id)
            .where(User.dealer_id == dealer_id, RoleRow.name == role, User.deleted_at.is_(None))
        )
    )
