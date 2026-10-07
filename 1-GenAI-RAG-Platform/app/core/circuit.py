"""Circuit breaker for LLM providers.

closed    -> calls go through; consecutive failures are counted.
open      -> after `failure_threshold` consecutive failures, calls fail instantly with CircuitOpenError for
             `reset_seconds`, so the fallback chain moves on without waiting on a provider that is down or
             out of quota.
half-open -> after the cool-down, one trial call is let through: success closes the circuit, failure reopens it.

State is per process (one uvicorn worker per pod), like the rate limits.
"""

import logging
import threading
import time
from collections.abc import Callable
from enum import IntEnum

from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)

CIRCUIT_STATE = Gauge("rag_circuit_state", "Circuit breaker state (0 closed, 1 half-open, 2 open)", ["breaker"])
CIRCUIT_REJECTIONS = Counter("rag_circuit_rejections_total", "Calls skipped because the circuit was open", ["breaker"])


class State(IntEnum):
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class CircuitOpenError(RuntimeError):
    def __init__(self, name: str, retry_in: float):
        super().__init__(f"circuit '{name}' is open; skipping for {retry_in:.0f}s more")
        self.name = name
        self.retry_in = retry_in


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None
        self._trial_in_flight = False
        CIRCUIT_STATE.labels(name).set(State.CLOSED)

    @property
    def state(self) -> State:
        with self._lock:
            return self._state()

    def _state(self) -> State:
        if self._opened_at is None:
            return State.CLOSED
        if self._clock() - self._opened_at >= self.reset_seconds:
            return State.HALF_OPEN
        return State.OPEN

    def before_call(self) -> None:
        """Raise CircuitOpenError if the call must be skipped."""
        with self._lock:
            state = self._state()
            if state == State.OPEN or (state == State.HALF_OPEN and self._trial_in_flight):
                CIRCUIT_REJECTIONS.labels(self.name).inc()
                retry_in = max(0.0, self.reset_seconds - (self._clock() - (self._opened_at or 0.0)))
                raise CircuitOpenError(self.name, retry_in)
            if state == State.HALF_OPEN:
                self._trial_in_flight = True  # only one trial call at a time

    def record_success(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                logger.info("circuit closed", extra={"breaker": self.name})
            self._failures = 0
            self._opened_at = None
            self._trial_in_flight = False
            CIRCUIT_STATE.labels(self.name).set(State.CLOSED)

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            reopen = self._trial_in_flight  # a failed half-open trial reopens immediately
            self._trial_in_flight = False
            if reopen or self._failures >= self.failure_threshold:
                if self._opened_at is None or reopen:
                    logger.warning(
                        "circuit opened",
                        extra={"breaker": self.name, "failures": self._failures, "cooldown_s": self.reset_seconds},
                    )
                self._opened_at = self._clock()
                CIRCUIT_STATE.labels(self.name).set(State.OPEN)


class BreakerRegistry:
    """One breaker per provider:model, shared by every chain that uses that model."""

    def __init__(self, failure_threshold: int, reset_seconds: float):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> CircuitBreaker:
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, self.failure_threshold, self.reset_seconds)
            return self._breakers[name]
