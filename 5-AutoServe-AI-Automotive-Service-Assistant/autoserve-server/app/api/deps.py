"""Shared FastAPI dependencies for AI components (overridable in tests)."""

from __future__ import annotations

from app.rag.embeddings import Embedder, get_embedder
from app.services.llm_service import LLM, LLMService, db_usage_recorder
from app.services.storage import Storage, get_storage


def get_llm() -> LLM:
    return LLMService(recorder=db_usage_recorder())


def get_embedder_dep() -> Embedder:
    return get_embedder()


def get_storage_dep() -> Storage:
    return get_storage()
