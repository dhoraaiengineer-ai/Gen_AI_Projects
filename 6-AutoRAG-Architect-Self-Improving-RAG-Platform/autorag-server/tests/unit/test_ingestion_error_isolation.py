"""Unit test: ingestion_node isolates a per-file parse failure (26-Jul-2026,
P1 UAT finding).

Verifies the specific claim: when one file in a multi-file pipeline fails to
parse (e.g. a corrupted upload), ingestion_node must NOT raise and abort the
whole run -- it should mark that one Document row as status="failed" with a
real error_message, and continue processing the other, healthy files. Before
this fix, one bad file raised out of the loop and aborted ingestion for every
document in the pipeline (confirmed live via a real corrupted-file repro that
also broke a later Evaluation run on the same pipeline).

Heavily mocked, same pattern as test_ingestion_pii_audit.py /
test_ingestion_document_evidence.py.
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
        x_trace_id="trace-error-isolation",
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
        source_uri="https://storage.example/good.pdf",
        organization_id=organization_id,
        chunk_strategy="semantic",
    )


@pytest.mark.asyncio
async def test_one_corrupted_file_does_not_abort_the_whole_ingestion_run() -> None:
    good_id = uuid.uuid4()
    bad_id = uuid.uuid4()

    def execute_side_effect(stmt: object) -> MagicMock:
        # Real code always does select(Document.id, Document.status).where(...
        # Document.storage_path == storage_path...). The compiled statement
        # doesn't expose storage_path cleanly for a mock to branch on, so
        # instead branch on call order: first call = good.pdf, second = bad.pdf.
        result = MagicMock()
        if execute_side_effect.calls == 0:
            result.first.return_value = MagicMock(id=good_id, status="uploaded")
        else:
            result.first.return_value = MagicMock(id=bad_id, status="uploaded")
        execute_side_effect.calls += 1
        return result

    execute_side_effect.calls = 0

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock()
    mock_db = MagicMock(return_value=mock_ctx)

    state = _make_state()

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [
        {"name": "good.pdf"},
        {"name": "bad.pdf"},
    ]
    mock_sb.storage.from_.return_value.download.return_value = b"fake bytes"
    mock_sb.storage.from_.return_value.upload.return_value = None

    good_pages = [
        {
            "text": "Real content from a healthy document.",
            "page_number": 1,
            "source_uri": "",
            "filename": "good.pdf",
            "file_type": "pdf",
            "char_count": 38,
            "masking_metadata": {"pii_masked": True, "redaction_counts": {}, "detector_version": "pii-v1"},
        }
    ]

    def parse_side_effect(raw_bytes: bytes, filename: str) -> list[dict]:
        if filename == "bad.pdf":
            raise ValueError("Failed to parse PDF: Stream has ended unexpectedly")
        return good_pages

    mock_chunker = MagicMock()
    mock_chunker.chunk = AsyncMock(
        side_effect=lambda text, metadata, x_trace_id: [
            _fake_chunk(text, metadata["page_number"], metadata["organization_id"])
        ]
    )

    with (
        patch("app.graph.nodes.ingestion._get_supabase_client", return_value=mock_sb),
        patch("app.graph.nodes.ingestion._parser.parse", side_effect=parse_side_effect),
        patch("app.graph.nodes.ingestion._build_chunker", return_value=mock_chunker),
        patch("app.graph.nodes.ingestion.AsyncSessionLocal", new=mock_db),
        patch("app.graph.nodes.ingestion.AuditLogRepository.insert", new_callable=AsyncMock),
        patch(
            "app.graph.nodes.ingestion.DocumentRepository.update_ingestion_evidence",
            new_callable=AsyncMock,
        ),
        patch(
            "app.graph.nodes.ingestion.DocumentRepository.update_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
    ):
        # Must not raise -- the whole point of this fix.
        result = await ingestion_node(state)

    assert not result.get("guardrail_blocked")

    # The bad file's document was marked failed with a real reason, not silently dropped.
    mock_update_status.assert_awaited_once()
    _, kwargs = mock_update_status.call_args
    assert kwargs["document_id"] == bad_id
    assert kwargs["status"] == "failed"
    assert "Failed to parse PDF" in kwargs["error_message"]

    # The good file's chunks still made it through -- one bad document does
    # not poison the rest of the pipeline.
    chunks_path_upload_calls = list(mock_sb.storage.from_.return_value.upload.call_args_list)
    assert len(chunks_path_upload_calls) == 1
    uploaded_payload = chunks_path_upload_calls[0].args[1]
    assert b"Real content from a healthy document" in uploaded_payload


@pytest.mark.asyncio
async def test_already_failed_document_is_skipped_without_reparsing() -> None:
    """A document already marked failed from a prior run must not be
    re-downloaded/re-parsed on the next graph invocation (e.g. a later
    Evaluation run re-entering the ingestion node)."""
    doc_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.first.return_value = MagicMock(id=doc_id, status="failed")
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock()
    mock_db = MagicMock(return_value=mock_ctx)

    state = _make_state()

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.list.return_value = [{"name": "already-bad.pdf"}]
    mock_sb.storage.from_.return_value.download.return_value = b"fake bytes"
    mock_sb.storage.from_.return_value.upload.return_value = None

    with (
        patch("app.graph.nodes.ingestion._get_supabase_client", return_value=mock_sb),
        patch("app.graph.nodes.ingestion._parser.parse") as mock_parse,
        patch("app.graph.nodes.ingestion.AsyncSessionLocal", new=mock_db),
    ):
        await ingestion_node(state)

    # Never even attempted to download/parse a file already known to be bad.
    mock_sb.storage.from_.return_value.download.assert_not_called()
    mock_parse.assert_not_called()
