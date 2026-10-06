"""Composition root: the only place that wires concrete providers together."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from app.agents.rag_graph import build_rag_graph
from app.agents.research_agent import build_research_agent
from app.config import Settings
from app.core.auth import TokenVerifier, build_supabase_verifier
from app.rag import providers
from app.rag.retriever import Retriever
from app.rag.service import RAGService

logger = logging.getLogger(__name__)

ReadinessCheck = Callable[[], bool]


@dataclass
class Container:
    service: RAGService
    readiness_checks: dict[str, ReadinessCheck]
    verifier: TokenVerifier | None  # None only when AUTH_ENABLED=false (local dev)
    _closers: list[Callable[[], None]] = field(default_factory=list)

    def close(self) -> None:
        for close in self._closers:
            close()


def build_container_from(
    settings: Settings,
    vector_store: VectorStore,
    llm: BaseChatModel,
    readiness_checks: dict[str, ReadinessCheck] | None = None,
    *,
    verifier: TokenVerifier | None = None,
    fallback_llm: BaseChatModel | None = None,
    agent_fallback_llm: BaseChatModel | None = None,
    fallback_exceptions: Sequence[type[BaseException]] = (Exception,),
) -> Container:
    """Wire the app from already-built dependencies. Tests use this with fakes."""
    retriever = Retriever(vector_store, settings.chunk_size, settings.chunk_overlap, settings.top_k)
    answer_llm = (
        llm.with_fallbacks([fallback_llm], exceptions_to_handle=tuple(fallback_exceptions)) if fallback_llm else llm
    )
    service = RAGService(
        retriever=retriever,
        rag_graph=build_rag_graph(retriever, answer_llm),
        research_agent=build_research_agent(retriever, llm, agent_fallback_llm, fallback_exceptions),
        model_name=settings.llm_model,
        agent_max_iterations=settings.agent_max_iterations,
    )
    return Container(service=service, readiness_checks=readiness_checks or {}, verifier=verifier)


def build_verifier(settings: Settings) -> TokenVerifier | None:
    if not settings.auth_enabled:
        if settings.environment in ("staging", "prod"):
            raise ValueError("AUTH_ENABLED=false is not allowed in staging/prod")
        logger.warning("AUTH IS DISABLED: every request is treated as an admin (local dev only)")
        return None
    # Fail fast at startup rather than rejecting every request later.
    return build_supabase_verifier(settings.supabase_jwks_url, settings.jwt_issuer, settings.jwt_audience)


def build_container(settings: Settings) -> Container:
    """Wire the app against the real providers (EURI + Postgres/pgvector + Supabase Auth)."""
    engine = providers.build_engine(settings)
    container = build_container_from(
        settings,
        vector_store=providers.build_vector_store(settings, providers.build_embeddings(settings), engine),
        llm=providers.build_chat_model(settings),
        readiness_checks={"database": lambda: providers.database_is_reachable(engine)},
        verifier=build_verifier(settings),
        fallback_llm=providers.build_fallback_model(settings, settings.llm_fallback_model),
        agent_fallback_llm=providers.build_fallback_model(settings, settings.agent_fallback_model),
        fallback_exceptions=providers.FALLBACK_EXCEPTIONS,
    )
    container._closers.append(engine.dispose)
    return container
