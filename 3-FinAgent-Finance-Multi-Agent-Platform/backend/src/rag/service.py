"""Knowledge-base facade: search, grounded answers (cached per KB version) and ingestion."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import Any

from src.core.domain import Role
from src.core.kv import MemoryKV
from src.core.ports import KeyValueStore
from src.core.tenancy import require_tenant
from src.data.repositories.knowledge import KnowledgeRepository, SearchFilters
from src.rag.answer import GroundedAnswerer
from src.rag.ingestion import IngestionService
from src.rag.retrieval import HybridRetriever, SearchResult

logger = logging.getLogger(__name__)


class AnswerCache:
    """Grounded answers in the shared key-value store (Redis; in-process fallback). Keys include
    the tenant and the KB version, so an ingestion makes old answers unreachable."""

    def __init__(self, kv: KeyValueStore | None = None, ttl_seconds: int = 900) -> None:
        self.kv: KeyValueStore = kv or MemoryKV(max_keys=256)
        self.ttl = ttl_seconds

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self.kv.get(f"rag:{key}")
        except Exception:
            logger.warning("answer cache read failed", exc_info=True)
            return None
        value: dict[str, Any] | None = json.loads(raw) if raw else None
        return value

    async def put(self, key: str, value: dict[str, Any]) -> None:
        try:
            await self.kv.set(f"rag:{key}", json.dumps(value, default=str), self.ttl)
        except Exception:
            logger.warning("answer cache write failed", exc_info=True)


class KnowledgeService:
    def __init__(
        self,
        repo: KnowledgeRepository,
        retriever: HybridRetriever,
        answerer: GroundedAnswerer,
        ingestion: IngestionService,
        cache: AnswerCache | None = None,
    ) -> None:
        self.repo, self.retriever, self.answerer, self.ingestion = (
            repo,
            retriever,
            answerer,
            ingestion,
        )
        self.cache = cache or AnswerCache()

    def filters(self, role: Role | str, **kwargs: Any) -> SearchFilters:
        return HybridRetriever.filters_for(role, **kwargs)

    async def search(
        self,
        query: str,
        filters: SearchFilters,
        *,
        k: int = 5,
        mode: str = "hybrid",
        rerank: bool = True,
    ) -> SearchResult:
        return await self.retriever.search(query, filters, k=k, mode=mode, rerank=rerank)

    async def ask(self, question: str, filters: SearchFilters, *, k: int = 5) -> dict[str, Any]:
        version, _ = await self.repo.kb_state()
        key_src = json.dumps(
            [str(require_tenant()), question.strip().lower(), asdict(filters), version, k],
            sort_keys=True,
            default=lambda o: sorted(o) if isinstance(o, set | frozenset) else str(o),
        )
        key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()
        if cached := await self.cache.get(key):
            return cached | {"cached": True}
        result = await self.search(question, filters, k=k)
        answer = await self.answerer.answer(
            question, result.hits, reranked=result.reranker == "cross_encoder"
        )
        payload = {
            "question": question,
            "answer": answer.answer,
            "answerSource": answer.source,
            "citations": answer.citations,
            "validation": answer.validation,
            "redactions": answer.redactions,
            "retrieval": {k: v for k, v in result.as_dict().items() if k != "results"},
            "kbVersion": version,
            "cached": False,
        }
        await self.cache.put(key, payload)
        return payload
