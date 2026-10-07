"""Application settings, loaded from environment variables (and `.env` in local dev).

Secrets are typed as `SecretStr` so they never show up in logs or reprs.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.rag.chunking import ChunkingStrategy

# All OpenAI-compatible: EURI is a gateway (one wallet for every model); Gemini and Groq are called directly.
Provider = Literal["euri", "gemini", "groq"]
PROVIDERS: tuple[str, ...] = ("euri", "gemini", "groq")


def parse_model_chain(value: str) -> list[tuple[Provider, str]]:
    """'groq:openai/gpt-oss-120b, gemini:gemini-3.5-flash' -> [("groq", "openai/gpt-oss-120b"), ...]."""
    chain: list[tuple[Provider, str]] = []
    for entry in filter(None, (part.strip() for part in value.split(","))):
        provider, sep, model = entry.partition(":")
        if not sep or provider not in PROVIDERS or not model.strip():
            raise ValueError(f'fallback entry {entry!r} must be "provider:model" with provider one of {PROVIDERS}')
        chain.append((provider, model.strip()))  # type: ignore[arg-type]
    return chain


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "genai-rag-platform"
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    # Unset: metrics at /metrics on the app port (local dev). Set (e.g. 9090 in k8s): metrics move to
    # their own port, reachable only in-cluster, and /metrics disappears from the public app port.
    metrics_port: int | None = Field(None, ge=1024, le=65535)

    # LLM + embeddings via the EURI OpenAI-compatible gateway
    euri_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.euron.one/api/v1/euri"
    llm_model: str = "gpt-4.1-nano"
    # Answer generation: 0.2-0.5 keeps wording natural while staying close to the documents.
    # The evaluation judge always runs at 0 so grades are repeatable.
    llm_temperature: float = Field(0.2, ge=0.2, le=0.5)
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1  # keep low: on quota/outage errors the fallback model is the better retry
    # Embeddings have no fallback (query and stored vectors must match), so retry rate limits with backoff.
    embedding_max_retries: int = Field(4, ge=0, le=10)
    # Circuit breaker per provider:model: open after N consecutive outage errors, skip it for the cool-down.
    circuit_breaker_failure_threshold: int = Field(3, ge=1)
    circuit_breaker_reset_seconds: float = Field(60.0, gt=0)
    # Used when the primary model errors (rate limit / daily quota / outage). Empty string disables.
    # Separate fallbacks because Gemini (via EURI or directly) can't complete a tool-call round trip in
    # LangChain: the OpenAI client drops its thought signature. The agent fallback must stay on EURI.
    llm_fallback_provider: Provider = "euri"  # "gemini" = Google's API directly, so a spent EURI wallet doesn't matter
    llm_fallback_model: str = "gemini-2.0-flash"
    agent_fallback_model: str = "gpt-4o-mini"
    # Further fallbacks, tried in order after the ones above: comma-separated "provider:model".
    # e.g. "groq:openai/gpt-oss-120b". Agent entries must pass a real tool-call round trip.
    llm_extra_fallbacks: str = ""
    agent_extra_fallbacks: str = ""
    # Embeddings: every stored vector and every query must use the same provider + model, so changing
    # these needs a fresh COLLECTION_NAME (and re-uploading the documents).
    embedding_provider: Provider = "euri"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Web search tool for the research agent (Tavily). Unset key = the agent only searches the knowledge base.
    tavily_api_key: SecretStr | None = None
    web_search_max_results: int = Field(3, ge=1, le=10)
    web_search_depth: Literal["basic", "advanced"] = "basic"  # advanced costs 2 Tavily credits per search
    web_search_timeout_seconds: float = Field(20.0, gt=0)

    # Google Gemini API, called directly through its OpenAI-compatible endpoint.
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Groq, called directly through its OpenAI-compatible endpoint.
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"

    @field_validator("llm_extra_fallbacks", "agent_extra_fallbacks")
    @classmethod
    def _check_model_chain(cls, value: str) -> str:
        parse_model_chain(value)  # raises on a malformed entry, so a typo fails at startup
        return value

    # Supabase / Postgres with pgvector
    database_url: SecretStr | None = None
    collection_name: str = "documents"

    # Chunking: the default strategy; /ingest can override it per request.
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    chunk_size: int = Field(1000, gt=0)  # recursive chunks, and the cap on semantic chunks
    # Overlap as % of the chunk size. Regular chunks: 15-20% keeps sentences at a boundary in both chunks.
    chunk_overlap_pct: float = Field(15.0, ge=0, le=50)
    # Semantic: split where neighbour distance exceeds this percentile. Lower = more, smaller chunks.
    semantic_breakpoint_percentile: float = Field(90.0, gt=0, lt=100)
    # Parent-child: children are embedded and matched; their parent is what the LLM sees.
    parent_chunk_size: int = Field(2000, gt=0)
    child_chunk_size: int = Field(400, gt=0)
    # Children are small and their parent supplies the context, so 10-15% is enough.
    child_chunk_overlap_pct: float = Field(10.0, ge=0, le=50)

    # Redis: answer + prompt cache and short-term conversation memory. Unset = in-process (local dev only).
    redis_url: SecretStr | None = None  # e.g. redis://localhost:6379/0 (may contain a password)
    cache_enabled: bool = True
    answer_cache_ttl_seconds: int = Field(3600, ge=0)  # repeated questions
    prompt_cache_ttl_seconds: int = Field(86400, ge=0)  # identical LLM prompts
    # Conversation memory: long-term in Postgres, the recent window in Redis.
    memory_window_messages: int = Field(8, ge=0, le=50)  # user + assistant messages used for follow-ups
    short_term_memory_ttl_seconds: int = Field(3600, ge=60)
    # Log question/answer text in the audit log (turn off where questions may contain personal data).
    audit_log_content: bool = True

    # Uploads: PDF, Excel, Word, PowerPoint, CSV, text. Files are parsed in memory (the container FS is read-only).
    max_upload_mb: int = Field(20, ge=1, le=200)
    # Golden dataset: Q&A pairs the LLM writes for each added/updated document (0 disables; 1 LLM call per doc).
    golden_questions_per_document: int = Field(3, ge=0, le=20)
    # Grades answers during evaluation. A stronger model than LLM_MODEL: nano-sized judges misgrade correct answers.
    # Empty string = use LLM_MODEL.
    eval_judge_model: str = "gpt-4o-mini"

    # Per-user requests per minute on the endpoints that spend LLM/embedding quota. 0 = no limit for that one.
    rate_limit_enabled: bool = True
    rate_limit_query_per_minute: int = Field(10, ge=0)
    rate_limit_agent_per_minute: int = Field(3, ge=0)  # several LLM calls per request
    rate_limit_ingest_per_minute: int = Field(5, ge=0)  # embeddings + golden Q&A generation
    rate_limit_eval_per_minute: int = Field(1, ge=0)  # up to 2 LLM calls per golden item

    # Hallucination guard on every answer: off | flag (mark ungrounded answers) | block (replace them with
    # a refusal). Checks citations and that numbers/identifiers in the answer appear in the passages.
    hallucination_guard: Literal["off", "flag", "block"] = "flag"

    # Guardrails: policy-driven input / document / output checks (app/guardrails/policy.yaml).
    guardrails_enabled: bool = True
    guardrails_policy_path: str | None = None  # another policy file; default = the packaged one
    # OCR for scanned PDF pages and image uploads (RapidOCR, offline).
    ocr_enabled: bool = True

    # Retrieval
    top_k: int = Field(4, ge=1, le=50)
    # Hybrid search: add Postgres full-text keyword matches to vector search (fused by reciprocal rank).
    hybrid_search: bool = True
    # Re-ranking: an LLM picks the best TOP_K out of RERANK_CANDIDATES hybrid results (1 LLM call per query).
    rerank_enabled: bool = True
    rerank_candidates: int = Field(12, ge=2, le=50)

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
