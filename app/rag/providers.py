"""Factories for the external dependencies: chat model, embeddings, vector store.

Everything provider-specific lives here, so swapping EURI for another OpenAI-compatible
gateway (or Supabase for another Postgres) is a config change, not a code change.
"""

import logging

import openai
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector
from sqlalchemy import Engine, create_engine, make_url, text

from app.config import Settings
from app.core.metrics import FallbackCounter

logger = logging.getLogger(__name__)


def _api_key(settings: Settings) -> str:
    if settings.euri_api_key is None:
        raise ValueError("EURI_API_KEY is not set")
    return settings.euri_api_key.get_secret_value()


def build_chat_model(settings: Settings, model: str | None = None, *, is_fallback: bool = False) -> BaseChatModel:
    name = model or settings.llm_model
    return ChatOpenAI(
        model=name,
        api_key=_api_key(settings),
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        callbacks=[FallbackCounter(name)] if is_fallback else None,
    )


def build_fallback_model(settings: Settings, model: str) -> BaseChatModel | None:
    return build_chat_model(settings, model, is_fallback=True) if model else None


# Errors worth retrying on a different model: rate limits / daily quota, outages, timeouts, 5xx.
# Also 4xx from the gateway, since a model-specific rejection may not apply to the fallback.
FALLBACK_EXCEPTIONS: tuple[type[BaseException], ...] = (openai.APIError,)


def build_embeddings(settings: Settings) -> Embeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=_api_key(settings),
        base_url=settings.llm_base_url,
        # Send raw strings, not tiktoken IDs: non-OpenAI gateways don't accept token arrays.
        check_embedding_ctx_length=False,
        max_retries=settings.llm_max_retries,
    )


def build_engine(settings: Settings) -> Engine:
    url = settings.sqlalchemy_database_url
    return create_engine(
        url,
        connect_args=connect_args_for(url),
        pool_pre_ping=True,  # survives Supabase's pooler dropping idle connections
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
    )


SUPABASE_TRANSACTION_POOLER_PORT = 6543


def connect_args_for(url: str) -> dict[str, object]:
    """Supabase's transaction pooler can hand each transaction a different backend connection,
    so server-side prepared statements (which psycopg creates automatically) break there."""
    if make_url(url).port == SUPABASE_TRANSACTION_POOLER_PORT:
        return {"prepare_threshold": None}
    return {}


def build_vector_store(settings: Settings, embeddings: Embeddings, engine: Engine) -> PGVector:
    store = PGVector(
        embeddings=embeddings,
        connection=engine,
        collection_name=settings.collection_name,
        embedding_length=settings.embedding_dim,
        use_jsonb=True,
    )
    logger.info("vector store ready", extra={"collection": settings.collection_name})
    return store


def database_is_reachable(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("database readiness check failed", exc_info=True)
        return False
