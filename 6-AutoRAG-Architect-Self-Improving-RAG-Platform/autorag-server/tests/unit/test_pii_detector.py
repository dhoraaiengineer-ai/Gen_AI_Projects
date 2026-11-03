"""Unit tests for app.guardrails.input.pii_detector — async compat wrapper (P0.7-1/P0.7-6).

Exhaustive per-category coverage lives in test_pii_engine.py. This file
verifies the async wrapper's own contract, and — the core P0.7-6 regression
requirement — that the document-ingestion path (pii_service.py, sync) and
the live-query path (pii_detector.py, async) protect the SAME category set,
since that path-dependent-coverage gap is exactly what P0.7 was written to
close.
"""

from __future__ import annotations

import pytest

from app.guardrails.input.pii_detector import (
    contains_pii,
    mask_pii,
    mask_pii_with_counts,
)
from app.services.pii_service import mask_pii as sync_mask_pii
from app.services.pii_service import mask_pii_with_counts as sync_mask_pii_with_counts


class TestAsyncWrapperContract:
    @pytest.mark.asyncio
    async def test_mask_pii_masks_email(self) -> None:
        result = await mask_pii("Contact a@b.com", trace_id="t-1")
        assert "[EMAIL]" in result
        assert "a@b.com" not in result

    @pytest.mark.asyncio
    async def test_mask_pii_with_counts_returns_counts(self) -> None:
        result = await mask_pii_with_counts("Contact a@b.com and c@d.com", trace_id="t-2")
        assert result.counts_by_type["EMAIL"] == 2
        assert result.total_redaction_count == 2

    @pytest.mark.asyncio
    async def test_contains_pii_true(self) -> None:
        assert await contains_pii("Email me at a@b.com") is True

    @pytest.mark.asyncio
    async def test_contains_pii_false(self) -> None:
        assert await contains_pii("Nothing sensitive here.") is False

    @pytest.mark.asyncio
    async def test_never_raises(self) -> None:
        for value in ["", "normal text", "a@b.com"]:
            await mask_pii(value, trace_id="t-3")  # must not raise


class TestIngestionAndQueryPathsShareCategoryContract:
    """P0.7-6 regression test: document ingestion (sync pii_service.py) and
    live query (async pii_detector.py) must protect the identical category
    set — this is the exact gap P0.7 closes (previously ingestion caught
    secrets but not SSN/credit-card/address; query caught the reverse)."""

    _SHARED_CASES: list[tuple[str, str]] = [
        ("Contact support@example.com", "[EMAIL]"),
        ("Call +1-555-123-4567", "[PHONE]"),
        ("SSN: 123-45-6789", "[SSN]"),
        ("Card: 4111111111111111", "[CREDIT_CARD]"),
        ("Ship to 742 Evergreen Street", "[ADDRESS]"),
        ("AWS Access Key ID: AKIAIOSFODNN7EXAMPLE", "[AWS_ACCESS_KEY]"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("text,expected_token", _SHARED_CASES)
    async def test_document_ingestion_and_live_query_detect_identically(
        self, text: str, expected_token: str
    ) -> None:
        # Document ingestion path (sync, ingestion.py/parser.py's real import)
        ingestion_result = sync_mask_pii(text)
        # Live query path (async, query.py's real import)
        query_result = await mask_pii(text, trace_id="t-parity")

        assert expected_token in ingestion_result, (
            f"Document ingestion path failed to detect {expected_token} in {text!r} "
            "-- this is the exact path-dependent coverage gap P0.7 was written to close."
        )
        assert expected_token in query_result, (
            f"Live query path failed to detect {expected_token} in {text!r} "
            "-- this is the exact path-dependent coverage gap P0.7 was written to close."
        )
        assert ingestion_result == query_result, (
            "Ingestion and query paths must produce byte-identical masked output "
            "for the same input -- proves both delegate to the same canonical engine."
        )

    @pytest.mark.asyncio
    async def test_counts_by_type_identical_across_paths(self) -> None:
        text = "Email a@b.com, SSN 123-45-6789, card 4111111111111111"
        ingestion_counts = sync_mask_pii_with_counts(text)
        query_counts = await mask_pii_with_counts(text, trace_id="t-parity-2")

        assert ingestion_counts.counts_by_type == query_counts.counts_by_type
        assert ingestion_counts.total_redaction_count == query_counts.total_redaction_count
        assert ingestion_counts.detector_version == query_counts.detector_version
