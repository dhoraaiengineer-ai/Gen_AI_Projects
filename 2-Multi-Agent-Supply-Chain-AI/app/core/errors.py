"""Error taxonomy.

Every error is classified as retryable or not and maps to one HTTP status. Provider errors are normalised
here so the rest of the code never handles SDK-specific exceptions:
quota or rate limit → 429, provider error → 502, provider unreachable → 503.
"""

from __future__ import annotations


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    retryable = False
    public_message = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message or self.public_message)
        self.message = message or self.public_message
        self.details = details or {}


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"
    public_message = "The request is invalid."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    public_message = "Not found."


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    public_message = "Sign in to continue."


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    public_message = "You don't have permission to do that."


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    public_message = "The resource changed. Refresh and try again."


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    retryable = True
    public_message = "Too many requests. Please wait a moment."

    def __init__(self, message: str | None = None, *, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GuardrailBlocked(AppError):
    status_code = 400
    code = "guardrail_blocked"
    public_message = "This request can't be processed."


# ----------------------------------------------------------------- providers (LLM, embeddings, web search)
class ProviderFailure(AppError):
    """Base for upstream provider failures. Subclasses that are outages trigger fallbacks and trip breakers."""

    status_code = 502
    code = "provider_error"
    retryable = True
    is_outage = True
    public_message = "The AI provider returned an error."


class ProviderQuotaExceeded(ProviderFailure):
    status_code = 429
    code = "provider_quota"
    public_message = "The AI provider's quota is exhausted. Please try again later."


class ProviderRateLimited(ProviderFailure):
    status_code = 429
    code = "provider_rate_limited"
    public_message = "The AI provider is rate limiting requests. Please try again shortly."


class ProviderUnavailable(ProviderFailure):
    status_code = 503
    code = "provider_unavailable"
    public_message = "The AI provider is unreachable. Please try again shortly."


class ProviderBadRequest(ProviderFailure):
    """A 4xx from the provider (not quota): our request was wrong. Not an outage — never trips the breaker."""

    status_code = 502
    code = "provider_bad_request"
    retryable = False
    is_outage = False


class CircuitOpen(ProviderFailure):
    status_code = 503
    code = "circuit_open"
    public_message = "The AI provider is temporarily disabled after repeated failures."


class ToolFailure(AppError):
    status_code = 502
    code = "tool_error"
    retryable = True
