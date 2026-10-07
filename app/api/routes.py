"""RAG endpoints.

Handlers are plain `def`: the LangChain / SQLAlchemy calls underneath are blocking,
so FastAPI runs them in its threadpool instead of stalling the event loop.

Authorization: any signed-in user can query and use the agent; only admins can ingest,
manage the golden dataset and run evaluations, since ingested documents become answers for everyone.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Request, UploadFile, status

from app.api.dependencies import get_service, rate_limit, require_admin, require_user
from app.core.auth import Principal
from app.models.schemas import (
    AgentRequest,
    AgentResponse,
    AuthConfigResponse,
    ChatMessage,
    ConversationOut,
    DeleteDocumentResponse,
    DocumentListResponse,
    ErrorResponse,
    EvalRequest,
    EvalResponse,
    GoldenImportRequest,
    GoldenListResponse,
    IngestRequest,
    IngestResponse,
    MeResponse,
    QueryFilters,
    QueryRequest,
    QueryResponse,
    SessionListResponse,
    SessionOut,
    SourceInfo,
    SourceListResponse,
)
from app.rag.chunking import ChunkingStrategy
from app.rag.filters import MetadataFilter
from app.rag.loaders import SUPPORTED_EXTENSIONS
from app.rag.service import RAGService, UploadedFile

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
    __: None = Depends(rate_limit("ingest")),
) -> IngestResponse:
    return service.ingest(body.documents, body.chunking, body.chunk_overlap_pct, body.tags)


@router.post("/query", response_model=QueryResponse, responses={**AUTH_ERRORS, **LLM_ERRORS})
def query(
    body: QueryRequest,
    service: RAGService = Depends(get_service),
    principal: Principal = Depends(require_user),
    __: None = Depends(rate_limit("query")),
) -> QueryResponse:
    return service.query(body.question, body.top_k, principal.user_id, body.session_id, _filters(body.filters))


@router.post("/agent", response_model=AgentResponse, responses={**AUTH_ERRORS, **LLM_ERRORS})
def agent(
    body: AgentRequest,
    service: RAGService = Depends(get_service),
    principal: Principal = Depends(require_user),
    __: None = Depends(rate_limit("agent")),
) -> AgentResponse:
    return service.run_agent(body.task, principal.user_id, body.session_id, _filters(body.filters))


@router.post(
    "/ingest/files",
    response_model=IngestResponse,
    responses={**AUTH_ERRORS, **LLM_ERRORS, 413: {"model": ErrorResponse}},
    description=f"Upload files ({', '.join(SUPPORTED_EXTENSIONS)}). Re-uploading a file only re-embeds what changed.",
)
def ingest_files(
    request: Request,
    files: Annotated[list[UploadFile], File(description="One or more documents")],
    chunking: Annotated[ChunkingStrategy | None, Form()] = None,
    chunk_overlap_pct: Annotated[float | None, Form(ge=0, le=50)] = None,
    tags: Annotated[str | None, Form(max_length=500, description="Comma-separated, e.g. finance,2024")] = None,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
    __: None = Depends(rate_limit("ingest")),
) -> IngestResponse:
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    uploads: list[UploadedFile] = []
    for upload in files:
        data = upload.file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"{upload.filename} is larger than {max_bytes // (1024 * 1024)} MB",
            )
        uploads.append(UploadedFile(upload.filename or "upload", data))
    return service.ingest_files(uploads, chunking, chunk_overlap_pct, tags.split(",") if tags else None)


@router.get("/golden", response_model=GoldenListResponse, responses=AUTH_ERRORS, tags=["evaluation"])
def list_golden(
    source: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
) -> GoldenListResponse:
    items = service.list_golden(source, limit)
    return GoldenListResponse(count=len(items), items=items)


@router.post("/golden", response_model=GoldenListResponse, responses=AUTH_ERRORS, tags=["evaluation"])
def import_golden(
    body: GoldenImportRequest,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
) -> GoldenListResponse:
    """Add hand-written golden Q&A (kept when a document is re-uploaded; generated ones are replaced)."""
    service.import_golden(body.items)
    items = service.list_golden()
    return GoldenListResponse(count=len(items), items=items)


@router.post("/eval", response_model=EvalResponse, responses={**AUTH_ERRORS, **LLM_ERRORS}, tags=["evaluation"])
def evaluate(
    body: EvalRequest,
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
    __: None = Depends(rate_limit("eval")),
) -> EvalResponse:
    return service.evaluate(body.source, body.limit, body.top_k, body.judge, body.metrics)


@router.get("/documents", response_model=DocumentListResponse, responses=AUTH_ERRORS, tags=["documents"])
def list_documents(
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
) -> DocumentListResponse:
    return service.list_documents()


@router.delete(
    "/documents",
    response_model=DeleteDocumentResponse,
    responses={**AUTH_ERRORS, 404: {"model": ErrorResponse}},
    tags=["documents"],
)
def delete_document(
    source: Annotated[str, Query(min_length=1, max_length=500, description="The document's source name")],
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_admin),
) -> DeleteDocumentResponse:
    """Remove a document from the knowledge base, with its chunks and golden Q&A."""
    result = service.delete_document(source)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No document named {source!r}")
    return result


@router.get("/conversations", response_model=SessionListResponse, responses=AUTH_ERRORS, tags=["conversations"])
def list_conversations(
    service: RAGService = Depends(get_service),
    principal: Principal = Depends(require_user),
) -> SessionListResponse:
    """The caller's own conversations, newest first (long-term memory)."""
    return SessionListResponse(
        sessions=[
            SessionOut(session_id=s.session_id, title=s.title, messages=s.messages, updated_at=s.updated_at)
            for s in service.sessions(principal.user_id)
        ]
    )


@router.get(
    "/conversations/{session_id}", response_model=ConversationOut, responses=AUTH_ERRORS, tags=["conversations"]
)
def get_conversation(
    session_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
    service: RAGService = Depends(get_service),
    principal: Principal = Depends(require_user),
) -> ConversationOut:
    """Messages of one of the caller's conversations. Another user's session id simply returns nothing."""
    turns = service.conversation(principal.user_id, session_id)
    return ConversationOut(session_id=session_id, messages=[ChatMessage(role=t.role, content=t.content) for t in turns])


@router.get("/sources", response_model=SourceListResponse, responses=AUTH_ERRORS, tags=["documents"])
def list_sources(
    service: RAGService = Depends(get_service),
    _: Principal = Depends(require_user),
) -> SourceListResponse:
    """Document names and types, for the "search in" filter. Any signed-in user; no content is returned."""
    return SourceListResponse(sources=[SourceInfo(source=s.source, file_type=s.file_type) for s in service.sources()])


def _filters(body: QueryFilters | None) -> MetadataFilter | None:
    return MetadataFilter.build(body.sources, body.file_types, body.tags) if body else None
