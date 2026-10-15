"""Answer cache and LLM prompt cache.

Answer cache: keyed on the (PHI-redacted) question, scope, filters and the corpus version, so any trusted
document change invalidates it; per-user upload changes invalidate that user's entries. Only clean
answers are stored: never triage/emergency, refusals, not-covered, guardrail-flagged or follow-up answers.

LLM prompt cache: a LangChain BaseCache over the KV store whose deserialisation only ever rebuilds plain
AIMessage text (no pickle, no langchain `loads`), so a poisoned cache entry cannot instantiate objects."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any

from langchain_core.caches import RETURN_VAL_TYPE, BaseCache
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, Generation

from app.core.kv import KeyValueStore
from app.core.metrics import CACHE_EVENTS
from app.rag.interfaces import SearchFilter
from app.rag.schemas import ChatAnswer

logger = logging.getLogger(__name__)

CORPUS_VERSION_KEY = "medinfo:corpus_version"


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class CorpusVersion:
    """Monotonic counters bumped on every document change (trusted corpus, or one user's uploads)."""

    def __init__(self, kv: KeyValueStore) -> None:
        self._kv = kv

    def trusted(self) -> str:
        return self._kv.get(CORPUS_VERSION_KEY) or "0"

    def user(self, user_id: str) -> str:
        return self._kv.get(f"medinfo:user_docs_version:{user_id}") or "0"

    def bump(self, *, trusted: bool, user_id: str | None = None) -> None:
        if trusted:
            self._kv.incr(CORPUS_VERSION_KEY)
        elif user_id:
            self._kv.incr(f"medinfo:user_docs_version:{user_id}")


class AnswerCache:
    def __init__(self, kv: KeyValueStore, versions: CorpusVersion, ttl_seconds: int) -> None:
        self._kv = kv
        self._versions = versions
        self._ttl = ttl_seconds

    def key(self, question: str, scope: str, filters: SearchFilter, user_id: str) -> str:
        user_ver = self._versions.user(user_id)
        # Users without uploads share entries; a user with uploads gets their own (their docs may matter).
        owner = "shared" if user_ver == "0" or filters.trusted_only else f"user:{user_id}:{user_ver}"
        f = {
            "trusted_only": filters.trusted_only,
            "publishers": sorted(filters.publishers),
            "doc_ids": sorted(filters.doc_ids),
            "doc_types": sorted(filters.doc_types),
            "jurisdiction": filters.jurisdiction,
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
        }
        norm_q = " ".join(question.lower().split())
        return "medinfo:answer:" + _digest(
            norm_q, scope, json.dumps(f, sort_keys=True), self._versions.trusted(), owner
        )

    def get(self, key: str) -> ChatAnswer | None:
        try:
            raw = self._kv.get(key)
        except Exception as exc:
            logger.warning("answer cache unavailable", extra={"error": type(exc).__name__})
            return None
        if raw is None:
            CACHE_EVENTS.labels("answer", "miss").inc()
            return None
        try:
            answer = ChatAnswer.model_validate_json(raw)
        except ValueError:
            CACHE_EVENTS.labels("answer", "invalid").inc()
            return None
        CACHE_EVENTS.labels("answer", "hit").inc()
        return answer

    @staticmethod
    def cacheable(answer: ChatAnswer, *, flagged: bool, has_history: bool) -> bool:
        return (
            answer.kind == "answer"
            and answer.emergency is None
            and not flagged
            and not has_history
            and all(answer.safety.checks.values())
        )

    def put(self, key: str, answer: ChatAnswer) -> None:
        try:
            self._kv.set(key, answer.model_dump_json(), self._ttl)
            CACHE_EVENTS.labels("answer", "store").inc()
        except Exception as exc:
            logger.warning("answer cache write failed", extra={"error": type(exc).__name__})


class SafeLLMCache(BaseCache):
    """Prompt cache whose stored form is plain JSON text; only AIMessage text is ever reconstructed."""

    def __init__(self, kv: KeyValueStore, ttl_seconds: int) -> None:
        self._kv = kv
        self._ttl = ttl_seconds

    @staticmethod
    def _key(prompt: str, llm_string: str) -> str:
        return "medinfo:llm:" + _digest(prompt, llm_string)

    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        try:
            raw = self._kv.get(self._key(prompt, llm_string))
        except Exception:
            return None
        if raw is None:
            CACHE_EVENTS.labels("llm", "miss").inc()
            return None
        try:
            items = json.loads(raw)
            gens: list[Generation] = []
            for item in items:
                if (
                    not isinstance(item, dict)
                    or item.get("type") != "ai"
                    or not isinstance(item.get("text"), str)
                ):
                    raise ValueError("unexpected cached type")
                gens.append(ChatGeneration(message=AIMessage(content=item["text"])))
        except (ValueError, TypeError):
            CACHE_EVENTS.labels("llm", "invalid").inc()
            return None
        CACHE_EVENTS.labels("llm", "hit").inc()
        return gens

    def update(self, prompt: str, llm_string: str, return_val: Sequence[Generation]) -> None:
        items: list[dict[str, Any]] = []
        for gen in return_val:
            msg = getattr(gen, "message", None)
            if not isinstance(msg, AIMessage) or not isinstance(msg.content, str) or msg.tool_calls:
                return  # only cache plain text replies
            items.append({"type": "ai", "text": msg.content})
        try:
            self._kv.set(self._key(prompt, llm_string), json.dumps(items), self._ttl)
        except Exception as exc:
            logger.warning("llm cache write failed", extra={"error": type(exc).__name__})

    def clear(self, **kwargs: Any) -> None:  # entries expire by TTL
        return None


class CachedEmbedder:
    """Query-embedding cache: repeated or popular searches skip the embedding call.

    Key = sha256(model, dimensions, text) - the text itself is never stored, only its vector. Only
    `embed_query` is cached: document embeddings already skip unchanged chunks by content hash at ingest.
    A cache read/write failure never fails the search (it falls through to the model)."""

    def __init__(self, inner: Any, kv: KeyValueStore, ttl_seconds: int) -> None:
        self._inner = inner
        self._kv = kv
        self._ttl = ttl_seconds
        self.name = inner.name
        self.dimensions = inner.dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        key = "medinfo:emb:" + _digest(self.name, str(self.dimensions), text)
        try:
            hit = self._kv.get(key)
        except Exception as exc:
            logger.warning("embedding cache read failed", extra={"error": type(exc).__name__})
            hit = None
        if hit is not None:
            vector = json.loads(hit)
            if isinstance(vector, list) and len(vector) == self.dimensions:
                CACHE_EVENTS.labels("embedding", "hit").inc()
                return [float(x) for x in vector]
        CACHE_EVENTS.labels("embedding", "miss").inc()
        vector = self._inner.embed_query(text)
        try:
            self._kv.set(key, json.dumps(vector), self._ttl)
        except Exception as exc:
            logger.warning("embedding cache write failed", extra={"error": type(exc).__name__})
        return vector
