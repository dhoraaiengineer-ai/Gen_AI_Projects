# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Diagnoser Agent Skill

## Purpose

Implement the AutoRAG **Diagnoser Agent** (Agent 7 in the 9-agent loop). This agent receives a failed evaluation run from the Observer and classifies the root cause into one of 6 failure types, then emits a remediation hint for the Improver.

---

## When to Use

- Adding or modifying the Diagnoser LangGraph node
- Changing failure classification logic or adding new failure categories
- Updating the failure-classification Jinja2 prompt template
- Writing integration tests for Diagnoser → Improver graph transitions

---

## 6 Failure Types (Exhaustive — no other types permitted)

| Code | Failure Type         | Trigger Condition                                              |
| ---- | -------------------- | -------------------------------------------------------------- |
| F-01 | Retrieval Miss       | Relevant information not in retrieved chunks (Recall@5 < 0.85) |
| F-02 | Context Overflow     | Relevant chunks truncated before LLM call (token budget hit)  |
| F-03 | Hallucination        | Answer contains facts absent from context (Faithfulness < 0.5) |
| F-04 | Answer Incompleteness| Answer is correct but misses key details (Quality score < 0.7) |
| F-05 | Latency Spike        | Valid output but p95 response > 3s                            |
| F-06 | Quality Drift        | Sustained Unified Score decline across a 5-run rolling window (added G-6, 10-Jul-2026) |

---

## GraphState Input Fields

```python
class DiagnoserInput(TypedDict):
    run_id: str                    # UUID v7 — pipeline run identifier
    x_trace_id: str                # propagated from request boundary
    unified_score: float           # overall score that triggered diagnosis
    ragas_metrics: dict            # context_precision, recall, faithfulness, relevancy
    retrieved_chunks: list[dict]   # chunks with similarity scores
    generated_answer: str          # PII-masked LLM output
    judge_reasoning: str           # evaluator's failure reasoning
    latency_p95_ms: int            # observed p95 latency in ms
```

## GraphState Output Fields

```python
class DiagnoserOutput(TypedDict):
    failure_type: str              # one of: F-01..F-06
    confidence: float              # 0.0–1.0 — classification confidence
    remediation_hint: str          # what Improver should tune
    root_cause_analysis: str       # human-readable explanation
    x_trace_id: str                # propagated unchanged
```

---

## Implementation Pattern

```python
# autorag-server/app/graph/nodes/diagnoser.py
async def diagnoser_node(state: GraphState) -> GraphState:
    """
    Classifies evaluation failure into one of 6 types.
    Stateless — all state in GraphState; no inline retry loops.
    PII must be masked before this node is called.
    """
    prompt = render_template(
        "failure-classification.jinja2",
        ragas_metrics=state["ragas_metrics"],
        retrieved_chunks=state["retrieved_chunks"],
        generated_answer=state["generated_answer"],
        judge_reasoning=state["judge_reasoning"],
        latency_p95_ms=state["latency_p95_ms"],
    )

    result = await llm_service.call(prompt, x_trace_id=state["x_trace_id"])
    classification = parse_json(result)  # {failure_type, confidence, remediation_hint, root_cause_analysis}

    return {
        **state,
        "failure_type": classification["failure_type"],
        "confidence": classification["confidence"],
        "remediation_hint": classification["remediation_hint"],
        "root_cause_analysis": classification["root_cause_analysis"],
    }
```

---

## Prompt Template

**Location**: `prompts/failure-classification.jinja2`

The template receives all evaluation context and outputs structured JSON. The negative constraint **"Do not invent failure types not in the 6-type taxonomy"** is mandatory in the template.

---

## Graph Edge Rules

After the Diagnoser node, the conditional edge routes to:

- **Improver** — if `confidence >= 0.7` and `failure_type` in {F-01, F-02, F-04, F-05, F-06}
- **Human Review** — if `failure_type == F-03` (Hallucination) — always requires HITL
- **Retry Diagnoser** — if `confidence < 0.7` — re-classify with expanded context (explicit graph edge, NOT inline retry)

---

## Safety Invariants

- PII must be stripped from `retrieved_chunks` and `generated_answer` before entering this node
- `x_trace_id` must be propagated to all downstream nodes and the `audit_log`
- Classification result must be logged to `audit_log` with event_type `eval_completed` (the nearest approved type — see DB_SCHEMA.md for the 14 approved event types)
- Never mutate `ragas_metrics` or `retrieved_chunks` in this node — read-only

---

## Tests Required

- Unit test: each of the 6 failure types is correctly classified from synthetic inputs
- Integration test: Diagnoser → Improver graph transition with real GraphState
- Integration test: Diagnoser → Human Review transition for F-03 (Hallucination)
- Edge test: low-confidence path triggers re-classification edge, not inline loop
