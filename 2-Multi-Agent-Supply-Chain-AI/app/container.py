"""Composition root: builds providers and services once, at startup. The only place (with
app/rag/providers.py) that knows which concrete providers are in use."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph import GraphDeps, build_graph
from app.agents.runner import AgentService
from app.core.auth import JwksVerifier, TokenVerifier
from app.core.circuit_breaker import BreakerRegistry
from app.core.config import Settings
from app.core.errors import ProviderFailure
from app.core.kv import InMemoryKV
from app.core.ports import KeyValueStore, OcrEngine, WebSearch
from app.core.rate_limit import RateLimiter
from app.db.models import EMBEDDING_DIMENSIONS
from app.db.session import Database
from app.guardrails.pipeline import Guardrails
from app.rag.ingest import IngestService
from app.rag.knowledge import KnowledgeService
from app.rag.providers import (
    LlmFactory,
    ResilientEmbeddings,
    ResilientRedisKV,
    TavilySearch,
    TesseractOcr,
    VisionLlmOcr,
)
from app.rag.retrieval import HybridRetriever
from app.services.dashboard import DashboardService
from app.services.inventory_analytics import InventoryAnalytics
from app.services.workflow import ActivityService, ApprovalService, MemoryService

logger = logging.getLogger(__name__)


@dataclass
class Services:
    settings: Settings
    db: Database
    kv: KeyValueStore
    guardrails: Guardrails
    analytics: InventoryAnalytics
    knowledge: KnowledgeService
    ingest: IngestService
    dashboard: DashboardService
    activity: ActivityService
    approvals: ApprovalService
    memory: MemoryService
    agents: AgentService
    rate_limiter: RateLimiter
    verifier: TokenVerifier | None
    breakers: BreakerRegistry
    web: WebSearch | None = None
    closers: list[Any] = field(default_factory=list)


def _ocr(settings: Settings, factory: LlmFactory) -> OcrEngine | None:
    if settings.ocr_engine == "off":
        return None
    if settings.ocr_engine == "vision_llm":
        from app.core.config import ModelSpec

        return VisionLlmOcr(factory.chat(ModelSpec.parse(settings.ocr_vision_model), temperature=0.2))
    try:
        return TesseractOcr(settings.ocr_languages)
    except Exception:  # binary missing outside the container image
        logger.warning("Tesseract unavailable — OCR disabled")
        return None


async def _checkpointer(settings: Settings) -> tuple[Any, Any]:
    """LangGraph Postgres checkpointer on the session pooler (pipelines/prepared statements need session mode)."""
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        url = settings.migration_url().replace("postgresql+psycopg://", "postgresql://")
        pool = AsyncConnectionPool(
            url, min_size=1, max_size=3, open=False, kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row}
        )
        await pool.open(wait=True, timeout=15)
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        await saver.setup()
        return saver, pool
    except Exception:
        logger.exception("Postgres checkpointer unavailable — using in-memory checkpoints (approvals won't survive restarts)")
        return InMemorySaver(), None


async def build_services(settings: Settings) -> Services:
    if settings.embedding_dimensions != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"EMBEDDING_DIMENSIONS={settings.embedding_dimensions} doesn't match the pgvector column ({EMBEDDING_DIMENSIONS}). Create a new collection and migration."  # noqa: E501
        )

    db = Database(settings.sqlalchemy_url(), settings.database_pool_size)
    kv: KeyValueStore = ResilientRedisKV(settings.redis_url) if settings.redis_url else InMemoryKV()
    breakers = BreakerRegistry(settings.breaker_failure_threshold, settings.breaker_cooldown_seconds)
    factory = LlmFactory(settings, breakers)
    guardrails = Guardrails(
        input_mode=settings.guardrail_input_mode,
        context_mode=settings.guardrail_context_mode,
        output_mode=settings.guardrail_output_mode,
        hallucination_mode=settings.hallucination_guard_mode,
        profiles=settings.profiles,
        max_chars=settings.max_query_chars,
    )
    embedder = ResilientEmbeddings(settings)
    analytics = InventoryAnalytics(db)
    web = TavilySearch(settings.tavily_api_key.get_secret_value()) if settings.tavily_api_key.get_secret_value() else None

    def answer_models() -> list[Any]:
        return factory.models(settings.answer_chain, streaming=True)

    def agent_models() -> list[Any]:
        return factory.models(settings.agent_chain, temperature=0.2)

    try:
        answer_llm = factory.models(settings.answer_chain)
        from app.core.llm import with_fallbacks

        answer_runnable = with_fallbacks(answer_llm)
        judge = with_fallbacks(factory.models(settings.agent_chain, temperature=0.2, max_tokens=200))
    except ProviderFailure:
        logger.exception("no LLM provider configured — answers will be unavailable")
        raise

    knowledge = KnowledgeService(
        db=db,
        retriever=HybridRetriever(db, embedder),
        answer_llm=answer_runnable,
        rerank_llm=judge,
        guardrails=guardrails,
        kv=kv,
        collection=settings.kb_collection,
        top_k=settings.rag_top_k,
        rerank_candidates=settings.rag_rerank_candidates,
    )
    ingest = IngestService(db, embedder, settings.kb_collection, _ocr(settings, factory), settings.max_upload_mb * 1_000_000)
    activity = ActivityService(db)
    approvals = ApprovalService(db, on_po_created=analytics.invalidate)
    memory = MemoryService(db, kv)
    agent_model_label = str(settings.agent_chain[0].model)
    dashboard = DashboardService(
        db,
        analytics,
        agent_models={
            "supervisor": agent_model_label,
            "demand": agent_model_label,
            "inventory": agent_model_label,
            "supplier": agent_model_label,
            "logistics": agent_model_label,
            "rag": f"{settings.embedding_spec.model} · {settings.answer_chain[0].model}",
            "research": f"{agent_model_label} · Tavily" if web else agent_model_label,
        },
        collection=settings.kb_collection,
        web_enabled=web is not None,
    )
    verifier: TokenVerifier | None = None
    if settings.supabase_jwks_url:
        verifier = JwksVerifier(settings.supabase_jwks_url, settings.supabase_jwt_audience)

    services = Services(
        settings=settings,
        db=db,
        kv=kv,
        guardrails=guardrails,
        analytics=analytics,
        knowledge=knowledge,
        ingest=ingest,
        dashboard=dashboard,
        activity=activity,
        approvals=approvals,
        memory=memory,
        agents=None,  # type: ignore[arg-type]  # set below (graph needs services)
        rate_limiter=RateLimiter(
            kv, {"chat": settings.rate_limit_chat, "upload": settings.rate_limit_upload, "default": settings.rate_limit_default}
        ),
        verifier=verifier,
        breakers=breakers,
        web=web,
    )
    checkpointer, pool = await _checkpointer(settings)
    graph = build_graph(
        GraphDeps(
            services=services,
            agent_models=agent_models,
            answer_models=answer_models,
            guardrails=guardrails,
            approval_threshold=settings.approval_po_value_threshold,
            approval_ttl_hours=settings.approval_ttl_hours,
            max_tool_iterations=settings.agent_max_tool_iterations,
            node_timeout_seconds=settings.agent_node_timeout_seconds,
            record_event=activity.record,
        ),
        checkpointer=checkpointer,
    )
    services.agents = AgentService(graph, memory, approvals, settings.agent_recursion_limit)
    services.closers = [db.dispose, *([pool.close] if pool else []), *([kv.close] if isinstance(kv, ResilientRedisKV) else [])]
    return services


async def close_services(services: Services) -> None:
    for close in services.closers:
        try:
            await close()
        except Exception:
            logger.exception("error during shutdown")
