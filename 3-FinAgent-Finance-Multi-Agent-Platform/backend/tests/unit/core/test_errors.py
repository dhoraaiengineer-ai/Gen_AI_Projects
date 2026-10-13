"""Error taxonomy: status codes and provider failure classification."""

from __future__ import annotations

import pytest

from src.core.errors import (
    DependencyTimeout,
    ProviderError,
    ProviderUnavailable,
    QuotaExceeded,
    RateLimited,
    classify_provider_failure,
)


@pytest.mark.parametrize(
    ("status", "message", "expected", "http"),
    [
        (429, "Too many requests", RateLimited, 429),
        (429, "You exceeded your current quota", QuotaExceeded, 429),
        (403, "Daily token quota exhausted for this model", QuotaExceeded, 429),
        (403, "invalid api key", ProviderError, 502),
        (401, "unauthorized", ProviderError, 502),
        (500, "internal error", ProviderError, 502),
        (503, "service unavailable", ProviderUnavailable, 503),
        (None, "connection refused", ProviderUnavailable, 503),
        (408, "request timeout", DependencyTimeout, 504),
    ],
)
def test_provider_failures_map_to_taxonomy(
    status: int | None, message: str, expected: type, http: int
) -> None:
    err = classify_provider_failure(status, message, provider="euri")
    assert type(err) is expected
    assert err.status_code == http
    assert err.details["provider"] == "euri"


def test_error_body_has_request_id_and_no_internals() -> None:
    body = QuotaExceeded("euri quota", details={"provider": "euri"}).to_dict("req_123")
    assert body == {
        "error": {
            "code": "quota_exceeded",
            "message": "euri quota",
            "requestId": "req_123",
            "details": {"provider": "euri"},
        }
    }


def test_groq_daily_token_limit_is_quota_but_per_minute_limit_is_not() -> None:
    daily = classify_provider_failure(
        429, "Rate limit reached for model on tokens per day (TPD)", provider="groq"
    )
    minute = classify_provider_failure(
        429, "Rate limit reached for model on requests per minute (RPM)", provider="groq"
    )
    assert type(daily) is QuotaExceeded
    assert type(minute) is RateLimited
