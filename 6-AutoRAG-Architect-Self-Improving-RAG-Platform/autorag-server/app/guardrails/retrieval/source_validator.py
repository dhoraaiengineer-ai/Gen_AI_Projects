"""
Source Validator — AutoRAG v3.0
Validates that retrieved chunk source URIs belong to the correct pipeline's allowed sources.
Prevents cross-pipeline data leakage and unauthorized document access.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SourceValidationResult:
    valid: bool
    invalid_sources: list[str]


async def validate_sources(
    chunks: list[dict],
    pipeline_id: str,
    organization_id: str,
    trace_id: str,
) -> SourceValidationResult:
    """
    Ensures all chunk source_uri values belong to the expected pipeline and organization.
    Rejects any chunk whose source does not match the scoping criteria.

    source_uri format: supabase://storage/{organization_id}/{pipeline_id}/{filename}
    """
    invalid: list[str] = []
    expected_prefix = f"supabase://storage/{organization_id}/{pipeline_id}/"

    for chunk in chunks:
        source = chunk.get("source_uri", "")
        if not source.startswith(expected_prefix):
            invalid.append(source)
            logger.warning(
                "Chunk source URI failed validation",
                extra={
                    "trace_id": trace_id,
                    "source_uri": source,
                    "pipeline_id": pipeline_id,
                },
            )

    return SourceValidationResult(valid=len(invalid) == 0, invalid_sources=invalid)
