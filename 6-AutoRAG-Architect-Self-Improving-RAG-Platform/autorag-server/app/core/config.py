"""Centralized application configuration for AutoRAG Architect."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, NamedTuple

import yaml  # type: ignore[import-untyped]
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─────────────────────────────────────────────────────────────
    # Pydantic Settings Configuration
    # ─────────────────────────────────────────────────────────────

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─────────────────────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────────────────────

    app_name: str = "AutoRAG Architect"
    app_version: str = "3.0.0"

    environment: Literal[
        "local",
        "development",
        "testing",
        "staging",
        "production",
    ] = "local"

    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    # ─────────────────────────────────────────────────────────────
    # CORS
    # ─────────────────────────────────────────────────────────────

    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # ─────────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────────

    database_url: str = Field(
        default=""
    )  # set DATABASE_URL in .env (docker-compose overrides)

    # 17-Jul-2026: lowered from 20/10 -- the shared dev Supabase project uses
    # a direct (non-pooled) connection with a low connection cap, and every
    # local `uv run uvicorn --reload` restart opens a fresh pool without
    # necessarily releasing the previous one cleanly (force-kills, crashes).
    # A handful of restarts across a dev session was enough to exhaust the
    # project's connection limit (asyncpg.exceptions.TooManyConnectionsError)
    # for every developer sharing it, not just the offending process.
    # staging/production should override via DB_POOL_SIZE / DB_MAX_OVERFLOW
    # env vars if they need larger pools (Rule 45 -- explicit per-environment
    # config, not code-branched defaults).
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_timeout_seconds: int = 30  # fail fast instead of hanging on a full pool
    db_pool_recycle_seconds: int = 1800  # recycle before Supabase's own idle timeout

    # ─────────────────────────────────────────────────────────────
    # Supabase
    # ─────────────────────────────────────────────────────────────

    supabase_url: str = ""
    supabase_key: str = ""  # anon key — limited RLS-scoped access
    supabase_service_role_key: str = ""  # BACKEND ONLY — never log or expose
    supabase_db_url: str = ""  # direct DB connection (asyncpg)
    supabase_jwt_secret: str = ""  # for verifying Supabase-issued JWTs

    # ─────────────────────────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────────────────────────

    redis_url: str = "redis://localhost:6379"
    llm_cache_ttl_seconds: int = Field(3600, validation_alias="LLM_CACHE_TTL_SECONDS")
    # LLM response cache TTL: 3600s (1 hour) matches typical prompt/answer stability.
    # Evaluator adversarial set reuses the same 10 questions every run -- cache saves
    # ~10 full LLM calls per pipeline evaluation after the first run.

    # ─────────────────────────────────────────────────────────────
    # Authentication / Security
    # ─────────────────────────────────────────────────────────────

    jwt_secret_key: str = Field(
        "autorag-local-dev-secret-key-minimum-32-chars"
    )  # local dev default — override JWT_SECRET_KEY in .env for dev+
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    pii_masking_enabled: bool = True

    # ─────────────────────────────────────────────────────────────
    # AI Providers
    # ─────────────────────────────────────────────────────────────

    # EURI-issued keys by default (legacy meaning, preserved for backward compat --
    # every currently-deployed real .env stores an EURI-issued key here). When the
    # matching *_base_url override below is set, this same field is reinterpreted
    # as the real provider key instead -- disambiguated entirely by whether the
    # override is present, never guessed.
    gemini_api_key: str = ""
    kimi_api_key: str = ""
    cohere_api_key: str = ""

    # ─────────────────────────────────────────────────────────────
    # Reranking -- Cohere Rerank v3 (primary) -> BGE-Reranker (fallback)
    # ─────────────────────────────────────────────────────────────

    cohere_rerank_model: str = "rerank-english-v3.0"
    bge_reranker_model: str = "BAAI/bge-reranker-base"

    # ─────────────────────────────────────────────────────────────
    # LLM endpoint -- EURI OpenAI-compatible gateway (default transport)
    # ─────────────────────────────────────────────────────────────

    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    # CORRECTED 17-Jul-2026: this default previously had a trailing /v1, which
    # returns 404 for /embeddings on EURI's real gateway (verified via direct
    # probe). All working .env files use the value without /v1 -- this default
    # only matters if EURI_BASE_URL is unset, but was wrong when it did apply.
    # Renamed from llm_base_url -- 17-Jul-2026, direct-provider-bypass feature --
    # see resolve_gemini()/resolve_kimi() below.
    euri_api_key: str = ""  # preferred EURI key; gemini_api_key/kimi_api_key are
    # used as a fallback so pre-existing .env files (which store the EURI key
    # under GEMINI_API_KEY/KIMI_API_KEY) keep working without any changes.
    llm_primary_model: str = "gemini-flash-3.5"  # EURI alias -- only used via EURI
    llm_fallback_model: str = "kimi-k2.6"        # EURI alias -- only used via EURI
    llm_last_resort_model: str = "gemini-3.5"    # EURI alias -- only used via EURI
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 2048

    # ─────────────────────────────────────────────────────────────
    # Batch evaluation rate-limit pacing (V4 MVP, 26-Jul-2026) -- scoped to
    # BatchEvalService's sequential per-question dispatch loop only, never
    # the shared LLMService.call() used by every agent/single-query path.
    # Free-tier judge providers (e.g. Groq llama-3.1-8b-instant, 6,000 TPM)
    # 429 under back-to-back RAGAS judge calls without pacing -- these
    # defaults mirror a proven reference implementation's constants.
    # Version 5: replace fixed values with provider-aware adaptive pacing
    # (see VERSION_5_ROADMAP.md).
    # ─────────────────────────────────────────────────────────────
    batch_eval_sample_cooldown_seconds: float = 25.0
    batch_eval_retry_wait_seconds: float = 65.0
    batch_eval_max_retries: int = 1
    batch_eval_max_context_chunks: int = 2
    batch_eval_max_context_chars: int = 400

    # ─────────────────────────────────────────────────────────────
    # Direct provider bypass (opt-in, 17-Jul-2026) -- set *_base_url to call a
    # provider's real API directly instead of routing through EURI. Empty (the
    # default) preserves existing EURI behavior exactly. No model ID is ever
    # inferred or hardcoded -- *_chat_model / *_embedding_model must be supplied
    # explicitly (see _validate_provider_overrides below, which fails fast at
    # startup if a *_base_url is set without its required model fields).
    # ─────────────────────────────────────────────────────────────

    gemini_base_url: str = ""       # e.g. https://generativelanguage.googleapis.com/v1beta/openai
    gemini_chat_model: str = ""     # real Gemini chat model ID -- required if gemini_base_url is set
    gemini_embedding_model: str = ""  # real Gemini embedding model ID -- required if gemini_base_url is set

    kimi_base_url: str = ""         # real Moonshot/KiMi OpenAI-compatible endpoint
    kimi_chat_model: str = ""       # required if kimi_base_url is set

    groq_base_url: str = ""         # e.g. https://api.groq.com/openai/v1
    groq_api_key: str = ""
    groq_chat_model: str = ""       # required if groq_base_url is set -- Groq has
    # no EURI equivalent, so unlike Gemini/KiMi there is no fallback transport.

    # Ordered chat failover chain -- comma-separated provider family names,
    # each resolved via resolve_gemini()/resolve_kimi()/resolve_groq() below.
    # Default preserves the exact pre-17-Jul-2026 chain (EURI, all three slots).
    # "gemini" may appear more than once (matches its historical two-slot EURI
    # role: primary alias, then last-resort alias) -- see
    # resolve_chat_provider_chain()'s occurrence-tracking for why.
    chat_provider_order: str = "gemini,kimi,gemini"

    # ─────────────────────────────────────────────────────────────
    # Embeddings
    # ─────────────────────────────────────────────────────────────

    embedding_model: str = "gemini-embedding-2"  # EURI alias -- only used via EURI
    embedding_dim: int = 768  # FROZEN contract (docs/DB_SCHEMA.md) — never change
    embedding_batch_size: int = 100  # chunks per Gemini embed_content call (D-12)

    # ─────────────────────────────────────────────────────────────
    # Guardrails / Evaluation
    # ─────────────────────────────────────────────────────────────

    unified_score_gate: float = 0.85
    faithfulness_block_threshold: float = 0.5
    injection_confidence_block: float = 0.9

    retrieval_similarity_floor: float = 0.3
    retrieval_outlier_threshold: float = 0.4

    # ─────────────────────────────────────────────────────────────
    # Observability — Prometheus + Grafana + CloudWatch (approved stack)
    # ─────────────────────────────────────────────────────────────

    # Note: Sentry is NOT in the approved observability stack for this project.
    # Use Prometheus metrics + Grafana dashboards + CloudWatch logs instead.

    # ─────────────────────────────────────────────────────────────
    # Notifications — SendGrid (email) + Twilio / Wati (WhatsApp)
    # Required for HITL approval alerts in dev+
    # ─────────────────────────────────────────────────────────────

    sendgrid_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # ─────────────────────────────────────────────────────────────
    # Experiment Tracking — MLflow
    # ─────────────────────────────────────────────────────────────

    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "autorag-experiments"

    # ─────────────────────────────────────────────────────────────
    # Logging & Metrics
    # ─────────────────────────────────────────────────────────────

    prometheus_enabled: bool = True
    prometheus_metrics_path: str = "/metrics"

    log_format: Literal["text", "json"] = "text"
    # text = human-readable (local/dev); json = structured (staging/production)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    # ─────────────────────────────────────────────────────────────
    # AWS — ECS Fargate + ALB Blue/Green deployment (Deployer agent)
    # Loaded from AWS Secrets Manager in staging/production; .env in dev/local
    # ─────────────────────────────────────────────────────────────

    aws_region: str = Field("ap-south-1", validation_alias="aws_region")
    ecs_cluster_name: str = Field("", validation_alias="ecs_cluster_name")
    ecs_service_name: str = Field("", validation_alias="ecs_service_name")
    ecr_repository_url: str = Field("", validation_alias="ecr_repository_url")
    alb_listener_arn: str = Field("", validation_alias="alb_listener_arn")
    alb_blue_target_group_arn: str = Field("", validation_alias="alb_blue_target_group_arn")
    alb_green_target_group_arn: str = Field("", validation_alias="alb_green_target_group_arn")

    # Canary window thresholds — Rule 90 (non-bypassable)
    canary_window_minutes: int = Field(10, validation_alias="canary_window_minutes")
    canary_error_rate_threshold: float = Field(0.01, validation_alias="canary_error_rate_threshold")
    canary_latency_p95_ms_threshold: int = Field(3000, validation_alias="canary_latency_p95_ms_threshold")
    canary_score_drop_threshold: float = Field(0.10, validation_alias="canary_score_drop_threshold")

    # ─────────────────────────────────────────────────────────────
    # Local Docker — only used by docker-compose (local env)
    # ─────────────────────────────────────────────────────────────

    grafana_password: str = (
        "admin"  # local Docker only — override via env in staging/prod
    )
    postgres_user: str = (
        "postgres"  # local Docker only — override via env in staging/prod
    )
    postgres_password: str = (
        "postgres"  # local Docker only — override via env in staging/prod
    )
    postgres_db: str = "autorag"  # local Docker only — override via env in staging/prod

    # ─────────────────────────────────────────────────────────────
    # Cost Budgets — Rule 86 (loaded per environment via env vars)
    # Default = production-safe strict values
    # ─────────────────────────────────────────────────────────────

    max_query_cost_usd: float = Field(0.01, validation_alias="max_query_cost_usd")
    max_eval_cost_usd: float = Field(0.60, validation_alias="max_eval_cost_usd")
    max_pipeline_build_usd: float = Field(
        2.00, validation_alias="max_pipeline_build_usd"
    )
    max_monthly_cost_increase_pct: float = Field(
        0.20, validation_alias="max_monthly_cost_increase_pct"
    )

    # ─────────────────────────────────────────────────────────────
    # Marketing chat rate limit — public, unauthenticated endpoint
    # (app/routes/marketing.py), per-IP requests/minute
    # ─────────────────────────────────────────────────────────────

    marketing_chat_rate_limit_per_minute: int = Field(
        10, validation_alias="marketing_chat_rate_limit_per_minute"
    )

    # ─────────────────────────────────────────────────────────────
    # Token Budgets — Rule 86 (env vars override token_budgets.yaml)
    # ─────────────────────────────────────────────────────────────

    max_prompt_tokens: int = Field(32000, validation_alias="max_prompt_tokens")
    max_completion_tokens: int = Field(4096, validation_alias="max_completion_tokens")
    max_context_tokens: int = Field(64000, validation_alias="max_context_tokens")

    # ─────────────────────────────────────────────────────────────
    # Provider Pricing — loaded from config/model_pricing.yaml at startup
    # Never hardcoded — update the YAML to change rates, no deploy needed
    # ─────────────────────────────────────────────────────────────

    model_pricing: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_provider_overrides(self) -> "Settings":
        """Fail fast (Rule 45) if a direct-provider bypass is half-configured.

        A *_base_url override with no matching *_chat_model would otherwise send
        an empty "model" field to a real provider API and fail confusingly deep
        inside a request -- catch it once, at startup, with a clear message.
        """
        if self.gemini_base_url and not self.gemini_chat_model:
            raise ValueError(
                "GEMINI_BASE_URL is set but GEMINI_CHAT_MODEL is empty -- set it "
                "to the real chat model ID from your provider console."
            )
        if self.gemini_base_url and not self.gemini_embedding_model:
            raise ValueError(
                "GEMINI_BASE_URL is set but GEMINI_EMBEDDING_MODEL is empty -- set "
                "it to the real embedding model ID from your provider console."
            )
        if self.kimi_base_url and not self.kimi_chat_model:
            raise ValueError(
                "KIMI_BASE_URL is set but KIMI_CHAT_MODEL is empty -- set it to "
                "the real chat model ID from your provider console."
            )
        if self.groq_base_url and not self.groq_chat_model:
            raise ValueError(
                "GROQ_BASE_URL is set but GROQ_CHAT_MODEL is empty -- set it to "
                "the real chat model ID from your provider console."
            )
        if self.groq_base_url and not self.groq_api_key:
            raise ValueError(
                "GROQ_BASE_URL is set but GROQ_API_KEY is empty -- Groq has no "
                "EURI fallback, so a real key is required."
            )
        # Must match _CHAT_RESOLVERS' keys exactly (defined after this class,
        # near resolve_chat_provider_chain() -- hardcoded here rather than
        # imported to avoid a definition-order problem: this validator runs
        # at module-import time, when Settings() is first constructed, which
        # is before _CHAT_RESOLVERS exists further down in this same file).
        known = {"gemini", "kimi", "groq"}
        requested = [n.strip() for n in self.chat_provider_order.split(",") if n.strip()]
        unknown = [n for n in requested if n not in known]
        if unknown:
            raise ValueError(
                f"CHAT_PROVIDER_ORDER has unknown provider(s) {unknown} -- must "
                f"only contain: {', '.join(sorted(known))}"
            )
        if not requested:
            raise ValueError("CHAT_PROVIDER_ORDER must not be empty.")
        return self

    @model_validator(mode="after")
    def _load_yaml_configs(self) -> "Settings":
        pricing_path = _CONFIG_DIR / "model_pricing.yaml"
        if not pricing_path.exists():
            raise ValueError(
                f"Required config not found: {pricing_path}. "
                "Cannot start without provider pricing — Rule 86."
            )
        with pricing_path.open() as f:
            self.model_pricing = yaml.safe_load(f).get("cost_per_token_usd", {})
        return self

    # ─────────────────────────────────────────────────────────────
    # Computed Helpers
    # ─────────────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Provider endpoint resolution (17-Jul-2026 -- direct-provider bypass)
#
# Every provider-calling service (llm_service.py, embedding_service.py,
# image_processor.py) resolves *where* to call through these two functions
# instead of reading settings.euri_base_url directly. This is the single
# place that decides EURI-vs-direct per provider; call sites only see the
# resolved (base_url, api_key, chat_model, embedding_model) tuple.
# ─────────────────────────────────────────────────────────────────────────────


class ProviderEndpoint(NamedTuple):
    """Resolved endpoint for one provider family.

    embedding_model is only meaningful for the "gemini" family (the only
    family this project embeds through) -- empty string for kimi/groq.

    is_direct distinguishes "calling the real provider API" from "calling it
    through EURI" -- used only to decide how to label the call for cost
    tracking and Prometheus metrics (see resolve_chat_provider_chain()).
    Groq has no EURI path, so it is always is_direct=True.
    """

    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str
    is_direct: bool


def resolve_gemini(settings: Settings, *, euri_chat_model: str = "") -> ProviderEndpoint:
    """Resolve the Gemini provider slot.

    If GEMINI_BASE_URL is set, calls go directly to that endpoint using
    GEMINI_API_KEY / GEMINI_CHAT_MODEL / GEMINI_EMBEDDING_MODEL -- validated
    non-empty at startup by _validate_provider_overrides, never inferred here.

    If GEMINI_BASE_URL is unset (default), calls route through the EURI
    gateway exactly as before this feature existed. EURI_API_KEY is preferred;
    GEMINI_API_KEY is used as a fallback so pre-existing .env files (which
    store the EURI-issued key under GEMINI_API_KEY) keep working unchanged.

    ``euri_chat_model`` selects which EURI alias to use when NOT bypassing
    EURI (the failover chain has two Gemini slots -- primary and last-resort --
    with different EURI aliases; irrelevant once GEMINI_BASE_URL is set, since
    both slots then collapse to the same real GEMINI_CHAT_MODEL).
    """
    if settings.gemini_base_url:
        return ProviderEndpoint(
            base_url=settings.gemini_base_url,
            api_key=settings.gemini_api_key,
            chat_model=settings.gemini_chat_model,
            embedding_model=settings.gemini_embedding_model,
            is_direct=True,
        )
    return ProviderEndpoint(
        base_url=settings.euri_base_url,
        api_key=settings.euri_api_key or settings.gemini_api_key,
        chat_model=euri_chat_model or settings.llm_primary_model,
        embedding_model=settings.embedding_model,
        is_direct=False,
    )


def resolve_kimi(settings: Settings) -> ProviderEndpoint:
    """Resolve the KiMi provider slot. Same override/fallback rules as Gemini."""
    if settings.kimi_base_url:
        return ProviderEndpoint(
            base_url=settings.kimi_base_url,
            api_key=settings.kimi_api_key,
            chat_model=settings.kimi_chat_model,
            embedding_model="",
            is_direct=True,
        )
    return ProviderEndpoint(
        base_url=settings.euri_base_url,
        api_key=settings.euri_api_key or settings.kimi_api_key,
        chat_model=settings.llm_fallback_model,
        embedding_model="",
        is_direct=False,
    )


def resolve_groq(settings: Settings) -> ProviderEndpoint:
    """Resolve the Groq provider slot. Groq has no EURI equivalent -- always direct."""
    return ProviderEndpoint(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
        chat_model=settings.groq_chat_model,
        embedding_model="",
        is_direct=True,
    )


_CHAT_RESOLVERS: dict[str, Any] = {
    "gemini": resolve_gemini,
    "kimi": resolve_kimi,
    "groq": resolve_groq,
}


def resolve_chat_provider_chain(settings: Settings) -> list[tuple[str, ProviderEndpoint]]:
    """Build the ordered chat failover chain from CHAT_PROVIDER_ORDER.

    Returns a list of (provider_label, endpoint) pairs, in the order they
    should be tried. provider_label is used for both cost lookup
    (config/model_pricing.yaml) and Prometheus metric labels:
      - EURI-routed entries reuse the exact historical label
        ("gemini-flash-3.5" / "kimi-k2.6" / "gemini-3.5") so existing pricing
        entries and Grafana dashboards keep working unchanged.
      - Direct-provider entries are labeled "{family}:{real_model_id}" (e.g.
        "groq:llama-3.3-70b-versatile") since the real model ID alone doesn't
        say which vendor served it. These won't have a model_pricing.yaml
        entry yet -- cost falls back to the safe default rate (see
        llm_service.py's _compute_cost) until pricing is added for that model.

    "gemini" may appear twice (its historical two-EURI-alias role): the first
    occurrence resolves with llm_primary_model, the second with
    llm_last_resort_model -- irrelevant once GEMINI_BASE_URL is set, since
    direct mode only has one GEMINI_CHAT_MODEL regardless of position.

    CHAT_PROVIDER_ORDER is validated at startup (Settings._validate_provider_overrides)
    to only contain known names and never be empty -- this function trusts that.
    """
    names = [n.strip() for n in settings.chat_provider_order.split(",") if n.strip()]
    chain: list[tuple[str, ProviderEndpoint]] = []
    gemini_seen = 0
    for name in names:
        if name == "gemini":
            euri_alias = (
                settings.llm_primary_model if gemini_seen == 0 else settings.llm_last_resort_model
            )
            endpoint = resolve_gemini(settings, euri_chat_model=euri_alias)
            gemini_seen += 1
        else:
            endpoint = _CHAT_RESOLVERS[name](settings)

        if endpoint.is_direct:
            label = f"{name}:{endpoint.chat_model}"
        else:
            label = endpoint.chat_model  # exact historical EURI alias string
        chain.append((label, endpoint))
    return chain
