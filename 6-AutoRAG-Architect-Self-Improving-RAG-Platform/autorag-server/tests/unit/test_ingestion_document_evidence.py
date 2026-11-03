"""Unit test: ingestion_node persists real per-document evidence (migration 0012,
P0.7 follow-up, 13-Jul-2026).

Verifies the specific claim this feature makes: page_count, char_count, and
per-type PII redaction counts are computed from this file's real parsed
pages and persisted to the matching Document row (matched by storage_path,
a real derivation) -- not reconstructed from node_trace after the fact.
Heavily mocked, same pattern as test_ingestion_pii_audit.py.
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
        x_trace_id="trace-doc-evidence",
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
def mock_db_with_document_row() -> tuple[MagicMock, uuid.UUID]:
    """AsyncSessionLocal() whose execute().first() resolves to a real-shaped
    Document row (id only, matching the select(Document.id) lookup)."""
    document_id = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    mock_result = MagicMock()
    mock_result.first.return_value = MagicMock(id=document_id)
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock()

    return MagicMock(return_value=mock_ctx), document_id


@pytest.mark.asyncio
async def test_ingestion_node_persists_document_evidence(
    mock_db_with_document_row: tuple[MagicMock, uuid.UUID],
) -> None:
    mock_db, expected_document_id = mock_db_with_document_row
    state = _make_state()
    org_id = state["organization_id"]

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
            "text": "No PII on this page at all.",
            "page_number": 2,
            "source_uri": "",
            "filename": "doc.pdf",
            "file_type": "pdf",
            "char_count": 28,
            "masking_metadata": {"pii_masked": True, "redaction_counts": {}, "detector_version": "pii-v1"},
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
        patch("app.graph.nodes.ingestion.AuditLogRepository.insert", new_callable=AsyncMock),
        patch(
            "app.graph.nodes.ingestion.DocumentRepository.update_ingestion_evidence",
            new_callable=AsyncMock,
        ) as mock_update_evidence,
    ):
        await ingestion_node(state)

    mock_update_evidence.assert_awaited_once()
    _, kwargs = mock_update_evidence.call_args
    assert kwargs["document_id"] == expected_document_id
    assert kwargs["organization_id"] == uuid.UUID(org_id)
    assert kwargs["page_count"] == 2
    # char_count is the real len() of each page's masked text, not the
    # fixture's (arbitrary, unused-by-the-node) "char_count" metadata field.
    assert kwargs["char_count"] == len(str(fake_pages[0]["text"])) + len(str(fake_pages[1]["text"]))
    assert kwargs["pii_redaction_count"] == 1
    assert kwargs["pii_counts_by_type"] == {"EMAIL": 1}


@pytest.mark.asyncio
async def test_ingestion_node_document_evidence_never_persists_original_pii(
    mock_db_with_document_row: tuple[MagicMock, uuid.UUID],
) -> None:
    """Audit-safety: the persisted evidence must be counts only, never the
    original PII value or a text sample."""
    mock_db, _ = mock_db_with_document_row
    state = _make_state()

    fake_pages = [
        {
            "text": "Contact [EMAIL] and [SSN] for help.",
            "page_number": 1,
            "source_uri": "",
            "filename": "doc.pdf",
            "file_type": "pdf",
            "char_count": 36,
            "masking_metadata": {
                "pii_masked": True,
                "redaction_counts": {"EMAIL": 1, "SSN": 1},
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
        patch("app.graph.nodes.ingestion.AuditLogRepository.insert", new_callable=AsyncMock),
        patch(
            "app.graph.nodes.ingestion.DocumentRepository.update_ingestion_evidence",
            new_callable=AsyncMock,
        ) as mock_update_evidence,
    ):
        await ingestion_node(state)

    _, kwargs = mock_update_evidence.call_args
    persisted_values = str(kwargs)
    assert "Contact" not in persisted_values
    assert "help" not in persisted_values
    # Only canonical type counts, never the raw or masked source text.
    assert kwargs["pii_counts_by_type"] == {"EMAIL": 1, "SSN": 1}
