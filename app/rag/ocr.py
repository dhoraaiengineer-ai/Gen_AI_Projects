"""OCR for scanned PDFs and image uploads.

RapidOCR (ONNX models bundled in the pip package) runs fully offline, on Windows and in the slim Docker
image, with no system binaries like Tesseract. The engine loads its models once, on first use (a few
seconds), then reads a page in well under a second.

Lines are returned in reading order (top to bottom, then left to right) and joined with newlines.
"""

import logging
import re
import threading
from typing import Protocol

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.5  # drop low-confidence fragments (speckles, stamps, signatures)


class OcrEngine(Protocol):
    def read(self, image: bytes) -> str: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def _load(self):  # type: ignore[no-untyped-def]
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR  # heavy import: only when OCR is first needed

                logger.info("loading OCR models")
                self._engine = RapidOCR()
            return self._engine

    def read(self, image: bytes) -> str:
        result, _ = self._load()(image)
        lines = [(box, text) for box, text, score in (result or []) if text.strip() and float(score) >= MIN_CONFIDENCE]
        # box = four corner points; sort by the top edge (rounded into rows), then by the left edge.
        lines.sort(key=lambda item: (round(min(p[1] for p in item[0]) / 12), min(p[0] for p in item[0])))
        return "\n".join(restore_spaces(text.strip()) for _, text in lines)


_SPACING_RULES = (
    (re.compile(r"(?<=[a-z]{3})(?=[A-Z])"), " "),  # CertificateNo -> Certificate No (not dBm, kHz)
    (re.compile(r"(?<=[A-Za-z]):(?=[^\s/])"), ": "),  # Instrument:Vector -> Instrument: Vector (not 10:30, not URLs)
    (re.compile(r"(?<=\d)(?=[A-Z][a-z])"), " "),  # 31December -> 31 December
    (re.compile(r"(?<=[a-z]{2})(?=\d{3,})"), " "),  # December2024 -> December 2024 (not dB3, not VNA-7)
)


def restore_spaces(line: str) -> str:
    """OCR often drops the space between words; put back the unambiguous ones. Decimals (2.4), codes
    (VNA-7, CAL-2024-031) and units (-97dBm) are left alone."""
    for pattern, replacement in _SPACING_RULES:
        line = pattern.sub(replacement, line)
    return line


_default: OcrEngine | None = None


def default_engine() -> OcrEngine:
    global _default
    if _default is None:
        _default = RapidOcrEngine()
    return _default


def set_default_engine(engine: OcrEngine | None) -> None:
    """Tests swap in a fake engine; None restores the real one on next use."""
    global _default
    _default = engine
