"""notify (agent spec 09): DEMO notifications after a recorded decision. No LLM; fixed templates."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.deps import NodeDeps, run_node
from app.graph.loaders import load_ro
from app.graph.state import ServiceGraphState
from app.models import WarrantyClaim
from app.models.enums import Role
from app.services.demo_adapters import dealer_staff, notify


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    review = state["review"]
    d = review["decision"]

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        advisors = await dealer_staff(s, b.ro.dealer_id, Role.SERVICE_ADVISOR)
        if review["kind"] == "estimate_approval":
            payload = {"ro_ref": b.ro.ro_ref, "decision": d["decision"]}
            sent = await notify(s, advisors, "estimate_decision_recorded", payload)
            sent += await notify(s, [b.vehicle.owner_id], "estimate_decision_recorded", payload, channel="sms")
        else:
            claim = await s.get(WarrantyClaim, uuid.UUID(str(state["claim_id"])))
            payload = {
                "ro_ref": b.ro.ro_ref,
                "claim_ref": claim.claim_ref if claim else None,
                "decision": d["decision"],
            }
            sent = await notify(s, advisors, "warranty_decision_recorded", payload)
        return {"notified": sent}, "ok"

    return await run_node(deps, state, "notify", {"decision_id": d["decision_id"]}, body)
