"""Request/response schemas -- evaluation_configs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EvaluationConfigCreateRequest(BaseModel):
    name: str
    pipeline_id: str | None = None
    retriever_strategy: str | None = None
    reranker: str | None = None
    embedding_model: str | None = None
    top_k: int | None = None
    chunk_size: int | None = None
    # judge_provider/judge_model: informational only today -- no graph node
    # reads these fields yet (RAGAS judging always uses LLMService's normal
    # resolve_chat_provider_chain() failover). Stored for reproducibility/
    # display; wiring an actual judge-model override into ragas_service.py
    # is a separate, not-yet-scoped change.
    judge_provider: str | None = None
    judge_model: str | None = None
    temperature: float | None = None


class EvaluationConfigResponse(BaseModel):
    id: str
    name: str
    pipeline_id: str | None
    retriever_strategy: str | None
    reranker: str | None
    embedding_model: str | None
    top_k: int | None
    chunk_size: int | None
    judge_provider: str | None
    judge_model: str | None
    temperature: float | None
    created_at: datetime
