"""
Input Validators — AutoRAG v3.0
Schema-level and content-level validation at the FastAPI route boundary.
Called before any PII masking or LangGraph dispatch.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class QueryInput(BaseModel):
    """Validated query schema. All routes accepting user queries must use this."""

    query: str = Field(..., min_length=1, max_length=4096)
    pipeline_id: str = Field(..., pattern=r"^[a-f0-9\-]{36}$")  # UUID v7 format
    organization_id: str = Field(..., pattern=r"^[a-f0-9\-]{36}$")

    @field_validator("query")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("Query contains null bytes — rejected")
        return v.strip()
