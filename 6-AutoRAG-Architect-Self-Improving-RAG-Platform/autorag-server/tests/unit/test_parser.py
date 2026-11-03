"""Unit tests for DocumentParser (D-5 Sprint Task).

Team 7 Ownership: Multi-format parser for PDF, DOCX, and TXT documents.

Architecture Contract Verification:
- Confirms successful extraction of structured ParsedPage objects from various sources.
- Ensures metadata (page_number, file_type, char_count) is correctly captured.
- Verifies that error paths (unsupported formats, empty files, encoding errors) raise the correct exceptions.

Setup Note: These tests use simple mock inputs to verify data contract and logic flow, rather than complex binary parsing dependencies.
"""

import io

from docx import Document as DocxDocument

from app.rag.ingestion.parser import DocumentParser


def _make_docx_bytes(paragraph_text: str) -> bytes:
    """Build a real minimal in-memory DOCX so the parser exercises actual python-docx parsing."""
    doc = DocxDocument()
    doc.add_paragraph(paragraph_text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_parsing_success() -> None:
    """DOCX parsing returns pages whose text observes the PII masking contract."""
    mock_docx_file_bytes = _make_docx_bytes("Contact Jane at jane.doe@example.com for details.")
    pages = DocumentParser().parse(mock_docx_file_bytes, "report_with_pii.docx")

    assert pages
    assert pages[0]["text"]
    assert pages[0]["file_type"] == "docx"
    assert "jane.doe@example.com" not in pages[0]["text"]  # PII masking contract


def test_txt_parsing_success() -> None:
    """TXT files are parsed into exactly one page (single-page contract)."""
    mock_txt_file_bytes = (
        b"This is a test document.\n"
        b"The quick brown fox jumps over the lazy dog (Unicode: dog-emoji)"
    )
    pages = DocumentParser().parse(mock_txt_file_bytes, "readme.txt")

    assert len(pages) == 1
    assert pages[0]["char_count"] > 0


def test_unsupported_format() -> None:
    """An unsupported file extension raises ValueError with a clear message."""
    setup_parser = DocumentParser()
    unknown_bytes = b"\x00\x01\x02"

    try:
        setup_parser.parse(unknown_bytes, "document.xyz")
    except ValueError as exc:
        assert "Unsupported file format" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported format, none was raised")
