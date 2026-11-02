"""Text extraction: pypdf for text PDFs, Tesseract OCR for images when available (P2-4).

If Tesseract is not installed, images are reported as unreadable (method="unavailable") — never guessed.
The backend Docker image installs tesseract-ocr; local Windows hosts may not have it (MEMORY L-008).
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image
from pypdf import PdfReader

Method = Literal["pdf_text", "ocr", "unavailable", "empty"]
MIN_CHARS = 20  # text-layer PDFs
MIN_OCR_CHARS = 5  # photos (e.g. "ODO 49950 km") are short


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    method: Method

    @property
    def readable(self) -> bool:
        if self.method == "ocr":
            return len(self.text.strip()) >= MIN_OCR_CHARS
        return self.method == "pdf_text" and len(self.text.strip()) >= MIN_CHARS


WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


@lru_cache
def tesseract_path() -> str | None:
    """TESSERACT_CMD setting → PATH → the Windows installer's default location."""
    from app.core.config import get_settings

    configured = get_settings().tesseract_cmd
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("tesseract")
    if found:
        return found
    return str(WINDOWS_DEFAULT) if WINDOWS_DEFAULT.exists() else None


def tesseract_available() -> bool:
    return tesseract_path() is not None


def _ocr(image: Image.Image) -> str:
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = tesseract_path() or "tesseract"
    gray = image.convert("L")
    if gray.width < 1500:  # small renders OCR better upscaled
        gray = gray.resize((gray.width * 2, gray.height * 2))
    return str(pytesseract.image_to_string(gray))


def extract_text(data: bytes, mime: str) -> list[PageText]:
    if mime == "application/pdf":
        pages = []
        for i, page in enumerate(PdfReader(io.BytesIO(data)).pages, start=1):
            text = page.extract_text() or ""
            pages.append(PageText(i, text, "pdf_text" if len(text.strip()) >= MIN_CHARS else "empty"))
        return pages  # scanned PDFs need page rasterisation (poppler) — out of scope; they stay "empty" → unreadable
    if not tesseract_available():
        return [PageText(1, "", "unavailable")]
    with Image.open(io.BytesIO(data)) as img:
        text = _ocr(img)
    return [PageText(1, text, "ocr" if len(text.strip()) >= MIN_OCR_CHARS else "empty")]
