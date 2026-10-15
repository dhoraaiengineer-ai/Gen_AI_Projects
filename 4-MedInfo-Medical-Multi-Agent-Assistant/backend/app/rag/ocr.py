"""OCR with RapidOCR (offline ONNX models bundled with the package; no network, no disk writes)."""

from __future__ import annotations

import io
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


def _group_lines(boxes: list[tuple[float, float, float, str]], tolerance: float) -> list[str]:
    """boxes: (top, left, height, text). Groups boxes on the same visual line, left to right."""
    lines: list[list[tuple[float, float, float, str]]] = []
    for box in sorted(boxes):
        if lines and abs(box[0] - lines[-1][0][0]) <= max(tolerance, box[2] * 0.5):
            lines[-1].append(box)
        else:
            lines.append([box])
    return [" ".join(b[3] for b in sorted(line, key=lambda b: b[1])) for line in lines]


def preprocess(data: bytes, border: int = 40) -> bytes:
    """Grayscale + autocontrast + white border: steadier text detection on real-world scans."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as im:
        out = ImageOps.autocontrast(im.convert("L")).convert("RGB")
    out = ImageOps.expand(out, border=border, fill=(255, 255, 255))
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


class RapidOcrEngine:
    # det_unclip_ratio 2.0 (default 1.6): measured on the synthetic scans, the default dropped whole
    # lines and merged words ("SYNTHETICTESTDOCUMENT"); 2.0 recovered every line with correct spacing.
    def __init__(self, min_confidence: float = 0.5, det_unclip_ratio: float = 2.0) -> None:
        self._min_confidence = min_confidence
        self._unclip = det_unclip_ratio
        self._engine: Any = None
        self._lock = threading.Lock()

    def _get(self) -> Any:
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR

                self._engine = RapidOCR(det_unclip_ratio=self._unclip)
                logger.info("RapidOCR loaded")
            return self._engine

    def image_to_text(self, data: bytes) -> str:
        result, _ = self._get()(preprocess(data))
        if not result:
            return ""
        boxes = []
        for points, text, score in result:
            if float(score) < self._min_confidence or not str(text).strip():
                continue
            ys = [p[1] for p in points]
            xs = [p[0] for p in points]
            boxes.append((min(ys), min(xs), max(ys) - min(ys), str(text).strip()))
        return "\n".join(_group_lines(boxes, tolerance=8.0))
