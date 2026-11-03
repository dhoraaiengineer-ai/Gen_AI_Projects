"""Query embedding service -- wraps LLMService.embed() for the retrieval path.

Applies PII masking via @security_masker before text reaches the embedding API.
"""

from __future__ import annotations

import uuid

from app.services.llm_service import LLMService
from app.utils.decorators import security_masker


class QueryEmbeddingService:
    """Generates 768-dim embedding vectors for user queries via Gemini Embedding 2.

    The @security_masker decorator masks PII in query_text before calling the
    embedding API (Rule 70 + graph-state-governance Rule 6).
    """

    def __init__(self) -> None:
        self._llm = LLMService()

    @security_masker
    async def get_embedding(
        self, query_text: str, model: str = "gemini-embedding-2"
    ) -> list[float]:
        """Return a 768-dim embedding vector for the (PII-masked) query text.

        Args:
            query_text: Raw query string. Masked by @security_masker before this
                        method body runs, so the value received here is already clean.
            model:      Embedding model name (informational; actual model is read from
                        settings.embedding_model via LLMService.embed).

        Returns:
            List of 768 floats.
        """
        trace_id = str(uuid.uuid4())
        return await self._llm.embed(query_text, x_trace_id=trace_id)
