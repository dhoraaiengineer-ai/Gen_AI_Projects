"""
Runtime Policy Loader — AutoRAG v3.0
Loads environment-specific guardrail thresholds from config.
Allows staging/production to have different sensitivity levels without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class GuardrailPolicy:
    faithfulness_block_threshold: float  # hard block if faithfulness < this
    injection_confidence_block: float  # block if injection confidence >= this
    similarity_floor: float  # chunks below this flagged as outliers
    outlier_fraction_threshold: float  # fraction of outlier chunks before blocking
    pii_masking_enabled: bool


def load_policy() -> GuardrailPolicy:
    """
    Returns the active guardrail policy for the current environment.
    All thresholds sourced from environment variables — never hardcoded.
    """
    return GuardrailPolicy(
        faithfulness_block_threshold=settings.faithfulness_block_threshold,  # default: 0.5
        injection_confidence_block=settings.injection_confidence_block,  # default: 0.9
        similarity_floor=settings.retrieval_similarity_floor,  # default: 0.3
        outlier_fraction_threshold=settings.retrieval_outlier_threshold,  # default: 0.4
        pii_masking_enabled=settings.pii_masking_enabled,  # required: True in dev+
    )
