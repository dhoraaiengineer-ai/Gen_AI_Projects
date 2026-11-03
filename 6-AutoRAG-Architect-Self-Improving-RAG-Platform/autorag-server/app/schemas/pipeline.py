"""Request/response schemas for pipeline endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PipelineCreateRequest(BaseModel):
    """POST /api/v1/pipelines — body.

    organization_id is NOT a body field — it comes from the X-Organization-ID
    header (app.core.dependencies.get_organization_id), matching every other
    route's tenancy pattern. See API_SPEC.md v1.1.
    """

    name: str
    config_yaml: str | None = None  # validated YAML from /configurator step 6
    chunk_strategy: str | None = None  # semantic | hierarchical | late
    # Only 'draft' is client-settable -- all other lifecycle transitions
    # (pending/running/ready/failed/decommissioned) are internal, driven by
    # the 9-agent loop, never freely settable via this endpoint. Used by the
    # Configurator wizard to create a real pipeline right after step 1
    # (16-Jul-2026), before the rest of the wizard is filled in.
    status: Literal["draft"] | None = None


class PipelineFinalizeRequest(BaseModel):
    """PATCH /api/v1/pipelines/{id} — body.

    Only one transition is exposed: draft -> pending, fired when the
    Configurator wizard's step 6 ("Launch Pipeline") completes. All other
    status transitions (running/ready/failed/decommissioned) are driven
    internally by the 9-agent loop, never via this client-facing route.

    chunk_strategy/variant_config (25-Jul-2026, Configurator wiring): the
    wizard's real chunking/retrieval/generation choices, made in steps 3-5 --
    AFTER the draft pipeline (and its v1) already exist from step 1->2.
    Optional: omitting both preserves the pipeline's existing config exactly
    as before this field existed.
    """

    status: Literal["pending"]
    chunk_strategy: Literal["semantic", "hierarchical", "late"] | None = None
    variant_config: dict | None = None


class PipelineResponse(BaseModel):
    """Single pipeline row returned to client."""

    id: str
    name: str
    status: str  # pending | running | ready | failed
    unified_score: float | None
    version: int
    created_at: str


class PipelineListResponse(BaseModel):
    """GET /api/v1/pipelines — paginated list."""

    items: list[PipelineResponse]
    total: int
    limit: int
    offset: int
