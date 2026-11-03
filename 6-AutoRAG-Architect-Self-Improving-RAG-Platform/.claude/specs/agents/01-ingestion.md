# Agent 1: Ingestion

**Status**: Spec | **Phase**: D-5, D-6 | **Team**: Team 5 + Team 7

---

## Responsibility

Parse raw documents, apply Custom PII Detection & Masking Functions, apply the configured chunking strategy, upload artifacts to Supabase Storage, and write embeddings to Supabase Vector.

---

## Input Schema

```python
class IngestionInput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    storage_source_uri: str      # Supabase Storage path — e.g. pipelines/{pipeline_id}/doc.pdf
    chunk_strategy: Literal["semantic", "hierarchical", "late"]
    chunk_size: int = 1024       # parent chunk size (tokens)
    child_chunk_size: int = 128  # hierarchical child size (tokens)
    x_trace_id: str              # propagated from API request
```

---

## Output Schema

```python
class IngestionOutput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    collection_name: str         # superseded 20-Jul-2026 -- chunks now live in the
                                  # shared pipeline_chunks table (Version 4.0,
                                  # migration 0016), partitioned by pipeline_version,
                                  # not a per-pipeline physical table/collection
    chunks_indexed: int
    pii_entities_masked: int
    storage_chunks_uri: str      # Supabase Storage path — chunks/{pipeline_id}/{version}/
    duration_ms: float
    x_trace_id: str
```

---

## Failure Modes

| Failure                  | Classification | Retry Policy                                                        |
| ------------------------ | -------------- | ------------------------------------------------------------------- |
| Supabase Storage read timeout | Transient | Retry via explicit graph edge — max 3 attempts, 5s backoff          |
| PII scan error      | Transient      | Retry once; if fails, halt and emit `agent.health_degraded` webhook |
| PII detected      | Not a failure     | **Corrected 13-Jul-2026 (P0.7-4)** — the canonical PII engine (`app/services/pii_engine.py`) masks detected PII in-line and ingestion proceeds with the masked text; a `pii_redacted` audit_log event records safe metadata (counts by type, source, detector version). This row previously described a hard block (`status: pii_block`) that was never implemented anywhere in the runtime — see PRD §12.1 for the matching correction. |
| Supabase Vector write failure     | Transient      | Retry via explicit LangGraph graph edge; push to Redis dead-letter key; do not inline retry |
| Unsupported file type    | Validation     | Return error immediately — no retry                                 |
| Chunk size exceeds limit | Validation     | Return error immediately — no retry                                 |

---

## Retry Policy

All retries modeled as explicit LangGraph graph edges — no inline `try/except` retry loops inside the node function. See MEMORY.md L-001.

---

## Telemetry Emitted

| Event                   | When                                     | Fields                                                            |
| ----------------------- | ---------------------------------------- | ----------------------------------------------------------------- |
| `repository.indexed`    | Successful completion                    | `pipeline_id`, `chunks_indexed`, `collection_name`, `duration_ms` |
| `agent.health_degraded` | PII masking failure or Supabase Vector write failure | `pipeline_id`, `error_type`, `x_trace_id`                         |
| Structured log (INFO)   | Each chunk batch written                 | `batch_size`, `collection_name`, `x_trace_id`                     |
| Structured log (ERROR)  | Any failure                              | `error_type`, `error_message`, `x_trace_id`                       |

---

## Dependencies

- Custom PII Detection & Masking Functions (PII masking — mandatory before any write)
- Supabase Storage client
- Supabase Vector client (pgvector)`autorag-server/app/services/supabase_vector_client.py`)
- Gemini embeddings (via Builder agent — Ingestion writes chunks; Builder embeds)
- `organization_id` must be present — scopes all Supabase Vector table operations

## Rule 86 — Cost & Latency

Ingestion does not call an LLM directly, but it does call Gemini Embedding 2 (via Builder).

> **Correction (24-Jul-2026 audit)**: this section previously instructed calling
> `TokenGuardrail.check(..., budget_type=TokenBudgetType.CONTEXT)` against the summed
> token count of every chunk in the whole document, before passing to Builder. That is
> the exact bug documented and removed 16-Jul-2026 (see
> `docs/case-study-large-document-ingestion-16jul2026.md`, Symptom 1 / bug #1):
> `TokenBudgetType.CONTEXT` guards a single LLM call's context window, not a vector
> index, which has no inherent size limit — the check rejected every real-world
> document over ~45-50 pages. **Do not implement a whole-document token gate at
> ingestion time.** `total_tokens` is still computed and logged in `execution_trace`
> for Rule 86 observability, but it is not a gate. The Compressor node already enforces
> the correct, narrower check (`TokenBudgetType.PROMPT`, scoped to the top-K *retrieved*
> chunks for one query) — that is the only place a context-window budget applies.
