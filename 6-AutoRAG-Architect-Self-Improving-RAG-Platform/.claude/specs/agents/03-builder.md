# Agent 3: Builder

**Status**: Spec | **Phase**: D-12 ✅ | **Team**: Team 5

---

## Responsibility

Embed document chunks using Gemini Embedding 2 (`gemini-embedding-2`), write vectors to the versioned Supabase Vector (pgvector) table, and configure HNSW index parameters. The Builder does NOT ingest documents — it consumes pre-chunked artifacts from Supabase Storage produced by the Ingestion agent.

---

## Input Schema

```python
class BuilderInput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    collection_name: str         # superseded 20-Jul-2026 -- chunks now live in the
                                  # shared pipeline_chunks table (Version 4.0,
                                  # migration 0016), partitioned by pipeline_version
    storage_chunks_uri: str      # Supabase Storage path — chunks/{pipeline_id}/{version}/
    embedding_model: str = "gemini-embedding-2"
    batch_size: int = 64         # Gemini Embedding batch size
    hnsw_m: int = 16
    hnsw_ef_construct: int = 200
    hnsw_ef_search: int = 128
    x_trace_id: str
```

---

## Output Schema

```python
class BuilderOutput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    collection_name: str
    vectors_written: int
    embedding_model: str
    embedding_dimensions: int    # 768 for gemini-embedding-2
    duration_ms: float
    cost_usd: float              # estimated Gemini embedding cost for this run
    x_trace_id: str
```

---

## Failure Modes

| Failure                                   | Classification | Retry Policy                                                                |
| ----------------------------------------- | -------------- | --------------------------------------------------------------------------- |
| Gemini API rate limit                         | Transient      | Explicit graph edge retry with exponential backoff                          |
| LLM provider down                         | Transient      | Retry 3× via explicit graph edge; push to Redis dead-letter key if all fail |
| Supabase Vector write failure                      | Transient      | Retry via explicit graph edge; Redis dead-letter key — do not inline retry  |
| Dimension mismatch on existing collection | Hard block     | New collection required — never mutate dimensions                           |
| Storage chunks not found                  | Validation     | Halt; Ingestion agent must complete first                                   |

---

## Retry Policy

Embedding batch failures are retried via explicit LangGraph graph edges with exponential backoff. Persistent failures are pushed to a Redis dead-letter key for manual inspection. Never block the async event loop with inline retries. See MEMORY.md Anti-Patterns.

---

## Telemetry Emitted

| Event                  | When               | Fields                                                             |
| ---------------------- | ------------------ | ------------------------------------------------------------------ |
| Structured log (INFO)  | Each batch written | `batch_index`, `vectors_in_batch`, `collection_name`, `x_trace_id` |
| Structured log (INFO)  | Build complete     | `vectors_written`, `cost_usd`, `duration_ms`, `x_trace_id`         |
| Structured log (ERROR) | Batch failure      | `batch_index`, `error_type`, `x_trace_id`                          |
| MLflow metric          | Build complete     | `embedding_cost_usd`, `vectors_written`, `build_duration_ms`       |

---

## Dependencies

- Gemini Embedding 2 API
- Supabase Vector client (pgvector)
- Supabase Storage (reads chunk artifacts)
- Redis (embedding response caching, checkpoint state, job-status lookups -- **not** a task queue;
  async dispatch runs via FastAPI in-process `BackgroundTasks`, corrected 24-Jul-2026, see
  `adr/005-supabase.md`'s R-052/R-050 correction note)
- `organization_id` scopes all Supabase Vector table operations

## Rule 86 — Cost & Latency

`cost_usd` in the output schema is populated by `LLMService` after embedding calls — the Builder node must NOT compute it from token counts directly. `TokenGuardrail.check()` must be called with `budget_type=TokenBudgetType.CONTEXT` before each embedding batch to guard against batch size drift. Provider pricing for `gemini-embedding-2` is loaded from `config/model_pricing.yaml`.
