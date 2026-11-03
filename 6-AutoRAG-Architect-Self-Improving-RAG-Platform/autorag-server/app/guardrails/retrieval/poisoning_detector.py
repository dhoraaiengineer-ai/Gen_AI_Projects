"""
Retrieval Poisoning Detector — AutoRAG v3.0
Detects anomalous chunks that may indicate vector store poisoning or adversarial injection.
Called between retrieval and LLM generation in the Builder/Evaluator nodes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Cosine similarity floor — chunks below this vs. query are flagged
_SIMILARITY_FLOOR = 0.3
# Max fraction of retrieved chunks allowed to be outliers before blocking
_OUTLIER_FRACTION_THRESHOLD = 0.4


@dataclass
class PoisoningResult:
    suspicious: bool
    outlier_count: int
    total_chunks: int
    reason: str | None


async def detect_retrieval_poisoning(
    chunks: list[dict],
    query_embedding: list[float],
    trace_id: str,
) -> PoisoningResult:
    """
    Checks retrieved chunks for similarity anomalies.

    Args:
        chunks: List of dicts with keys: chunk_id, content, similarity_score, source_uri
        query_embedding: The query's embedding vector (for outlier distance checks)
        trace_id: X-Trace-ID for correlation

    Returns:
        PoisoningResult with suspicious=True if outlier fraction exceeds threshold.
    """
    if not chunks:
        return PoisoningResult(
            suspicious=False, outlier_count=0, total_chunks=0, reason=None
        )

    outliers = [c for c in chunks if c.get("similarity_score", 1.0) < _SIMILARITY_FLOOR]
    outlier_fraction = len(outliers) / len(chunks)

    if outlier_fraction >= _OUTLIER_FRACTION_THRESHOLD:
        logger.warning(
            "Retrieval poisoning suspected",
            extra={
                "trace_id": trace_id,
                "outlier_count": len(outliers),
                "total_chunks": len(chunks),
                "outlier_fraction": outlier_fraction,
            },
        )
        return PoisoningResult(
            suspicious=True,
            outlier_count=len(outliers),
            total_chunks=len(chunks),
            reason=f"{len(outliers)}/{len(chunks)} chunks below similarity floor {_SIMILARITY_FLOOR}",
        )

    return PoisoningResult(
        suspicious=False,
        outlier_count=len(outliers),
        total_chunks=len(chunks),
        reason=None,
    )
