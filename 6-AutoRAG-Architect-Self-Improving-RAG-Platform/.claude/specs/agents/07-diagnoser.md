# Agent 7: Diagnoser

**Status**: Spec | **Phase**: E-1 ✅ | **Team**: Team 4

---

## Responsibility

Classify the root cause of a pipeline failure or quality regression into one of exactly 6 failure types (F-06 Quality Drift added via G-6, 10-Jul-2026). Produce a structured diagnosis that the Improver agent uses to generate targeted hyperparameter variants.

---

## Input Schema

```python
class DiagnoserInput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    trigger: Literal["eval_hard_block", "observer_alert", "manual"]
    metrics_snapshot: MetricsSnapshot  # from Observer
    evaluation_result: EvaluatorOutput | None  # from Evaluator, if available
    x_trace_id: str
```

---

## Output Schema

```python
class DiagnoserOutput(BaseModel):
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
    confidence: float            # 0.0–1.0 — classifier confidence
    evidence: list[str]          # supporting metric values that led to classification
    recommended_actions: list[str]  # human-readable remediation suggestions
    trigger_improver: bool
    x_trace_id: str
```

---

## Failure Type Definitions

| Type                    | Primary Signal                              | Secondary Signal                            |
| ----------------------- | ------------------------------------------- | ------------------------------------------- |
| `Retrieval Miss`        | `recall_at_5 < 0.70`                        | Low context precision in RAGAS              |
| `Context Overflow`      | `tokens_used >= token_budget`               | Answer truncated or incomplete              |
| `Hallucination`         | `faithfulness < 0.5` OR adversarial failure | Fabricated answer detected                  |
| `Answer Incompleteness` | `answer_relevancy < 0.60`                   | Answer relevancy low despite good retrieval |
| `Latency Spike`         | `latency_p95_ms > 3000`                     | Cost spike correlating with slow LLM        |
| `Quality Drift`         | Sustained Unified Score decline across a 5-run rolling window (G-6, `QualityDriftDetector`) | `autorag_quality_drift_detected` Prometheus counter fires |

---

## Failure Modes

| Failure                                 | Classification | Retry Policy                                                   |
| --------------------------------------- | -------------- | -------------------------------------------------------------- |
| Classifier LLM unavailable              | Transient      | Retry with KiMi K2.6 fallback                                     |
| Insufficient metrics for classification | Soft failure   | Default to `Retrieval Miss` (most common); flag low confidence |
| `confidence < 0.50`                     | Soft failure   | Emit result with low confidence flag; do not block Improver    |

---

## Telemetry Emitted

| Event                 | When                          | Fields                                                             |
| --------------------- | ----------------------------- | ------------------------------------------------------------------ |
| Structured log (INFO) | Classification complete       | `failure_type`, `confidence`, `x_trace_id`                         |
| Structured log (WARN) | Low confidence classification | `failure_type`, `confidence`, `fallback_reason`, `x_trace_id`      |
| MLflow tag            | Every run                     | `failure_type`, `confidence`                                       |
| PostgreSQL write      | Every run                     | `pipeline_runs.failure_type`, `pipeline_runs.diagnosis_confidence` |

---

## Dependencies

- Google Gemini Flash 3.5 API (LLM-assisted classification — primary)
- KiMi K2.6 (fallback)
- Gemini 3.5 (last resort)
- Observer output (`MetricsSnapshot`)
- Evaluator output (`EvaluatorOutput`) — optional but improves classification accuracy
- PostgreSQL `pipeline_runs` table (writes `failure_type`)
- Improver agent (triggered when `trigger_improver = True`)

## Rule 86 — Cost & Latency

Every LLM call (Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5) routes through `LLMService`, which records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` into `execution_trace`. The Diagnoser node must NOT compute `cost_usd` independently. `CostGuardrail.check()` fires inside `LLMService`.
