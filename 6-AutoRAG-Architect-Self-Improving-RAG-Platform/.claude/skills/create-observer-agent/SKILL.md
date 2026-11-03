# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Observer Agent Skill

## Purpose

Build the monitoring node that tracks production performance and triggers the improvement loop.

## Requirements

- **Thresholds**: Trigger `Diagnoser` if `Unified Score` drops by `> 0.10` from the baseline (matches `specs/agents/06-observer.md`'s `unified_score_trend` threshold and the auto-rollback threshold in CLAUDE.md SS9 -- keep both in sync).
- **Latency Alert**: Trigger alert if `p95 latency > 3s`.
- **Data Source**: Read from `query_logs` and `pipeline_runs` tables.

## Anti-Patterns

- **Over-Triggering**: Starting an improvement loop for a single low-score query; use moving averages.
- **Ignoring Cost**: Failing to alert on sudden spikes in token usage.
