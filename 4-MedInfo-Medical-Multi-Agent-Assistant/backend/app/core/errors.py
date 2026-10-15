"""Domain errors. The API layer maps these to HTTP status codes (see app/api/errors.py)."""

from __future__ import annotations


class AppError(Exception):
    """Base class for errors that carry a safe, user-facing message."""

    status_code = 500
    public_message = "Something went wrong. Please try again."

    def __init__(self, detail: str | None = None, *, retry_after: int | None = None) -> None:
        super().__init__(detail or self.public_message)
        self.detail = detail or self.public_message
        self.retry_after = retry_after


class ProviderQuotaError(AppError):
    """Provider quota spent or rate limited (includes gateways that report quota as HTTP 403)."""

    status_code = 429
    public_message = "The AI provider's quota or rate limit was reached. Please try again later."


class ProviderError(AppError):
    """The provider answered with an error."""

    status_code = 502
    public_message = "The AI provider returned an error. Please try again."


class ProviderUnavailableError(AppError):
    """Provider unreachable, timed out, not configured, or all circuits open."""

    status_code = 503
    public_message = "The AI service is temporarily unavailable. Please try again shortly."


class InputRejectedError(AppError):
    status_code = 422
    public_message = "The question could not be processed."
