# Agent 5: Evaluator

**Status**: Spec | **Phase**: D-15 | **Team**: Team 2

---

## Responsibility

Execute the full 3-Layer Evaluation stack: (1) Unified Score calculation, (2) RAGAS component metrics, (3) Adversarial Q&A hallucination test. Write results to the `evaluations` table. Trigger the deployment gate decision.

---

## Input Schema

```python
class EvaluatorInput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    query: str
    answer: str                  # LLM-generated answer
    context: list[str]           # compressed context chunks used
    ground_truth: str | None     # optional — required for RAGAS faithfulness
    recall_score: float          # computed by retrieval layer
    latency_ms: float            # end-to-end query latency
    cost_usd: float              # LLM + embedding cost for this run
    x_trace_id: str
```

---

## Output Schema

```python
class EvaluatorOutput(BaseModel):
    pipeline_id: UUID
    run_id: UUID
    organization_id: UUID
    unified_score: float         # (0.25R + 0.35Q + 0.25F - 0.10L - 0.05C)
    recall: float                 # v1.2 (24-Jul-2026): 0.5*ContextPrecision + 0.5*ContextRecall
    quality: float                # v1.2 (24-Jul-2026): 0.6*AnswerCorrectness + 0.4*AnswerRelevancy
                                   # (falls back to AnswerRelevancy alone when no ground truth)
    faithfulness: float
    latency_penalty: float
    cost_penalty: float
    ragas_scores: RAGASScores
    adversarial_result: AdversarialResult
    gate_decision: Literal["deploy_eligible", "hitl_required", "hard_block"]
    gate_reason: str
    x_trace_id: str

class RAGASScores(BaseModel):
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    answer_correctness: float | None  # None when no ground truth is seeded for the run

class AdversarialResult(BaseModel):
    questions_tested: int        # always 10
    questions_passed: int
    fabricated_answers: list[str]
    passed: bool                 # True only if fabricated_answers is empty
```

---

## Failure Modes

| Failure                                     | Classification | Retry Policy                                                                                         |
| ------------------------------------------- | -------------- | ---------------------------------------------------------------------------------------------------- |
| RAGAS computation error                     | Transient      | Retry once via graph edge; if fails, mark `ragas_scores` as null and proceed with Unified Score only |
| Adversarial test dataset missing            | Hard block     | Halt entire evaluation — dataset is mandatory                                                        |
| Any adversarial fabrication detected        | Hard block     | `gate_decision = "hard_block"` — non-bypassable                                                      |
| `faithfulness < 0.5`                        | Hard block     | `gate_decision = "hard_block"` — non-bypassable regardless of total score                            |
| LLM judge unavailable (for quality scoring) | Transient      | Retry with KiMi K2.6 fallback                                                                           |
| DB write failure on `evaluations`           | Transient      | Retry 3× via explicit LangGraph graph edge                                                           |

---

## Gate Decision Logic

```
if adversarial_result.fabricated_answers:
    gate_decision = "hard_block"
elif faithfulness < 0.5:
    gate_decision = "hard_block"
elif unified_score >= 0.85:
    gate_decision = "deploy_eligible"
elif unified_score >= 0.70:
    gate_decision = "hitl_required"   # triggers SendGrid + Twilio
else:
    gate_decision = "hard_block"      # triggers Diagnoser
```

---

## Telemetry Emitted

| Event                                | When                              | Fields                                                         |
| ------------------------------------ | --------------------------------- | -------------------------------------------------------------- |
| `workflow.requires_approval` webhook | `gate_decision = "hitl_required"` | `pipeline_id`, `run_id`, `unified_score`, `gate_reason`        |
| Structured log (INFO)                | Evaluation complete               | `unified_score`, `gate_decision`, `faithfulness`, `x_trace_id` |
| Structured log (ERROR)               | Hard block triggered              | `block_reason`, `x_trace_id`                                   |
| MLflow metrics                       | Every run                         | All score components, `gate_decision`                          |

---

## Dependencies

- RAGAS library (`ragas` Python package)
- Adversarial Q&A fixture file (sealed — path: `autorag-server/tests/fixtures/adversarial_qa.json`)
- LLM judge for quality scoring (Gemini Flash 3.5 primary -> KiMi K2.6 fallback)
- PostgreSQL `evaluations` table
- MLflow tracking server
