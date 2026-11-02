"""Application settings, loaded from environment variables only (rules/10, ADR-007, ADR-008)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["euri", "gemini", "groq"]
PROVIDERS: tuple[Provider, ...] = ("euri", "gemini", "groq")


@dataclass(frozen=True)
class ChainEntry:
    provider: Provider
    model: str


def parse_chain(raw: str) -> tuple[ChainEntry, ...]:
    """Parse ``provider:model,provider:model`` (first entry = primary). Models may contain ``/`` but not ``,``."""
    entries: list[ChainEntry] = []
    for part in (p.strip() for p in raw.split(",")):
        if not part:
            continue
        provider, sep, model = part.partition(":")
        if not sep or not model.strip():
            raise ValueError(f"chain entry {part!r} must be 'provider:model'")
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; allowed: {', '.join(PROVIDERS)}")
        entries.append(ChainEntry(provider=provider, model=model.strip()))
    if not entries:
        raise ValueError("chain must contain at least one provider:model entry")
    return tuple(entries)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "ci", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    # ── Database (ADR-007) ──
    database_url: str = "postgresql+asyncpg://autoserve:autoserve@localhost:5432/autoserve"
    database_url_migrations: str | None = None
    database_pooler_mode: Literal["direct", "session", "transaction"] = "direct"
    db_connect_timeout_s: float = 5.0
    db_use_null_pool: bool = False  # tests: avoid sharing asyncpg connections across event loops

    # ── LLM providers (ADR-008) ──
    llm_provider: Literal["openai_compatible"] = "openai_compatible"
    euri_api_key: SecretStr | None = None
    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_answer_chain: str = "euri:gpt-4.1-mini"
    llm_agent_chain: str = "euri:gpt-4.1-mini"
    llm_temperature: float = 0.2
    llm_timeout_s: float = 30.0  # primary entry of a chain
    llm_fallback_timeout_s: float = 10.0  # later entries: fail over fast (user decision 2026-10-26)
    llm_max_retries: int = Field(default=2, ge=0, le=2)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_provider: Literal["euri", "hashing"] = "euri"  # hashing = offline, deterministic (tests only)

    # ── Optional integrations (ADR-008) ──
    web_search_enabled: bool = False
    tavily_api_key: SecretStr | None = None
    typesafe_api_key: SecretStr | None = None
    typesafe_base_url: str = "https://api.typesafe.ai"
    jev_model: str = "jev-latest"
    decision_timeout_seconds: float = 5.0

    # ── Object storage (MinIO local / S3) ──
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "autoserve-documents"
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str = "us-east-1"
    s3_sse: Literal["none", "AES256", "aws:kms"] = "none"  # local MinIO has no KMS → none; AWS → aws:kms (rules/70)
    s3_kms_key_id: str | None = None
    storage_backend: Literal["s3", "local"] = "s3"
    local_storage_dir: str = ".local-storage"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_upload_pages: int = 20
    extraction_confidence_threshold: float = Field(default=0.80, ge=0, le=1)
    tesseract_cmd: str | None = None  # path to tesseract if not on PATH (e.g. Windows installer location)

    # ── Auth (DEMO JWT locally, OIDC in prod) ──
    auth_mode: Literal["demo", "oidc"] = "demo"
    jwt_secret: SecretStr | None = None
    jwt_ttl_minutes: int = Field(default=60, ge=1, le=60)
    jwt_issuer: str = "autoserve-demo"
    jwt_audience: str = "autoserve-api"
    # Prod OIDC (Cognito) — config only until P5; marked PROD in docs.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    login_rate_limit_per_minute: int = 10

    @field_validator("llm_temperature")
    @classmethod
    def _temperature_range(cls, v: float) -> float:
        if not 0.2 <= v <= 0.5:
            raise ValueError("LLM_TEMPERATURE must be between 0.2 and 0.5 (ADR-008)")
        return v

    @field_validator("embedding_dimensions")
    @classmethod
    def _embedding_dims(cls, v: int) -> int:
        if v != 1536:
            raise ValueError("EMBEDDING_DIMENSIONS must be 1536 to match knowledge_chunks.embedding (ADR-008)")
        return v

    @field_validator("web_search_enabled")
    @classmethod
    def _no_web_search(cls, v: bool) -> bool:
        if v:
            raise ValueError("WEB_SEARCH_ENABLED must stay false: domain facts come only from the corpus (A1, ADR-008)")
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_strength(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None and len(v.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def _validate_chains(self) -> Settings:
        parse_chain(self.llm_answer_chain)
        if any(e.provider == "gemini" for e in parse_chain(self.llm_agent_chain)):
            raise ValueError("LLM_AGENT_CHAIN must not include gemini (tool calls fail over its OpenAI-compatible API)")
        return self

    @property
    def answer_chain(self) -> tuple[ChainEntry, ...]:
        return parse_chain(self.llm_answer_chain)

    @property
    def agent_chain(self) -> tuple[ChainEntry, ...]:
        return parse_chain(self.llm_agent_chain)

    def provider_credentials(self, provider: Provider) -> tuple[str, SecretStr | None]:
        return {
            "euri": (self.euri_base_url, self.euri_api_key),
            "gemini": (self.gemini_base_url, self.gemini_api_key),
            "groq": (self.groq_base_url, self.groq_api_key),
        }[provider]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
