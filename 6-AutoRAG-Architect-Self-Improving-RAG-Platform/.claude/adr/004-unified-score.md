# ADR-004: Weighted Unified Score as Deployment Gate

**Status**: Accepted | **Date**: 05-Jul-2026
**Deciders**: Mahesh Kumar

## Decision

Use a weighted composite formula as the primary deployment gate, replacing ad-hoc manual quality checks.

```
Score = (0.25 × Recall) + (0.35 × Quality) + (0.25 × Faithfulness)
        - (0.10 × Latency) - (0.05 × Cost)
```

Threshold: **>= 0.85** for automatic promotion. Below 0.70 = hard block.

## Rationale

- Quality (Answer Relevancy) carries the highest weight (0.35) because user-perceived quality is the primary product metric
- Recall and Faithfulness share equal weight (0.25 each) — retrieval coverage and factual grounding are equally critical for a RAG system
- Latency and Cost are penalized but at lower weights (0.10 / 0.05) — they are important but secondary to quality
- A single composite score makes the deployment decision auditable, automatable, and consistent across all 28 team members
- The 0.70–0.84 HITL band provides a human override window without eliminating automation

## Consequences

- **Faithfulness < 0.5 is a hard block regardless of total score** — non-bypassable; prevents hallucination reaching production
- **Adversarial pass rate < 1.0 is a hard block** — 100% pass rate required on the 10-question unanswerable benchmark; a single fabricated answer = deployment blocked
- Score is computed by the Evaluator agent on every pipeline run and stored in the `evaluation_runs` table
- Changes to weights or thresholds require an ADR revision and Architect approval (High risk tier)
- MLflow tracks every score component per variant run for experiment comparison
- `CostGuardrail` and `TokenGuardrail` enforce the cost/latency penalty factors before any variant is promoted

## See Also

- [rules/50-rag-system.md](../rules/50-rag-system.md) — evaluation stack enforcement
- [rules/80-testing-quality.md](../rules/80-testing-quality.md) — KPI targets (Recall@5 >= 0.85, Faithfulness >= 0.80)
- [rules/86-cost-latency-monitoring.md](../rules/86-cost-latency-monitoring.md) — cost/latency penalty factors; CostGuardrail enforcement
- [rules/evaluator-standards.md](../rules/evaluator-standards.md) — full evaluator governance (adversarial gate, HITL band, retry routing)
- [specs/api-design.md](../specs/api-design.md) — `/api/v1/score/{run_id}` endpoint

