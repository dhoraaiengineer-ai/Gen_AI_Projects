# Deferred Backend Wiring Matrix

**Date**: 12-Jul-2026 (IST) | **Status**: 11 pages hidden from primary nav, fabrication removed

These 11 pages previously rendered fully fabricated data (hardcoded numbers, `Math.random()`
latency/cost/tokens, invented run histories) with no real backend behind them. Per the MVP scope
decision (12-Jul-2026): hide from primary navigation, strip all fabrication, show an honest
"Advanced feature — backend data source is not connected in this build" state if visited directly,
and preserve the original mock components untouched for future real wiring. **No new backend work
was done for these pages in this pass** — that decision protects the MVP's real closed-loop scope.

Real data these pages implied is not lost — it already surfaces in the flagship Mission Control
screens (Pipeline Progress, Evaluation, Observer, Diagnoser, Improver, Deploy, Audit Log), per the
MVP metrics table below.

## Hidden pages

| Page | Route | Intended capability | Required backend source | Current status | Future implementation requirement |
|---|---|---|---|---|---|
| Agent Control Center | `/agents` | Fleet-wide per-agent run history, cost, latency | Query `agent_metrics` grouped by `agent_name` across all runs (currently only queryable per `run_id`) | Hidden, honest placeholder | New repository method + route: `agent_metrics` aggregated by agent_name/org, paginated |
| Agent State Viewer | `/agent-state` | Live GraphState snapshot per running pipeline | No live-streaming/snapshot endpoint exists (Part 0 confirmed no per-node streaming) | Hidden, honest placeholder | Would need a checkpoint-read API against `PostgresSaver`/`MemorySaver`, or a live WebSocket |
| Workflow | `/workflow` | Visual DAG of the 9-agent graph with live highlighting | No live execution-position endpoint | Hidden, honest placeholder | Real node_trace (already real, on Pipeline Progress) could drive a DAG view — deferred as a visualization enhancement, not new data |
| Chunk Explorer | `/chunks` | Browse/search a pipeline's real chunks with relevance scores | `VectorService.list_all_chunks` exists (used internally by ground_truth_service) but has no public route | Hidden, honest placeholder | New `GET /pipelines/{id}/chunks` route wrapping the existing service method |
| Embedding Explorer | `/embeddings` | UMAP/vector visualization of a pipeline's real embeddings | No embedding-projection computation exists anywhere in the backend | Hidden, honest placeholder | Would need a real UMAP/t-SNE reduction step — nontrivial, likely a background job |
| AI Chat Playground | `/chat` | Freeform chat against a pipeline's knowledge base | `GET /query` (routes/query.py) is real and could back this | Hidden, honest placeholder | Wire this page to the real `queryRetrieval`/`GET /query` endpoint already used by Retrieval Explorer |
| Cost Analytics | `/cost` | Org-wide cost trends, breakdown by agent/provider/pipeline | `agent_metrics` has the raw data but no aggregation route exists | Hidden, honest placeholder | New `GET /analytics/cost` route with GROUP BY agent_name/provider/date |
| Security Dashboard | `/security` | Guardrail block history, PII detection stats, injection attempts | `audit_log` has real `guardrail_blocked` events (Audit Log page already shows these) | Hidden, honest placeholder | A dedicated security view could re-query `audit_log` filtered to security event types — mostly a frontend aggregation of already-real data |
| Infrastructure Dashboard | `/infrastructure` | ECS task health, resource utilization, deployment topology | No AWS/infra introspection endpoint exists (Phase 1 is Docker-only locally) | Hidden, honest placeholder | Requires real AWS SDK calls (ECS DescribeServices etc.) — production-environment only |
| Dataset Manager | `/datasets` | Manage curated eval/training datasets | No dataset CRUD backend exists — `Document`/pipeline tables are the closest real analog | Hidden, honest placeholder | Would need new `datasets` table + CRUD routes — a real, separate feature |
| Prompt Studio | `/prompts` | Version/edit Jinja2 prompt templates in the UI | Prompts are file-based (`_ANSWER_GENERATION_PROMPT_V1` etc. in node source) — no DB-backed prompt versioning | Hidden, honest placeholder | Would need prompts moved to a DB table with versioning — a real architecture change (currently intentionally file-based per ai-safety.md) |

## MVP metrics — where they really live now

Per the 12-Jul-2026 scope decision, hiding these pages does not mean the underlying metrics stopped
being tracked. See `evaluation/results/HISTORICAL_REPORT_COVERAGE_MATRIX.md` for the full
MEASURED/DERIVED/ESTIMATED/NOT_COLLECTED classification of every metric below.

| Area | Metrics | Real UI location |
|---|---|---|
| Pipeline | status, current node, total duration, node trace | Pipeline Progress (`/dashboard/[id]`) |
| 9 Agents | status, latency, tokens, cost, provider, retries | Pipeline Progress |
| Ingestion | pages, PII count, chunks, tokens, strategy, guardrail | Pipeline Progress |
| Retrieval | Recall@5 (golden-path doc only), retrieved/relevant IDs | Evaluation |
| Quality | Unified Score + its 5 weighted components | Evaluation |
| RAGAS | Context Precision/Recall, Faithfulness, Answer Relevancy | Evaluation |
| Adversarial | pass rate, per-question failure detail | Evaluation |
| Observer | score history, signals, quality drift | Observer |
| Diagnoser | F-01–F-06 classification, confidence, remediation, root cause | Diagnoser |
| Improver | 3 real candidates, config diff, estimated score deltas | Improver |
| LLM | prompt/completion tokens, cost, latency, provider | Pipeline Progress (`agent_metrics`) |
| Deployment | status, HITL approval state | Deploy / Dashboard HITL queue |
| Guardrails | block events, cost/token limit violations | Audit Log |
