"""Integration test for RerankService — exercises the REAL BGE-Reranker model.

Skipped automatically unless RUN_BGE_INTEGRATION=1 is set (downloads BGE model
weights from Hugging Face Hub on first run — not run on every `make test`).
AC: "Cohere failure -> BGE activates" verified against real cross-encoder
inference rather than a mocked model.
"""

from __future__ import annotations

import os

import pytest

from app.core.config import get_settings
from app.services.rerank_service import RerankService

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_bge() -> None:
    if os.getenv("RUN_BGE_INTEGRATION") != "1":
        pytest.skip("RUN_BGE_INTEGRATION not set — opt-in, downloads BGE model weights")


class TestRerankServiceIntegration:
    async def test_cohere_failure_activates_real_bge_reranker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No COHERE_API_KEY configured -> falls back to real BGE inference."""
        monkeypatch.setenv("COHERE_API_KEY", "")
        get_settings.cache_clear()

        chunks = [
            {
                "chunk_id": "c-ecs",
                "chunk_text": (
                    "ECS Fargate automatically scales tasks based on CPU utilization"
                ),
                "chunk_strategy": "semantic",
                "page_number": 1,
                "source_uri": "s3://bucket/ecs-guide.pdf",
                "parent_chunk_id": None,
                "score": 0.1,
            },
            {
                "chunk_id": "c-pasta",
                "chunk_text": "Cooking pasta requires boiling water and adding salt",
                "chunk_strategy": "semantic",
                "page_number": 2,
                "source_uri": "s3://bucket/recipes.pdf",
                "parent_chunk_id": None,
                "score": 0.1,
            },
        ]

        svc = RerankService()
        results = await svc.rerank(
            "How does ECS Fargate scale?", chunks, top_k=2, x_trace_id="integ-bge"
        )

        assert results[0]["chunk_id"] == "c-ecs"
        assert all(r["rerank_provider"] == "bge" for r in results)

        get_settings.cache_clear()
