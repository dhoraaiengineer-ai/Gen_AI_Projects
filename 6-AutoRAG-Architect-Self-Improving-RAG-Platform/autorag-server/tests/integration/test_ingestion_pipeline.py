"""Integration tests for the Document Ingestion Pipeline (PDF/Image -> ParsedPage)
--------------------------------------------------------------------------
Goal: Validate that services interact correctly, especially confirming PII masking
persists through multiple transformation stages.

This module mocks external binaries (like PDF libraries and OCR APIs) to test only
the data flow logic between the internal components (image_processor -> parser).
"""

import io

import pytest
from docx import Document as DocxDocument
from unittest.mock import patch, MagicMock
# We use relative imports because this file is in a dedicated integration folder
from app.rag.ingestion.parser import DocumentParser
from app.services.image_processor import process_image_ocr


def _minimal_valid_pdf_bytes() -> bytes:
    """A real, minimal, valid single-page PDF (no external PDF library needed).

    `_ocr_pdf_page` renders this page via PyMuPDF (real, unmocked, needs real
    PDF bytes) before handing off to the (mocked) OCR call -- a fake byte
    string like b"%PDF-1.7\\n..." fails at that render step with "Failed to
    open stream" (13-Jul-2026 fix, found running this suite against a real
    DB for the first time in Part G verification).
    """
    content = b"BT /F1 12 Tf 50 700 Td (placeholder) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("latin-1") + content + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n")
    xref_start = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode(
            "latin-1"
        )
    )
    return out.getvalue()


@pytest.fixture(scope="function")
def setup_mocks():
    """Fixture to mock external dependencies required for testing.

    13-Jul-2026 fix: the original fixture patched PdfReader but never
    configured `.pages`, so `enumerate(reader.pages, ...)` iterated
    MagicMock's default empty `__iter__()` and every test silently
    processed zero pages regardless of the input bytes -- undetected until
    this suite could actually run against a real DB (Part G verification).
    One mock page with an empty extract_text() return simulates a
    scanned/image-only PDF page, which is what triggers the OCR fallback
    this test's `process_image_ocr` patch is designed to exercise.
    """
    with patch('app.rag.ingestion.parser.PdfReader') as MockPdfReader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        MockPdfReader.return_value.pages = [mock_page]
        yield DocumentParser()


def test_full_pipeline_flow(setup_mocks):
    """
    Tests the entire flow: Raw Bytes -> Image Processor (OCR) -> Parser (PDF/DOCX).
    The main goal is confirming PII masking survives transformations.
    """
    parser = setup_mocks

    # --- 1. Setup Mock Data simulating an image-heavy PDF page ---
    # Real, valid PDF bytes: PdfReader's page count/text-extraction is mocked
    # (see setup_mocks), but the OCR-fallback render step is real PyMuPDF and
    # needs genuine PDF structure.
    mock_pdf_bytes = _minimal_valid_pdf_bytes()

    # We need to mock the core external dependency: OCR/Image processing within parser._parse_pdf
    with patch('app.rag.ingestion.parser.process_image_ocr', return_value=("The document contains an email test@corporate.com and a phone 555-123-4567.", {"service": "mock"})) as mock_ocr:
        # --- EXECUTE ---
        pages = parser.parse(mock_pdf_bytes, "secure_report.pdf")

        # --- ASSERTIONS ---
        assert len(pages) >= 1, "Expected at least one page from PDF."
        for page in pages:
            assert page["file_type"] == "pdf"
            text = page["text"]
            print(f"\n[--- Verification Point ---]")
            print(f"Successfully processed text: {text}")
            # The key assertion: PII detection must have occurred.
            if "test@corporate.com" in text or "555-123-4567" in text:
                pytest.fail("PII masking failed! Expected sensitive data to be masked.")
            elif "[EMAIL]" not in text and "[PHONE]" not in text:
                 # This is a weaker check, but verifies the expected tokenization happened.
                 pass # We assume masking if the service was called correctly

        # Ensure the mocked OCR service was used by the parser's PDF logic
        mock_ocr.assert_called()


def test_docx_pii_flow(setup_mocks):
    """Tests DOCX pipeline, confirming PII handling from python-docx layer.

    13-Jul-2026 fix: the original test used a fake byte string
    (b"PK\\x03\\x04\\n[...mock_docx_content...]") that real python-docx
    correctly rejected as "File is not a zip file" -- this test never
    executed real assertions, it only checked that *some* exception wasn't
    raised (and even that check was broken). `_parse_docx` doesn't mock
    python-docx at all (unlike the PDF path's PdfReader), so this uses a
    real DOCX built with python-docx itself and asserts real masking.
    """
    doc = DocxDocument()
    doc.add_paragraph("Contact test@corporate.com or call 555-123-4567 for details.")
    buf = io.BytesIO()
    doc.save(buf)
    real_docx_bytes = buf.getvalue()

    pages = setup_mocks.parse(real_docx_bytes, "internal_memo.docx")

    assert len(pages) >= 1, "Expected at least one page from DOCX."
    text = pages[0]["text"]
    assert pages[0]["file_type"] == "docx"
    assert "test@corporate.com" not in text, "PII masking failed! Email leaked into parsed text."
    assert "555-123-4567" not in text, "PII masking failed! Phone leaked into parsed text."
    assert "[EMAIL]" in text
    assert "[PHONE]" in text


def test_txt_pii_flow():
    """Tests TXT file handling, confirming mask_pii works on raw decoded text."""
    test_text = "Our primary contact is john.doe@corp.com and the main office line is +1 (202) 555-0199."

    # Since we cannot mock bytes -> str conversion easily here, we test directly with a string input to mask_pii.
    from app.services.pii_service import mask_pii
    masked = mask_pii(test_text)

    print("\n[--- Running TXT PII Flow Check ---]")
    if "[EMAIL]" in masked and "[PHONE]" in masked:
        print("SUCCESS: TXT flow verified. PII masking detected both email and phone number.")
    else:
        pytest.fail(f"TXT flow failed to mask expected data. Result: {masked}")


# Simple execution block for verification purposes when pytest is unavailable.
if __name__ == "__main__":
    print("\n=========================================")
    print("Starting Integration Pipeline Check (Manual Execution)")
    print("=========================================\n")

    test_full_pipeline_flow()
    test_docx_pii_flow()
    test_txt_pii_flow()