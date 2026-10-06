"""Caching for repeated questions and repeated prompts.

Two layers over one key-value store (Redis when REDIS_URL is set, in-process memory otherwise):

- AnswerCache: a repeated /query question (same normalized text, same top_k) returns the stored answer
  without retrieval or an LLM call. Any document upload, update or deletion bumps a "knowledge base
  version" that is part of every key, so answers never outlive the documents they were built from.
- PromptCache: LangChain's BaseCache, keyed on the exact prompt + model + parameters. Covers every LLM
  call (answers, follow-up rewriting, golden Q&A, judge). Prompts embed the retrieved context, so a
  document change naturally produces a different key.

The Redis store lives in providers.py. A store failure is a cache miss, never a failed request.
"""

import hashlib
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.caches import RETURN_VAL_TYPE, BaseCache
from langchain_core.load import dumps, loads
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, Generation
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Cached LLM responses only ever contain these. Restricting deserialization means a tampered cache entry
# can't make LangChain construct anything else (e.g. a model client pointed at another host).
_CACHED_TYPES = (ChatGeneration, Generation, AIMessage, AIMessageChunk, ChatGenerationChunk)

CACHE_REQUESTS = Counter("rag_cache_requests_total", "Cache lookups", ["cache", "outcome"])


class KeyValueStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

    def incr(self, key: str) -> int: ...

    def delete_prefix(self, prefix: str) -> None: ...


class InMemoryKeyValueStore:
    """Bounded, TTL-aware dict. Per process: fine for local dev and tests, not shared between pods."""

    def __init__(self, max_entries: int = 10_000, clock: Any = time.monotonic):
        self._data: OrderedDict[str, tuple[str, float | None]] = OrderedDict()
        self._max = max_entries
        self._clock = clock
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            value, expires = item
            if expires is not None and self._clock() >= expires:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (value, self._clock() + ttl_seconds if ttl_seconds > 0 else None)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def incr(self, key: str) -> int:
        with self._lock:
            value = int(self._data.get(key, ("0", None))[0]) + 1
            self._data[key] = (str(value), None)
            return value

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [k for k in self._data if k.startswith(prefix)]:
                del self._data[key]


def normalize_question(question: str) -> str:
    """'  What is the ISSN?? ' and 'what is the issn' share a cache entry."""
    return re.sub(r"\s+", " ", question).strip().rstrip("?!. ").lower()


def _digest(*parts: object) -> str:
    return hashlib.sha256("\x00".join(map(str, parts)).encode()).hexdigest()


class AnswerCache:
    def __init__(self, store: KeyValueStore, namespace: str, ttl_seconds: int):
        self.store = store
        self.namespace = namespace
        self.ttl = ttl_seconds

    def _version(self) -> str:
        return self.store.get(f"{self.namespace}:kb_version") or "0"

    def _key(self, question: str, top_k: int | None) -> str:
        return f"{self.namespace}:answer:{self._version()}:{_digest(normalize_question(question), top_k)}"

    def get(self, question: str, top_k: int | None) -> dict[str, Any] | None:
        raw = self.store.get(self._key(question, top_k))
        CACHE_REQUESTS.labels("answer", "hit" if raw else "miss").inc()
        return json.loads(raw) if raw else None

    def set(self, question: str, top_k: int | None, value: dict[str, Any]) -> None:
        self.store.set(self._key(question, top_k), json.dumps(value), self.ttl)

    def invalidate(self) -> None:
        """Documents changed: bump the version so every cached answer becomes unreachable (it then expires)."""
        self.store.incr(f"{self.namespace}:kb_version")
        logger.info("answer cache invalidated", extra={"namespace": self.namespace})


class PromptCache(BaseCache):
    """LangChain LLM response cache over the key-value store (pass as ChatOpenAI(cache=...))."""

    def __init__(self, store: KeyValueStore, namespace: str, ttl_seconds: int):
        self.store = store
        self.namespace = namespace
        self.ttl = ttl_seconds

    def _key(self, prompt: str, llm_string: str) -> str:
        return f"{self.namespace}:prompt:{_digest(llm_string, prompt)}"

    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        raw = self.store.get(self._key(prompt, llm_string))
        CACHE_REQUESTS.labels("prompt", "hit" if raw else "miss").inc()
        if not raw:
            return None
        try:
            return loads(raw, allowed_objects=_CACHED_TYPES)
        except Exception:  # an entry written by an incompatible LangChain version: treat as a miss
            logger.warning("unreadable prompt cache entry", exc_info=True)
            return None

    def update(self, prompt: str, llm_string: str, return_val: Sequence[Any]) -> None:
        self.store.set(self._key(prompt, llm_string), dumps(list(return_val)), self.ttl)

    def clear(self, **kwargs: Any) -> None:
        self.store.delete_prefix(f"{self.namespace}:prompt:")
