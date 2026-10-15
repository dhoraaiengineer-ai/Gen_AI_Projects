"""Provider-specific implementations (OpenAI-compatible chat and embedding models, Postgres/pgvector).
Only this module and app/container.py import provider SDKs; everything else depends on app.rag.interfaces."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import openai
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector
from pydantic import SecretStr
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from app.core.errors import AppError, ProviderError, ProviderQuotaError, ProviderUnavailableError
from app.core.metrics import LLM_TOKENS
from app.rag.gateway import current_task
from app.rag.interfaces import IndexedChunk, RegistryEntry, SearchFilter

logger = logging.getLogger(__name__)

_QUOTA_WORDS = re.compile(
    r"quota|rate.?limit|limit (exceeded|reached)|exceeded|insufficient|credits?|too many requests", re.I
)


def classify_provider_exception(exc: Exception, model: str) -> AppError:
    """Map SDK errors to domain errors: quota -> 429, error -> 502, unreachable -> 503."""
    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, openai.RateLimitError):
        return ProviderQuotaError(retry_after=_retry_after(exc))
    if isinstance(exc, openai.APIConnectionError):  # includes APITimeoutError
        return ProviderUnavailableError()
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        if status == 402 or (status == 403 and _QUOTA_WORDS.search(str(exc.message) + str(exc.body))):
            # Some gateways report a spent quota as 403 (or 402).
            return ProviderQuotaError()
        if status in (502, 503, 504):
            return ProviderUnavailableError()
        return ProviderError()
    return ProviderError()


def _retry_after(exc: openai.APIStatusError) -> int | None:
    try:
        value = exc.response.headers.get("retry-after")
        return int(float(value)) if value else None
    except (ValueError, AttributeError):
        return None


# ---- chat ---------------------------------------------------------------------------------------
class OpenAICompatibleChatModel:
    """Chat model over any OpenAI-compatible endpoint (EURI, Gemini, Groq)."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: SecretStr,
        timeout: float,
        max_tokens: int,
        reasoning_effort: str | None = None,
        cache: Any = None,
    ) -> None:
        self.name = f"{provider}:{model}"
        self._max_tokens = max_tokens
        kwargs: dict[str, Any] = {}
        if reasoning_effort:
            # Reasoning models (gpt-oss, Gemini thinking) otherwise spend max_tokens on thinking.
            kwargs["reasoning_effort"] = reasoning_effort
        if cache is not None:
            kwargs["cache"] = cache
        self._llm = ChatOpenAI(
            model=model, base_url=base_url, api_key=api_key, timeout=timeout, max_retries=1, **kwargs
        )

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        try:
            msg = self._llm.invoke(
                [SystemMessage(system), HumanMessage(user)],
                temperature=temperature,
                max_tokens=max_tokens or self._max_tokens,
            )
        except Exception as exc:
            err = classify_provider_exception(exc, self.name)
            logger.warning(
                "provider call failed",
                extra={"model": self.name, "error": type(exc).__name__, "mapped": type(err).__name__},
            )
            raise err from exc
        usage = getattr(msg, "usage_metadata", None)  # absent on cached responses
        if usage:
            task = current_task.get()
            LLM_TOKENS.labels(task, self.name, "input").inc(int(usage.get("input_tokens") or 0))
            LLM_TOKENS.labels(task, self.name, "output").inc(int(usage.get("output_tokens") or 0))
        content = msg.content
        return (
            content
            if isinstance(content, str)
            else "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        )


class UnconfiguredChatModel:
    """Used when no API key is configured: every call fails as 'unavailable' (503)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        raise ProviderUnavailableError("No model provider is configured.")


# ---- database -----------------------------------------------------------------------------------
def make_engine(database_url: SecretStr, pool_size: int = 5) -> Engine:
    # Supabase's transaction pooler (port 6543) does not support prepared statements.
    return create_engine(
        database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=2,
        connect_args=_connect_args(database_url),
    )


def _connect_args(database_url: SecretStr) -> dict[str, Any]:
    from sqlalchemy.engine import make_url

    args: dict[str, Any] = {"prepare_threshold": None, "connect_timeout": 10}
    host = make_url(database_url.get_secret_value()).host or ""
    if host not in {"localhost", "127.0.0.1", "postgres", "pgvector", "db"}:
        args["sslmode"] = "require"  # encryption in transit to managed Postgres
    return args


class SqlAlchemyProbe:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ping(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("database ping failed", extra={"error": type(exc).__name__})
            return False


# ---- embeddings ---------------------------------------------------------------------------------
class OpenAICompatibleEmbedder:
    """Embeddings over an OpenAI-compatible endpoint (EURI text-embedding-3-small by default)."""

    def __init__(
        self, *, provider: str, model: str, base_url: str, api_key: SecretStr, dimensions: int, timeout: float
    ) -> None:
        self.name = f"{provider}:{model}"
        self.dimensions = dimensions
        self._emb = OpenAIEmbeddings(
            model=model,
            base_url=base_url,
            api_key=api_key,
            dimensions=dimensions,
            # Gateways are not OpenAI: skip tiktoken length checks (which also download encodings).
            check_embedding_ctx_length=False,
            max_retries=4,  # more retries than chat: ingest batches are idempotent
            chunk_size=64,
            timeout=timeout,
        )

    def _call(self, fn: Any, arg: Any) -> Any:
        try:
            return fn(arg)
        except Exception as exc:
            err = classify_provider_exception(exc, self.name)
            logger.warning(
                "embedding call failed",
                extra={"model": self.name, "error": type(exc).__name__, "mapped": type(err).__name__},
            )
            raise err from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._call(self._emb.embed_documents, texts)
        self._check(vectors)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vector = self._call(self._emb.embed_query, text)
        self._check([vector])
        return vector

    def _check(self, vectors: list[list[float]]) -> None:
        if vectors and len(vectors[0]) != self.dimensions:
            # Mis-sized embeddings would silently corrupt retrieval.
            raise ProviderError(f"Embedding size {len(vectors[0])} != configured {self.dimensions}.")


class UnconfiguredEmbedder:
    def __init__(self, name: str, dimensions: int) -> None:
        self.name = name
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ProviderUnavailableError("No embedding provider is configured.")

    def embed_query(self, text: str) -> list[float]:
        raise ProviderUnavailableError("No embedding provider is configured.")


class _NoEmbeddings(Embeddings):
    """PGVector requires an Embeddings object; vectors are always computed by the Embedder instead."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embeddings are computed outside PGVector")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("embeddings are computed outside PGVector")


# ---- pgvector index -----------------------------------------------------------------------------
def filter_sql(f: SearchFilter, params: dict[str, Any]) -> str:
    """WHERE fragment over langchain_pg_embedding.cmetadata (same semantics as metadata_matches)."""
    clauses = []
    if f.trusted_only or f.owner_id is None:
        clauses.append("(e.cmetadata->>'trusted')::boolean IS TRUE")
    else:
        params["owner_id"] = f.owner_id
        clauses.append("((e.cmetadata->>'trusted')::boolean IS TRUE OR e.cmetadata->>'owner_id' = :owner_id)")
    for key, values in (("publisher", f.publishers), ("doc_id", f.doc_ids), ("doc_type", f.doc_types)):
        if values:
            names = []
            for i, v in enumerate(values):
                params[f"{key}_{i}"] = v
                names.append(f":{key}_{i}")
            clauses.append(f"e.cmetadata->>'{key}' IN ({', '.join(names)})")
    if f.jurisdiction:
        params["jurisdiction"] = f.jurisdiction
        clauses.append("e.cmetadata->>'jurisdiction' = :jurisdiction")
    if f.date_from:
        params["date_from"] = f.date_from.isoformat()
        clauses.append("e.cmetadata->>'publication_date' >= :date_from")
    if f.date_to:
        params["date_to"] = f.date_to.isoformat()
        clauses.append("e.cmetadata->>'publication_date' <= :date_to")
    return " AND ".join(clauses)


# BM25-style keyword search over Postgres full-text search: IDF from document frequencies in the
# (filtered) collection, saturating term frequency and length normalisation (k1=1.2, b=0.75).
BM25_SQL = """
WITH qterms AS (
    SELECT DISTINCT u.lexeme FROM unnest(to_tsvector('english', :query)) AS u
),
docs AS (
    SELECT e.id, e.document, e.cmetadata, e.tsv, GREATEST(length(e.tsv), 1)::float AS dl
    FROM langchain_pg_embedding e
    JOIN langchain_pg_collection c ON c.uuid = e.collection_id
    WHERE c.name = :collection AND {where}
),
stats AS (SELECT count(*)::float AS n, COALESCE(avg(dl), 1)::float AS avgdl FROM docs),
tf AS (
    SELECT d.id, u.lexeme, COALESCE(array_length(u.positions, 1), 1)::float AS tf
    FROM docs d, unnest(d.tsv) AS u
    WHERE u.lexeme IN (SELECT lexeme FROM qterms)
),
df AS (SELECT lexeme, count(*)::float AS df FROM tf GROUP BY lexeme)
SELECT d.id, d.document, d.cmetadata,
       sum(ln(1 + (s.n - df.df + 0.5) / (df.df + 0.5))
           * tf.tf * 2.2 / (tf.tf + 1.2 * (0.25 + 0.75 * d.dl / s.avgdl))) AS score
FROM tf
JOIN docs d ON d.id = tf.id
JOIN df ON df.lexeme = tf.lexeme
CROSS JOIN stats s
GROUP BY d.id, d.document, d.cmetadata
ORDER BY score DESC
LIMIT :k
"""

VECTOR_SQL = """
SELECT e.id, e.document, e.cmetadata, 1 - (e.embedding <=> CAST(:vector AS vector)) AS score
FROM langchain_pg_embedding e
JOIN langchain_pg_collection c ON c.uuid = e.collection_id
WHERE c.name = :collection AND {where}
ORDER BY e.embedding <=> CAST(:vector AS vector)
LIMIT :k
"""


class PgVectorIndex:
    """Chunks in Supabase Postgres via langchain-postgres PGVector (cosine), plus BM25-style FTS."""

    def __init__(self, engine: Engine, dimensions: int) -> None:
        self._engine = engine
        self._dimensions = dimensions
        self._stores: dict[str, PGVector] = {}

    def store(self, collection: str) -> PGVector:
        if collection not in self._stores:
            self._stores[collection] = PGVector(
                embeddings=_NoEmbeddings(),
                connection=self._engine,
                collection_name=collection,
                embedding_length=self._dimensions,
                use_jsonb=True,
                create_extension=False,  # done once by scripts/db_init.py
            )
        return self._stores[collection]

    def upsert(self, collection: str, chunks: list[IndexedChunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        self.store(collection).add_embeddings(
            texts=[c.text for c in chunks],
            embeddings=vectors,
            metadatas=[c.metadata for c in chunks],
            ids=[c.id for c in chunks],
        )

    def delete(self, collection: str, ids: list[str]) -> None:
        if ids:
            self.store(collection).delete(ids=ids)

    def _rows(self, sql: str, params: dict[str, Any]) -> list[tuple[IndexedChunk, float]]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).all()
        return [
            (IndexedChunk(id=str(r.id), text=r.document, metadata=dict(r.cmetadata)), float(r.score))
            for r in rows
        ]

    def vector_search(
        self, collection: str, vector: list[float], k: int, filters: SearchFilter
    ) -> list[tuple[IndexedChunk, float]]:
        params: dict[str, Any] = {
            "collection": collection,
            "k": k,
            "vector": "[" + ",".join(map(str, vector)) + "]",
        }
        return self._rows(VECTOR_SQL.format(where=filter_sql(filters, params)), params)

    def keyword_search(
        self, collection: str, query: str, k: int, filters: SearchFilter
    ) -> list[tuple[IndexedChunk, float]]:
        params: dict[str, Any] = {"collection": collection, "k": k, "query": query}
        return self._rows(BM25_SQL.format(where=filter_sql(filters, params)), params)


# ---- ingest registry ----------------------------------------------------------------------------
_meta = MetaData()
registry_table = Table(
    "medinfo_ingest_registry",
    _meta,
    Column("doc_id", String(64), primary_key=True),
    Column("collection", String(200), nullable=False),
    Column("filename", String(300), nullable=False),
    Column("file_hash", String(64), nullable=False),
    Column("chunk_hashes", JSONB, nullable=False),
    Column("provenance", JSONB, nullable=False),
    Column("trusted", Boolean, nullable=False),
    Column("owner_id", String(64), nullable=True, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
parents_table = Table(
    "medinfo_parent_chunks",
    _meta,
    Column("parent_id", String(64), primary_key=True),
    Column(
        "doc_id",
        String(64),
        ForeignKey("medinfo_ingest_registry.doc_id", ondelete="CASCADE"),
        index=True,
    ),
    Column("text", Text, nullable=False),
)


class SqlRegistry:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ensure_schema(self) -> None:
        _meta.create_all(self._engine)

    @staticmethod
    def _entry(row: Any) -> RegistryEntry:
        return RegistryEntry(
            doc_id=row.doc_id,
            collection=row.collection,
            filename=row.filename,
            file_hash=row.file_hash,
            chunk_hashes=dict(row.chunk_hashes),
            provenance=dict(row.provenance),
            trusted=row.trusted,
            owner_id=row.owner_id,
            updated_at=row.updated_at.isoformat(timespec="seconds") if row.updated_at else "",
        )

    def get(self, doc_id: str) -> RegistryEntry | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(registry_table).where(registry_table.c.doc_id == doc_id)).first()
        return self._entry(row) if row else None

    def put(self, entry: RegistryEntry) -> None:
        values = {
            "doc_id": entry.doc_id,
            "collection": entry.collection,
            "filename": entry.filename,
            "file_hash": entry.file_hash,
            "chunk_hashes": entry.chunk_hashes,
            "provenance": entry.provenance,
            "trusted": entry.trusted,
            "owner_id": entry.owner_id,
            "updated_at": datetime.fromisoformat(entry.updated_at) if entry.updated_at else datetime.now(UTC),
        }
        stmt = pg_insert(registry_table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["doc_id"], set_={k: stmt.excluded[k] for k in values if k != "doc_id"}
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)
            conn.execute(delete(parents_table).where(parents_table.c.doc_id == entry.doc_id))
            if entry.parents:
                conn.execute(
                    parents_table.insert(),
                    [
                        {"parent_id": pid, "doc_id": entry.doc_id, "text": t}
                        for pid, t in entry.parents.items()
                    ],
                )

    def delete(self, doc_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(parents_table).where(parents_table.c.doc_id == doc_id))
            conn.execute(delete(registry_table).where(registry_table.c.doc_id == doc_id))

    def list(self, *, trusted: bool | None = None, owner_id: str | None = None) -> list[RegistryEntry]:
        q = select(registry_table).order_by(registry_table.c.filename)
        if trusted is not None:
            q = q.where(registry_table.c.trusted == trusted)
        if owner_id is not None:
            q = q.where(registry_table.c.owner_id == owner_id)
        with self._engine.connect() as conn:
            return [self._entry(r) for r in conn.execute(q).all()]

    def parent_text(self, parent_id: str) -> str | None:
        with self._engine.connect() as conn:
            return conn.execute(
                select(parents_table.c.text).where(parents_table.c.parent_id == parent_id)
            ).scalar_one_or_none()


def init_database(engine: Engine, collections: list[str], dimensions: int) -> None:
    """One-off, idempotent schema setup (scripts/db_init.py): pgvector extension, PGVector tables and
    collections, the FTS column + indexes used by keyword search, and the app tables."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    index = PgVectorIndex(engine, dimensions)
    for name in collections:
        index.store(name)  # creates the PGVector tables and the collection row
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE langchain_pg_embedding ADD COLUMN IF NOT EXISTS tsv tsvector "
                "GENERATED ALWAYS AS (to_tsvector('english', coalesce(document, ''))) STORED"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_medinfo_embedding_tsv ON langchain_pg_embedding USING gin (tsv)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_medinfo_embedding_meta "
                "ON langchain_pg_embedding USING gin (cmetadata jsonb_path_ops)"
            )
        )
    SqlRegistry(engine).ensure_schema()
    logger.info("database initialised", extra={"collections": collections})


# ---- Redis ----------------------------------------------------------------------------------------
class RedisKV:
    """KeyValueStore over Redis (caches, short-term memory, rate limits)."""

    def __init__(self, url: SecretStr) -> None:
        import redis

        self._r = redis.Redis.from_url(
            url.get_secret_value(), decode_responses=True, socket_timeout=2, socket_connect_timeout=2
        )

    def get(self, key: str) -> str | None:
        return self._r.get(key)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._r.set(key, value, ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._r.delete(key)

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        pipe = self._r.pipeline()
        pipe.incr(key)
        if ttl_seconds:
            pipe.expire(key, ttl_seconds, nx=True)  # TTL only set when the window starts
        return int(pipe.execute()[0])

    def ttl(self, key: str) -> int:
        return int(self._r.ttl(key))

    def list_push(self, key: str, value: str, max_len: int, ttl_seconds: int | None = None) -> None:
        pipe = self._r.pipeline()
        pipe.rpush(key, value)
        pipe.ltrim(key, -max_len, -1)
        if ttl_seconds:
            pipe.expire(key, ttl_seconds)
        pipe.execute()

    def list_range(self, key: str) -> list[str]:
        return list(self._r.lrange(key, 0, -1))

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except Exception:
            return False


# ---- long-term conversation store ------------------------------------------------------------------
conversations_table = Table(
    "medinfo_conversations",
    _meta,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), nullable=False, index=True),
    Column("title_enc", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, index=True),
)
messages_table = Table(
    "medinfo_messages",
    _meta,
    Column("id", String(64), primary_key=True),
    Column(
        "conversation_id", String(64), ForeignKey("medinfo_conversations.id", ondelete="CASCADE"), index=True
    ),
    Column("role", String(16), nullable=False),
    Column("text_enc", Text, nullable=False),
    Column("meta", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class SqlConversationStore:
    """Conversations in Postgres. Titles and message text are encrypted by the app before storage."""

    def __init__(self, engine: Engine, cipher: Any) -> None:
        self._engine = engine
        self._cipher = cipher

    def _conv(self, row: Any) -> Any:
        from app.rag.memory import Conversation

        return Conversation(
            id=row.id,
            user_id=row.user_id,
            title=self._cipher.decrypt(row.title_enc),
            created_at=row.created_at.isoformat(timespec="seconds"),
            updated_at=row.updated_at.isoformat(timespec="seconds"),
        )

    def create(self, user_id: str, title: str) -> Any:
        import uuid

        ts = datetime.now(UTC)
        values = {
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "title_enc": self._cipher.encrypt(title),
            "created_at": ts,
            "updated_at": ts,
        }
        with self._engine.begin() as conn:
            conn.execute(conversations_table.insert().values(**values))
        return self._conv(type("Row", (), values))

    def get(self, conv_id: str, user_id: str) -> Any:
        q = select(conversations_table).where(
            conversations_table.c.id == conv_id, conversations_table.c.user_id == user_id
        )
        with self._engine.connect() as conn:
            row = conn.execute(q).first()
        return self._conv(row) if row else None

    def append(self, conv_id: str, user_id: str, message: Any) -> None:
        import uuid

        from app.rag.memory import ConversationNotFoundError

        ts = datetime.fromisoformat(message.created_at)
        with self._engine.begin() as conn:
            updated = conn.execute(
                conversations_table.update()
                .where(conversations_table.c.id == conv_id, conversations_table.c.user_id == user_id)
                .values(updated_at=ts)
            )
            if updated.rowcount == 0:
                raise ConversationNotFoundError()
            conn.execute(
                messages_table.insert().values(
                    id=uuid.uuid4().hex,
                    conversation_id=conv_id,
                    role=message.role,
                    text_enc=self._cipher.encrypt(message.text),
                    meta=message.meta,
                    created_at=ts,
                )
            )

    def messages(self, conv_id: str, user_id: str, limit: int = 200) -> list[Any]:
        from app.rag.memory import ConversationNotFoundError, Message

        if self.get(conv_id, user_id) is None:
            raise ConversationNotFoundError()
        q = (
            select(messages_table)
            .where(messages_table.c.conversation_id == conv_id)
            .order_by(messages_table.c.created_at.desc())
            .limit(limit)
        )
        with self._engine.connect() as conn:
            rows = list(reversed(conn.execute(q).all()))
        return [
            Message(
                role=r.role,
                text=self._cipher.decrypt(r.text_enc),
                created_at=r.created_at.isoformat(timespec="seconds"),
                meta=dict(r.meta),
            )
            for r in rows
        ]

    def list(self, user_id: str, limit: int = 50) -> list[Any]:
        q = (
            select(conversations_table)
            .where(conversations_table.c.user_id == user_id)
            .order_by(conversations_table.c.updated_at.desc())
            .limit(limit)
        )
        with self._engine.connect() as conn:
            return [self._conv(r) for r in conn.execute(q).all()]

    def delete(self, conv_id: str, user_id: str) -> bool:
        with self._engine.begin() as conn:
            conn.execute(
                delete(messages_table).where(
                    messages_table.c.conversation_id.in_(
                        select(conversations_table.c.id).where(
                            conversations_table.c.id == conv_id, conversations_table.c.user_id == user_id
                        )
                    )
                )
            )
            res = conn.execute(
                delete(conversations_table).where(
                    conversations_table.c.id == conv_id, conversations_table.c.user_id == user_id
                )
            )
        return res.rowcount > 0

    def delete_all(self, user_id: str) -> int:
        ids = select(conversations_table.c.id).where(conversations_table.c.user_id == user_id)
        with self._engine.begin() as conn:
            conn.execute(delete(messages_table).where(messages_table.c.conversation_id.in_(ids)))
            res = conn.execute(delete(conversations_table).where(conversations_table.c.user_id == user_id))
        return int(res.rowcount)

    def purge_older_than(self, cutoff: datetime) -> int:
        old = select(conversations_table.c.id).where(conversations_table.c.updated_at < cutoff)
        with self._engine.begin() as conn:
            conn.execute(delete(messages_table).where(messages_table.c.conversation_id.in_(old)))
            res = conn.execute(delete(conversations_table).where(conversations_table.c.updated_at < cutoff))
        return int(res.rowcount)


# ---- web search (Tavily) -------------------------------------------------------------------------
class TavilyWebSearch:
    """Tavily search restricted to an allow-list of medical domains. Results are UNTRUSTED data."""

    URL = "https://api.tavily.com/search"

    def __init__(self, api_key: SecretStr, allowed_domains: list[str], timeout: float = 15.0) -> None:
        self._key = api_key
        self._domains = [d.lower().lstrip(".") for d in allowed_domains]
        self._timeout = timeout

    def allowed(self, url: str) -> bool:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in self._domains)

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        import httpx

        try:
            resp = httpx.post(
                self.URL,
                json={
                    "query": query,
                    "max_results": max_results,
                    "include_domains": self._domains,
                    "search_depth": "basic",
                },
                headers={"Authorization": f"Bearer {self._key.get_secret_value()}"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Web search is unavailable.") from exc
        if resp.status_code in (429, 432, 433):
            raise ProviderQuotaError("Web search quota reached.")
        if resp.status_code >= 400:
            raise ProviderError("Web search failed.")
        results = resp.json().get("results") or []
        # Defence in depth: never trust the provider to honour include_domains.
        kept = [r for r in results if isinstance(r, dict) and self.allowed(str(r.get("url", "")))]
        logger.info("web search", extra={"results": len(results), "kept": len(kept)})
        return kept


# ---- tool-calling models (research agent) ----------------------------------------------------------
class OpenAICompatibleToolModel:
    """LangChain chat model with tools bound, for the research agent's tool loop."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: SecretStr,
        timeout: float,
        reasoning_effort: str | None = None,
    ) -> None:
        self.name = f"{provider}:{model}"
        kwargs: dict[str, Any] = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        self._llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=1,
            temperature=0,
            **kwargs,
        )

    def invoke(self, messages: list[Any], tools: list[Any]) -> Any:
        try:
            return self._llm.bind_tools(tools).invoke(messages)
        except Exception as exc:
            err = classify_provider_exception(exc, self.name)
            logger.warning(
                "tool model call failed",
                extra={"model": self.name, "error": type(exc).__name__, "mapped": type(err).__name__},
            )
            raise err from exc


# ---- clinician review store ---------------------------------------------------------------------------
review_table = Table(
    "medinfo_review_items",
    _meta,
    Column("id", String(64), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("source", String(16), nullable=False),
    Column("question", Text, nullable=False),
    Column("answer_json", Text, nullable=False),
    Column("status", String(16), nullable=False, index=True),
    Column("verdict", String(32), nullable=True),
    Column("notes", Text, nullable=True),
    Column("reviewer_id", String(64), nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
)


class SqlReviewStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @staticmethod
    def _item(row: Any) -> Any:
        from app.rag.review import ReviewItem

        return ReviewItem(
            id=row.id,
            created_at=row.created_at.isoformat(timespec="seconds"),
            source=row.source,
            question=row.question,
            answer_json=row.answer_json,
            status=row.status,
            verdict=row.verdict,
            notes=row.notes,
            reviewer_id=row.reviewer_id,
            reviewed_at=row.reviewed_at.isoformat(timespec="seconds") if row.reviewed_at else None,
        )

    def add(self, item: Any) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                review_table.insert().values(
                    id=item.id,
                    created_at=datetime.fromisoformat(item.created_at),
                    source=item.source,
                    question=item.question,
                    answer_json=item.answer_json,
                    status=item.status,
                )
            )

    def queue(self, limit: int = 50) -> list[Any]:
        q = (
            select(review_table)
            .where(review_table.c.status == "pending")
            .order_by(review_table.c.created_at)
            .limit(limit)
        )
        with self._engine.connect() as conn:
            return [self._item(r) for r in conn.execute(q).all()]

    def get(self, item_id: str) -> Any:
        with self._engine.connect() as conn:
            row = conn.execute(select(review_table).where(review_table.c.id == item_id)).first()
        return self._item(row) if row else None

    def record(self, item_id: str, *, verdict: str, notes: str | None, reviewer_id: str, at: str) -> Any:
        from app.rag.review import ReviewItemNotFoundError

        with self._engine.begin() as conn:
            res = conn.execute(
                review_table.update()
                .where(review_table.c.id == item_id)
                .values(
                    status="reviewed",
                    verdict=verdict,
                    notes=notes,
                    reviewer_id=reviewer_id,
                    reviewed_at=datetime.fromisoformat(at),
                )
            )
        if res.rowcount == 0:
            raise ReviewItemNotFoundError()
        return self.get(item_id)

    def all(self) -> list[Any]:
        with self._engine.connect() as conn:
            return [
                self._item(r)
                for r in conn.execute(select(review_table).order_by(review_table.c.created_at)).all()
            ]


# ---- evaluation run history -------------------------------------------------------------------------
eval_runs_table = Table(
    "medinfo_eval_runs",
    _meta,
    Column("id", String(64), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("label", String(200), nullable=False),
    Column("params", JSONB, nullable=False),
    Column("metrics", JSONB, nullable=False),
)


class SqlEvalRunStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, run: Any) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                eval_runs_table.insert().values(
                    id=run.id,
                    created_at=datetime.fromisoformat(run.created_at),
                    label=run.label,
                    params=run.params,
                    metrics=run.metrics,
                )
            )

    def latest(self, limit: int = 20) -> list[Any]:
        from app.rag.evaluation import EvalRun

        q = select(eval_runs_table).order_by(eval_runs_table.c.created_at.desc()).limit(limit)
        with self._engine.connect() as conn:
            return [
                EvalRun(
                    id=r.id,
                    created_at=r.created_at.isoformat(timespec="seconds"),
                    label=r.label,
                    params=dict(r.params),
                    metrics=dict(r.metrics),
                )
                for r in conn.execute(q).all()
            ]
