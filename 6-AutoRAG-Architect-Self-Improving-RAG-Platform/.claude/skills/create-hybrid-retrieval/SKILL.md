# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Hybrid Retrieval Skill

## Purpose

Build the retrieval logic for the Builder and serving endpoints.

## The 4-Stage Stack (v3.0)

1. **Dense**: Supabase Vector (pgvector) HNSW cosine similarity.
2. **BM25**: Keyword search for precise term matching.
3. **Cross-encoder**: Reranking top-20 candidates down to top-5 (Cohere/BGE).
4. **HyDE**: Hypothetical Answer Embedding for abstract queries.

## Requirements

- **Alpha Blending**: Use weighted scores to combine Dense and BM25 results.
- **Payload Indexing**: Always filter `pipeline_chunks` queries by `organization_id` AND `pipeline_id` AND `pipeline_version` (Version 4.0, migration 0016) -- missing `pipeline_version` is an explicit CLAUDE.md Forbidden Pattern (#4).
- **Reranker Fallback**: Local BGE-Reranker if Cohere API is unavailable.

## Anti-Patterns

- **Pure Semantic**: Relying only on dense vectors for technical IDs or names.
- **Top-K Overflow**: Sending more than 10 chunks to the generation stage.
