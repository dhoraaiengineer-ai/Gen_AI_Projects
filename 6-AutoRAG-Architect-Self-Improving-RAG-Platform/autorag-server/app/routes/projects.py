"""GET /api/v1/projects -- Returns pipelines shaped as projects (V3 demo bridge).

In V3 there is no separate projects table -- pipelines are the primary entity.
This route shapes pipeline dicts into the Project DTO the frontend expects so
ConfiguratorWizard.listProjects() resolves a usable ID without 404.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.services.pipeline_service import PipelineService

router = APIRouter()


@router.get("")
async def list_projects(
    status: str | None = Query(default=None, description="active | archived"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Return pipelines shaped as Project DTOs.

    The frontend Project interface expects: id, name, description, owner_id,
    created_by, status, created_at, updated_at.  Pipeline dicts contain all
    the fields needed to satisfy that shape, so no separate table is required.

    Status translation (frontend → pipeline DB value):
      active   → None (return all non-deleted: pending, running, ready)
      archived → decommissioned
    """
    # Translate frontend status vocabulary to pipeline status column values
    pipeline_status: str | None
    if status == "active":
        pipeline_status = None  # all non-deleted pipelines are "active" from the UI's perspective
    elif status == "archived":
        pipeline_status = "decommissioned"
    else:
        pipeline_status = status

    svc = PipelineService(db)
    pipelines = await svc.list_by_org(
        organization_id=organization_id,
        status=pipeline_status,
        limit=limit,
        offset=0,
    )

    projects = [
        {
            "id": p["id"],
            "name": p.get("name") or f"Pipeline {str(p['id'])[:8]}",
            "description": p.get("config_yaml") or "",
            "owner_id": organization_id,
            "created_by": organization_id,
            "status": p.get("status") or "active",
            "created_at": p.get("created_at") or "",
            "updated_at": p.get("updated_at") or "",
        }
        for p in pipelines
    ]

    return {
        "status": "ok",
        "data": {"projects": projects, "total": len(projects)},
        "error": None,
        "request_id": trace_id,
    }
