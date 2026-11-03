# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Agents — AutoRAG 9-Agent System

## Orchestration Layer

**LangGraph** state machine. All nodes are `async def` stateless functions.

**Graph source**: `autorag-server/app/core/workflow.py`
**State source**: `autorag-server/app/core/state.py` (`GraphState` TypedDict)
**Node implementations**: `autorag-server/app/graph/nodes/`

---

## Agent Inventory (v3.0)

| LangGraph node name | Agent | Type | Team | Role |
|---|---|---|---|---|
| `ingestion` | Ingestion | Async | Team 5 | Parse docs → PII mask → chunk → embed → Supabase Vector |
| `query_rewriter` | Query Rewriter | Async | Team 2 | Rewrite `raw_query` → `rewritten_query` + `query_embedding` |
| `builder` | Builder | Async | Team 6 | 4-stage retrieval: dense → hybrid → rerank (Cohere) → HyDE → `retrieved_chunks` |
| `compressor` | Context Compressor | Async | Team 4/8 | Prune to token budget → `compressed_context`, `token_count` |
| `evaluator` | Evaluator | Async | Team 2 | Unified Score + RAGAS + Adversarial → `unified_score`, `faithfulness`, `adversarial_pass_rate` |
| `observer` | Observer | Conditional | Team 10 | Monitor production drift → `error_rate`, `quality_trend`, `alert_triggered` |
| `diagnoser` | Diagnoser | Async | Team 4 | Classify root cause → `failure_type` (F-01…F-06), `confidence`, `remediation_hint` |
| `improver` | Improver | Async | Team 4+3 | Generate hyperparameter variants → `variant_config`, `variant_id` (logged to MLflow) |
| `deployer` | Deployer | Async | Team 1+10 | ECS Blue/Green deploy → `deploy_status`, `blue_task_arn`, `green_task_arn` |

---

## Edge Routing (from `app/core/workflow.py`)

```
ingestion → query_rewriter → builder → compressor → evaluator

evaluator [_route_after_evaluator]:
  faithfulness < 0.5          → observer   # hard block — non-bypassable
  score >= 0.85 + adversarial → deployer   # auto-approve
  score >= 0.70               → deployer   # HITL approval required
  else                        → observer   # retry loop

observer [_route_after_observer]:
  retry_count >= 3            → END
  else                        → diagnoser

diagnoser → improver → ingestion   # improvement loop

deployer → END
```

---

## GraphState Fields Written by Each Agent

| Agent | Key output fields |
|---|---|
| Query Rewriter | `rewritten_query`, `query_embedding` |
| Builder | `retrieved_chunks`, `hyde_document`, `retrieval_strategy` |
| Compressor | `compressed_context`, `token_count` |
| Evaluator | `unified_score`, `faithfulness`, `adversarial_pass_rate`, `ragas_metrics`, `generated_answer`, `llm_provider_used`, `latency_p95_ms`, `cost_per_query_usd` |
| Observer | `error_rate`, `quality_trend`, `alert_triggered` |
| Diagnoser | `failure_type`, `confidence`, `remediation_hint`, `root_cause_analysis` |
| Improver | `variant_config`, `variant_id` |
| Deployer | `ecr_image_uri`, `blue_task_arn`, `green_task_arn`, `deploy_status`, `active_task_arn`, `rollback_reason` |
| Every node | appends one `ExecutionTraceEntry` to `execution_trace` |

---

## Failure Classification (Diagnoser output → `failure_type`)

| Code | Meaning | Typical Fix |
|---|---|---|
| `F-01` | Retrieval Miss — low recall | Increase k, change chunking strategy |
| `F-02` | Context Overflow — truncated | Reduce chunk size, increase compression |
| `F-03` | Hallucination — low faithfulness | Strengthen negative constraints in prompt |
| `F-04` | Answer Incompleteness — low quality | Increase retrieved chunks |
| `F-05` | Latency Spike — p95 > 3s | Reduce embedding dims, cache lookups |
| `F-06` | Quality Drift — sustained multi-run score decline (5-run window, added G-6) | Investigate data/model drift; trigger recalibration or manual review |

---

## LLM Failover Chain

```
Gemini Flash 3.5  →  KiMi K2.6  →  Gemini 3.5
(primary)            (fallback)     (last resort)
```

Reflected in `GraphState.llm_provider_used` after generation.

---

## Safety Gates (enforced across all agents)

| Check | Source field | Threshold | Action |
|---|---|---|---|
| Faithfulness hard block | `faithfulness` | `< 0.5` | Deploy blocked — `_route_after_evaluator` → observer |
| Adversarial block | `adversarial_pass_rate` | `< 1.0` | Deploy blocked |
| Guardrail block | `guardrail_blocked` | `True` | All output stops immediately |
| Max retry | `retry_count` | `>= 3` | `observer` routes to END |

