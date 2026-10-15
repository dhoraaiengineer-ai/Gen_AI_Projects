"""Application settings. Every value comes from environment variables (see .env.example)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = PROJECT_ROOT.parent  # repository root (compose.yaml, .env, frontend/, deploy/)
_DEFAULT_FRONTEND = REPO_ROOT / "frontend" / "src"

# Classifiers and judges always run at temperature 0. This is not configurable.
CLASSIFIER_TEMPERATURE = 0.0

PROVIDERS = ("euri", "gemini", "groq")


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_chain(raw: str) -> list[ModelRef]:
    """Parse 'euri:gpt-4.1-mini,groq:openai/gpt-oss-120b' into model refs."""
    refs: list[ModelRef] = []
    for item in (x.strip() for x in raw.split(",")):
        if not item:
            continue
        provider, sep, model = item.partition(":")
        if not sep or provider not in PROVIDERS or not model:
            raise ValueError(
                f"invalid model chain entry {item!r}; expected provider:model with provider in {PROVIDERS}"
            )
        refs.append(ModelRef(provider, model))
    if not refs:
        raise ValueError("model chain is empty")
    return refs


class Settings(BaseSettings):
    # .env lives at the repository root (shared with compose.yaml); a backend/.env would override it.
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_env: Literal["local", "test", "production"] = "local"
    app_name: str = "MedInfo Assistant"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    audit_log_enabled: bool = True

    # --- Supabase auth ---
    supabase_url: str = ""
    supabase_publishable_key: str = ""  # public by design (used by the browser sign-in)
    supabase_secret_key: SecretStr | None = None  # service role; server-side admin tasks only
    supabase_jwks_url: str = ""
    supabase_jwt_audience: str = "authenticated"
    jwks_cache_seconds: int = 600
    jwt_clock_skew_seconds: int = Field(default=30, ge=0, le=300)  # tolerated iat/nbf/exp skew

    # --- Database ---
    database_url: SecretStr | None = None

    # --- Model providers (OpenAI-compatible) ---
    euri_api_key: SecretStr | None = None
    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Chains are "provider:model" lists in fallback order. Stage 1 uses the first answer model;
    # Stage 4 adds fallback with per-model circuit breakers.
    llm_answer_chain: str = "euri:gpt-4.1-mini"
    llm_agent_chain: str = "euri:gpt-4.1-mini"
    # Optional cheaper/faster chain for classifiers, re-ranker and rewriter (LLM gateway route "fast").
    # Empty -> the answer chain is used for every task. Routing table: app/rag/llm_gateway.yaml.
    llm_fast_chain: str = ""
    llm_timeout_seconds: float = 45.0
    llm_max_tokens: int = 1200
    # Answers run at 0.1-0.3 (safety requirement); classifiers and judges always at 0.
    llm_temperature: float = Field(default=0.2, ge=0.1, le=0.3)

    # --- Embeddings (one provider per collection; never mixed) ---
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- Web search ---
    tavily_api_key: SecretStr | None = None

    # --- Region / safety messaging ---
    region: str = "international"
    audience: Literal["public", "clinician", "mixed"] = "public"
    emergency_number: str = "112"
    emergency_service_name: str = "emergency services"
    crisis_line_name: str = ""
    crisis_line_number: str = ""
    poison_line_number: str = ""

    # --- Safety thresholds (ops-tunable only; the safety layer itself cannot be disabled) ---
    stale_source_years: int = Field(default=5, ge=1, le=30)
    max_question_chars: int = Field(default=2000, ge=50, le=20000)

    # --- Retrieval ---
    # auto -> pgvector when DATABASE_URL is set, else the static Stage 1 corpus.
    # memory -> in-process index (no persistence); static -> BM25 over CORPUS_PATH (read-only).
    retrieval_backend: Literal["auto", "static", "memory", "pgvector"] = "auto"
    corpus_path: Path = PROJECT_ROOT / "data" / "synthetic" / "stage1_corpus.json"
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_min_score: float = Field(default=0.5, ge=0.0)  # static BM25 backend
    retrieval_min_similarity: float = Field(default=0.25, ge=-1.0, le=1.0)  # vector backends (cosine)
    retrieval_candidates: int = Field(default=12, ge=2, le=50)  # hybrid candidates sent to the re-ranker
    rerank_enabled: bool = True  # quality knob only; safety checks never depend on it
    embedding_provider: Literal["euri", "gemini"] = "euri"
    collection_prefix: str = Field(default="medinfo", pattern=r"^[a-z][a-z0-9_]{1,30}$")

    # --- Cache, memory, rate limits (Redis; in-process fallback when REDIS_URL is unset) ---
    redis_url: SecretStr | None = None
    answer_cache_ttl_seconds: int = Field(default=3600, ge=0)
    llm_cache_ttl_seconds: int = Field(default=86400, ge=0)
    embedding_cache_ttl_seconds: int = Field(default=604800, ge=0)  # query vectors only; 0 disables
    conversation_retention_days: int = Field(default=30, ge=1, le=3650)
    conversation_encryption_key: SecretStr | None = None  # Fernet key; REQUIRED in production
    short_term_turns: int = Field(default=10, ge=2, le=50)
    rate_limit_chat_per_minute: int = Field(default=20, ge=1)
    rate_limit_research_per_hour: int = Field(default=20, ge=1)
    rate_limit_upload_per_hour: int = Field(default=30, ge=1)

    # --- Resilience ---
    circuit_failure_threshold: int = Field(default=3, ge=1)
    circuit_reset_seconds: float = Field(default=30.0, gt=0)
    model_retry_attempts: int = Field(default=2, ge=1, le=5)
    model_retry_base_delay: float = Field(default=0.5, ge=0)

    # --- UI (local development) ---
    # In Docker/Kubernetes the frontend container (nginx) serves the UI and proxies /api here. For local
    # development the backend can serve frontend/src itself; unset or missing -> no UI routes.
    frontend_dir: Path | None = _DEFAULT_FRONTEND if _DEFAULT_FRONTEND.is_dir() else None

    # --- Observability ---
    metrics_token: SecretStr | None = None  # if set, /metrics requires a bearer token

    # --- Clinician review ---
    review_sample_rate: float = Field(default=0.05, ge=0.0, le=1.0)  # share of live answers queued for review

    # --- Research mode (clinicians and admins) ---
    research_enabled: bool = True
    web_allowed_domains: list[str] = [
        "who.int",
        "nice.org.uk",
        "cdc.gov",
        "nih.gov",
        "ncbi.nlm.nih.gov",
        "medlineplus.gov",
        "nhs.uk",
        "fda.gov",
        "ema.europa.eu",
        "cochranelibrary.com",
    ]

    # --- Ingestion ---
    chunk_strategy: Literal["recursive", "semantic", "parent_child"] = "recursive"
    chunk_size: int = Field(default=1000, ge=200, le=8000)
    parent_chunk_size: int = Field(default=2000, ge=400, le=16000)
    child_chunk_size: int = Field(default=400, ge=100, le=4000)
    max_upload_mb: int = Field(default=10, ge=1, le=100)

    @field_validator("supabase_url", "euri_base_url", "gemini_base_url", "groq_base_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("llm_answer_chain", "llm_agent_chain")
    @classmethod
    def _valid_chain(cls, v: str) -> str:
        parse_chain(v)
        return v

    @field_validator("llm_fast_chain")
    @classmethod
    def _valid_optional_chain(cls, v: str) -> str:
        if v.strip():
            parse_chain(v)
        return v

    def resolved_backend(self) -> str:
        if self.retrieval_backend != "auto":
            return self.retrieval_backend
        return "pgvector" if self.database_url is not None else "static"

    def collection_names(self) -> tuple[str, str]:
        """(trusted, user) collection names. They embed the embedding model and size, so switching
        models can never mix vectors: a new model means new collections and a re-ingest."""
        slug = re.sub(r"[^a-z0-9]+", "_", f"{self.embedding_provider}_{self.embedding_model}".lower()).strip(
            "_"
        )
        suffix = f"{slug}_{self.embedding_dimensions}"
        return f"{self.collection_prefix}_trusted__{suffix}", f"{self.collection_prefix}_user__{suffix}"

    def agent_chain(self) -> list[ModelRef]:
        return parse_chain(self.llm_agent_chain)

    def answer_chain(self) -> list[ModelRef]:
        return parse_chain(self.llm_answer_chain)

    def fast_chain(self) -> list[ModelRef] | None:
        return parse_chain(self.llm_fast_chain) if self.llm_fast_chain.strip() else None

    def provider_credentials(self, provider: str) -> tuple[str, SecretStr | None]:
        return {
            "euri": (self.euri_base_url, self.euri_api_key),
            "gemini": (self.gemini_base_url, self.gemini_api_key),
            "groq": (self.groq_base_url, self.groq_api_key),
        }[provider]

    @model_validator(mode="after")
    def _derive_and_check(self) -> Settings:
        if not self.supabase_jwks_url and self.supabase_url:
            self.supabase_jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
        if self.app_env == "production":
            # Emergency messaging must be a deliberate, region-specific choice in production.
            if "emergency_number" not in self.model_fields_set:
                raise ValueError("EMERGENCY_NUMBER must be set explicitly in production")
            if not self.supabase_jwks_url:
                raise ValueError("SUPABASE_URL or SUPABASE_JWKS_URL is required in production")
            if self.database_url is None:
                raise ValueError("DATABASE_URL is required in production")
            if self.conversation_encryption_key is None:
                raise ValueError("CONVERSATION_ENCRYPTION_KEY is required in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
