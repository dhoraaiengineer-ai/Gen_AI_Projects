# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 50: AutoRAG System

## Enforces:

1.  **Ingestion**: Advanced Chunking (Semantic, Hierarchical, or Late Chunking).
2.  **Retrieval**: The 4-Stage Stack (Dense -> Hybrid -> Cross-encoder Reranker -> HyDE).
3.  **Generation**: Wrapped in the 3-layer evaluation stack (Unified Score, RAGAS, Adversarial).
4.  **Metadata**: Mandatory `source_uri`, `chunk_strategy`, and `page_number` in Supabase Vector (pgvector) tables.
5.  **Safety**: `Faithfulness < 0.5` strictly blocks deployment.

## Anti-Patterns:

- Pure keyword search without semantic fallback.
- Flat chunking for documents over 50 pages.
- Bypassing the evaluation gate for "emergency" fixes.
