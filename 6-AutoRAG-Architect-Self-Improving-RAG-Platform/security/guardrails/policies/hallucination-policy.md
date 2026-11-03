# Hallucination Policy — AutoRAG v4.0

**Classification**: Internal — Security Governance
**Owner**: Team 8 (Compliance) + Team 2 (Evaluation)
**Updated**: 21-Jul-2026

---

## Hard Block Rule

> **Faithfulness < 0.5 = HARD BLOCK. Non-bypassable. No override permitted.**

Any pipeline run where the LLM generates an answer with faithfulness below 0.5 is blocked from:
- Returning a response to the user
- Progressing to the Deployer Agent
- Entering production via the CI/CD gate chain

This rule is enforced in three independent places:
1. `autorag-server/app/guardrails/output/hallucination_scorer.py`, via `score_hallucination()` — runtime check on the live query path, invoked from `app/guardrails/middleware/guardrail_pipeline.py`'s output guard stage
2. `autorag-server/app/graph/nodes/evaluator.py` — the pipeline evaluation run gate. Computes `faithfulness` directly from `RAGASService` (not via `hallucination_scorer.py` — that module backs the query-time guardrail path only) and sets `guardrail_blocked=True, guardrail_block_reason="hallucination"` when `faithfulness < 0.5`
3. `.github/workflows/deploy.yml` — CI/CD Unified Score gate. **Currently `.github/workflows/deploy.yml.disabled`** (renamed 16-Jul-2026 pending a real ECS worker service — see `.claude/docs/DEPLOYMENT.md`); until restored, this enforcement point does not run in CI. The evaluator's `guardrail_blocked` output (point 2) is the only currently-active gate before a pipeline reaches `deploy_status`

---

## Faithfulness Score Definition

Faithfulness measures whether all factual claims in the generated answer are supported by the retrieved context chunks. A score of 1.0 means every claim traces to a source chunk. A score of 0.0 means no claims are grounded.

**Formula**: computed via RAGAS faithfulness metric (claim extraction + NLI-based grounding check).

---

## Adversarial Hallucination Gate

The Evaluator Agent runs 10 unanswerable questions against each pipeline:
- If the model fabricates an answer → **score = 0, hard block**
- All 10 must return "I don't know" or equivalent → **100% pass rate required**

This gate is separate from the faithfulness score and is always enforced.
