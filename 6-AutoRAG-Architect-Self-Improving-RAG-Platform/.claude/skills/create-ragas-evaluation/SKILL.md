# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create RAGAS Evaluation Skill

## Purpose

Implement the secondary diagnostic layer using the RAGAS framework.

## Core Metrics

1. **Context Precision**: Signal-to-noise ratio in retrieved chunks.
2. **Context Recall**: Presence of the answer in the retrieved context.
3. **Answer Relevancy**: Semantic alignment of answer to query.

## Requirements

- **Async Execution**: Must run as an async task within the Evaluator node's own execution -- dispatched via FastAPI `BackgroundTasks` in-process, not a Redis-backed worker queue (no such queue exists today, see `adr/005-supabase.md`'s R-052/R-050 correction).
- **Persistence**: Store raw RAGAS scores in the `evaluations` table (JSONB).

## Anti-Patterns

- **Using RAGAS as Gate**: Blocking deployment based on RAGAS (only Unified Score is a gate).
- **Small Samples**: Running RAGAS on fewer than 50 questions (unreliable signal).
