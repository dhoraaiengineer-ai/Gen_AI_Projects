# Agent 2: Query Rewriter

**Status**: Spec | **Phase**: D-7 | **Team**: Team 3

---

## Responsibility

Rewrite vague, ambiguous, or poorly structured user queries into precise, retrieval-optimized queries before they reach the Builder and retrieval pipeline. Improves Recall@5 without changing user intent.

---

## Input Schema

```python
class QueryRewriterInput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    original_query: str          # raw user query (PII-masked upstream)
    rewrite_mode: Literal["expand", "decompose", "clarify"] = "expand"
    x_trace_id: str
```

---

## Output Schema

```python
class QueryRewriterOutput(BaseModel):
    pipeline_id: UUID
    organization_id: UUID
    original_query: str
    rewritten_query: str         # optimized query for retrieval
    rewrite_mode: str
    llm_provider_used: str       # "gemini-flash-3.5" | "kimi-k2.6" | "gemini-3.5"
    duration_ms: float
    x_trace_id: str
```

---

## Failure Modes

| Failure                  | Classification | Retry Policy                                                      |
| ------------------------ | -------------- | ----------------------------------------------------------------- |
| Gemini API timeout       | Transient      | Graph edge → KiMi K2.6 fallback                                   |
| KiMi K2.6 timeout           | Transient      | Graph edge → Gemini 3.5 fallback                                |
| Gemini 3.5 unavailable       | Hard block     | Halt; emit `agent.health_degraded`                                |
| Rewritten query is empty | Validation     | Return `original_query` unchanged; log warning                    |
| PII detected in query    | Hard block     | Custom PII masking must run upstream — Rewriter refuses unmasked input |

---

## Retry Policy

LLM failover modeled as explicit graph edges: `gemini_flash_node` → `kimi_k2_6_node` → `gemini_3_5_node`. No inline fallback inside a single node function.

---

## Telemetry Emitted

| Event                  | When                 | Fields                                                           |
| ---------------------- | -------------------- | ---------------------------------------------------------------- |
| Structured log (INFO)  | Rewrite complete     | `rewrite_mode`, `llm_provider_used`, `duration_ms`, `x_trace_id` |
| Structured log (WARN)  | Fallback activated   | `failed_provider`, `fallback_provider`, `x_trace_id`             |
| Structured log (ERROR) | All providers failed | `error_type`, `x_trace_id`                                       |

---

## Dependencies

- Google Gemini Flash 3.5 API (primary)
- KiMi K2.6 (fallback)
- Gemini 3.5 (last resort)
- Custom PII masking must be applied to `original_query` before this node receives it

## Rule 86 — Cost & Latency

Every LLM call (Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5) routes through `LLMService` (`app/services/llm_service.py`), which records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` into `execution_trace`. The node must NOT compute `cost_usd` independently. `CostGuardrail.check()` fires inside `LLMService`; `llm_provider_used` is written to `execution_trace`. Provider pricing is loaded from `config/model_pricing.yaml`.
