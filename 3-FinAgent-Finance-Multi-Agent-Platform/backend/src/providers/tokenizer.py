"""Token counting with tiktoken (cl100k_base); falls back to the chars/4 estimate."""

from __future__ import annotations

import logging
from functools import lru_cache

from src.core.tokens import estimate_tokens
from src.rag.types import TokenCounter

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def token_counter() -> TokenCounter:
    try:
        import tiktoken  # noqa: PLC0415 — optional; loads BPE ranks on first use

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        logger.warning("tiktoken unavailable; estimating tokens", extra={"error": str(exc)[:200]})
        return estimate_tokens

    def count(text: str) -> int:
        return len(encoding.encode(text, disallowed_special=()))

    return count
