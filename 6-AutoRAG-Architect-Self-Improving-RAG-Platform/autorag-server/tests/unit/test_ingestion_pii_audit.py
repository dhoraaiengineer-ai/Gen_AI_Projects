"""Unit test: ingestion_node emits a real pii_redacted audit_log event (P0.7-2/P0.7-6).

Heavily mocks Supabase Storage, the parser, and the chunker so this stays a
fast unit test (real end-to-end ingestion is covered by
tests/integration/test_ingestion_pipeline.py, which needs a live DB). What
this test verifies that no other test does: the ingestion_node aggregates
real per-page redaction_counts (attached by parser.py, P0.7-3) across every
page/file in the run and writes exactly one pii_redacted audit_log row with
safe metadata only.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.state import GraphState, initial_state
from app.graph.nodes.ingestion import ingestion_node
from app.schemas.document import ChunkResult


def _make_state() -> GraphState:
    return initial_state(
        run_id=str(uuid.uuid4()),
        pipeline_id=str(uuid.uuid4()),
        organization_id=str(uuid.uuid4()),
        x_trace_id="trace-pii-audit",
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        raw_query="",
    )


def _fake_chunk(text: str, page_number: int, organization_id: str) -> ChunkResult:
    return ChunkResult(
        chunk_id=str(uuid.uuid4()),
        chunk_text=text,
        token_count=10,
        chunk_index=0,
        page_number=page_number,
        source_uri="https://storage.example/doc.pdf",
        organization_id=organization_id,
        chunk_strategy="semantic",
    )


@pytest.fixture
def mock_db() -> MagicMock:
    """AsyncSessionLocal() as an async context manager (matches test_observer.py)."""
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock()

    return MagicMock(return_value=mock_ctx)


@pytest.mark.asyncio
async def test_ingestion_node_writes_pii_redacted_audit_event(mock_db: MagicMock) -> None:
    state = _make_state()
    org_id = state["organization_id"]

    # Two pages, each already masked by parser.py with real redaction_counts
    # (P0.7-3) -- this is exactly what the real DocumentParser attaches.
    fake_pages = [
        {
            "text": "Contact [EMAIL] for help.",
            "page_number": 1,
            "source_uri": "",
            "filename": "doc.pdf",
            "file_type": "pdf",
            "char_count": 26,
            "masking_metadata": {
                "pii_masked": True,
                "redaction_counts": {"EMAIL": 1},
                "detector_version": "pii-v1",
            },
        },
        {
            "text": "SSN [SSN] and phone [PHONE] on file.",
            "page_number": 2,
            "source_uri": "",
            "filename": "doc.pdf",
            "file_type": "pdf",
            "char_count": 37,
            "masking_metadata": {
                "pii_masked": True,
                "redaction_counts": {"SSN": 1, "PHONE": 1},
                "detector_version": "pii-v1",
            },
        },
    ]

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [{"name": "doc.pdf"}]
    mock_sb.storage.from_.return_value.download.return_value = b"fake bytes"
    mock_sb.storage.from_.return_value.upload.return_value = None

    mock_chunker = MagicMock()
    mock_chunker.chunk = AsyncMock(
        side_effect=lambda text, metadata, x_trace_id: [
            _fake_chunk(text, metadata["page_number"], metadata["organization_id"])
        ]
    )

    with (
        patch("app.graph.nodes.ingestion._get_supabase_client", return_value=mock_sb),
        patch("app.graph.nodes.ingestion._parser.parse", return_value=fake_pages),
        patch("app.graph.nodes.ingestion._build_chunker", return_value=mock_chunker),
        patch("app.graph.nodes.ingestion.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.ingestion.AuditLogRepository.insert", new_callable=AsyncMock
        ) as mock_insert,
    ):
        result = await ingestion_node(state)

    assert not result.get("guardrail_blocked")
    mock_insert.assert_awaited_once()
    _, kwargs = mock_insert.call_args
    assert kwargs["event_type"] == "pii_redacted"
    assert kwargs["organization_id"] == uuid.UUID(org_id)
    payload = kwargs["payload"]
    assert payload["source"] == "document_ingestion"
    assert payload["detector_version"] == "pii-v1"
    assert payload["counts_by_type"] == {"EMAIL": 1, "SSN": 1, "PHONE": 1}
    assert payload["total_redaction_count"] == 3

    # Audit-safety: the payload must never carry the original masked text or
    # any of the source PII values, only counts and metadata (P0.7-6).
    assert "text" not in payload
    assert "EMAIL" not in str(payload.get("original", ""))


@pytest.mark.asyncio
async def test_ingestion_node_skips_audit_when_no_pii_found(mock_db: MagicMock) -> None:
    """No audit event should be written when a run has zero redactions."""
    state = _make_state()

    fake_pages = [
        {
            "text": "Nothing sensitive on this page.",
            "page_number": 1,
            "source_uri": "",
            "filename": "clean.txt",
            "file_type": "txt",
            "char_count": 32,
            "masking_metadata": {"pii_masked": True, "redaction_counts": {}, "detector_version": "pii-v1"},
        },
    ]

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [{"name": "clean.txt"}]
    mock_sb.storage.from_.return_value.download.return_value = b"fake bytes"
    mock_sb.storage.from_.return_value.upload.return_value = None

    mock_chunker = MagicMock()
    mock_chunker.chunk = AsyncMock(
        side_effect=lambda text, metadata, x_trace_id: [
            _fake_chunk(text, metadata["page_number"], metadata["organization_id"])
        ]
    )

    with (
        patch("app.graph.nodes.ingestion._get_supabase_client", return_value=mock_sb),
        patch("app.graph.nodes.ingestion._parser.parse", return_value=fake_pages),
        patch("app.graph.nodes.ingestion._build_chunker", return_value=mock_chunker),
        patch("app.graph.nodes.ingestion.AsyncSessionLocal", new=mock_db),
        patch(
            "app.graph.nodes.ingestion.AuditLogRepository.insert", new_callable=AsyncMock
        ) as mock_insert,
    ):
        await ingestion_node(state)

    mock_insert.assert_not_awaited()
