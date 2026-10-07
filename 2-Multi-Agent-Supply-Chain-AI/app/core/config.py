"""Application settings, loaded from environment variables (and `.env` outside tests).

Secrets are `SecretStr` so they never appear in logs or reprs. Every setting is documented in `.env.example`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod", "test"]


@dataclass(frozen=True)
class ModelSpec:
    """A `provider:model` reference, e.g. `euri:gpt-4.1-mini`."""

    provider: str
    model: str

    @classmethod
    def parse(cls, value: str) -> ModelSpec:
        provider, sep, model = value.strip().partition(":")
        if not sep or not provider or not model:
            raise ValueError(f"model spec must look like 'provider:model', got {value!r}")
        return cls(provider=provider.lower(), model=model)

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


def _parse_chain(value: str) -> list[ModelSpec]:
    specs = [ModelSpec.parse(v) for v in value.split(",") if v.strip()]
    if not specs:
        raise ValueError("a model chain needs at least one provider:model entry")
    return specs


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    # ------------------------------------------------------------ app
    env: Environment = "local"
    app_name: str = "supply-chain-ai"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    cors_origins: str = "http://localhost:3000"

    # ------------------------------------------------------------ LLM providers (OpenAI-compatible)
    euri_api_key: SecretStr = SecretStr("")
    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    groq_api_key: SecretStr = SecretStr("")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    llm_answer_chain: str = "euri:gpt-4.1-mini,gemini:gemini-3.5-flash,groq:openai/gpt-oss-120b"
    llm_agent_chain: str = "euri:gpt-4.1-mini,groq:qwen/qwen3.8-27b,groq:openai/gpt-oss-120b"
    llm_judge_model: str = "euri:gpt-4.1-mini"
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 1500

    embedding_model: str = "gemini:gemini-embedding-001"
    embedding_dimensions: int = 1536
    kb_collection: str = "documents_gemini"

    # ------------------------------------------------------------ database
    database_url: SecretStr = SecretStr("postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
    database_migration_url: SecretStr | None = None
    database_pool_size: int = 5

    # ------------------------------------------------------------ auth
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: SecretStr = SecretStr("")
    supabase_jwks_url: str = ""
    supabase_jwt_audience: str = "authenticated"

    # ------------------------------------------------------------ redis / web search
    redis_url: str = "redis://localhost:6379/0"
    tavily_api_key: SecretStr = SecretStr("")

    # ------------------------------------------------------------ RAG
    rag_top_k: int = 5
    rag_rerank_candidates: int = 12
    rag_rerank_in_agent: bool = False
    max_upload_mb: int = 20
    ocr_engine: Literal["tesseract", "vision_llm", "off"] = "tesseract"
    ocr_languages: str = "eng"
    ocr_min_confidence: float = 60.0
    ocr_vision_model: str = "euri:gpt-4.1-mini"

    # ------------------------------------------------------------ agents / human-in-the-loop
    agent_recursion_limit: int = 40
    agent_max_tool_iterations: int = 4
    agent_node_timeout_seconds: float = 60.0
    tool_timeout_seconds: float = 10.0
    approval_po_value_threshold: float = 50_000.0
    approval_ttl_hours: int = 24

    # ------------------------------------------------------------ guardrails
    guardrail_profiles: str = "pii,hipaa"
    guardrail_input_mode: Literal["off", "flag", "block"] = "block"
    guardrail_context_mode: Literal["off", "flag", "block"] = "block"
    guardrail_output_mode: Literal["off", "flag", "block"] = "block"
    hallucination_guard_mode: Literal["off", "flag", "block"] = "flag"
    max_query_chars: int = 4000
    audit_log_content: bool = False

    # ------------------------------------------------------------ rate limits (per user per minute)
    rate_limit_chat: int = 20
    rate_limit_upload: int = 10
    rate_limit_default: int = 120

    # ------------------------------------------------------------ circuit breaker
    breaker_failure_threshold: int = 3
    breaker_cooldown_seconds: float = 60.0

    # ------------------------------------------------------------ observability
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr = SecretStr("")
    langchain_project: str = "supply-chain-ai"

    aws_region: str = "ap-northeast-1"

    # ------------------------------------------------------------ demo data
    demo_seed: bool = True

    @field_validator("llm_temperature")
    @classmethod
    def _temperature_range(cls, v: float) -> float:
        if not 0.2 <= v <= 0.5:
            raise ValueError("LLM_TEMPERATURE must be between 0.2 and 0.5 (the judge always uses 0)")
        return v

    @field_validator("llm_answer_chain", "llm_agent_chain")
    @classmethod
    def _valid_chain(cls, v: str) -> str:
        _parse_chain(v)
        return v

    # Derived views -----------------------------------------------------------
    @property
    def answer_chain(self) -> list[ModelSpec]:
        return _parse_chain(self.llm_answer_chain)

    @property
    def agent_chain(self) -> list[ModelSpec]:
        return _parse_chain(self.llm_agent_chain)

    @property
    def embedding_spec(self) -> ModelSpec:
        return ModelSpec.parse(self.embedding_model)

    @property
    def profiles(self) -> set[str]:
        return {p.strip().lower() for p in self.guardrail_profiles.split(",") if p.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env in {"staging", "prod"}

    def sqlalchemy_url(self) -> str:
        return self.database_url.get_secret_value()

    def migration_url(self) -> str:
        url = self.database_migration_url or self.database_url
        return url.get_secret_value()

    def provider_credentials(self, provider: str) -> tuple[str, SecretStr]:
        """Base URL and API key for an OpenAI-compatible provider."""
        table = {
            "euri": (self.euri_base_url, self.euri_api_key),
            "groq": (self.groq_base_url, self.groq_api_key),
            "gemini": (self.gemini_base_url, self.gemini_api_key),
        }
        if provider not in table:
            raise ValueError(f"unknown LLM provider {provider!r}")
        return table[provider]


class TestSettings(Settings):
    """Settings for tests: never read `.env`."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


__all__ = ["Environment", "ModelSpec", "Settings", "TestSettings", "get_settings"]
