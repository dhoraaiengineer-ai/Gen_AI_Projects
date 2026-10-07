"""Composition root: the only place that wires concrete providers together."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.vectorstores import VectorStore

from app.agents.rag_graph import build_rag_graph
from app.agents.research_agent import as_model_list, build_research_agent
from app.config import Settings
from app.core.auth import TokenVerifier, build_supabase_verifier
from app.core.circuit import BreakerRegistry
from app.guardrails.engine import Guardrails, load_policy
from app.rag import loaders, providers
from app.rag.cache import AnswerCache, InMemoryKeyValueStore, KeyValueStore, PromptCache
from app.rag.chunking import (
    Chunker,
    ChunkingStrategy,
    ParentChildChunker,
    RecursiveChunker,
    SemanticChunker,
    TableAwareChunker,
    overlap_chars,
)
from app.rag.evaluation import Evaluator
from app.rag.filters import MetadataFilter, to_callable_filter, to_pgvector_filter
from app.rag.golden import GoldenGenerator, GoldenStore, InMemoryGoldenStore
from app.rag.memory import ConversationMemory, ConversationStore, InMemoryConversationStore
from app.rag.prompts import prompt_fingerprints
from app.rag.ragas_metrics import RagasJudge
from app.rag.registry import DocumentRegistry, InMemoryDocumentRegistry
from app.rag.rerank import LLMReranker
from app.rag.retriever import KeywordSearch, Retriever
from app.rag.service import RAGService
from app.rag.websearch import WebSearch

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
    fallback_llm: BaseChatModel | Sequence[BaseChatModel] | None = None,  # tried in order
    agent_fallback_llm: BaseChatModel | Sequence[BaseChatModel] | None = None,  # must be tool-capable
    fallback_exceptions: Sequence[type[BaseException]] = (Exception,),
    registry: DocumentRegistry | None = None,
    golden_store: GoldenStore | None = None,
    judge_llm: Runnable[LanguageModelInput, BaseMessage] | None = None,
    web_search: WebSearch | None = None,
    kv_store: KeyValueStore | None = None,
    conversations: ConversationStore | None = None,
    keyword_search: KeywordSearch | None = None,
    vector_filter: Callable[[MetadataFilter], Any] = to_callable_filter,
) -> Container:
    """Wire the app from already-built dependencies. Tests use this with fakes (and in-memory stores)."""
    kv_store = kv_store or InMemoryKeyValueStore()
    answer_cache = (
        AnswerCache(kv_store, settings.collection_name, settings.answer_cache_ttl_seconds)
        if settings.cache_enabled
        else None
    )
    memory = ConversationMemory(
        conversations or InMemoryConversationStore(),
        kv_store,
        settings.memory_window_messages,
        settings.short_term_memory_ttl_seconds,
    )
    retriever = Retriever(
        vector_store,
        partial(build_chunker, settings, vector_store.embeddings),
        settings.chunking_strategy,
        settings.top_k,
        registry or InMemoryDocumentRegistry(),
        keyword_search if settings.hybrid_search else None,
        rerank_candidates=settings.rerank_candidates,
        vector_filter=vector_filter,
    )
    answer_llm = (
        llm.with_fallbacks(answer_fallbacks, exceptions_to_handle=tuple(fallback_exceptions))
        if (answer_fallbacks := as_model_list(fallback_llm))
        else llm
    )
    if settings.rerank_enabled:
        retriever.reranker = LLMReranker(answer_llm)  # same fallback chain, breakers and prompt cache
    guardrails = (
        Guardrails(load_policy(settings.guardrails_policy_path), prompt_fingerprints())
        if settings.guardrails_enabled
        else None
    )
    loaders.OCR_ENABLED = settings.ocr_enabled
    rag_graph = build_rag_graph(retriever, answer_llm)
    service = RAGService(
        retriever=retriever,
        rag_graph=rag_graph,
        research_agent=build_research_agent(
            retriever,
            llm,
            agent_fallback_llm,
            fallback_exceptions,
            web_search,
            settings.web_search_max_results,
            content_guard=(lambda text: guardrails.check_document(text, "web").text) if guardrails else None,
        ),
        model_name=settings.llm_model,
        agent_max_iterations=settings.agent_max_iterations,
        golden_store=golden_store or InMemoryGoldenStore(),
        golden_generator=GoldenGenerator(answer_llm, settings.golden_questions_per_document),
        evaluator=Evaluator(
            retriever, rag_graph, judge_llm or answer_llm, RagasJudge(judge_llm or answer_llm, vector_store.embeddings)
        ),
        answer_cache=answer_cache,
        memory=memory,
        rewriter=answer_llm,
        hallucination_guard=settings.hallucination_guard,
        guardrails=guardrails,
        audit_content=settings.audit_log_content,
    )
    return Container(service=service, readiness_checks=readiness_checks or {}, verifier=verifier)


def build_chunker(
    settings: Settings,
    embeddings: Embeddings | None,
    strategy: ChunkingStrategy,
    overlap_pct: float | None = None,
) -> Chunker:
    """Build the chunker for one ingest. `overlap_pct` overrides every overlap for that upload; otherwise
    regular chunks use CHUNK_OVERLAP_PCT and parent-child children use CHILD_CHUNK_OVERLAP_PCT."""
    chunk_overlap = overlap_chars(
        settings.chunk_size, settings.chunk_overlap_pct if overlap_pct is None else overlap_pct
    )
    match strategy:
        case ChunkingStrategy.RECURSIVE:
            return RecursiveChunker(settings.chunk_size, chunk_overlap)
        case ChunkingStrategy.TABLE:
            return TableAwareChunker(settings.chunk_size, chunk_overlap)
        case ChunkingStrategy.PARENT_CHILD:
            parent_pct = settings.chunk_overlap_pct if overlap_pct is None else overlap_pct
            child_pct = settings.child_chunk_overlap_pct if overlap_pct is None else overlap_pct
            return ParentChildChunker(
                settings.parent_chunk_size,
                settings.child_chunk_size,
                overlap_chars(settings.parent_chunk_size, parent_pct),
                overlap_chars(settings.child_chunk_size, child_pct),
            )
        case ChunkingStrategy.SEMANTIC:
            if embeddings is None:
                raise ValueError("semantic chunking needs an embedding model")
            return SemanticChunker(
                embeddings, settings.semantic_breakpoint_percentile, settings.chunk_size, chunk_overlap
            )


def build_verifier(settings: Settings) -> TokenVerifier | None:
    if not settings.auth_enabled:
        if settings.environment in ("staging", "prod"):
            raise ValueError("AUTH_ENABLED=false is not allowed in staging/prod")
        logger.warning("AUTH IS DISABLED: every request is treated as an admin (local dev only)")
        return None
    # Fail fast at startup rather than rejecting every request later.
    return build_supabase_verifier(settings.supabase_jwks_url, settings.jwt_issuer, settings.jwt_audience)


def _with_fallback(llm: BaseChatModel, fallbacks: list[BaseChatModel]) -> Runnable[LanguageModelInput, BaseMessage]:
    if not fallbacks:
        return llm
    return llm.with_fallbacks(fallbacks, exceptions_to_handle=providers.FALLBACK_EXCEPTIONS)


def build_container(settings: Settings) -> Container:
    """Wire the app against the real providers (EURI + Postgres/pgvector + Supabase Auth)."""
    engine = providers.build_engine(settings)
    providers.ensure_schema(engine)
    kv_store = providers.build_kv_store(settings)
    breakers = BreakerRegistry(settings.circuit_breaker_failure_threshold, settings.circuit_breaker_reset_seconds)
    prompt_cache = (
        PromptCache(kv_store, settings.collection_name, settings.prompt_cache_ttl_seconds)
        if settings.cache_enabled
        else None
    )
    models = {"breakers": breakers, "cache": prompt_cache}
    vector_store = providers.build_vector_store(settings, providers.build_embeddings(settings), engine)
    providers.ensure_keyword_index(engine)  # PGVector's tables exist now
    web_search = providers.build_web_search(settings)
    logger.info("research agent web search", extra={"enabled": web_search is not None})
    quick_fallbacks = providers.build_fallback_chain(
        settings,
        (settings.llm_fallback_provider, settings.llm_fallback_model),
        settings.llm_extra_fallbacks,
        **models,
    )
    agent_fallbacks = providers.build_fallback_chain(
        settings, ("euri", settings.agent_fallback_model), settings.agent_extra_fallbacks, **models
    )
    logger.info(
        "fallback chains",
        extra={
            "answer": [m.model_name for m in quick_fallbacks],  # type: ignore[attr-defined]
            "agent": [m.model_name for m in agent_fallbacks],  # type: ignore[attr-defined]
        },
    )
    container = build_container_from(
        settings,
        vector_store=vector_store,
        llm=providers.build_chat_model(settings, **models),
        readiness_checks={"database": lambda: providers.database_is_reachable(engine)},
        verifier=build_verifier(settings),
        fallback_llm=quick_fallbacks,
        agent_fallback_llm=agent_fallbacks,
        fallback_exceptions=providers.FALLBACK_EXCEPTIONS,
        registry=providers.PostgresDocumentRegistry(engine, settings.collection_name),
        golden_store=providers.PostgresGoldenStore(engine, settings.collection_name),
        judge_llm=_with_fallback(
            # temperature 0: the same answer must always get the same grade
            providers.build_chat_model(settings, settings.eval_judge_model or None, temperature=0.0, **models),
            quick_fallbacks,
        ),
        web_search=web_search,
        kv_store=kv_store,
        conversations=providers.PostgresConversationStore(engine, settings.collection_name),
        keyword_search=providers.PostgresKeywordSearch(engine, settings.collection_name),
        vector_filter=to_pgvector_filter,
    )
    container._closers.append(engine.dispose)
    if isinstance(kv_store, providers.RedisKeyValueStore):
        # Redis only speeds things up, so it's reported but doesn't fail readiness.
        logger.info("redis connected", extra={"reachable": kv_store.ping()})
    if web_search is not None:
        container._closers.append(web_search.close)
    return container
