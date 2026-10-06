"""Request / response schemas for the public API."""

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1_000_000)
    source: str = Field("inline", max_length=500, description="Where the text came from (filename, URL, ...)")
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[DocumentIn] = Field(..., min_length=1, max_length=100)


class IngestResponse(BaseModel):
    documents: int
    chunks: int


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int | None = Field(None, ge=1, le=20)


class SourceChunk(BaseModel):
    source: str
    text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    model: str


class AgentRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4000)


class AgentResponse(BaseModel):
    answer: str
    tool_calls: int
    model: str


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, bool]


class ErrorResponse(BaseModel):
    detail: str


class MeResponse(BaseModel):
    user_id: str
    email: str | None
    role: str


class AuthConfigResponse(BaseModel):
    enabled: bool
    supabase_url: str | None
    supabase_publishable_key: str | None
