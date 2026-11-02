"""Typed domain errors → API error codes (docs/API_SPEC.md §2)."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.details = details


class ValidationFailed(DomainError):
    code, http_status, default_message = "VALIDATION_ERROR", 400, "Request validation failed."


class InvalidVin(DomainError):
    code, http_status, default_message = "INVALID_VIN", 400, "VIN is invalid."


class InvalidDtc(DomainError):
    code, http_status, default_message = "INVALID_DTC", 400, "DTC format is invalid."


class Unauthenticated(DomainError):
    code, http_status, default_message = "UNAUTHENTICATED", 401, "Authentication required."


class ForbiddenRole(DomainError):
    code, http_status, default_message = "FORBIDDEN_ROLE", 403, "Your role cannot perform this action."


class NotFound(DomainError):
    code, http_status, default_message = "NOT_FOUND", 404, "Not found."


class InvalidTransition(DomainError):
    code, http_status, default_message = "INVALID_TRANSITION", 409, "This status change is not allowed."


class IdempotencyConflict(DomainError):
    code, http_status, default_message = "IDEMPOTENCY_CONFLICT", 409, "Idempotency key reused with a different request."


class OdometerRegression(DomainError):
    code, http_status, default_message = "ODOMETER_REGRESSION", 409, "Odometer is lower than the last recorded value."


class SlotUnavailable(DomainError):
    code, http_status, default_message = "SLOT_UNAVAILABLE", 409, "That slot is no longer available."


class FileTooLarge(DomainError):
    code, http_status, default_message = "FILE_TOO_LARGE", 413, "File is too large."


class UnsupportedMedia(DomainError):
    code, http_status, default_message = "UNSUPPORTED_MEDIA", 415, "Unsupported file type."


class NotEstimable(DomainError):
    code, http_status, default_message = "NOT_ESTIMABLE", 422, "Estimate cannot be calculated."


class RationaleRequired(DomainError):
    code, http_status, default_message = "RATIONALE_REQUIRED", 422, "A reason or note is required."


class RateLimited(DomainError):
    code, http_status, default_message = "RATE_LIMITED", 429, "Too many requests."


class LlmUnavailable(DomainError):
    code, http_status = "LLM_UNAVAILABLE", 502
    default_message = "The assistant is temporarily unavailable. Please try again or contact your service advisor."


class NotReady(DomainError):
    code, http_status, default_message = "NOT_READY", 503, "Service is not ready."


# HTTP status → code for framework-raised HTTPExceptions (e.g. unknown route).
HTTP_STATUS_CODES: dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN_ROLE",
    404: "NOT_FOUND",
    405: "VALIDATION_ERROR",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA",
    429: "RATE_LIMITED",
}
