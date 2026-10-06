"""RAG endpoints.

Handlers are plain `def`: the LangChain / SQLAlchemy calls underneath are blocking,
so FastAPI runs them in its threadpool instead of stalling the event loop.

Authorization: any signed-in user can query and use the agent; only admins can ingest,
since ingested documents become answers for everyone.
"""

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_service, require_admin, require_user
from app.core.auth import Principal
from app.models.schemas import (
    AgentRequest,
    AgentResponse,
    AuthConfigResponse,
    ErrorResponse,
    IngestRequest,
    IngestResponse,
    MeResponse,
    QueryRequest,
    QueryResponse,
)
from app.rag.service import RAGService

router = APIRouter(prefix="/api/v1", tags=["rag"])

AUTH_ERRORS = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}
LLM_ERRORS = {429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


@router.get("/auth/config", response_model=AuthConfigResponse, tags=["auth"])
def auth_config(request: Request) -> AuthConfigResponse:
    """Public: what the UI needs to sign users in. The publishable key is public by design."""
    settings = request.app.state.settings
    return AuthConfigResponse(
        enabled=settings.auth_enabled,
        supabase_url=settings.supabase_url,
        supabase_publishable_key=settings.supabase_publishable_key,
    )


@router.get("/me", response_model=MeResponse, responses=AUTH_ERRORS, tags=["auth"])
def me(principal: Principal = Depends(require_user)) -> MeResponse:
    return MeResponse(user_id=principal.user_id, email=principal.email, role=principal.role.value)


@router.post("/ingest", response_model=IngestResponse, responses={**AUTH_ERRORS, **LLM_ERRORS})
def ingest(
    body: IngestRequest,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
) -> IngestResponse:
    return service.ingest(body.documents)


@router.post("/query", response_model=QueryResponse, responses={**AUTH_ERRORS, **LLM_ERRORS})
def query(
    body: QueryRequest,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_user),
) -> QueryResponse:
    return service.query(body.question, body.top_k)


@router.post("/agent", response_model=AgentResponse, responses={**AUTH_ERRORS, **LLM_ERRORS})
def agent(
    body: AgentRequest,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_user),
) -> AgentResponse:
    return service.run_agent(body.task)
