"""Request / response schemas for the public API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.rag.chunking import ChunkingStrategy


class DocumentIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1_000_000)
    source: str = Field("inline", max_length=500, description="Where the text came from (filename, URL, ...)")
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[DocumentIn] = Field(..., min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20, description="Tags for filtering, e.g. finance")
    chunking: ChunkingStrategy | None = Field(None, description="Chunking strategy; omit to use the server default")
    chunk_overlap_pct: float | None = Field(
        None,
        ge=0,
        le=50,
        description="Overlap as % of chunk size for this upload. Omit for the defaults (15% chunks, 10% children)",
    )


class DocumentResult(BaseModel):
    source: str
    status: Literal["added", "updated", "unchanged", "empty", "failed"]
    chunking: ChunkingStrategy | None = None
    chunks: int = Field(0, description="Chunks the document has after this upload")
    added: int = Field(0, description="Chunks embedded by this upload")
    removed: int = Field(0, description="Stale chunks deleted by this upload")
    golden_questions: int = Field(0, description="Golden Q&A pairs generated for this document")
    guardrail_flags: list[str] = Field(default_factory=list, description="e.g. prompt_injection found in the file")
    error: str | None = None


class IngestResponse(BaseModel):
    documents: int
    chunks: int = Field(..., description="Chunks embedded by this upload (unchanged documents add none)")
    chunking: ChunkingStrategy
    results: list[DocumentResult]


SESSION_ID = Field(
    None,
    pattern=r"^[A-Za-z0-9_-]{1,64}$",
    description="Conversation id. Messages with the same id share memory, so follow-up questions work.",
)


class QueryFilters(BaseModel):
    """Metadata filter: only search chunks from these documents / file types / tags (all optional)."""

    sources: list[str] = Field(default_factory=list, max_length=50, description="File names")
    file_types: list[str] = Field(default_factory=list, max_length=20, description='e.g. ["pdf", "xlsx"]')
    tags: list[str] = Field(default_factory=list, max_length=20, description="Tags given at upload")


class GuardrailEvent(BaseModel):
    stage: Literal["input", "documents", "output"]
    check: str
    action: Literal["allow", "flag", "redact", "block"]
    detail: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int | None = Field(None, ge=1, le=20)
    session_id: str | None = SESSION_ID
    filters: QueryFilters | None = None


class SourceChunk(BaseModel):
    source: str
    location: str | None = Field(None, description='Where in the source: "p. 3", "sheet Sales", "slide 4"')
    text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    model: str
    cached: bool = Field(False, description="Served from the answer cache (no retrieval or LLM call)")
    standalone_question: str | None = Field(None, description="The follow-up rewritten using the conversation")
    grounded: bool | None = Field(None, description="Passed the hallucination guard (None when it is off)")
    grounding_issues: list[str] = Field(default_factory=list, description="Why the answer may not be grounded")
    blocked: bool = Field(False, description="Stopped by a guardrail (the answer is the policy refusal)")
    guardrails: list[GuardrailEvent] = Field(default_factory=list, description="Guardrail checks that fired")


class AgentRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = SESSION_ID
    filters: QueryFilters | None = None


class AgentResponse(BaseModel):
    answer: str
    tool_calls: int
    model: str
    web_sources: list[str] = Field(default_factory=list, description="URLs of web results the agent read")
    blocked: bool = False
    guardrails: list[GuardrailEvent] = Field(default_factory=list)


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


class GoldenItemIn(BaseModel):
    source: str = Field(..., min_length=1, max_length=500, description="Must match the uploaded file name")
    question: str = Field(..., min_length=5, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=4000)
    evidence: str = Field(..., min_length=5, max_length=2000, description="Verbatim quote that proves the answer")
    location: str | None = Field(None, max_length=100)


class GoldenImportRequest(BaseModel):
    items: list[GoldenItemIn] = Field(..., min_length=1, max_length=500)


class GoldenItemOut(GoldenItemIn):
    id: str
    origin: Literal["generated", "manual"]


class GoldenListResponse(BaseModel):
    count: int
    items: list[GoldenItemOut]


class EvalRequest(BaseModel):
    source: str | None = Field(None, description="Only evaluate this document's golden items")
    limit: int = Field(20, ge=1, le=200, description="Max golden items to run")
    top_k: int | None = Field(None, ge=1, le=20)
    judge: bool = Field(
        True, description="Also generate answers and grade them: LLM-judge correctness plus the RAGAS metrics"
    )
    metrics: list[Literal["faithfulness", "answer_relevancy", "context_precision", "context_recall"]] = Field(
        default_factory=lambda: ["faithfulness", "answer_relevancy", "context_precision", "context_recall"],
        description="RAGAS metrics to compute when judge is true (1 LLM call each per item)",
    )


class EvalItemOut(BaseModel):
    question: str
    expected_answer: str
    source: str
    evidence: str
    retrieved: list[str]
    evidence_rank: int | None
    source_hit: bool
    answer: str | None
    correct: bool | None
    judge_reason: str | None
    cited_expected_source: bool | None
    grounded: bool | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None


class EvalResponse(BaseModel):
    count: int
    top_k: int
    judged: bool
    evidence_hit_rate: float | None = Field(None, description="Share of items whose evidence was retrieved")
    source_hit_rate: float | None
    mrr: float | None = Field(None, description="Mean reciprocal rank of the evidence chunk")
    answer_accuracy: float | None = Field(None, description="LLM-as-judge: answer matches the reference")
    citation_accuracy: float | None
    grounded_rate: float | None = Field(None, description="Answers passing the hallucination guard")
    faithfulness: float | None = Field(None, description="RAGAS: answer claims supported by the contexts")
    answer_relevancy: float | None = Field(None, description="RAGAS: answer addresses the question")
    context_precision: float | None = Field(None, description="RAGAS: useful contexts ranked high")
    context_recall: float | None = Field(None, description="RAGAS: reference facts present in the contexts")
    items: list[EvalItemOut]


class DocumentInfo(BaseModel):
    source: str
    chunking: str
    chunks: int


class DocumentListResponse(BaseModel):
    count: int
    documents: list[DocumentInfo]


class DeleteDocumentResponse(BaseModel):
    source: str
    chunks_deleted: int
    golden_deleted: int


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConversationOut(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class SessionOut(BaseModel):
    session_id: str
    title: str
    messages: int
    updated_at: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionOut]


class SourceInfo(BaseModel):
    source: str
    file_type: str


class SourceListResponse(BaseModel):
    sources: list[SourceInfo]
