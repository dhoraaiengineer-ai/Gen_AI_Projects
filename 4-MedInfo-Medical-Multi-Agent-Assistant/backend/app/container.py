"""Composition root: the only place that wires provider implementations into the use cases."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import Engine

from app.agents.rag_graph import build_rag_graph
from app.agents.research import AgentModelSelector, ResearchRetriever, WebSearch
from app.config import ModelRef, Settings
from app.core.audit import AuditLogger
from app.core.auth import JwksKeyResolver, SigningKeyResolver, TokenVerifier
from app.core.circuit_breaker import CircuitBreaker
from app.core.kv import InProcessKV, KeyValueStore
from app.core.rate_limit import RateLimiter
from app.guardrails.engine import PolicyEngine
from app.rag.cache import AnswerCache, CachedEmbedder, CorpusVersion, SafeLLMCache
from app.rag.chunking import Chunker
from app.rag.evaluation import InMemoryEvalRunStore
from app.rag.fallback import FallbackChatModel
from app.rag.gateway import LLMGateway
from app.rag.ingest import IngestService, TrustedSources
from app.rag.interfaces import (
    ChatModel,
    DatabaseProbe,
    DocumentRegistry,
    Embedder,
    OcrEngine,
    Retriever,
    VectorIndex,
)
from app.rag.memory import (
    ConversationStore,
    FernetCipher,
    InMemoryConversationStore,
    MemoryService,
    PlainCipher,
    ShortTermMemory,
)
from app.rag.memory_store import InMemoryRegistry, InMemoryVectorIndex
from app.rag.ocr import RapidOcrEngine
from app.rag.providers import (
    OpenAICompatibleChatModel,
    OpenAICompatibleEmbedder,
    OpenAICompatibleToolModel,
    PgVectorIndex,
    RedisKV,
    SqlAlchemyProbe,
    SqlConversationStore,
    SqlEvalRunStore,
    SqlRegistry,
    SqlReviewStore,
    TavilyWebSearch,
    UnconfiguredChatModel,
    UnconfiguredEmbedder,
    make_engine,
)
from app.rag.rerank import LLMReranker, MultiQueryExpander
from app.rag.retrieval import HybridRetriever, InMemoryBM25Retriever, load_corpus
from app.rag.review import InMemoryReviewStore, ReviewService
from app.rag.service import ChatService
from app.safety.answer_checks import AnswerChecker, FaithfulnessJudge, load_lexicon
from app.safety.scope import ScopeClassifier
from app.safety.templates import SafetyContacts
from app.safety.triage import RedFlagRules, TriageService

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    chat: ChatService
    ingest: IngestService
    memory: MemoryService
    review: ReviewService
    eval_runs: Any
    retriever: Retriever
    rate_limiter: RateLimiter
    kv: KeyValueStore
    verifier: TokenVerifier | None
    db_probe: DatabaseProbe | None
    rules: RedFlagRules
    backend: str
    research_available: bool = False
    gateway: LLMGateway | None = None


def reasoning_effort_for(model: str) -> str | None:
    """Reasoning models spend max_tokens on thinking unless told to keep it low."""
    m = model.lower()
    return (
        "low"
        if ("gpt-oss" in m or m.startswith("gemini-3") or m.startswith("o3") or m.startswith("o4"))
        else None
    )


def build_chat_model(
    settings: Settings, llm_cache: Any = None, chain: list[ModelRef] | None = None
) -> ChatModel:
    """A model chain (default: the answer chain EURI -> Gemini -> Groq) with a circuit breaker per model."""
    chain = chain or settings.answer_chain()
    models: list[ChatModel] = []
    for ref in chain:
        base_url, key = settings.provider_credentials(ref.provider)
        if key is None or not key.get_secret_value():
            logger.warning("no API key; model skipped", extra={"model": ref.label})
            continue
        models.append(
            OpenAICompatibleChatModel(
                provider=ref.provider,
                model=ref.model,
                base_url=base_url,
                api_key=key,
                timeout=settings.llm_timeout_seconds,
                max_tokens=settings.llm_max_tokens,
                reasoning_effort=reasoning_effort_for(ref.model),
                cache=llm_cache,
            )
        )
    if not models:
        logger.warning("no model provider configured; chat will return 503")
        return UnconfiguredChatModel(chain[0].label)
    breakers = {
        m.name: CircuitBreaker(m.name, settings.circuit_failure_threshold, settings.circuit_reset_seconds)
        for m in models
    }
    return FallbackChatModel(
        models,
        breakers=breakers,
        retry_attempts=settings.model_retry_attempts,
        retry_base_delay=settings.model_retry_base_delay,
    )


def build_agent_selector(settings: Settings) -> AgentModelSelector | None:
    models = []
    for ref in settings.agent_chain():
        if ref.provider == "gemini":
            # Gemini's OpenAI-compatible API drops tool-call thought signatures: never an agent model.
            logger.warning("gemini excluded from agent chain", extra={"model": ref.label})
            continue
        base_url, key = settings.provider_credentials(ref.provider)
        if key is None or not key.get_secret_value():
            continue
        models.append(
            OpenAICompatibleToolModel(
                provider=ref.provider,
                model=ref.model,
                base_url=base_url,
                api_key=key,
                timeout=settings.llm_timeout_seconds,
                reasoning_effort=reasoning_effort_for(ref.model),
            )
        )
    return AgentModelSelector(models) if models else None


def build_embedder(settings: Settings) -> Embedder:
    base_url, key = settings.provider_credentials(settings.embedding_provider)
    name = f"{settings.embedding_provider}:{settings.embedding_model}"
    if key is None or not key.get_secret_value():
        logger.warning(
            "no API key for embeddings; ingestion and vector search return 503", extra={"model": name}
        )
        return UnconfiguredEmbedder(name, settings.embedding_dimensions)
    return OpenAICompatibleEmbedder(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        base_url=base_url,
        api_key=key,
        dimensions=settings.embedding_dimensions,
        timeout=settings.llm_timeout_seconds,
    )


def build_container(
    settings: Settings,
    *,
    model: ChatModel | None = None,
    classifier: ChatModel | None = None,
    retriever: Retriever | None = None,
    embedder: Embedder | None = None,
    index: VectorIndex | None = None,
    registry: DocumentRegistry | None = None,
    ocr: OcrEngine | None = None,
    key_resolver: SigningKeyResolver | None = None,
    db_probe: DatabaseProbe | None = None,
    engine: Engine | None = None,
    kv: KeyValueStore | None = None,
    conversations: ConversationStore | None = None,
    web_search: WebSearch | None = None,
    agent_selector: AgentModelSelector | None = None,
) -> Container:
    """Production wiring by default; tests pass fakes for every external dependency."""
    if kv is None:
        kv = RedisKV(settings.redis_url) if settings.redis_url is not None else InProcessKV()
    llm_cache = SafeLLMCache(kv, settings.llm_cache_ttl_seconds) if settings.llm_cache_ttl_seconds else None
    model = model or build_chat_model(settings, llm_cache)
    if classifier is None:
        fast = settings.fast_chain()
        classifier = build_chat_model(settings, llm_cache, fast) if fast else model
    # LLM gateway: routing (fast/quality) + per-task token limits for every chat-model call.
    gateway = LLMGateway({"quality": model, "fast": classifier})
    backend = settings.resolved_backend()
    trusted_col, user_col = settings.collection_names()

    if engine is None and settings.database_url is not None and backend == "pgvector":
        engine = make_engine(settings.database_url)
    if db_probe is None and engine is not None:
        db_probe = SqlAlchemyProbe(engine)

    embedder = embedder or build_embedder(settings)
    query_embedder: Embedder = (
        CachedEmbedder(embedder, kv, settings.embedding_cache_ttl_seconds)
        if settings.embedding_cache_ttl_seconds
        else embedder
    )
    if index is None:
        index = (
            PgVectorIndex(engine, settings.embedding_dimensions)
            if engine is not None
            else InMemoryVectorIndex()
        )
    if registry is None:
        registry = SqlRegistry(engine) if engine is not None else InMemoryRegistry()

    if retriever is None:
        if backend == "static":
            retriever = InMemoryBM25Retriever(load_corpus(settings.corpus_path), settings.retrieval_min_score)
        else:
            retriever = HybridRetriever(
                index=index,
                embedder=query_embedder,
                registry=registry,
                trusted_collection=trusted_col,
                user_collection=user_col,
                min_similarity=settings.retrieval_min_similarity,
                reranker=LLMReranker(gateway.for_task("rerank")) if settings.rerank_enabled else None,
                candidates=settings.retrieval_candidates,
            )

    if key_resolver is None and settings.supabase_jwks_url:
        key_resolver = JwksKeyResolver(settings.supabase_jwks_url, settings.jwks_cache_seconds)
    issuer = f"{settings.supabase_url}/auth/v1" if settings.supabase_url else None
    verifier = (
        TokenVerifier(key_resolver, settings.supabase_jwt_audience, issuer, settings.jwt_clock_skew_seconds)
        if key_resolver
        else None
    )

    audit = AuditLogger(settings.audit_log_enabled)
    guard = PolicyEngine.load()
    versions = CorpusVersion(kv)
    cache = (
        AnswerCache(kv, versions, settings.answer_cache_ttl_seconds)
        if settings.answer_cache_ttl_seconds
        else None
    )

    if settings.conversation_encryption_key is not None:
        cipher: Any = FernetCipher(settings.conversation_encryption_key.get_secret_value())
    else:
        logger.warning(
            "CONVERSATION_ENCRYPTION_KEY unset: stored messages are not app-encrypted (local only)"
        )
        cipher = PlainCipher()
    if conversations is None:
        conversations = (
            SqlConversationStore(engine, cipher) if engine is not None else InMemoryConversationStore()
        )
    memory = MemoryService(
        conversations, ShortTermMemory(kv, settings.short_term_turns), settings.conversation_retention_days
    )

    research_graph = None
    if settings.research_enabled:
        if web_search is None and settings.tavily_api_key is not None:
            web_search = TavilyWebSearch(settings.tavily_api_key, settings.web_allowed_domains)
        agent_selector = agent_selector or build_agent_selector(settings)
        if agent_selector is not None:
            research_graph = build_rag_graph(
                ResearchRetriever(corpus=retriever, web=web_search, selector=agent_selector, guard=guard),
                gateway.for_task("answer"),
                settings.llm_temperature,
            )
    eval_runs: Any = SqlEvalRunStore(engine) if engine is not None else InMemoryEvalRunStore()
    review_store: Any = SqlReviewStore(engine) if engine is not None else InMemoryReviewStore()
    review = ReviewService(review_store, settings.review_sample_rate)
    rate_limiter = RateLimiter(
        kv,
        {
            "chat": (settings.rate_limit_chat_per_minute, 60),
            "research": (settings.rate_limit_research_per_hour, 3600),
            "upload": (settings.rate_limit_upload_per_hour, 3600),
        },
    )
    rules = RedFlagRules.load()
    lexicon = load_lexicon()
    contacts = SafetyContacts(
        emergency_number=settings.emergency_number,
        emergency_service_name=settings.emergency_service_name,
        crisis_line_name=settings.crisis_line_name,
        crisis_line_number=settings.crisis_line_number,
        poison_line_number=settings.poison_line_number,
    )
    chat = ChatService(
        triage=TriageService(rules, gateway.for_task("triage")),
        scope=ScopeClassifier(gateway.for_task("scope")),
        rag_graph=build_rag_graph(
            retriever,
            gateway.for_task("answer"),
            settings.llm_temperature,
            expander=MultiQueryExpander(gateway.for_task("rewrite")),
        ),
        checker=AnswerChecker(lexicon, FaithfulnessJudge(gateway.for_task("judge"))),
        contacts=contacts,
        lexicon=lexicon,
        audit=audit,
        top_k=settings.retrieval_top_k,
        stale_years=settings.stale_source_years,
        max_question_chars=settings.max_question_chars,
        guard=guard,
        cache=cache,
        memory=memory,
        research_graph=research_graph,
        review=review,
    )
    ingest = IngestService(
        registry=registry,
        index=index,
        embedder=embedder,
        chunker=Chunker(
            settings.chunk_strategy,
            chunk_size=settings.chunk_size,
            parent_size=settings.parent_chunk_size,
            child_size=settings.child_chunk_size,
            embedder=embedder if settings.chunk_strategy == "semantic" else None,
        ),
        ocr=ocr or RapidOcrEngine(),
        trusted_sources=TrustedSources.load(),
        trusted_collection=trusted_col,
        user_collection=user_col,
        max_bytes=settings.max_upload_mb * 1024 * 1024,
        audit=audit,
        guard=guard,
        on_change=lambda trusted, owner: versions.bump(trusted=trusted, user_id=owner),
    )
    logger.info("container built", extra={"backend": backend, "trusted_collection": trusted_col})
    return Container(
        settings=settings,
        chat=chat,
        ingest=ingest,
        memory=memory,
        review=review,
        eval_runs=eval_runs,
        retriever=retriever,
        rate_limiter=rate_limiter,
        kv=kv,
        verifier=verifier,
        db_probe=db_probe,
        rules=rules,
        backend=backend,
        research_available=research_graph is not None,
        gateway=gateway,
    )
