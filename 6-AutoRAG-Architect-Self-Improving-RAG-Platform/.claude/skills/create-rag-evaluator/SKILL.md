# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create RAG Evaluator Skill

## Purpose

Build the Evaluator Agent node responsible for the 3-layer quality gate.

## Requirements

- **Parallelization**: Must run all 3 evaluation layers (Unified, RAGAS, Adversarial) in parallel using `asyncio.gather`.
- **Reasoning**: Mandatory `judge_reasoning` field for every score to feed the Diagnoser.
- **Reproducibility**: Use fixed temperature (0) and specific model versions.

## Required Components

1. **Layer 1**: Unified Score (`0.25R + 0.35Q + 0.25F - 0.10L - 0.05C`).
2. **Layer 2**: RAGAS component metrics (Context Precision, Recall).
3. **Layer 3**: Adversarial Q&A (10 unanswerable questions).

## Anti-Patterns

- **Bypassing Hallucination**: Allowing a deploy when Adversarial Pass is False.
- **Serial Execution**: Running evaluation layers sequentially (violates 8-minute SLO).
- **Hardcoded Haiku**: Using low-fidelity models for the primary Quality/Faithfulness judge.

## Rule 86 Compliance

> The Evaluator reads `cost_usd` and `latency_ms` from `execution_trace` entries written by `LLMService` — it does NOT re-calculate cost. The `cost_per_query_usd` field fed into the Unified Score formula (`-0.05×Cost`) comes from `execution_trace` aggregation. Every evaluation run must log `cost_per_query_usd`, `latency_p95_ms`, `unified_score`, `total_tokens`, and `llm_provider_used` to MLflow. See `rules/86-cost-latency-monitoring.md`.
