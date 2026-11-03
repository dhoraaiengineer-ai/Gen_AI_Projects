# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-rag-pipeline
description: Build or extend an AutoRAG pipeline component (ingestion, advanced chunking, embedding, hybrid retrieval, generation)

---

# Create RAG Pipeline Skill

## Goal

Build or extend an AutoRAG pipeline component following the v3.0 separation of concerns.

## Steps

1. Ask for: which pipeline stage (Ingestion, Builder, Evaluator, Query Rewriter, Context Compressor).
2. For **ingestion**: implement Advanced Chunking (Semantic, Hierarchical, or Late Chunking based on document type).
3. For **embedding**: use Gemini Embedding 2 (768-dim) — the only approved embedding model.
4. For **retrieval**: implement the 4-stage method: Dense -> Hybrid -> Cross-encoder Reranker -> HyDE.
5. For **generation**: wrap all generation inside the 3-layer evaluation stack (Unified Score, RAGAS, Adversarial).
6. Log all events to the `audit_log` with one of the 14 approved event types.
7. Add unit tests: minimum 80% coverage.

## Quality rules

- Enforce `Faithfulness < 0.5` blocks deployment.
- Store embeddings in Supabase Vector (pgvector) with `chunk_strategy` in payload.
- All in-flight state goes into the LangGraph checkpoint store in PostgreSQL.
- Keep prompt templates in `/prompts` folder, not inline.
