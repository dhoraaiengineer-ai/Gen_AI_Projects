"""Fallback model chain (EURI -> Gemini -> Groq): each model has its own circuit breaker; transient
outages get a short retry with exponential backoff before moving to the next model."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from app.core.circuit_breaker import CircuitBreaker
from app.core.errors import AppError, ProviderError, ProviderQuotaError, ProviderUnavailableError
from app.core.metrics import FALLBACKS, MODEL_CALLS
from app.rag.interfaces import ChatModel

logger = logging.getLogger(__name__)


def with_retries(
    fn: Callable[[], str], *, attempts: int, base_delay: float, sleep: Callable[[float], None] = time.sleep
) -> str:
    """Retry only transient 'unavailable' errors; quota and provider errors move on immediately."""
    for attempt in range(attempts):
        try:
            return fn()
        except ProviderUnavailableError:
            if attempt == attempts - 1:
                raise
            sleep(base_delay * (2**attempt))
    raise AssertionError("unreachable")


class FallbackChatModel:
    def __init__(
        self,
        models: list[ChatModel],
        *,
        breakers: dict[str, CircuitBreaker] | None = None,
        retry_attempts: int = 2,
        retry_base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not models:
            raise ValueError("at least one model is required")
        self._models = models
        self._breakers = breakers or {m.name: CircuitBreaker(m.name) for m in models}
        self._attempts = retry_attempts
        self._delay = retry_base_delay
        self._sleep = sleep
        self.name = "chain(" + ",".join(m.name for m in models) + ")"

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        errors: list[AppError] = []
        for model in self._models:
            breaker = self._breakers[model.name]
            if not breaker.allow():
                continue
            started = time.perf_counter()
            try:
                out = with_retries(
                    lambda m=model: m.complete(system, user, temperature=temperature, max_tokens=max_tokens),
                    attempts=self._attempts,
                    base_delay=self._delay,
                    sleep=self._sleep,
                )
            except (ProviderQuotaError, ProviderUnavailableError, ProviderError) as exc:
                MODEL_CALLS.labels(model.name, "error").observe(time.perf_counter() - started)
                breaker.record_failure()
                FALLBACKS.labels(model.name, type(exc).__name__).inc()
                logger.warning(
                    "model failed; trying next", extra={"model": model.name, "error": type(exc).__name__}
                )
                errors.append(exc)
                continue
            MODEL_CALLS.labels(model.name, "ok").observe(time.perf_counter() - started)
            breaker.record_success()
            return out
        if not errors:
            raise ProviderUnavailableError("All model circuits are open. Please try again shortly.")
        # Quota on every attempted model -> 429; otherwise the last error decides (502/503).
        if all(isinstance(e, ProviderQuotaError) for e in errors):
            raise errors[-1]
        raise next((e for e in reversed(errors) if not isinstance(e, ProviderQuotaError)), errors[-1])
