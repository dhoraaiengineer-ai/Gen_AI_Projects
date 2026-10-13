"""Application settings from environment variables.

Every setting is documented in ``.env.example``. Secrets are ``SecretStr`` so they never appear in
logs or reprs. Under test (``FINAGENT_TESTING=1``) the ``.env`` file is not read, so tests are
hermetic and never depend on the developer's keys.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

KNOWN_PROVIDERS = frozenset({"euri", "gemini", "groq", "openai", "anthropic", "bedrock"})
TESTING_FLAG = "FINAGENT_TESTING"


class ModelSpec(BaseModel, frozen=True):
    """One ``provider:model`` entry of a model chain."""

    provider: str
    model: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"

    @classmethod
    def parse(cls, raw: str) -> ModelSpec:
        provider, sep, model = raw.strip().partition(":")
        provider = provider.strip().lower()
        model = model.strip()
        if not sep or not provider or not model:
            raise ValueError(f"model spec {raw!r} must look like provider:model")
        if provider not in KNOWN_PROVIDERS:
            raise ValueError(
                f"unknown provider {provider!r} in {raw!r}; known: {sorted(KNOWN_PROVIDERS)}"
            )
        return cls(provider=provider, model=model)


def parse_chain(raw: str) -> list[ModelSpec]:
    """Parse ``provider:model,provider:model`` into specs; rejects empty chains and duplicates."""
    specs = [ModelSpec.parse(part) for part in raw.split(",") if part.strip()]
    if not specs:
        raise ValueError("model chain is empty")
    keys = [s.key for s in specs]
    if len(set(keys)) != len(keys):
        raise ValueError(f"model chain has duplicates: {keys}")
    return specs


# backend/src/config/settings.py → repo root (shared .env for backend, frontend and Compose).
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"


def _env_file() -> str | None:
    if os.environ.get(TESTING_FLAG) == "1":
        return None
    return str(REPO_ROOT / ".env")


class Settings(BaseSettings):
    """All runtime configuration. Construct via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- app
    app_env: Literal["local", "test", "staging", "production"] = "local"
    demo_mode: bool = True
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    api_port: int = Field(default=8020, ge=1, le=65535)
    frontend_port: int = Field(default=3020, ge=1, le=65535)
    cors_origins: str = "http://localhost:3020,http://127.0.0.1:3020"

    # --- LLM providers
    euri_api_key: SecretStr | None = None
    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # --- model chains
    llm_answer_chain: str = "euri:gpt-4.1-mini,gemini:gemini-3.8-flash,groq:openai/gpt-oss-120b"
    llm_agent_chain: str = "euri:gpt-4.1-mini,groq:qwen/qwen3.8-27b,groq:openai/gpt-oss-20b"
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    # agents: LLM tool loop (False = deterministic plans only, zero LLM tokens for agents)
    agent_llm_tool_loop: bool = True
    agent_max_tool_iterations: int = Field(default=2, ge=0, le=6)
    # narrative synthesis with the answer chain (False = deterministic narrative)
    llm_narrative: bool = True
    llm_routing: bool = True  # False: Jev (if configured) then keyword routing, no LLM call
    # token budgets (ADR-029): per call type and per request
    llm_request_token_budget: int = Field(default=12_000, ge=1_000, le=200_000)
    llm_classify_max_input_tokens: int = Field(default=600, ge=100, le=8_000)
    llm_classify_max_output_tokens: int = Field(default=60, ge=10, le=1_000)
    llm_agent_max_input_tokens: int = Field(default=3_000, ge=500, le=32_000)
    llm_agent_max_output_tokens: int = Field(default=300, ge=50, le=4_000)
    llm_tool_result_max_tokens: int = Field(default=450, ge=100, le=8_000)
    llm_narrative_max_input_tokens: int = Field(default=2_500, ge=500, le=32_000)
    llm_narrative_max_output_tokens: int = Field(default=450, ge=100, le=4_000)
    llm_narrative_min_output_tokens: int = Field(default=40, ge=0, le=1_000)

    # --- embeddings / re-ranking / chunking / vector store
    embedding_provider: str = "euri"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, gt=0)
    reranker: Literal["cross_encoder", "llm", "none"] = "cross_encoder"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # or BAAI/bge-reranker-base
    reranker_top_n: int = Field(default=12, ge=1, le=100)
    chunking_strategy: str = "auto"
    multimodal_captions: bool = False
    vector_store: Literal["pgvector", "qdrant", "opensearch"] = "pgvector"
    vector_db_url: str | None = None

    # --- web search
    tavily_api_key: SecretStr | None = None

    # --- decision model: TypeSafe AI Jev (ADR-027)
    typesafe_api_key: SecretStr | None = None
    typesafe_base_url: str = "https://api.typesafe.ai"
    jev_model: str = "jev-latest"
    decision_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    # --- Supabase
    supabase_url: str | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_jwks_url: str | None = None

    # --- Postgres
    database_target: Literal["supabase", "local"] = "supabase"
    database_url: SecretStr | None = None
    db_host: str | None = None
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_name: str = "postgres"
    db_port_transaction: int = 6543
    db_port_session: int = 5432

    # --- Redis / MCP / ML
    redis_url: str = "redis://127.0.0.1:6390/0"  # IPv4: Windows resolves localhost to ::1 first
    redis_enabled: bool = True  # False = in-process memory, limits and caches only
    mcp_transport: Literal["inmemory", "http"] = "inmemory"
    # MCP_TRANSPORT=http: one URL per server, {server} and {port} filled in (ports 8021–8026)
    mcp_url_template: str = "http://127.0.0.1:{port}/mcp"
    mcp_service_token: SecretStr | None = None  # API gateway → MCP servers (ADR-036)
    mlflow_url: str = "sqlite:///mlruns/mlflow.db"  # relative paths resolve under backend/
    ml_fraud_model_version: str = "latest"
    ml_risk_model_version: str = "latest"
    ml_forecast_model_version: str = "latest"

    # --- approvals and safety
    approval_value_threshold: float = Field(default=250_000, gt=0)
    approval_ttl_hours: int = Field(default=24, ge=1, le=720)
    max_input_chars: int = Field(default=4000, ge=100, le=50_000)

    # --- rate limits (requests per user per minute, per endpoint group)
    rate_limit_chat: int = Field(default=20, ge=1)
    rate_limit_analyze: int = Field(default=20, ge=1)
    rate_limit_read: int = Field(default=300, ge=1)
    rate_limit_upload: int = Field(default=10, ge=1)

    # --- demo users
    demo_user_password: SecretStr | None = None

    # --- observability
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "finagent"
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "finagent-api"
    metrics_token: SecretStr | None = None  # set → GET /metrics requires this bearer token

    # --- AWS (not needed locally)
    aws_region: str = "ap-southeast-1"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None

    @field_validator("llm_temperature")
    @classmethod
    def _temperature_in_range(cls, value: float) -> float:
        if not 0.2 <= value <= 0.5:
            raise ValueError("LLM_TEMPERATURE must be between 0.2 and 0.5")
        return value

    @field_validator("llm_answer_chain", "llm_agent_chain")
    @classmethod
    def _chain_is_valid(cls, value: str) -> str:
        parse_chain(value)
        return value

    @field_validator("embedding_provider")
    @classmethod
    def _embedding_provider_known(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in KNOWN_PROVIDERS | {"hash"}:
            raise ValueError(f"unknown EMBEDDING_PROVIDER {value!r}")
        return value

    @field_validator(
        "llm_provider",
        "llm_model",
        "db_host",
        "db_user",
        "vector_db_url",
        "supabase_url",
        "supabase_jwks_url",
        "otel_exporter_otlp_endpoint",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator(
        "euri_api_key",
        "gemini_api_key",
        "groq_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "tavily_api_key",
        "typesafe_api_key",
        "supabase_publishable_key",
        "supabase_secret_key",
        "database_url",
        "db_password",
        "demo_user_password",
        "langsmith_api_key",
        "aws_access_key_id",
        "aws_secret_access_key",
        "mcp_service_token",
        "metrics_token",
        mode="before",
    )
    @classmethod
    def _blank_secret_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _shorthand_pair(self) -> Settings:
        if bool(self.llm_provider) != bool(self.llm_model):
            raise ValueError("set both LLM_PROVIDER and LLM_MODEL, or neither")
        if self.llm_provider and self.llm_model:
            ModelSpec.parse(f"{self.llm_provider}:{self.llm_model}")
        return self

    # ------------------------------------------------------------------ derived values
    @property
    def answer_chain(self) -> list[ModelSpec]:
        if self.llm_provider and self.llm_model:
            return [ModelSpec.parse(f"{self.llm_provider}:{self.llm_model}")]
        return parse_chain(self.llm_answer_chain)

    @property
    def agent_chain(self) -> list[ModelSpec]:
        if self.llm_provider and self.llm_model:
            return [ModelSpec.parse(f"{self.llm_provider}:{self.llm_model}")]
        return parse_chain(self.llm_agent_chain)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def _db_url(self, port: int) -> str:
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        if not (self.db_host and self.db_user and self.db_password):
            raise ValueError(
                "database not configured: set DATABASE_URL or DB_HOST/DB_USER/DB_PASSWORD"
            )
        password = quote(self.db_password.get_secret_value(), safe="")
        user = quote(self.db_user, safe="")
        return f"postgresql+psycopg://{user}:{password}@{self.db_host}:{port}/{self.db_name}"

    @property
    def app_database_url(self) -> str:
        """Transaction pooler (6543) for the app; prepared statements must be disabled."""
        return self._db_url(self.db_port_transaction)

    @property
    def session_database_url(self) -> str:
        """Session pooler (5432) for migrations, seeding and the LangGraph checkpointer."""
        return self._db_url(self.db_port_session)

    @property
    def database_configured(self) -> bool:
        return self.database_url is not None or bool(
            self.db_host and self.db_user and self.db_password
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Tests construct ``Settings(...)`` directly instead."""
    settings = Settings()
    logger.info(
        "settings loaded",
        extra={
            "app_env": settings.app_env,
            "demo_mode": settings.demo_mode,
            "answer_chain": [s.key for s in settings.answer_chain],
            "agent_chain": [s.key for s in settings.agent_chain],
            "database_configured": settings.database_configured,
        },
    )
    return settings
