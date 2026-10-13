"""Circuit breaker, retry policy and SDK exception mapping."""

from __future__ import annotations

import pytest

from src.core.circuit_breaker import CircuitBreaker, CircuitState
from src.core.errors import (
    AppError,
    CircuitOpen,
    DependencyTimeout,
    ProviderError,
    ProviderUnavailable,
    QuotaExceeded,
    map_provider_exception,
)
from src.core.retry import is_retryable, retry_sync


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_breaker_opens_after_threshold_and_recovers_via_half_open() -> None:
    clock = Clock()
    breaker = CircuitBreaker("euri:m", failure_threshold=2, recovery_seconds=30, clock=clock)
    breaker.record_failure(ProviderUnavailable("down"))
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure(ProviderUnavailable("down"))
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpen):
        breaker.before_call()
    clock.now = 31
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.before_call()  # the single trial call
    with pytest.raises(CircuitOpen, match="trial"):
        breaker.before_call()
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED


def test_failed_trial_reopens() -> None:
    clock = Clock()
    breaker = CircuitBreaker("k", failure_threshold=1, recovery_seconds=10, clock=clock)
    breaker.record_failure(ProviderUnavailable("down"))
    clock.now = 11
    breaker.before_call()
    breaker.record_failure(ProviderUnavailable("still down"))
    assert breaker.state is CircuitState.OPEN


def test_quota_opens_immediately_for_cooldown() -> None:
    clock = Clock()
    breaker = CircuitBreaker("k", quota_cooldown_seconds=600, clock=clock)
    breaker.record_failure(QuotaExceeded("quota"))
    assert breaker.state is CircuitState.OPEN
    clock.now = 599
    assert breaker.state is CircuitState.OPEN
    clock.now = 601
    assert breaker.state is CircuitState.HALF_OPEN


def test_client_errors_do_not_trip_the_breaker() -> None:
    breaker = CircuitBreaker("k", failure_threshold=1)
    breaker.record_failure(AppError("bad request"))  # 500-class base, counted
    assert breaker.state is CircuitState.OPEN
    other = CircuitBreaker("k2", failure_threshold=1)

    class BadInput(AppError):
        status_code = 422
        code = "validation_failed"

    other.record_failure(BadInput("schema"))
    assert other.state is CircuitState.CLOSED


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (ProviderUnavailable("x"), True),
        (DependencyTimeout("x"), True),
        (QuotaExceeded("x"), False),
        (CircuitOpen("x"), False),
        (ProviderError("x"), False),
        (ValueError("x"), False),
    ],
)
def test_retry_policy(error: BaseException, retryable: bool) -> None:
    assert is_retryable(error) is retryable


def test_retry_sync_retries_transient_then_succeeds() -> None:
    calls: list[int] = []
    delays: list[float] = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ProviderUnavailable("blip")
        return "ok"

    assert retry_sync(flaky, attempts=4, sleep=delays.append) == "ok"
    assert len(calls) == 3
    assert len(delays) == 2


def test_retry_sync_gives_up_on_quota_immediately() -> None:
    calls: list[int] = []

    def quota() -> None:
        calls.append(1)
        raise QuotaExceeded("quota")

    with pytest.raises(QuotaExceeded):
        retry_sync(quota, attempts=4, sleep=lambda _: None)
    assert len(calls) == 1


class FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


@pytest.mark.parametrize(
    ("exc", "expected", "http"),
    [
        (FakeStatusError(429, "Rate limit reached"), "rate_limited", 429),
        (FakeStatusError(403, "You exceeded your daily quota"), "quota_exceeded", 429),
        (FakeStatusError(401, "bad key"), "provider_error", 502),
        (FakeStatusError(503, "overloaded"), "provider_unavailable", 503),
        (APITimeoutError("read timed out"), "timeout", 504),
        (APIConnectionError("dns"), "provider_unavailable", 503),
        (RuntimeError("weird"), "provider_error", 502),
    ],
)
def test_sdk_exceptions_map_to_taxonomy(exc: BaseException, expected: str, http: int) -> None:
    error = map_provider_exception(exc, provider="groq")
    assert error.code == expected
    assert error.status_code == http
