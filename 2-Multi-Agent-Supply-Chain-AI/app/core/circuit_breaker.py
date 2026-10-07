"""Per provider:model circuit breaker.

closed → (N consecutive outage errors) → open → (cool-down) → half-open: one trial call →
success closes it, failure re-opens it. Only outages count (quota, rate limit, 5xx, timeout) — never 400s.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.metrics import CIRCUIT_STATE


@dataclass
class _State:
    failures: int = 0
    opened_at: float | None = None
    trial_in_flight: bool = False


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    clock: Callable[[], float] = time.monotonic
    _state: _State = field(default_factory=_State)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def state(self) -> str:
        with self._lock:
            return self._state_name()

    def _state_name(self) -> str:
        s = self._state
        if s.opened_at is None:
            return "closed"
        if self.clock() - s.opened_at >= self.cooldown_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        """Whether a call may proceed. In half-open state exactly one trial call is let through."""
        with self._lock:
            name = self._state_name()
            if name == "closed":
                return True
            if name == "half_open" and not self._state.trial_in_flight:
                self._state.trial_in_flight = True
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._state = _State()
        CIRCUIT_STATE.labels(self.name).set(0)

    def record_failure(self, is_outage: bool) -> None:
        if not is_outage:
            # A bad request says nothing about provider health; release a half-open trial slot.
            with self._lock:
                self._state.trial_in_flight = False
            return
        with self._lock:
            s = self._state
            s.trial_in_flight = False
            s.failures += 1
            if s.opened_at is not None or s.failures >= self.failure_threshold:
                s.opened_at = self.clock()
        if self._state.opened_at is not None:
            CIRCUIT_STATE.labels(self.name).set(1)


class BreakerRegistry:
    def __init__(self, failure_threshold: int, cooldown_seconds: float) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> CircuitBreaker:
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, self._threshold, self._cooldown)
            return self._breakers[name]

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return {n: b.state for n, b in self._breakers.items()}
