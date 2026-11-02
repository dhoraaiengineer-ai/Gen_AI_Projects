# ADR-003 — PostgreSQL 16 + pgvector for relational, vector, and checkpoints

**Status:** Accepted — hosting amended by [ADR-007](007-supabase-postgres-hosting.md); embeddings amended by [ADR-008](008-openai-compatible-llm-chains.md) · **Date:** 2026-10-26

## Context
We need relational integrity (ROs, claims, audit), vector search over a small corpus (< 100k chunks), full-text search
for DTC/op-code exact matches, and LangGraph checkpoints. Role/visibility filters must apply in the same query as similarity.

## Decision
- A single PostgreSQL 16 instance with `pgvector` (`pgvector/pgvector:pg16` locally, RDS PostgreSQL 16 in AWS).
- `knowledge_chunks.embedding vector(N)` with an HNSW cosine index; `tsv tsvector` with a GIN index; hybrid fusion via RRF in SQL/Python.
- Embedding dimension **N is fixed per deployment** by `EMBEDDINGS_PROVIDER`: `voyage-3` = 1024, local `BAAI/bge-small-en-v1.5` = 384.
  Changing the provider means a migration + full re-ingest (documented in the runbook).

## Alternatives
- Dedicated vector DB (Pinecone, Qdrant, Weaviate): another service, and filter/join logic is split across systems.
- Supabase (legacy AutoRAG): managed convenience, but adds platform coupling not in the AutoServe stack.
- OpenSearch: good hybrid search, heavier ops.

## Consequences
- + One backup and one security boundary; transactional consistency between chunk metadata and filters.
- + Exact-match boosts are easy through FTS.
- − Provider switch requires a re-embed. Must verify pgvector availability on RDS (supported) during P5.
