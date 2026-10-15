"""Per-model circuit breaker: after N consecutive failures the model is skipped for a cool-down,
then one trial call (half-open) decides whether it closes again."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from enum import IntEnum

from app.core.metrics import CIRCUIT_STATE

logger = logging.getLogger(__name__)


class State(IntEnum):
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self._threshold = failure_threshold
        self._reset = reset_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at = 0.0
        self._state = State.CLOSED
        self._lock = threading.Lock()
        CIRCUIT_STATE.labels(name).set(State.CLOSED)

    @property
    def state(self) -> State:
        with self._lock:
            if self._state is State.OPEN and self._clock() - self._opened_at >= self._reset:
                self._set(State.HALF_OPEN)
            return self._state

    def allow(self) -> bool:
        return self.state is not State.OPEN

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state is not State.CLOSED:
                self._set(State.CLOSED)

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state is State.HALF_OPEN or self._failures >= self._threshold:
                self._opened_at = self._clock()
                self._set(State.OPEN)

    def _set(self, state: State) -> None:
        if state is not self._state:
            logger.warning("circuit state change", extra={"model": self.name, "state": state.name.lower()})
        self._state = state
        CIRCUIT_STATE.labels(self.name).set(state)
