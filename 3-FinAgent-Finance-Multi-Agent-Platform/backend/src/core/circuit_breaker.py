"""Circuit breaker, one per dependency key (e.g. ``euri:gpt-4.1-mini``).

CLOSED → (``failure_threshold`` consecutive failures) → OPEN → (after ``recovery_seconds``) →
HALF_OPEN → one trial call → CLOSED on success / OPEN on failure.

Quota exhaustion opens the circuit immediately for ``quota_cooldown_seconds`` so a model whose
daily quota is spent is skipped (and the chain falls back) instead of being hammered.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum

from src.core.errors import AppError, CircuitOpen, QuotaExceeded

logger = logging.getLogger(__name__)


class CircuitState(IntEnum):
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


@dataclass
class CircuitBreaker:
    key: str
    failure_threshold: int = 3
    recovery_seconds: float = 30.0
    quota_cooldown_seconds: float = 600.0
    clock: Callable[[], float] = time.monotonic
    on_state_change: Callable[[str, CircuitState], None] | None = None
    _state: CircuitState = CircuitState.CLOSED
    _failures: int = 0
    _open_until: float = 0.0
    _trial_in_flight: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _set(self, state: CircuitState) -> None:
        if state is not self._state:
            logger.info("circuit state change", extra={"circuit": self.key, "state": state.name})
            self._state = state
            if self.on_state_change:
                self.on_state_change(self.key, state)

    def _maybe_half_open(self) -> None:
        if self._state is CircuitState.OPEN and self.clock() >= self._open_until:
            self._set(CircuitState.HALF_OPEN)
            self._trial_in_flight = False

    def before_call(self) -> None:
        """Raise :class:`CircuitOpen` if calls are not allowed right now."""
        with self._lock:
            self._maybe_half_open()
            if self._state is CircuitState.OPEN:
                retry_in = max(0.0, self._open_until - self.clock())
                raise CircuitOpen(
                    f"{self.key} temporarily disabled after repeated failures",
                    details={"circuit": self.key, "retryInSeconds": round(retry_in, 1)},
                )
            if self._state is CircuitState.HALF_OPEN:
                if self._trial_in_flight:
                    raise CircuitOpen(
                        f"{self.key} trial call in progress", details={"circuit": self.key}
                    )
                self._trial_in_flight = True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._trial_in_flight = False
            self._set(CircuitState.CLOSED)

    def record_failure(self, error: AppError | None = None) -> None:
        """Count a failure. Client-side errors (4xx other than quota/rate) are not counted."""
        with self._lock:
            self._trial_in_flight = False
            if isinstance(error, QuotaExceeded):
                self._open(self.quota_cooldown_seconds)
                return
            if error is not None and not error.retryable and error.status_code < 500:
                return
            self._failures += 1
            if self._state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._open(self.recovery_seconds)

    def _open(self, seconds: float) -> None:
        self._open_until = self.clock() + seconds
        self._failures = 0
        self._set(CircuitState.OPEN)


class BreakerRegistry:
    """Process-wide breakers keyed by dependency."""

    def __init__(self, on_state_change: Callable[[str, CircuitState], None] | None = None) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self._on_state_change = on_state_change

    def get(self, key: str) -> CircuitBreaker:
        with self._lock:
            if key not in self._breakers:
                self._breakers[key] = CircuitBreaker(key, on_state_change=self._on_state_change)
            return self._breakers[key]

    def snapshot(self) -> dict[str, str]:
        return {k: b.state.name for k, b in self._breakers.items()}

    def reset(self) -> None:
        with self._lock:
            self._breakers.clear()
