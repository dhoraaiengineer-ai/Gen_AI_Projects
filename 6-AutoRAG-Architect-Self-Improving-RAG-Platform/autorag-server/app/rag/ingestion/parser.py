"""Document Parser — D-5 Sprint Task.

Team 7 (D-5) Responsibility:
    Multi-format parser for PDF, DOCX, and TXT documents into structured ParsedPage objects.
    Hand off to Team 5 who will upload parsed pages to Supabase Storage.

Architecture Contract:
      - Returns list[ParsedPage] matching the shared interface in app/rag/ingestion/models.py
      - Supports: PDF (pypdf), DOCX (python-docx), TXT (UTF-8 decode)
      - Populates: text, page_number, filename, file_type, char_count
      - Raises ValueError on unsupported formats

Usage:
    from app.rag.ingestion.parser import DocumentParser

    parser = DocumentParser()
    pages = parser.parse(file_bytes, filename)   # returns list[ParsedPage]
"""

import io
import logging
from pathlib import Path
from typing import Final

from app.services.image_processor import process_image_ocr
from app.services.pii_service import mask_pii_with_counts

# Import parser dependencies at module level to satisfy static type checkers
try:
    from pypdf import PdfReader  # noqa: F821
except ImportError:
    PdfReader = None  # type: ignore

try:
    from docx import Document  # noqa: F821
except ImportError:
    Document = None  # type: ignore

try:
    import fitz  # PyMuPDF — renders PDF pages to images for OCR fallback
except ImportError:
    fitz = None  # type: ignore

from app.rag.ingestion.models import ParsedPage

logger = logging.getLogger(__name__)


__all__: list[str] = ["DocumentParser"]


class DocumentParser:
    """Multi-format document parser implementing D-5 sprint task.

    Parses uploaded documents into structured ParsedPage objects that Team 5
    will upload to Supabase Storage for vector embedding and indexing.

    Supported Formats:
        - PDF (.pdf): Extract text using pypdf
        - DOCX (.docx): Extract text using python-docx
        - TXT (.txt): Decode UTF-8 text directly

    Output Contract:
        list[ParsedPage] where each page contains:
            - text: Raw extracted text content
            - page_number: 1-indexed page number from original document
            - source_uri: Populated by Team 5 during storage upload
            - filename: Original uploaded filename
            - file_type: One of "pdf", "docx", or "txt"
            - char_count: Character count of the extracted text

    Raises:
        ValueError: If file extension is not supported
    """

    _ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset(["pdf", "docx", "txt", "md", "markdown"])

    def __init__(self) -> None:
        """Initialize parser with no dependencies (stateless design)."""
        pass

    def parse(self, file_bytes: bytes, filename: str) -> list[ParsedPage]:
        """Parse document bytes into structured ParsedPage objects.

        Dispatches to format-specific parsers based on file extension.

        Args:
            file_bytes: Raw binary content of uploaded document
            filename: Original filename (used for extension detection and metadata)

        Returns:
            list[ParsedPage]: Structured page data matching the Team 5/7 contract

        Raises:
            ValueError: If file extension is not in {pdf, docx, txt}
        """
        ext = Path(filename).suffix.lstrip(".").lower()

        if ext not in self._ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format: {ext}. "
                f"Supported formats: {', '.join(sorted(self._ALLOWED_EXTENSIONS))}"
            )

        logger.info(f"Parsing document with extension: {ext}")

        pages = self._parse_by_extension(file_bytes, filename, ext)

        # source_uri is set to "" in each format parser; Team 5's StorageService
        # fills it during upload. This loop is a safety net for any format parser
        # that forgets to set it.
        for page in pages:
            if not page.get("source_uri"):
                page["source_uri"] = ""

        return pages

    def _parse_by_extension(
        self,
        file_bytes: bytes,
        filename: str,
        ext: str,
    ) -> list[ParsedPage]:
        """Route to format-specific parser implementation.

        Args:
            file_bytes: Raw binary content of uploaded document
            filename: Original filename (used for metadata)
            ext: Lowercase extension — one of {pdf, docx, txt}

        Returns:
            list[ParsedPage]: Structured page data matching the Team 5/7 contract
        """
        if ext == "pdf":
            return self._parse_pdf(file_bytes, filename)
        elif ext == "docx":
            return self._parse_docx(file_bytes, filename)
        elif ext in ("txt", "md", "markdown"):
            return self._parse_txt(file_bytes, filename)
        raise ValueError(f"Unsupported file format: {ext}")

    def _parse_pdf(self, file_bytes: bytes, filename: str) -> list[ParsedPage]:
        """Parse PDF document into ParsedPage objects.

        Primary path: pypdf text extraction (fast, no API cost).
        Fallback path: PyMuPDF renders the page to PNG, then Gemini vision
        extracts the text (handles scanned / image-only PDFs).

        PII masking is applied to all text before storage (Rule 70).
        """
        if PdfReader is None:
            raise ImportError(
                "pypdf is required for PDF parsing. "
                "Run: uv add pypdf"
            )

        logger.info(f"Parsing PDF document: {filename}")

        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {e}")

        pages: list[ParsedPage] = []

        for i, page in enumerate(reader.pages, start=1):
            raw_text: str | None = page.extract_text()
            ocr_used = False

            if not raw_text or not raw_text.strip():
                # Text layer empty — try OCR fallback for scanned pages
                raw_text, ocr_meta = self._ocr_pdf_page(file_bytes, page_index=i - 1)
                if not raw_text:
                    logger.warning(
                        "pdf_page_skipped page=%d filename=%s reason=no_text_and_ocr_failed",
                        i, filename,
                    )
                    continue
                ocr_used = True
                logger.info(
                    "pdf_ocr_fallback_used page=%d filename=%s latency_ms=%s",
                    i, filename, ocr_meta.get("latency_ms", "?"),
                )

            # PII masking is mandatory before any storage write (Rule 70) --
            # canonical engine (P0.7-1); counts are attached to
            # masking_metadata so ingestion.py can aggregate real per-run
            # redaction counts for the pii_redacted audit event (P0.7-2).
            redaction = mask_pii_with_counts(raw_text)
            masked_text = redaction.masked_text
            char_count = len(masked_text)

            pages.append(
                ParsedPage(
                    text=masked_text,
                    page_number=i,
                    filename=filename,
                    file_type="pdf",
                    char_count=char_count,
                    source_uri="",
                    masking_metadata={
                        "ocr_used": ocr_used,
                        "pii_masked": True,
                        "redaction_counts": redaction.counts_by_type,
                        "detector_version": redaction.detector_version,
                    },
                )
            )

        logger.info("pdf_parse_complete filename=%s pages=%d", filename, len(pages))
        return pages

    def _ocr_pdf_page(
        self, file_bytes: bytes, page_index: int
    ) -> tuple[str | None, dict]:
        """Render a single PDF page to PNG via PyMuPDF, then run Gemini OCR.

        Args:
            file_bytes: Raw PDF bytes (the full document).
            page_index: 0-indexed page number to render.

        Returns:
            (text, metadata) from process_image_ocr, or (None, error_dict).
        """
        if fitz is None:
            logger.warning(
                "pymupdf_not_installed — OCR fallback unavailable. Run: uv add pymupdf"
            )
            return None, {"error": "pymupdf not installed"}

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[page_index]
            # 150 DPI gives readable text quality with manageable payload size
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            png_bytes: bytes = pix.tobytes("png")
            doc.close()
        except Exception as exc:
            logger.error(
                "pdf_page_render_failed page_index=%d error=%s", page_index, str(exc)
            )
            return None, {"error": str(exc)}

        return process_image_ocr(png_bytes)

    def _parse_docx(self, file_bytes: bytes, filename: str) -> list[ParsedPage]:
        """Parse DOCX document into ParsedPage objects.

        Uses python-docx library for text extraction. Each page becomes a separate
        ParsedPage with the original content.

        Args:
            file_bytes: Raw binary DOCX content
            filename: Original filename (used for metadata)

        Returns:
            list[ParsedPage]: One ParsedPage per extracted DOCX page
        """
        if Document is None:
            raise ImportError(
                "python-docx is required for DOCX parsing. "
                "Run: uv add python-docx"
            )

        logger.info(f"Parsing DOCX document: {filename}")

        try:
            doc = Document(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {e}")

        pages: list[ParsedPage] = []

        for i, _paragraph in enumerate(doc.paragraphs, start=1):
            raw_text = _paragraph.text
            redaction = mask_pii_with_counts(raw_text)
            masked_text = redaction.masked_text
            if not masked_text.strip():
                logger.warning(f"DOCX page {i} yielded no visible text after masking or extraction.")
                continue

            logger.info("pii_masking_applied docx_file=%s page=%d char_count=%d", filename, i, len(masked_text))

            pages.append(
                ParsedPage(
                    text=masked_text, # Use masked text
                    page_number=i,
                    filename=filename,
                    file_type="docx",
                    char_count=len(masked_text),
                    source_uri="",
                    masking_metadata={
                        "pii_masked": True,
                        "redaction_counts": redaction.counts_by_type,
                        "detector_version": redaction.detector_version,
                    },
                )
            )

        logger.info(f"Successfully parsed DOCX '{filename}' -> {len(pages)} pages")

        return pages

    def _parse_txt(self, file_bytes: bytes, filename: str) -> list[ParsedPage]:
        """Parse TXT document into ParsedPage objects.

        Decodes UTF-8 text directly. Creates a single ParsedPage for the entire
        file content (TXT files are treated as single-page documents).

        Args:
            file_bytes: Raw binary TXT content
            filename: Original filename (used for metadata)

        Returns:
            list[ParsedPage]: Single ParsedPage containing full file content
        """
        logger.info(f"Parsing TXT document: {filename}")

        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to latin-1 first if UTF-8 fails on the whole file decode.
            try:
                text = file_bytes.decode("latin-1")
                logger.warning(f"UTF-8 decode failed, fallback to latin-1 for '{filename}'")
            except UnicodeDecodeError as latin_error:
                raise ValueError(
                    f"Failed to decode TXT file '{filename}': "
                    f"Unsupported encoding. Error: {latin_error}"
                ) from latin_error
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode TXT file as UTF-8: {e}")

        # --- PII Masking Integration (Rule 6, Rule 70) ---
        redaction = mask_pii_with_counts(text)
        masked_text = redaction.masked_text
        char_count = len(masked_text)
        logger.info("pii_masking_applied txt_file=%s char_count=%d", filename, char_count)

        pages: list[ParsedPage] = [
            ParsedPage(
                text=masked_text, # Store masked text
                page_number=1,
                filename=filename,
                file_type="txt",
                char_count=char_count,
                source_uri="",
                masking_metadata={
                    "pii_masked": True,
                    "redaction_counts": redaction.counts_by_type,
                    "detector_version": redaction.detector_version,
                },
            )
        ]

        logger.info(f"Successfully parsed TXT '{filename}' -> 1 page ({char_count} characters)")

        return pages

    def parse_from_path(self, filepath: str | Path) -> list[ParsedPage]:
        """Parse document from file path into structured ParsedPage objects.

        Convenience method that reads file bytes from disk before parsing.

        Args:
            filepath: Path to the document file (local or absolute)

        Returns:
            list[ParsedPage]: Structured page data matching the Team 5/7 contract

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If file extension is unsupported or parsing fails
        """
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {filepath}")

        return self.parse(path.read_bytes(), path.name)
