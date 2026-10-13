"""Composition root.

This module and the ``src/providers`` package are the only places allowed to import provider
SDKs (ADR-022). Everything else depends on ports / LangChain interfaces and receives concrete
adapters from here. Enforced by ``tests/architecture``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from src.a2a.client import A2AClient, A2ARecorder, InProcessTransport, NullA2ARecorder
from src.a2a.server import A2AServer
from src.agents.base import AgentDeps
from src.agents.registry import build_agents, publish
from src.config.settings import BACKEND_ROOT, REPO_ROOT, Settings
from src.core.decisions import DecisionService
from src.core.domain import Role
from src.core.errors import ProviderUnavailable
from src.core.kv import FallbackKV, MemoryKV
from src.core.ports import KeyValueStore, NewsProvider
from src.core.rate_limit import Limit, RateLimiter
from src.core.tokens import trim_to_tokens
from src.data.ingestion.synthetic_news import SyntheticNewsProvider
from src.data.processing.analytics import PortfolioAnalytics
from src.data.repositories.activity import ActivityRepository
from src.data.repositories.approvals import ApprovalRepository
from src.data.repositories.audit import AuditRepository
from src.data.repositories.conversations import ConversationRepository
from src.data.repositories.knowledge import KnowledgeRepository
from src.data.repositories.market import MarketRepository, all_instruments
from src.data.repositories.ml import MlRepository
from src.data.repositories.payments import PaymentsRepository
from src.data.repositories.portfolio import PortfolioRepository
from src.data.repositories.telemetry import DbA2ARecorder, DbToolCallRecorder, TelemetryWriter
from src.db.checkpointer import Checkpointer
from src.db.session import Database
from src.mcp.client import McpGateway, http_servers, in_process_servers
from src.ml.registry import ModelStore, tracking_uri_for
from src.orchestration.graph import GraphDeps, build_graph
from src.orchestration.memory import ConversationMemory
from src.orchestration.routing import (
    Classification,
    Intent,
    PortfolioRef,
    Router,
    classifier_prompt,
)
from src.orchestration.runner import SupervisorRunner
from src.orchestration.state import FinanceState
from src.providers.decisions import JevDecisionModel
from src.providers.embeddings import build_embeddings
from src.providers.kv import RedisKV
from src.providers.llm import BREAKERS, LlmFactory
from src.providers.ocr import TesseractOcr
from src.providers.reranker import CrossEncoderReranker
from src.providers.search import TavilyNewsProvider
from src.providers.tokenizer import token_counter
from src.rag.answer import GroundedAnswerer
from src.rag.ingestion import IngestionService
from src.rag.reranking import LlmReranker, RerankerChain
from src.rag.retrieval import HybridRetriever
from src.rag.service import AnswerCache, KnowledgeService
from src.rag.types import Reranker
from src.security.audit import AuditService
from src.security.auth import JwtVerifier
from src.tools.base import NullRecorder, ToolCallRecorder, ToolContext
from src.tools.catalog import build_registry
from src.tools.deps import ToolDeps
from src.tools.registry import ToolRegistry


class LlmIntent(BaseModel):
    """Structured-output schema for LLM intent classification (fallback after Jev)."""

    intent: Intent


logger = logging.getLogger(__name__)

HealthCheck = Callable[[], Awaitable[None]]


@dataclass
class Container:
    """Process-wide dependencies. Built once at startup, closed at shutdown."""

    settings: Settings
    db: Database | None = None
    recorder: ToolCallRecorder = field(default_factory=NullRecorder)
    a2a_recorder: A2ARecorder = field(default_factory=NullA2ARecorder)
    health_checks: dict[str, HealthCheck] = field(default_factory=dict)
    telemetry: TelemetryWriter | None = None
    serves_tools: bool = False  # True in MCP server processes (src.mcp.run)
    _gateway: McpGateway | None = None
    _runner: SupervisorRunner | None = None
    _checkpointer: Checkpointer | None = None
    _a2a_server: A2AServer | None = None
    _router: Router | None = None

    @classmethod
    def build(cls, settings: Settings) -> Container:
        container = cls(settings=settings)
        if settings.database_configured:
            container.db = Database.from_url(settings.app_database_url)
            container.health_checks["database"] = container.db.ping
            container.telemetry = TelemetryWriter(container.db)
            container.recorder = DbToolCallRecorder(container.telemetry, container.audit)
            container.a2a_recorder = DbA2ARecorder(container.telemetry)
        else:
            logger.warning("database not configured; readiness will report it")
        return container

    # ------------------------------------------------------------------ providers
    @cached_property
    def llm(self) -> LlmFactory:
        return LlmFactory(self.settings)

    @cached_property
    def embeddings(self) -> Embeddings:
        return build_embeddings(self.settings)

    @cached_property
    def jwt_verifier(self) -> JwtVerifier | None:
        s = self.settings
        if not (s.supabase_jwks_url and s.supabase_url):
            return None
        return JwtVerifier(s.supabase_jwks_url, issuer=f"{s.supabase_url.rstrip('/')}/auth/v1")

    @cached_property
    def decisions(self) -> DecisionService:
        """TypeSafe Jev when TYPESAFE_API_KEY is set; otherwise callers use their fallbacks."""
        s = self.settings
        if s.typesafe_api_key is None:
            return DecisionService(None)
        return DecisionService(
            JevDecisionModel(
                s.typesafe_api_key,
                base_url=s.typesafe_base_url,
                model=s.jev_model,
                timeout=s.decision_timeout_seconds,
            )
        )

    @cached_property
    def web_news(self) -> NewsProvider:
        """Tavily when configured and not in demo mode; synthetic otherwise."""
        key = self.settings.tavily_api_key
        if key is not None and not self.settings.demo_mode:
            return TavilyNewsProvider(key)
        return SyntheticNewsProvider()

    # ------------------------------------------------------------------ data + tools
    def _require_db(self) -> Database:
        if self.db is None:
            raise ProviderUnavailable("database not configured")
        return self.db

    @property
    def database(self) -> Database:
        """The database, or ProviderUnavailable when it is not configured."""
        return self._require_db()

    @cached_property
    def market_repo(self) -> MarketRepository:
        return MarketRepository(self._require_db())

    @cached_property
    def portfolio_repo(self) -> PortfolioRepository:
        return PortfolioRepository(self._require_db())

    @cached_property
    def analytics(self) -> PortfolioAnalytics:
        return PortfolioAnalytics(self.market_repo, self.portfolio_repo)

    @cached_property
    def models(self) -> ModelStore:
        """Pinned model versions from the MLflow registry; exported bundles as the fallback."""
        s = self.settings
        resolved = tracking_uri_for(s.mlflow_url, BACKEND_ROOT, create=False)
        sqlite_file = resolved.removeprefix("sqlite:///") if resolved.startswith("sqlite:") else ""
        # Never trained here → don't create an empty store; use the exported bundles.
        tracking = None if sqlite_file and not Path(sqlite_file).exists() else resolved
        return ModelStore(
            REPO_ROOT / "models",
            tracking_uri=tracking,
            versions={
                "fraud": s.ml_fraud_model_version,
                "risk": s.ml_risk_model_version,
                "prediction": s.ml_forecast_model_version,
            },
        )

    @cached_property
    def audit(self) -> AuditService:
        return AuditService(AuditRepository(self.db) if self.db is not None else None)

    @cached_property
    def kv(self) -> KeyValueStore:
        """Redis with an in-process fallback (or in-process only when Redis is disabled)."""
        if not self.settings.redis_enabled:
            return MemoryKV()
        return FallbackKV(RedisKV(self.settings.redis_url))

    @cached_property
    def rate_limiter(self) -> RateLimiter:
        s = self.settings
        return RateLimiter(
            self.kv,
            {
                "chat": Limit(s.rate_limit_chat, 60),
                "analyze": Limit(s.rate_limit_analyze, 60),
                "read": Limit(s.rate_limit_read, 60),
                "upload": Limit(s.rate_limit_upload, 60),
            },
        )

    @cached_property
    def conversations(self) -> ConversationRepository:
        return ConversationRepository(self._require_db())

    @cached_property
    def memory(self) -> ConversationMemory:
        return ConversationMemory(self.kv, self.conversations if self.db is not None else None)

    @cached_property
    def activity(self) -> ActivityRepository:
        return ActivityRepository(self._require_db())

    @cached_property
    def approvals(self) -> ApprovalRepository:
        return ApprovalRepository(self._require_db(), ttl_hours=self.settings.approval_ttl_hours)

    async def checkpointer(self) -> Any:
        """Postgres saver (session pooler) so approval pauses survive restarts."""
        if self._checkpointer is None:
            checkpointer = Checkpointer(self.settings.session_database_url)
            await checkpointer.start()
            self._checkpointer = checkpointer
        return self._checkpointer.saver

    @cached_property
    def cross_encoder(self) -> CrossEncoderReranker | None:
        s = self.settings
        return CrossEncoderReranker(s.reranker_model) if s.reranker == "cross_encoder" else None

    @cached_property
    def knowledge(self) -> KnowledgeService:
        """Hybrid retrieval, cross-encoder (fallbacks: LLM judge, fused order), grounded answers."""
        s = self.settings
        repo = KnowledgeRepository(self._require_db())
        chain: list[Reranker] = []
        if self.cross_encoder is not None:
            chain.append(self.cross_encoder)
        if s.reranker in {"cross_encoder", "llm"}:
            chain.append(LlmReranker(lambda: self.llm.answer_model(max_tokens=80)))
        retriever = HybridRetriever(
            repo, self.embeddings, RerankerChain(chain), rerank_top_n=s.reranker_top_n
        )
        answerer = GroundedAnswerer(
            lambda: self.llm.answer_model(max_tokens=s.llm_narrative_max_output_tokens),
            max_input_tokens=s.llm_narrative_max_input_tokens,
            min_relevance=-6.0 if s.reranker == "cross_encoder" else None,
        )
        ingestion = IngestionService(
            repo,
            self.embeddings,
            TesseractOcr(),
            embedding_model=f"{s.embedding_provider}:{s.embedding_model}",
            dimensions=s.embedding_dimensions,
            count=token_counter(),
        )
        return KnowledgeService(repo, retriever, answerer, ingestion, AnswerCache(self.kv))

    @cached_property
    def tools(self) -> ToolRegistry:
        deps = ToolDeps(
            db=self._require_db(),
            market=self.market_repo,
            portfolios=self.portfolio_repo,
            payments=PaymentsRepository(self._require_db()),
            analytics=self.analytics,
            market_news=SyntheticNewsProvider(),
            web_news=self.web_news,
            models=self.models,
            ml_repo=MlRepository(self._require_db()),
            kb=self.knowledge,
        )
        return build_registry(deps, self.recorder)

    async def mcp(self) -> McpGateway:
        """Connected MCP gateway over all six servers (in-process, or HTTP when
        ``MCP_TRANSPORT=http`` — the servers then run as separate processes, ADR-036)."""
        if self._gateway is None:
            s = self.settings
            if s.mcp_transport == "http":
                token = s.mcp_service_token
                if token is None:
                    raise RuntimeError("MCP_TRANSPORT=http requires MCP_SERVICE_TOKEN")
                gateway = McpGateway(
                    self.tools,
                    http_servers(s.mcp_url_template),
                    service_token=token.get_secret_value(),
                )
            else:
                gateway = McpGateway(self.tools, in_process_servers(self.tools))
            await gateway.start()
            self._gateway = gateway
        return self._gateway

    def tool_schemas(self, names: Sequence[str]) -> list[dict[str, Any]]:
        """OpenAI-style function schemas for the named registry tools (LLM tool binding)."""
        schemas = []
        for name in names:
            spec = self.tools.get(name)
            if spec is None:
                continue
            parameters = spec.input_model.model_json_schema()
            parameters.pop("title", None)
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": parameters,
                    },
                }
            )
        return schemas

    async def router(self) -> Router:
        """Intent routing: Jev (if configured) → LLM structured output (if enabled) → keywords."""
        if self._router is not None:
            return self._router
        s = self.settings

        async def llm_classify(question: str) -> Classification | None:
            model = self.llm.structured_model(
                LlmIntent, chain="answer", max_tokens=s.llm_classify_max_output_tokens
            )
            question = trim_to_tokens(question, s.llm_classify_max_input_tokens)
            result = await model.ainvoke([("system", classifier_prompt()), ("human", question)])
            return Classification(
                intent=result.intent, standalone_question=question, confidence=0.7, method="llm"
            )

        answer_ready = any(self.llm.is_configured(m) for m in s.answer_chain)
        tickers = frozenset(i.ticker for i in await all_instruments(self._require_db()))
        self._router = Router(
            self.decisions,
            llm_classify if answer_ready and s.llm_routing else None,
            known_tickers=tickers,
        )

        return self._router

    async def supervisor(self) -> SupervisorRunner:
        """The supervisor graph with agents on A2A, tools over MCP, Jev/LLM routing."""
        if self._runner is None:
            self._runner = await self.build_runner(persist_approvals=True)
        return self._runner

    async def build_runner(self, *, persist_approvals: bool) -> SupervisorRunner:
        """A supervisor runner. ``persist_approvals=False`` (evaluation) never writes approvals
        and needs no checkpointer."""
        s = self.settings
        gateway = await self.mcp()
        llm_ready = any(self.llm.is_configured(m) for m in s.agent_chain)
        model_factory = (
            (
                lambda schemas: self.llm.agent_model(
                    schemas, max_tokens=s.llm_agent_max_output_tokens
                )
            )
            if s.agent_llm_tool_loop and llm_ready and s.agent_max_tool_iterations > 0
            else None
        )
        deps = AgentDeps(
            tools=gateway,
            tool_schemas=self.tool_schemas,
            model_factory=model_factory,
            max_tool_iterations=s.agent_max_tool_iterations,
            max_input_tokens=s.llm_agent_max_input_tokens,
            tool_result_max_tokens=s.llm_tool_result_max_tokens,
        )
        transport = publish(
            build_agents(deps, approval_threshold=s.approval_value_threshold), InProcessTransport()
        )
        a2a = A2AClient(transport, self.a2a_recorder)
        self._a2a_server = A2AServer(transport, self.a2a_recorder)

        router = await self.router()

        async def list_portfolios(state: FinanceState) -> list[PortfolioRef]:
            ctx = ToolContext(
                role=Role(state["role"]),
                tenant_id=state["tenant_id"],
                request_id=state["request_id"],
                trace_id=state["trace_id"],
            )
            result = await gateway.call("list_portfolios", {}, ctx)
            if not result.ok or not isinstance(result.data, dict):
                return []
            return [PortfolioRef(p["portfolioId"], p["name"]) for p in result.data["portfolios"]]

        answer_ready = any(self.llm.is_configured(m) for m in s.answer_chain)
        narrative = (
            (lambda: self.llm.answer_model(max_tokens=s.llm_narrative_max_output_tokens))
            if s.llm_narrative and answer_ready
            else None
        )
        graph = build_graph(
            GraphDeps(
                a2a=a2a,
                router=router,
                list_portfolios=list_portfolios,
                narrative_model=narrative,
                narrative_max_input_tokens=s.llm_narrative_max_input_tokens,
                narrative_min_output_tokens=s.llm_narrative_min_output_tokens,
                max_input_chars=s.max_input_chars,
                audit=self.audit,
                approvals=self.approvals if persist_approvals else None,
                checkpointer=await self.checkpointer() if persist_approvals else None,
            )
        )
        return SupervisorRunner(
            graph,
            token_budget=s.llm_request_token_budget,
            approvals=self.approvals if persist_approvals else None,
        )

    async def a2a_server(self) -> A2AServer:
        """HTTP A2A server over the same agents and transport the supervisor uses."""
        if self._a2a_server is None:
            await self.supervisor()
        assert self._a2a_server is not None  # noqa: S101 - set by supervisor()
        return self._a2a_server

    async def warm_up(self) -> None:
        """Load ML models in the background at startup so the first request does not pay the
        registry load (MLflow can take ~20 s cold) and the cross-encoder (first download can exceed
        the 30 s knowledge-tool timeout). Failures are logged; everything still loads lazily.
        With ``MCP_TRANSPORT=http`` the tools run in the MCP servers (which warm themselves), so
        the API skips this and keeps ~1 GB of models out of its memory."""
        if self.settings.mcp_transport == "http" and not self.serves_tools:
            logger.info("warm-up skipped: tools run in the MCP servers")
            return
        for kind in ("fraud", "risk", "prediction"):
            try:
                await self.models.get(kind)
            except Exception:
                logger.warning("model warm-up failed", extra={"model": kind}, exc_info=True)
        if self.cross_encoder is not None:
            try:
                await self.cross_encoder.warm()
            except Exception:
                logger.warning("cross-encoder warm-up failed", exc_info=True)

    def circuit_states(self) -> dict[str, str]:
        return BREAKERS.snapshot()

    async def aclose(self) -> None:
        if self._gateway is not None:
            await self._gateway.close()
        if self._checkpointer is not None:
            await self._checkpointer.aclose()
        if self.telemetry is not None:
            await self.telemetry.aclose()
        if self.db is not None:
            await self.db.dispose()
