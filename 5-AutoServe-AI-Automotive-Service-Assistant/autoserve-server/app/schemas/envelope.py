"""Response envelope used by every endpoint: {status, data, error, request_id}."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class Envelope[T](BaseModel):
    status: Literal["ok", "error"]
    data: T | None = None
    error: ErrorBody | None = None
    request_id: str

    @classmethod
    def ok(cls, data: T, request_id: str) -> Envelope[T]:
        return cls(status="ok", data=data, error=None, request_id=request_id)

    @classmethod
    def fail(cls, code: str, message: str, request_id: str, details: dict[str, Any] | None = None) -> Envelope[T]:
        return cls(
            status="error",
            data=None,
            error=ErrorBody(code=code, message=message, details=details),
            request_id=request_id,
        )
