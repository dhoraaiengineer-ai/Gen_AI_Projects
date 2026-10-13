"""Error taxonomy.

Every failure the API can report is an :class:`AppError` subclass with a stable ``code`` and HTTP
status. Responses carry the request id and never a stack trace.

| Error | HTTP |
|---|---|
| quota exhausted / rate limited (incl. gateways that answer 403 for quota) | 429 |
| provider returned an error | 502 |
| provider/dependency unreachable, circuit open | 503 |
| timeout | 504 |
"""

from __future__ import annotations

from typing import Any, ClassVar


class AppError(Exception):
    """Base class for expected, user-reportable errors."""

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "internal_error"
    retryable: ClassVar[bool] = False

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self, request_id: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message, "requestId": request_id}
        if self.details:
            body["details"] = self.details
        return {"error": body}


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class GuardrailBlocked(AppError):
    status_code = 400
    code = "guardrail_blocked"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after = retry_after


class QuotaExceeded(RateLimited):
    code = "quota_exceeded"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"


class ProviderUnavailable(AppError):
    status_code = 503
    code = "provider_unavailable"
    retryable = True


class CircuitOpen(ProviderUnavailable):
    code = "circuit_open"


class ModelUnavailable(ProviderUnavailable):
    """An ML model is not trained, not registered, or failed its integrity check."""

    code = "model_unavailable"


class DependencyTimeout(AppError):
    status_code = 504
    code = "timeout"
    retryable = True


# Quota (daily/billing) vs short-term rate limit. Groq daily limits say "tokens per day (TPD)".
_QUOTA_MARKERS = ("quota", "insufficient_quota", "exceeded your", "tokens per day", "per day")


def classify_provider_failure(status: int | None, message: str, *, provider: str) -> AppError:
    """Map a provider HTTP status/message to the taxonomy.

    Some OpenAI-compatible gateways answer 403 when the quota is exhausted; that is a 429.
    """
    text = message.lower()
    details = {"provider": provider, "upstreamStatus": status}
    if status == 429 or (status in {402, 403} and any(m in text for m in _QUOTA_MARKERS)):
        cls: type[RateLimited] = (
            QuotaExceeded if any(m in text for m in _QUOTA_MARKERS) else RateLimited
        )
        return cls(f"{provider} rate limit or quota exhausted", details=details)
    if status in {401, 403}:
        return ProviderError(f"{provider} rejected the credentials", details=details)
    if status is None or status in {502, 503, 504}:
        return ProviderUnavailable(f"{provider} is unreachable", details=details)
    if status == 408:
        return DependencyTimeout(f"{provider} timed out", details=details)
    return ProviderError(f"{provider} returned an error", details=details)


def map_provider_exception(exc: BaseException, *, provider: str) -> AppError:
    """Map any SDK/transport exception to the taxonomy without importing provider SDKs.

    Works by duck typing: OpenAI, Anthropic and httpx exceptions expose ``status_code`` and/or
    have recognisable class names (``...Timeout...``, ``...Connection...``).
    """
    if isinstance(exc, AppError):
        return exc
    name = type(exc).__name__
    if isinstance(exc, TimeoutError) or "Timeout" in name:
        return DependencyTimeout(f"{provider} timed out", details={"provider": provider})
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
        message = str(getattr(exc, "message", "") or exc)
        response = getattr(exc, "response", None)
        try:  # quota wording is often only in the body (e.g. httpx HTTPStatusError)
            body = str(getattr(response, "text", "") or "")[:500]
        except Exception:  # streaming responses may not expose .text
            body = ""
        return classify_provider_failure(status, f"{message} {body}", provider=provider)
    if isinstance(exc, ConnectionError) or "Connection" in name or "Connect" in name:
        return ProviderUnavailable(f"{provider} is unreachable", details={"provider": provider})
    return ProviderError(
        f"{provider} call failed", details={"provider": provider, "exception": name}
    )
