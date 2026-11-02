"""Non-review route outcomes (specs/graph-state.md): INFO_PENDING and the recall-job recommendation.

Both end the run. INFO_PENDING resumes by re-running the workflow after an upload / field edit. The recall job is only
RECOMMENDED — an advisor confirms it (no automatic state change).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SYSTEM_ACTOR
from app.graph.deps import NodeDeps, run_node
from app.graph.loaders import load_ro
from app.graph.state import ServiceGraphState
from app.models.enums import Role, ROStatus
from app.services.demo_adapters import dealer_staff, notify
from app.services.state_machine import transition


async def info_pending(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    reasons = (state.get("route") or {}).get("reasons", [])

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        if b.ro.status == ROStatus.DIAGNOSING:
            await transition(s, b.ro, ROStatus.INFO_PENDING, SYSTEM_ACTOR, reason="; ".join(reasons)[:500])
        sent = await notify(
            s,
            await dealer_staff(s, b.ro.dealer_id, Role.SERVICE_ADVISOR),
            "ro_info_pending",
            {"ro_ref": b.ro.ro_ref, "reasons": reasons},
        )
        return {"notified": sent}, "ok"

    return await run_node(deps, state, "info_pending", {"ro_id": state["ro_id"], "reasons": reasons}, body)


async def recall_job(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    reasons = (state.get("route") or {}).get("reasons", [])

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        sent = await notify(
            s,
            await dealer_staff(s, b.ro.dealer_id, Role.SERVICE_ADVISOR),
            "recall_job_recommended",
            {"ro_ref": b.ro.ro_ref, "reasons": reasons},
        )
        return {"notified": sent}, "ok"

    return await run_node(deps, state, "recall_job", {"ro_id": state["ro_id"], "reasons": reasons}, body)
