"""Re-ranking: the second retrieval stage.

Stage 1 (Retriever): hybrid search (vector cosine similarity + BM25-style keyword search), merged with
reciprocal rank fusion, gives ~3x top_k candidates.
Stage 2 (here): an LLM reads the question and every candidate and returns the indices of the passages that
best answer it, best first. The top_k of those are used. This fixes the cases neither score handles alone,
e.g. "What is the DOI of the article?" where "article" is a rarer word than "DOI".

A cross-encoder model would be the classic choice, but it needs PyTorch in the image; an LLM through the
existing fallback chain (with its circuit breakers and prompt cache) keeps the image small. Any failure keeps
the fused order, so re-ranking can only improve results, never break a query.
"""

import json
import logging
import re
from collections.abc import Sequence

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from prometheus_client import Counter

from app.rag.prompts import RERANK_SYSTEM_PROMPT, RERANK_USER_TEMPLATE
from app.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)

RERANKS = Counter("rag_rerank_total", "Re-ranking calls", ["outcome"])

MAX_PASSAGE_CHARS = 700  # enough to judge relevance; keeps the prompt small


def parse_ranking(text: str, candidates: int) -> list[int]:
    """'[3, 1, 7]' (possibly wrapped in prose or code fences) -> 0-based, valid, unique indices."""
    match = re.search(r"\[[\d,\s]*\]", text)
    if not match:
        raise ValueError("no index list in the re-ranker response")
    ranked: list[int] = []
    for value in json.loads(match.group(0)):
        index = int(value) - 1
        if 0 <= index < candidates and index not in ranked:
            ranked.append(index)
    return ranked


class LLMReranker:
    def __init__(self, llm: Runnable[LanguageModelInput, BaseMessage]):
        self.llm = llm

    def rerank(self, query: str, chunks: Sequence[RetrievedChunk], k: int) -> list[RetrievedChunk]:
        if len(chunks) <= 1:
            return list(chunks)[:k]
        passages = "\n\n".join(
            f'<passage index="{i}" source="{c.citation}">\n{c.document.page_content[:MAX_PASSAGE_CHARS]}\n</passage>'
            for i, c in enumerate(chunks, start=1)
        )
        prompt = RERANK_USER_TEMPLATE.format(question=query, passages=passages, k=k)
        try:
            response = self.llm.invoke([SystemMessage(RERANK_SYSTEM_PROMPT), HumanMessage(prompt)])
            order = parse_ranking(str(response.content), len(chunks))
        except Exception:
            RERANKS.labels("failed").inc()
            logger.warning("re-ranking failed; keeping the fused order", exc_info=True)
            return list(chunks)[:k]
        RERANKS.labels("ok").inc()
        # Passages the model left out keep their fused order after the ones it ranked.
        order += [i for i in range(len(chunks)) if i not in order]
        return [chunks[i] for i in order[:k]]
