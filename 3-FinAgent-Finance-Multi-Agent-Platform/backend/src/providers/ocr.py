"""OCR adapter: pypdfium2 renders PDF pages, Tesseract (pytesseract) reads text.

Tesseract is a system binary; when it is missing ``available()`` is False and loaders mark
scanned pages as ``needs_ocr`` instead of failing.
"""

from __future__ import annotations

import io
import logging
import shutil

logger = logging.getLogger(__name__)


class TesseractOcr:
    def __init__(self, lang: str = "eng", dpi: int = 200) -> None:
        self.lang, self.dpi = lang, dpi

    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def image_text(self, data: bytes) -> str:
        import pytesseract  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        decode = Image.open  # binary image decoder (not text I/O)
        with decode(io.BytesIO(data)) as image:
            return str(pytesseract.image_to_string(image, lang=self.lang))

    def pdf_page_text(self, data: bytes, page_index: int) -> str:
        import pypdfium2  # noqa: PLC0415
        import pytesseract  # noqa: PLC0415

        pdf = pypdfium2.PdfDocument(data)
        try:
            image = pdf[page_index].render(scale=self.dpi / 72).to_pil()
            return str(pytesseract.image_to_string(image, lang=self.lang))
        finally:
            pdf.close()


class NoOcr:
    def available(self) -> bool:
        return False

    def image_text(self, data: bytes) -> str:
        raise RuntimeError("OCR not available")

    def pdf_page_text(self, data: bytes, page_index: int) -> str:
        raise RuntimeError("OCR not available")
