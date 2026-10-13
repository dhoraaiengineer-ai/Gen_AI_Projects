"""Approvals presenter: list, detail and decide (human-in-the-loop for draft orders).

A decision resumes the paused supervisor run (Postgres checkpoint) so the run's report records
the outcome. If the run is no longer paused (e.g. its checkpoint was cleared), the decision is
recorded directly — the same segregation-of-duties and expiry rules apply in the repository.
Refused attempts (own proposal, already decided, expired) are audited.
"""

from __future__ import annotations

from typing import Any

from src.container import Container
from src.core.errors import AppError, Conflict, Forbidden
from src.schemas.views import ApprovalDecisionRequest
from src.security.audit import AuditEvent
from src.security.auth import Principal


class ApprovalsPresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    async def list(self, status: str | None) -> list[dict[str, Any]]:
        return await self.container.approvals.list(status)

    async def get(self, approval_id: str) -> dict[str, Any]:
        return await self.container.approvals.get(approval_id)

    async def decide(
        self, principal: Principal, approval_id: str, body: ApprovalDecisionRequest
    ) -> dict[str, Any]:
        approval = await self.container.approvals.get(approval_id)
        decision = {"approve": body.approve, "decidedBy": principal.user_id, "note": body.note}
        runner = await self.container.supervisor()
        try:
            pending = await runner.pending_approval(approval["threadId"], principal.tenant_id)
            if pending is not None and pending.get("approvalId") == approval_id:
                report = await runner.resume(
                    approval["threadId"], decision, tenant_id=principal.tenant_id
                )
                result = report["approval"]
                outcome = {
                    "status": result["status"],
                    "draftOrders": result.get("createdDraftOrders", []),
                }
                await self._audit(principal, approval_id, outcome["status"], body.note, outcome)
            else:
                result = await self.container.approvals.decide(
                    approval_id, approve=body.approve, decided_by=principal.user_id, note=body.note
                )
                outcome = {"status": result["status"], "draftOrders": result["draftOrders"]}
                await self._audit(principal, approval_id, outcome["status"], body.note, outcome)
        except (Forbidden, Conflict) as exc:
            await self._audit(principal, approval_id, "deny", exc.message, {})
            raise
        except AppError:
            raise
        return await self.container.approvals.get(approval_id) | {
            "createdDraftOrders": outcome["draftOrders"]
        }

    async def _audit(
        self,
        principal: Principal,
        approval_id: str,
        decision: str,
        reason: str | None,
        details: dict[str, Any],
    ) -> None:
        await self.container.audit.record(
            AuditEvent(
                action="approval.decide",
                decision=decision,
                reason=reason or decision,
                resource=f"approval:{approval_id}",
                user_id=principal.user_id,
                user_role=principal.role.value,
                details={"draftOrders": len(details.get("draftOrders", []))},
            )
        )
