"""Application settings, loaded from environment variables (and `.env` in local dev).

Secrets are typed as `SecretStr` so they never show up in logs or reprs.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "genai-rag-platform"
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"

    # LLM + embeddings via the EURI OpenAI-compatible gateway
    euri_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.euron.one/api/v1/euri"
    llm_model: str = "gpt-4.1-nano"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1  # keep low: on quota/outage errors the fallback model is the better retry
    # Used when the primary model errors (rate limit / daily quota / outage). Empty string disables.
    # Separate fallbacks because Gemini via EURI can't complete a tool-call round trip in LangChain.
    llm_fallback_model: str = "gemini-2.0-flash"
    agent_fallback_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Supabase / Postgres with pgvector
    database_url: SecretStr | None = None
    collection_name: str = "documents"

    # Retrieval
    chunk_size: int = Field(1000, gt=0)
    chunk_overlap: int = Field(150, ge=0)
    top_k: int = Field(4, ge=1, le=50)

    # Agent
    agent_max_iterations: int = Field(6, ge=1, le=20)

    # Auth: Supabase Auth issues ES256 JWTs; the API verifies them against the project's public JWKS.
    auth_enabled: bool = True
    supabase_url: str | None = None  # https://<project-ref>.supabase.co
    supabase_publishable_key: str | None = None  # public by design; the UI uses it to call Supabase Auth
    jwt_audience: str = "authenticated"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self._supabase_base()}/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return f"{self._supabase_base()}/auth/v1"

    def _supabase_base(self) -> str:
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is not set")
        return self.supabase_url.rstrip("/")

    @property
    def sqlalchemy_database_url(self) -> str:
        """Supabase hands out `postgresql://` URLs; SQLAlchemy needs the psycopg3 driver named."""
        if self.database_url is None:
            raise ValueError("DATABASE_URL is not set")
        url = self.database_url.get_secret_value()
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
