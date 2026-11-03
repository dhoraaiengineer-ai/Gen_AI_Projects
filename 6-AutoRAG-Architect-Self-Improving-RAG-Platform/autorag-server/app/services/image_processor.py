"""Image Processing Service — OCR via Gemini Flash vision, through the EURI gateway.

Converts raw image bytes (PNG, JPEG) into text using Gemini's multimodal
capability. Called by DocumentParser when a PDF page has no text layer
(scanned documents, image-only pages).

Key constraints (Rule 86 + Rule 70):
- No cost calculation here; cost is owned by llm_service.py only.
- The caller is responsible for PII-masking the returned text before
  storing it anywhere. This service only extracts — it does not mask.
- No user input or document content is logged (PII safety).

CORRECTED 17-Jul-2026: previously called Google's real API directly via the
deprecated `google.generativeai` SDK (`genai.configure` + `GenerativeModel`).
That SDK talks to googleapis.com directly, which rejects EURI-issued keys
with "API key not valid" -- confirmed via direct reproduction, this made
OCR fail 100% of the time for every image-only PDF page, not intermittently.
`embedding_service.py` and `llm_service.py` already avoid this exact trap by
routing through the EURI OpenAI-compatible gateway instead -- this file now
does the same, using the standard OpenAI vision message format (verified
working against the real EURI gateway: a real PNG with text was correctly
OCR'd via gemini-flash-3.5). Kept synchronous (httpx.Client, not AsyncClient) because every caller up the
chain (DocumentParser._parse_pdf/_ocr_pdf_page) is synchronous too. The
caller's caller -- app/graph/nodes/ingestion.py -- is responsible for running
the whole synchronous parse (OCR included) off the event loop via
asyncio.to_thread(); see the 17-Jul-2026 fix note at that call site (a prior
version of this comment incorrectly assumed that thread-offload already
existed -- it didn't, and running OCR's blocking HTTP calls directly on the
event loop was live-confirmed to corrupt in-flight EURI connections and
cause reproducible embeddings 500s downstream in the same request).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.core.config import resolve_gemini, settings

logger = logging.getLogger(__name__)

_OCR_PROMPT = (
    "Extract all text visible in this image. "
    "Return only the extracted text, preserving paragraph and line structure. "
    "Do not add commentary, explanations, or formatting tags. "
    "If no text is visible, return an empty string."
)


def process_image_ocr(
    image_bytes: bytes, x_trace_id: str = ""
) -> tuple[str | None, dict]:
    """Extract text from image bytes via Gemini Flash vision (through EURI).

    Args:
        image_bytes: Raw PNG or JPEG bytes (e.g., a rendered PDF page).
        x_trace_id: Propagated trace ID for structured logging (Rule 85).

    Returns:
        (text, metadata) where text is the extracted string or None on failure.
        metadata contains ocr_service, latency_ms, and success flag.

    Notes:
        Resolves via resolve_gemini() -- the same EURI-or-direct logic used by
        llm_service.py and embedding_service.py. Synchronous (matches every
        caller); when calling from an async context wrap with
        asyncio.to_thread(), same as before.
    """
    if not image_bytes:
        return None, {"error": "empty image bytes", "ocr_service": "gemini-vision"}

    if not settings.gemini_api_key:
        logger.warning(
            "gemini_api_key not configured — OCR unavailable",
            extra={"x_trace_id": x_trace_id},
        )
        return None, {
            "error": "gemini_api_key not configured",
            "ocr_service": "gemini-vision",
            "success": False,
        }

    endpoint = resolve_gemini(settings)
    mime_type = _detect_mime(image_bytes)
    image_b64 = base64.b64encode(image_bytes).decode()
    url = f"{endpoint.base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": endpoint.chat_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
        "X-Trace-ID": x_trace_id,
    }

    try:
        start = time.monotonic()
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        latency_ms = int((time.monotonic() - start) * 1000)
        body: dict[str, Any] = resp.json()
        text = body["choices"][0]["message"]["content"].strip()

        logger.info(
            "ocr_complete",
            extra={
                "x_trace_id": x_trace_id,
                "ocr_service": "gemini-vision",
                "char_count": len(text),
                "latency_ms": latency_ms,
            },
        )

        return (text if text else None), {
            "ocr_service": "gemini-vision",
            "model": settings.llm_primary_model,
            "latency_ms": latency_ms,
            "success": bool(text),
        }

    except Exception as exc:
        logger.error(
            "ocr_failed",
            extra={"x_trace_id": x_trace_id, "error": str(exc)},
        )
        return None, {
            "error": str(exc),
            "ocr_service": "gemini-vision",
            "success": False,
        }


def _detect_mime(image_bytes: bytes) -> str:
    """Identify image type from magic bytes rather than file extension."""
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    return "image/png"  # safe default — rendered PDF pages are always PNG
