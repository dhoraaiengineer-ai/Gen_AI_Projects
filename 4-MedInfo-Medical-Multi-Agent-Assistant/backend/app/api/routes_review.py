"""Clinician review queue (clinician/admin) and verdict export (admin)."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.deps import get_container, require_admin, require_clinician
from app.container import Container
from app.core.auth import Principal

router = APIRouter(prefix="/api/review", tags=["review"])
admin_router = APIRouter(prefix="/api/admin/review", tags=["admin-review"])


class VerdictIn(BaseModel):
    verdict: Literal["safe_and_correct", "minor_issue", "incorrect", "unsafe"]
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/queue")
def review_queue(
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(require_clinician),
    container: Container = Depends(get_container),
) -> list[dict[str, object]]:
    return [
        {
            "id": i.id,
            "created_at": i.created_at,
            "source": i.source,
            "question": i.question,
            "answer": json.loads(i.answer_json),
        }
        for i in container.review.queue(limit)
    ]


@router.post("/{item_id}")
def record_verdict(
    item_id: str,
    body: VerdictIn,
    principal: Principal = Depends(require_clinician),
    container: Container = Depends(get_container),
) -> dict[str, str | None]:
    item = container.review.record(
        item_id, verdict=body.verdict, notes=body.notes, reviewer_id=principal.user_id
    )
    return {"id": item.id, "status": item.status, "verdict": item.verdict}


@router.get("/summary")
def review_summary(
    principal: Principal = Depends(require_clinician), container: Container = Depends(get_container)
) -> dict[str, int]:
    return container.review.summary()


@admin_router.get("/export")
def export_reviews(
    fmt: Literal["json", "csv"] = Query(default="json", alias="format"),
    principal: Principal = Depends(require_admin),
    container: Container = Depends(get_container),
) -> PlainTextResponse:
    media = "text/csv" if fmt == "csv" else "application/json"
    return PlainTextResponse(container.review.export(fmt), media_type=media)
