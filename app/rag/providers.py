"""Factories for the external dependencies: chat model, embeddings, vector store.

Everything provider-specific lives here, so swapping EURI for another OpenAI-compatible
gateway (or Supabase for another Postgres) is a config change, not a code change.
Chat/embedding providers, all through the OpenAI client: EURI (gateway, default), Gemini and Groq (direct).
Web search for the research agent: Tavily.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

import httpx
import openai
import redis
from langchain_core.caches import BaseCache
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector
from pydantic import PrivateAttr
from sqlalchemy import Connection, Engine, create_engine, make_url, text

from app.config import Provider, Settings, parse_model_chain
from app.core.circuit import BreakerRegistry, CircuitBreaker, CircuitOpenError
from app.core.metrics import FallbackCounter, LLMLatencyCallback
from app.rag.cache import InMemoryKeyValueStore, KeyValueStore
from app.rag.filters import MetadataFilter
from app.rag.golden import GoldenItem
from app.rag.memory import ChatTurn, SessionSummary
from app.rag.registry import DocumentRecord
from app.rag.websearch import WebResult, WebSearchError

logger = logging.getLogger(__name__)


def _endpoint(settings: Settings, provider: Provider) -> tuple[str, str]:
    """(api key, base URL) for a provider. Fails at startup if the key is missing."""
    if provider == "gemini":
        if settings.gemini_api_key is None:
            raise ValueError("GEMINI_API_KEY is not set, but a Gemini provider is configured")
        return settings.gemini_api_key.get_secret_value(), settings.gemini_base_url
    if provider == "groq":
        if settings.groq_api_key is None:
            raise ValueError("GROQ_API_KEY is not set, but a Groq provider is configured")
        return settings.groq_api_key.get_secret_value(), settings.groq_base_url
    if settings.euri_api_key is None:
        raise ValueError("EURI_API_KEY is not set")
    return settings.euri_api_key.get_secret_value(), settings.llm_base_url


def _counts_as_outage(exc: BaseException) -> bool:
    """Quota, rate limit, 5xx, timeouts and connection errors trip the breaker; a bad request doesn't."""
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code not in (400, 404, 422)
    return isinstance(exc, openai.APIError)


class GuardedChatOpenAI(ChatOpenAI):
    """ChatOpenAI behind a circuit breaker. Overriding _generate covers plain calls and bind_tools() alike,
    and LangChain's response cache is checked before _generate, so cache hits never touch the breaker."""

    _breaker: CircuitBreaker | None = PrivateAttr(default=None)

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        breaker = self._breaker
        if breaker is None:
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        breaker.before_call()
        try:
            result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            if _counts_as_outage(exc):
                breaker.record_failure()
            raise
        breaker.record_success()
        return result


def build_chat_model(
    settings: Settings,
    model: str | None = None,
    *,
    provider: Provider = "euri",
    is_fallback: bool = False,
    breakers: BreakerRegistry | None = None,
    cache: BaseCache | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    name = model or settings.llm_model
    api_key, base_url = _endpoint(settings, provider)
    llm = GuardedChatOpenAI(
        model=name,
        api_key=api_key,
        base_url=base_url,
        temperature=settings.llm_temperature if temperature is None else temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        callbacks=[LLMLatencyCallback(name), *([FallbackCounter(name)] if is_fallback else [])],
        # Reasoning models (Gemini 3, gpt-oss on Groq) think before answering, and thinking tokens count
        # against max_tokens: keep it short so RAG answers aren't cut off.
        reasoning_effort="low" if _is_reasoning_model(provider, name) else None,
        cache=cache,  # identical prompt + model + params -> stored response, no API call
    )
    if breakers is not None:
        llm._breaker = breakers.get(f"{provider}:{name}")
    return llm


def _is_reasoning_model(provider: Provider, model: str) -> bool:
    return provider == "gemini" or (provider == "groq" and "gpt-oss" in model)


def build_fallback_model(
    settings: Settings,
    model: str,
    provider: Provider = "euri",
    *,
    breakers: BreakerRegistry | None = None,
    cache: BaseCache | None = None,
) -> BaseChatModel | None:
    if not model:
        return None
    return build_chat_model(settings, model, provider=provider, is_fallback=True, breakers=breakers, cache=cache)


def build_fallback_chain(
    settings: Settings,
    first: tuple[Provider, str] | None,
    extra: str,
    *,
    breakers: BreakerRegistry | None = None,
    cache: BaseCache | None = None,
) -> list[BaseChatModel]:
    """The configured single fallback (if any), then the comma-separated "provider:model" extras, in order."""
    entries = ([first] if first and first[1] else []) + parse_model_chain(extra)
    return [
        build_chat_model(settings, model, provider=provider, is_fallback=True, breakers=breakers, cache=cache)
        for provider, model in entries
    ]


# Errors worth retrying on a different model: rate limits / daily quota, outages, timeouts, 5xx.
# Also 4xx from the gateway, since a model-specific rejection may not apply to the fallback.
# CircuitOpenError: the breaker skipped a provider that is down, so try the next one.
FALLBACK_EXCEPTIONS: tuple[type[BaseException], ...] = (openai.APIError, CircuitOpenError)


def build_embeddings(settings: Settings) -> Embeddings:
    api_key, base_url = _endpoint(settings, settings.embedding_provider)
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        base_url=base_url,
        # Send raw strings, not tiktoken IDs: non-OpenAI gateways don't accept token arrays.
        check_embedding_ctx_length=False,
        max_retries=settings.embedding_max_retries,  # the OpenAI client backs off exponentially on 429/5xx
        # Gemini's model defaults to 3072 dims; ask for the size the pgvector column was created with.
        dimensions=settings.embedding_dim if settings.embedding_provider == "gemini" else None,
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


# ---------- Ingest registry + golden dataset (plain tables next to the LangChain ones) ----------

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS rag_documents (
        collection   text NOT NULL,
        source       text NOT NULL,
        content_hash text NOT NULL,
        chunking     text NOT NULL,
        chunk_ids    jsonb NOT NULL,
        updated_at   timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (collection, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rag_golden_qa (
        collection text NOT NULL,
        id         text NOT NULL,
        source     text NOT NULL,
        question   text NOT NULL,
        answer     text NOT NULL,
        evidence   text NOT NULL,
        location   text,
        origin     text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (collection, id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS rag_golden_qa_source ON rag_golden_qa (collection, source)",
    """
    CREATE TABLE IF NOT EXISTS rag_conversation_messages (
        id         bigserial PRIMARY KEY,
        collection text NOT NULL,
        user_id    text NOT NULL,
        session_id text NOT NULL,
        role       text NOT NULL CHECK (role IN ('user', 'assistant')),
        content    text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS rag_conversation_session "
    "ON rag_conversation_messages (collection, user_id, session_id, id)",
)


def ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _SCHEMA:
            conn.execute(text(statement))


class PostgresDocumentRegistry:
    def __init__(self, engine: Engine, collection: str):
        self.engine = engine
        self.collection = collection

    def get(self, source: str) -> DocumentRecord | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT content_hash, chunking, chunk_ids FROM rag_documents WHERE collection = :c AND source = :s"
                ),
                {"c": self.collection, "s": source},
            ).first()
        return DocumentRecord(source, row.content_hash, row.chunking, tuple(row.chunk_ids)) if row else None

    def put(self, record: DocumentRecord) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO rag_documents (collection, source, content_hash, chunking, chunk_ids) "
                    "VALUES (:c, :s, :h, :k, CAST(:ids AS jsonb)) "
                    "ON CONFLICT (collection, source) DO UPDATE SET content_hash = EXCLUDED.content_hash, "
                    "chunking = EXCLUDED.chunking, chunk_ids = EXCLUDED.chunk_ids, updated_at = now()"
                ),
                {
                    "c": self.collection,
                    "s": record.source,
                    "h": record.content_hash,
                    "k": record.chunking,
                    "ids": json.dumps(list(record.chunk_ids)),
                },
            )

    def list(self) -> list[DocumentRecord]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT source, content_hash, chunking, chunk_ids FROM rag_documents WHERE collection = :c "
                    "ORDER BY source"
                ),
                {"c": self.collection},
            ).all()
        return [DocumentRecord(r.source, r.content_hash, r.chunking, tuple(r.chunk_ids)) for r in rows]

    def delete(self, source: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rag_documents WHERE collection = :c AND source = :s"),
                {"c": self.collection, "s": source},
            )


class PostgresGoldenStore:
    _COLUMNS = "id, source, question, answer, evidence, location, origin"

    def __init__(self, engine: Engine, collection: str):
        self.engine = engine
        self.collection = collection

    def upsert(self, items: Sequence[GoldenItem]) -> None:
        with self.engine.begin() as conn:
            self._insert(conn, items)

    def delete_source(self, source: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM rag_golden_qa WHERE collection = :c AND source = :s"),
                {"c": self.collection, "s": source},
            )
        return result.rowcount

    def replace_generated(self, source: str, items: Sequence[GoldenItem]) -> None:
        with self.engine.begin() as conn:  # one transaction: readers never see the source with no items
            conn.execute(
                text("DELETE FROM rag_golden_qa WHERE collection = :c AND source = :s AND origin = 'generated'"),
                {"c": self.collection, "s": source},
            )
            self._insert(conn, items)

    def list(self, source: str | None = None, limit: int | None = None) -> list[GoldenItem]:
        query = f"SELECT {self._COLUMNS} FROM rag_golden_qa WHERE collection = :c"
        params: dict[str, object] = {"c": self.collection}
        if source is not None:
            query += " AND source = :s"
            params["s"] = source
        query += " ORDER BY source, created_at, id"
        if limit:
            query += " LIMIT :n"
            params["n"] = limit
        with self.engine.connect() as conn:
            rows = conn.execute(text(query), params).all()
        return [GoldenItem(r.id, r.source, r.question, r.answer, r.evidence, r.location, r.origin) for r in rows]

    def _insert(self, conn: Connection, items: Sequence[GoldenItem]) -> None:
        if not items:
            return
        conn.execute(
            text(
                f"INSERT INTO rag_golden_qa (collection, {self._COLUMNS}) "
                "VALUES (:c, :id, :source, :question, :answer, :evidence, :location, :origin) "
                "ON CONFLICT (collection, id) DO UPDATE SET answer = EXCLUDED.answer, evidence = EXCLUDED.evidence, "
                "location = EXCLUDED.location, origin = EXCLUDED.origin"
            ),
            [{"c": self.collection, **asdict(item)} for item in items],
        )


# ---------- Web search (Tavily) ----------


class TavilyWebSearch:
    """Tavily's search REST API over httpx (already a dependency through the OpenAI client)."""

    URL = "https://api.tavily.com/search"

    def __init__(
        self, api_key: str, search_depth: str = "basic", timeout: float = 20.0, client: httpx.Client | None = None
    ):
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self.search_depth = search_depth
        self._client = client or httpx.Client(timeout=timeout)

    def search(self, query: str, max_results: int) -> list[WebResult]:
        payload = {"query": query, "max_results": max_results, "search_depth": self.search_depth}
        try:
            response = self._client.post(self.URL, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            # Tavily's error body says why (bad key, out of credits); it never echoes the key.
            raise WebSearchError(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise WebSearchError(f"{type(exc).__name__}: {exc}") from exc
        return [
            WebResult(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                content=str(item.get("content") or ""),
                score=float(item.get("score") or 0.0),
            )
            for item in data.get("results", [])
            if item.get("url")
        ]

    def close(self) -> None:
        self._client.close()


def build_web_search(settings: Settings) -> TavilyWebSearch | None:
    """None when no key is configured: the agent then only has the knowledge base tool."""
    if settings.tavily_api_key is None or not settings.tavily_api_key.get_secret_value():
        return None
    return TavilyWebSearch(
        settings.tavily_api_key.get_secret_value(), settings.web_search_depth, settings.web_search_timeout_seconds
    )


# ---------- Redis (cache + short-term memory) ----------


class RedisKeyValueStore:
    """KeyValueStore on Redis. Any Redis error is logged and treated as a miss / no-op, so a Redis outage
    makes the app slower (no cache) but never fails a request."""

    def __init__(self, client: "redis.Redis"):
        self.client = client

    def get(self, key: str) -> str | None:
        try:
            value = self.client.get(key)
        except redis.RedisError:
            logger.warning("redis get failed", exc_info=True)
            return None
        return value.decode() if isinstance(value, bytes) else value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self.client.set(key, value, ex=ttl_seconds if ttl_seconds > 0 else None)
        except redis.RedisError:
            logger.warning("redis set failed", exc_info=True)

    def incr(self, key: str) -> int:
        try:
            return int(self.client.incr(key))
        except redis.RedisError:
            logger.warning("redis incr failed", exc_info=True)
            return 0

    def delete_prefix(self, prefix: str) -> None:
        try:
            for key in self.client.scan_iter(match=f"{prefix}*", count=500):
                self.client.delete(key)
        except redis.RedisError:
            logger.warning("redis delete failed", exc_info=True)

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False


def build_kv_store(settings: Settings) -> KeyValueStore:
    if settings.redis_url is None:
        logger.warning("REDIS_URL not set: cache and short-term memory are in-process (not shared between pods)")
        return InMemoryKeyValueStore()
    client = redis.Redis.from_url(
        settings.redis_url.get_secret_value(), socket_timeout=2, socket_connect_timeout=2, health_check_interval=30
    )
    return RedisKeyValueStore(client)


# ---------- Long-term conversation memory (Postgres) ----------


class PostgresConversationStore:
    def __init__(self, engine: Engine, collection: str):
        self.engine = engine
        self.collection = collection

    def append(self, user_id: str, session_id: str, turns: Sequence[ChatTurn]) -> None:
        if not turns:
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO rag_conversation_messages (collection, user_id, session_id, role, content) "
                    "VALUES (:c, :u, :s, :r, :m)"
                ),
                [{"c": self.collection, "u": user_id, "s": session_id, "r": t.role, "m": t.content} for t in turns],
            )

    def history(self, user_id: str, session_id: str, limit: int) -> list[ChatTurn]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT role, content FROM (SELECT id, role, content FROM rag_conversation_messages "
                    "WHERE collection = :c AND user_id = :u AND session_id = :s ORDER BY id DESC LIMIT :n) t "
                    "ORDER BY id"
                ),
                {"c": self.collection, "u": user_id, "s": session_id, "n": limit},
            ).all()
        return [ChatTurn(r.role, r.content) for r in rows]

    def sessions(self, user_id: str, limit: int) -> list[SessionSummary]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT session_id, count(*) AS messages, max(created_at) AS updated_at, "
                    "(array_agg(content ORDER BY id) FILTER (WHERE role = 'user'))[1] AS title "
                    "FROM rag_conversation_messages WHERE collection = :c AND user_id = :u "
                    "GROUP BY session_id ORDER BY max(created_at) DESC LIMIT :n"
                ),
                {"c": self.collection, "u": user_id, "n": limit},
            ).all()
        return [SessionSummary(r.session_id, (r.title or "")[:80], r.messages, r.updated_at) for r in rows]


# ---------- Keyword search (Postgres full-text) for hybrid retrieval ----------


class PostgresKeywordSearch:
    """Keyword search with BM25-style IDF ranking, on Postgres full-text search.

    Query words are stemmed by Postgres ('english' config). A chunk scores the sum of the IDF of the query
    words it contains, so rare, specific words ("DOI", "ISSN", "S4") outweigh common ones ("article").
    It scans the collection's chunks per query: fine for thousands of chunks; for much larger collections
    store the tsvector in a generated column and rank over a GIN-indexed pre-filter instead."""

    _SQL = (  # {filters}: optional metadata conditions, see _metadata_sql
        "WITH terms AS ("
        "  SELECT DISTINCT word FROM unnest(tsvector_to_array(to_tsvector('english', :query))) AS word"
        "), docs AS ("
        "  SELECT e.id, e.document, e.cmetadata, to_tsvector('english', e.document) AS v"
        "  FROM langchain_pg_embedding e JOIN langchain_pg_collection c ON c.uuid = e.collection_id"
        "  WHERE c.name = :collection {filters}"
        "), idf AS ("
        "  SELECT t.word, ln(1 + ((SELECT count(*) FROM docs) - count(d.id) + 0.5) / (count(d.id) + 0.5)) AS idf"
        "  FROM terms t LEFT JOIN docs d ON d.v @@ CAST(quote_literal(t.word) AS tsquery)"
        "  GROUP BY t.word"
        ") "
        "SELECT d.id, d.document, d.cmetadata, sum(i.idf) AS rank "
        "FROM docs d JOIN idf i ON d.v @@ CAST(quote_literal(i.word) AS tsquery) "
        "GROUP BY d.id, d.document, d.cmetadata "
        "ORDER BY rank DESC LIMIT :k"
    )

    def __init__(self, engine: Engine, collection: str):
        self.engine = engine
        self.collection = collection

    def search(self, query: str, k: int, filters: MetadataFilter | None = None) -> list[tuple[Document, float]]:
        clauses, params = _metadata_sql(filters)
        sql = text(self._SQL.format(filters=clauses))
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(sql, {"query": query, "collection": self.collection, "k": k, **params}).all()
        except Exception:  # keyword search only improves ranking; vector results still answer the question
            logger.warning("keyword search failed", exc_info=True)
            return []
        return [
            (Document(id=str(r.id), page_content=r.document, metadata=r.cmetadata or {}), float(r.rank)) for r in rows
        ]


def _metadata_sql(filters: MetadataFilter | None) -> tuple[str, dict[str, object]]:
    """SQL conditions (with bound parameters) equivalent to to_pgvector_filter()."""
    if filters is None or filters.is_empty:
        return "", {}
    clauses, params = [], {}
    if filters.sources:
        clauses.append("e.cmetadata->>'source' = ANY(:f_sources)")
        params["f_sources"] = list(filters.sources)
    if filters.file_types:
        clauses.append("lower(e.cmetadata->>'source') LIKE ANY(:f_types)")
        params["f_types"] = [f"%.{t}" for t in filters.file_types]
    if filters.tags:
        clauses.append("coalesce(e.cmetadata->>'tags', '') ILIKE ANY(:f_tags)")
        params["f_tags"] = [f"%,{t},%" for t in filters.tags]
    return " AND " + " AND ".join(clauses), params


def ensure_keyword_index(engine: Engine) -> None:
    """GIN index for the full-text search. Run after PGVector has created its tables."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS rag_embedding_fts ON langchain_pg_embedding "
                "USING gin (to_tsvector('english', document))"
            )
        )
