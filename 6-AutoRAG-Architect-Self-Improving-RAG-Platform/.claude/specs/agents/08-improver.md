# Agent 8: Improver

**Status**: Spec | **Phase**: E-2 ✅ | **Team**: Team 4 + Team 3

---

## Responsibility

Generate at least 3 alternative pipeline hyperparameter variants based on the Diagnoser's failure classification. Score each variant via the Evaluator before recommending. Log all variants and scores to MLflow for experiment traceability.

---

## Input Schema

```python
class ImproverInput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    failure_type: Literal[
        "Retrieval Miss",
        "Context Overflow",
        "Hallucination",
        "Answer Incompleteness",
        "Latency Spike",
        "Quality Drift"
    ]
    current_config: PipelineConfig
    x_trace_id: str

class PipelineConfig(BaseModel):
    chunk_strategy: str
    chunk_size: int
    child_chunk_size: int
    overlap: int
    k_value: int                 # retrieval top-k
    rerank_top_k: int
    embedding_model: str
    prompt_template_version: str
```

---

## Output Schema

```python
class ImproverOutput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    variants_generated: int      # always >= 3
    variants: list[PipelineVariant]
    best_variant: PipelineVariant | None  # highest scoring variant above gate
    recommendation: str          # human-readable summary
    x_trace_id: str

class PipelineVariant(BaseModel):
    variant_id: UUID
    config: PipelineConfig
    unified_score: float
    score_delta: float           # vs. current config score
    mlflow_run_id: str
```

---

## Variant Generation Strategy by Failure Type

| Failure Type            | Hyperparameters to Tune                                                                |
| ----------------------- | -------------------------------------------------------------------------------------- |
| `Retrieval Miss`        | Increase `k_value`; switch `chunk_strategy` to `hierarchical`; reduce `chunk_size`     |
| `Context Overflow`      | Reduce `k_value`; increase `rerank_top_k` selectivity; reduce `token_budget`           |
| `Hallucination`         | Switch prompt template version; add stricter negative constraints; reduce `chunk_size` |
| `Answer Incompleteness` | Increase `chunk_size`; increase `overlap`; increase `k_value`                          |
| `Latency Spike`         | Reduce `rerank_top_k`; switch to faster embedding model variant; reduce `k_value`      |
| `Quality Drift`         | Re-tune broadly across `chunk_strategy`/`k_value`/`prompt_template_version` — no single hyperparameter is implicated by a multi-run trend; treat as a wider search than a single-run failure type |

---

## Failure Modes

| Failure                                 | Classification | Retry Policy                                                           |
| --------------------------------------- | -------------- | ---------------------------------------------------------------------- |
| Evaluator returns error for a variant   | Transient      | Skip variant; log and continue with remaining                          |
| All variants score below current config | Soft failure   | Return output with `best_variant = None`; recommend manual review      |
| MLflow logging failure                  | Transient      | Retry once; do not block variant generation                            |
| LLM variant suggestion unavailable      | Transient      | Fall back to rule-based variant generation (deterministic grid search) |

---

## Telemetry Emitted

| Event                 | When                 | Fields                                                              |
| --------------------- | -------------------- | ------------------------------------------------------------------- |
| Structured log (INFO) | Each variant scored  | `variant_id`, `unified_score`, `score_delta`, `x_trace_id`          |
| Structured log (INFO) | Improvement complete | `variants_generated`, `best_variant.unified_score`, `x_trace_id`    |
| MLflow experiment run | Each variant         | Full `PipelineConfig` + all score components                        |
| PostgreSQL write      | Best variant         | `pipeline_runs.best_variant_id`, `pipeline_runs.best_variant_score` |

---

## Cost & Token Enforcement (Rule 86 — Mandatory)

Before generating any variant, Improver MUST call both guardrails:

```python
from app.services.cost_guardrail import CostGuardrail, CostBudget
from app.services.token_guardrail import TokenGuardrail

async def improver_node(state: GraphState) -> GraphState:
    cost_guard  = CostGuardrail()
    token_guard = TokenGuardrail()

    projected_cost = estimate_variant_cost(state["variant_config"])
    cost_guard.check(projected_cost, settings.max_pipeline_build_usd, "improver-variant")

    projected_tokens = estimate_variant_tokens(state["variant_config"])
    token_guard.check(projected_tokens, "context_tokens", "improver-context-expansion")
    ...
```

**HITL escalation required when:**
- Projected monthly cost increase > 20% (`MAX_MONTHLY_COST_INCREASE_PCT` env var)
- Pipeline build cost > `MAX_PIPELINE_BUILD_USD` env var

**Improver MUST NOT:**
- Auto-upgrade to a more expensive LLM provider model
- Increase `max_prompt_tokens` beyond the limit in `config/token_budgets.yaml`
- Bypass `CostGuardrail.check()` for any variant — no exceptions

All cost limit violations that reach the guardrail are automatically written to `audit_log` (`cost_limit_exceeded` event) by `CostGuardrail`.

---

## Dependencies

- Diagnoser output (`failure_type`, `current_config`)
- Evaluator agent (scores each generated variant)
- MLflow tracking server (logs all variants)
- `app/services/cost_guardrail.py` — `CostGuardrail` (Rule 86 — mandatory)
- `app/services/token_guardrail.py` — `TokenGuardrail` (Rule 86 — mandatory)
- `config/model_pricing.yaml` — provider pricing for cost projection
- `config/token_budgets.yaml` — token limits for context expansion guard
- Gemini Flash 3.5 API (LLM-assisted variant suggestion — primary)
- Deterministic grid search fallback (rule-based — no LLM dependency)
