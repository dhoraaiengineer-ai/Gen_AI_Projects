# Runbook: Low Unified Score (< 0.85)

**Alert**: `UnifiedScoreDrop`
**Severity**: Warning (< 0.85) | Critical (< 0.70)
**Auto-rollback**: Yes if score drops > 0.10 in 10-minute canary window
**Owner**: Team 2 (Evaluator) + Team 4 (Agents)

---

## Trigger Conditions

- `autorag_unified_score < 0.85` for 5 minutes
- Score = `0.25×Recall + 0.35×Quality + 0.25×Faithfulness - 0.10×Latency - 0.05×Cost`

---

## Symptoms

- Grafana: Unified Score panel shows red (< 0.85) for current pipeline
- HITL approval queue has entries awaiting review (score 0.70–0.84)
- Deployer Agent blocked — logs show `deploy_status: blocked_low_score`
- MLflow experiment run shows `unified_score < 0.85` for recent run

---

## Diagnosis Steps

### Step 1 — Identify which component dropped

Check RAGAS sub-metrics in MLflow or `/api/v1/evaluate/{run_id}`:

| Metric | Min Target | If Below |
|--------|-----------|----------|
| Faithfulness | 0.50 (hard floor) | Hard block — see faithfulness section |
| Answer Relevancy | 0.80 | Retrieval or generation issue |
| Context Recall | 0.80 | Chunking or embedding issue |
| Context Precision | 0.75 | Reranking issue |
| Recall@5 | 0.85 | Dense/hybrid search issue |

### Step 2 — Run Diagnoser Agent
```bash
curl http://localhost:8000/api/v1/diagnose/<run_id>
```

The Diagnoser classifies into 6 failure types (verbatim from `app/graph/nodes/diagnoser.py`):
- F-01: Retrieval Miss — retrieved chunks empty or all low-score
- F-02: Context Overflow — token_count exceeds budget
- F-03: Hallucination — faithfulness < 0.5
- F-04: Answer Incomplete — low unified_score but faithfulness OK
- F-05: Latency Spike — latency_p95_ms > 3000ms
- F-06: Quality Drift — sustained multi-run score decline (G-6 / Plan v4)

### Step 3 — Check chunking strategy
If Context Recall < 0.80: the chunk boundaries may be splitting key information.
Try switching from `semantic` to `hierarchical` chunking in the Configurator.

### Step 4 — Check embedding quality
Verify Gemini Embedding 2 is active (not falling back to a local embedding):
```bash
grep "embedding_model" autorag-server/.env.dev
```

---

## Resolution by Score Range

| Score | Action |
|-------|--------|
| 0.70–0.84 | HITL required. Notify Mahesh Kumar via SendGrid + Twilio for manual approval |
| < 0.70 | Hard block. Trigger Improver Agent to generate variant_config |
| Faithfulness < 0.50 | Hard block regardless of score. Do not override. |

### Trigger Improver Agent
The Improver runs automatically as part of the graph's retry loop
(`observer -> diagnoser -> improver -> ingestion`, max 3 retries — see
`app/core/workflow.py` `_route_after_observer()`) once a run scores below the
retry threshold; it is not triggered by a standalone endpoint. To view the
3 real scored candidates it generated for a given run:
```bash
curl http://localhost:8000/api/v1/improve/<run_id>
```
To apply one of those candidates and rebuild (20-Jul-2026 Apply Improvement feature):
```bash
curl -X POST http://localhost:8000/api/v1/pipelines/<pipeline_id>/apply-improvement \
  -H "Content-Type: application/json" \
  -d '{"run_id": "<run_id>", "variant_id": "<variant_id>"}'
```

---

## Escalation

- Score < 0.70 for > 30 min: Page Team 2 lead (Mrityunjay)
- Faithfulness hard block persists after Improver: Page Mahesh Kumar (Team 10)
- If adversarial_pass_rate < 1.0 co-occurs: Treat as F-02 hallucination incident

---

## Post-Incident

1. There is no dedicated `audit_log` event type for a low-score incident (the
   14 real `APPROVED_EVENT_TYPES` in `app/models/audit_log.py` are the only
   ones the backend will accept — see `hitl_rejected`/`eval_completed` for the
   closest real trail of this run's outcome). Log root cause in the run's
   `evaluation_runs.failure_taxonomy` / MLflow instead, never a fabricated
   event type — `AuditLogRepository.insert()` raises `ValueError` on anything
   outside the approved set.
2. Update adversarial test set if new failure pattern found
3. Run `post_pr_update.py` to confirm TASK_TRACKER.md reflects any task changes
