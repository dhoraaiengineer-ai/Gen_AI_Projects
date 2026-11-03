"""Data models for document ingestion.

D-5: ParsedPage interface contract shared with Team 5 (Storage upload service).
All format parsers must return objects matching this TypedDict schema.

Schema:
- text: raw text content of the page
- page_number: 1-indexed page number from original document
- source_uri: Supabase Storage URL (filled by Team 5's StorageService)
- filename: original uploaded filename
- file_type: "pdf" | "docx" | "txt"
- char_count: character count of the text content

Usage (all parser implementations):
    from app.rag.ingestion.models import ParsedPage

    pages = DocumentParser.parse(file_bytes, filename)
     # returns list[ParsedPage] matching this schema
"""

from typing import TypedDict


class ParsedPage(TypedDict):
    """Parsed page data structure for document ingestion.

    This is the contract between Team 7 (Document Parser) and Team 5 (Storage Service).
    All parsers (PDF, DOCX, TXT, ImageOCR) must return ParsedPage objects matching this schema.

    Schema Fields:
        text (str): Raw extracted text content of this page from the document. MUST be PII masked.
        page_number (int): 1-indexed page number in the original document.
        source_uri (str): Supabase Storage URL (populated by Team 5 during upload).
        filename (str): Original uploaded filename with extension.
        file_type (str): Document format — one of "pdf", "docx", "txt", or "image".
        char_count (int): Character count of the text content after masking.
        masking_metadata (dict): Audit metadata proving PII compliance for this page.
            P0.7-1 (13-Jul-2026) canonical shape: {"pii_masked": bool,
            "redaction_counts": dict[str, int], "detector_version": str}
            -- redaction_counts is canonical-PII-type -> count (e.g.
            {"EMAIL": 2, "PHONE": 1}), never a sample of the original value.
            ingestion.py aggregates these across all pages/files in a run to
            emit one `pii_redacted` audit_log event (P0.7-2).

    Example:
        {
            "text": "This is the extracted text from page 1 of the document.",
            "page_number": 1,
            "source_uri": "https://storage.supabase.co/docs/pipeline_123/page_1.pdf",
            "filename": "example_document.pdf",
            "file_type": "pdf",
            "char_count": 542,
            "masking_metadata": {"pii_masked": True, "redaction_counts": {"EMAIL": 2}, "detector_version": "pii-v1"}
        }

    Team Ownership:
        Team 7 (D-5): Implements the parser logic to extract these fields.
        Team 5 (D-5): Populates 'source_uri' during storage upload and validates 'masking_metadata'.
    """

    text: str
    page_number: int
    source_uri: str
    filename: str
    file_type: str
    char_count: int
    masking_metadata: dict | None
