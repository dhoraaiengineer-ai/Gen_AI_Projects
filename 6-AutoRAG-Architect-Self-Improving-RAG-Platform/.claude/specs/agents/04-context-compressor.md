# Agent 4: Context Compressor

**Status**: Spec | **Phase**: D-14, D-7 | **Team**: Team 8

---

## Responsibility

Compress and filter the retrieved context chunks to fit within the LLM token budget before generation. Applies cross-encoder reranking (Cohere Rerank API), removes low-relevance passages, and trims to a target token ceiling. Runs after retrieval and before the LLM generation call.

---

## Input Schema

```python
class ContextCompressorInput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    query: str                   # rewritten query from Query Rewriter
    retrieved_chunks: list[RetrievedChunk]  # raw retrieval output (up to top-20)
    token_budget: int = 4096     # max tokens to pass to LLM
    rerank_top_k: int = 20       # candidates passed to Cohere
    x_trace_id: str

class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    source_uri: str
    page_number: int
    chunk_strategy: str
```

---

## Output Schema

```python
class ContextCompressorOutput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    query: str
    compressed_context: list[RetrievedChunk]  # reranked, trimmed subset
    tokens_used: int
    reranker_provider: str       # "cohere" | "bge-reranker"
    chunks_before: int
    chunks_after: int
    duration_ms: float
    x_trace_id: str
```

---

## Failure Modes

| Failure                                 | Classification | Retry Policy                                             |
| --------------------------------------- | -------------- | -------------------------------------------------------- |
| Cohere API unavailable                  | Transient      | Graph edge → BGE-Reranker local fallback                 |
| BGE-Reranker unavailable                | Hard block     | Halt; emit `agent.health_degraded`                       |
| Token budget exceeded after compression | Validation     | Truncate to budget; log warning — do not fail            |
| All chunks below relevance threshold    | Soft block     | Pass top-1 chunk; log warning for Diagnoser              |
| Empty retrieved_chunks input            | Validation     | Return empty context; trigger Diagnoser (Retrieval Miss) |

---

## Retry Policy

Cohere fallback to BGE-Reranker is an explicit conditional graph edge. If both are unavailable, the pipeline halts and the Diagnoser is triggered with failure type `Context Overflow`.

---

## Telemetry Emitted

| Event                 | When                      | Fields                                                                            |
| --------------------- | ------------------------- | --------------------------------------------------------------------------------- |
| Structured log (INFO) | Compression complete      | `chunks_before`, `chunks_after`, `tokens_used`, `reranker_provider`, `x_trace_id` |
| Structured log (WARN) | Cohere fallback activated | `fallback_reason`, `x_trace_id`                                                   |
| Structured log (WARN) | Token budget truncation   | `tokens_truncated`, `x_trace_id`                                                  |

---

## Dependencies

- Cohere Rerank API (primary reranker)
- BGE-Reranker (local fallback — must be available in ECS container)
- Retrieval output from hybrid search (Dense + BM25 fusion)
- `token_budget` is set per LLM provider — Gemini Flash 3.5, KiMi K2.6, and Gemini 3.5 have different context windows

## Rule 86 — Cost & Latency

Before passing `compressed_context` into the generation step, call `TokenGuardrail.check(token_count=tokens_used, budget_type=TokenBudgetType.CONTEXT, x_trace_id=state["x_trace_id"])`. The `token_budget` input field must never exceed `MAX_CONTEXT_TOKENS` from environment variables — `TokenGuardrail.check_expansion_safe()` guards this. Cost for the downstream LLM generation call is tracked by `LLMService`, not by this node.
