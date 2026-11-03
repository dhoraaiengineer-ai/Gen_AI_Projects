"""Shared response envelope and error schema."""
# TODO (Team 1): implement — Spec: .claude/specs/api-design.md § response envelope
# All responses must use: { status, data, error, request_id }

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard response wrapper for all 46 endpoints."""

    status: str  # "success" | "error"
    data: Any  # endpoint-specific payload
    error: dict | None  # { code, message } or None
    request_id: str  # UUID v7 — echoed from X-Trace-ID


class ErrorDetail(BaseModel):
    """Structured error returned in APIResponse.error."""

    code: str  # e.g. "ERR_PIPELINE_NOT_FOUND"
    message: str  # human-friendly
    request_id: str
