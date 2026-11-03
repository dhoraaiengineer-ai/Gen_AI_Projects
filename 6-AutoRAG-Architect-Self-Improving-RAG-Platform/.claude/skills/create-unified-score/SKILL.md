# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Unified Score Skill

## Purpose

Implement the mathematical logic for the AutoRAG production gate.

## Formula (top-level weights frozen, unchanged since v3.0)

`Score = 0.25 × Recall + 0.35 × Quality + 0.25 × Faithfulness − 0.10 × Latency − 0.05 × Cost`

### Recall/Quality sub-formulas (v1.2, 24-Jul-2026 — what these two terms are MADE OF changed)

The top-level weights above never changed, but v1.0/v1.1 computed `Recall` from raw
`context_recall` and `Quality` from `answer_relevancy` alone, double-counting RAGAS
metrics across sub-scores. Implement the real, current composites instead
(`compute_retrieval_score()` / `compute_quality_score()` in
`autorag-server/app/services/evaluation_service.py`):

```
Recall  = 0.5 × ContextPrecision + 0.5 × ContextRecall
Quality = 0.6 × AnswerCorrectness + 0.4 × AnswerRelevancy
          (falls back to AnswerRelevancy alone when AnswerCorrectness is
           unavailable -- i.e. no ground truth seeded for the run)
```

`Faithfulness` stays an independent top-level term (RAGAS `faithfulness`, unchanged) — no
RAGAS metric may appear in more than one term. See CLAUDE.md SS9 and
`specs/agents/05-evaluator.md` for the full rationale.

## Thresholds

- **Production Ready**: `Score ≥ 0.85`.
- **Needs Improvement**: `0.70 ≤ Score < 0.85`.
- **Blocked**: `Score < 0.70` OR `Faithfulness < 0.50`.

## Anti-Patterns

- **Weight Drift**: Modifying formula weights without an ADR.
- **Missing Penalties**: Forgetting to subtract Latency/Cost components.
- **Rounding Errors**: Incorrect precision handling for the final 0.00-1.00 float.
