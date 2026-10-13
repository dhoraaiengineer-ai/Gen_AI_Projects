"""Retries with exponential backoff and full jitter, for retryable :class:`AppError` only."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

from src.core.errors import AppError, CircuitOpen, QuotaExceeded

logger = logging.getLogger(__name__)

_rng = random.SystemRandom()


def is_retryable(error: BaseException) -> bool:
    """Retry transient failures; never quota exhaustion, open circuits or client errors."""
    return (
        isinstance(error, AppError)
        and error.retryable
        and not isinstance(error, QuotaExceeded | CircuitOpen)
    )


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    """Full-jitter delay for ``attempt`` (1-based)."""
    return _rng.uniform(0, min(cap, base * 2 ** (attempt - 1)))


def retry_sync[T](
    fn: Callable[[], T],
    *,
    attempts: int,
    base: float = 0.5,
    label: str = "call",
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except AppError as exc:
            if attempt >= attempts or not is_retryable(exc):
                raise
            delay = backoff_delay(attempt, base)
            logger.warning(
                "retrying",
                extra={
                    "label": label,
                    "attempt": attempt,
                    "error": exc.code,
                    "delay_s": round(delay, 2),
                },
            )
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


async def retry_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base: float = 0.5,
    label: str = "call",
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except AppError as exc:
            if attempt >= attempts or not is_retryable(exc):
                raise
            delay = backoff_delay(attempt, base)
            logger.warning(
                "retrying",
                extra={
                    "label": label,
                    "attempt": attempt,
                    "error": exc.code,
                    "delay_s": round(delay, 2),
                },
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
