"""Approval routes: human-in-the-loop decisions on draft orders."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query

from src.api.deps import get_container
from src.api.limits import limited
from src.container import Container
from src.presenters.approvals import ApprovalsPresenter
from src.schemas.views import ApprovalDecisionRequest
from src.security.auth import Principal

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

Deps = Annotated[Container, Depends(get_container)]
# Proposers see what they proposed; approvers need the queue too.
Proposer = Annotated[Principal, Depends(limited(("portfolio:propose", "approvals:decide"), "read"))]
Approver = Annotated[Principal, Depends(limited("approvals:decide", "analyze"))]
ApprovalId = Annotated[str, Path(pattern=r"^[0-9a-fA-F\-]{36}$")]
Status = Literal["pending", "approved", "rejected", "expired"]


@router.get("")
async def list_approvals(
    principal: Proposer, container: Deps, status: Annotated[Status | None, Query()] = None
) -> list[dict[str, Any]]:
    """Approvals, newest first (optionally by status)."""
    return await ApprovalsPresenter(container).list(status)


@router.get("/{approval_id}")
async def get_approval(
    approval_id: ApprovalId, principal: Proposer, container: Deps
) -> dict[str, Any]:
    return await ApprovalsPresenter(container).get(approval_id)


@router.post("/{approval_id}/decision")
async def decide(
    approval_id: ApprovalId, body: ApprovalDecisionRequest, principal: Approver, container: Deps
) -> dict[str, Any]:
    """Approve or reject. The requester cannot approve their own proposal; approval creates
    draft orders only (nothing is executed)."""
    return await ApprovalsPresenter(container).decide(principal, approval_id, body)
