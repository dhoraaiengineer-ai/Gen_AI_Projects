"""
Guardrail Pipeline — AutoRAG v3.0
====================================
Single integration point for all 3 guardrail layers.
Called by FastAPI routes and LangGraph nodes. Never scatter guard calls elsewhere.

Usage:
    from app.guardrails.middleware.guardrail_pipeline import GuardrailPipeline

    pipeline = GuardrailPipeline()

    # Layer 1 — at FastAPI route boundary, before LangGraph dispatch
    clean_query = await pipeline.run_input_guards(raw_query, trace_id=x_trace_id)

    # Layer 2 — inside Builder/Evaluator nodes, after retrieval
    validated_chunks = await pipeline.run_retrieval_guards(chunks, query_embedding, pipeline_id, org_id, trace_id)

    # Layer 3 — inside Evaluator node, after LLM generation
    safe_answer = await pipeline.run_output_guards(answer, context_chunks, trace_id)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.exceptions import GuardrailBlockedError
from app.guardrails.input.jailbreak_detector import detect_jailbreak
from app.guardrails.input.pii_detector import mask_pii
from app.guardrails.input.prompt_injection import detect_injection
from app.guardrails.output.citation_validator import validate_citations
from app.guardrails.output.hallucination_scorer import (
    FAITHFULNESS_HARD_BLOCK,
    score_hallucination,
)
from app.guardrails.output.moderation import moderate_output
from app.guardrails.retrieval.poisoning_detector import detect_retrieval_poisoning
from app.guardrails.retrieval.source_validator import validate_sources
from app.metrics import (
    GUARDRAIL_INJECTION_BLOCKS,
    GUARDRAIL_JAILBREAK_BLOCKS,
    GUARDRAIL_OUTPUT_BLOCKS,
    GUARDRAIL_PII_DETECTIONS,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.ragas_service import RAGASService

logger = logging.getLogger(__name__)

_ORG_UNKNOWN = "unknown"


class GuardrailPipeline:
    """
    Orchestrates all 3 guardrail layers.
    Raises GuardrailBlockedError on hard blocks (injection, jailbreak, faithfulness < 0.5).

    Args:
        llm_service: Optional LLMService used to construct RAGASService for hallucination
                     scoring. When None, hallucination scorer uses a neutral fallback (0.5).
    """

    def __init__(self, llm_service: "LLMService | None" = None) -> None:
        self._ragas_service: "RAGASService | None" = None
        if llm_service is not None:
            from app.services.ragas_service import RAGASService  # lazy import avoids cycles

            self._ragas_service = RAGASService(llm_service)

    async def run_input_guards(
        self, raw_query: str, trace_id: str, organization_id: str = _ORG_UNKNOWN
    ) -> str:
        """
        Layer 1: PII masking → injection detection → jailbreak detection.
        Returns PII-masked query. Raises GuardrailBlockedError on detection.
        Emits Prometheus counters for blocked events.
        """
        # Step 1: PII masking (always runs — never skip)
        clean_query = await mask_pii(raw_query, trace_id=trace_id)
        if clean_query != raw_query:
            GUARDRAIL_PII_DETECTIONS.labels(organization_id=organization_id).inc()

        # Step 2: Prompt injection
        injection = await detect_injection(clean_query, trace_id=trace_id)
        if injection.detected and injection.confidence >= 0.9:
            GUARDRAIL_INJECTION_BLOCKS.labels(organization_id=organization_id).inc()
            logger.error(
                "Input blocked: prompt injection", extra={"trace_id": trace_id}
            )
            raise GuardrailBlockedError("prompt_injection", trace_id=trace_id)

        # Step 3: Jailbreak
        jailbreak = await detect_jailbreak(clean_query, trace_id=trace_id)
        if jailbreak.detected:
            GUARDRAIL_JAILBREAK_BLOCKS.labels(organization_id=organization_id).inc()
            logger.error(
                "Input blocked: jailbreak attempt", extra={"trace_id": trace_id}
            )
            raise GuardrailBlockedError("jailbreak", trace_id=trace_id)

        return clean_query

    async def run_retrieval_guards(
        self,
        chunks: list[dict],
        query_embedding: list[float],
        pipeline_id: str,
        organization_id: str,
        trace_id: str,
    ) -> list[dict]:
        """
        Layer 2: Source validation → poisoning detection.
        Returns validated chunks. Raises GuardrailBlockedError on poisoning.
        """
        source_result = await validate_sources(
            chunks, pipeline_id, organization_id, trace_id
        )
        if not source_result.valid:
            valid_chunks = [
                c
                for c in chunks
                if c.get("source_uri", "") not in source_result.invalid_sources
            ]
            logger.warning(
                "Invalid source chunks filtered",
                extra={
                    "trace_id": trace_id,
                    "removed": len(source_result.invalid_sources),
                },
            )
            chunks = valid_chunks

        poisoning = await detect_retrieval_poisoning(chunks, query_embedding, trace_id)
        if poisoning.suspicious:
            raise GuardrailBlockedError("retrieval_poisoning", trace_id=trace_id)

        return chunks

    async def run_output_guards(
        self,
        answer: str,
        context_chunks: list[dict],
        trace_id: str,
        organization_id: str = _ORG_UNKNOWN,
    ) -> str:
        """
        Layer 3: PII masking → hallucination scoring → moderation → citation validation.
        Returns safe answer. Raises GuardrailBlockedError if faithfulness < 0.5 or unsafe.
        Emits Prometheus counters for output block events.
        """
        # Re-mask PII in generated output (LLM may echo masked tokens or reconstruct PII)
        clean_answer = await mask_pii(answer, trace_id=trace_id)
        if clean_answer != answer:
            GUARDRAIL_PII_DETECTIONS.labels(organization_id=organization_id).inc()

        # Hallucination scoring — hard block if faithfulness < 0.5
        hall_score = await score_hallucination(
            clean_answer, context_chunks, trace_id, ragas_service=self._ragas_service
        )
        if hall_score.blocked:
            GUARDRAIL_OUTPUT_BLOCKS.labels(block_reason="hallucination").inc()
            raise GuardrailBlockedError(
                "hallucination",
                trace_id=trace_id,
                detail=f"faithfulness={hall_score.faithfulness:.2f} < {FAITHFULNESS_HARD_BLOCK}",
            )

        # Output moderation
        mod = await moderate_output(clean_answer, trace_id=trace_id)
        if not mod.safe:
            GUARDRAIL_OUTPUT_BLOCKS.labels(block_reason="unsafe_output").inc()
            raise GuardrailBlockedError("unsafe_output", trace_id=trace_id)

        # Citation validation (informational — does not block; feeds downstream scoring)
        await validate_citations(clean_answer, context_chunks, trace_id)

        return clean_answer
