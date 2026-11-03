# ADR-005: Supabase as Unified Data Platform

**Status**: Accepted | **Date**: 29-May-2026
**Proposer**: Mahesh Kumar
**Deciders**: Mahesh Kumar
**Supersedes**: v2.4 Qdrant vector database decision (archived); implicit AWS RDS + S3 decisions. In v3.0, ADR-002 is re-assigned to the Gemini LLM decision.

> **Partial update — 20-Jul-2026 (Version 4.0)**: the per-pipeline vector table naming
> convention below (`autorag_{pipeline_id}_{version}`) was replaced by a single shared
> `pipeline_chunks` table (migration 0016) partitioned by a `pipeline_version` column —
> real integration testing found the per-version physical table was never actually
> reachable by real version increments, so Apply Improvement rebuilds silently
> overwrote data instead of isolating versions. Supabase/pgvector/Gemini Embedding 2
> itself is unaffected — only the table-naming mechanics below are superseded. See
> `.claude/docs/DB_SCHEMA.md`'s "Immutable Versioned Indexes" addendum for the full
> replacement design.

---

## Context

AutoRAG Architect v2.4 used three separate AWS-managed data services:

- **RDS PostgreSQL 15** — operational system of record (pipeline configs, audit log, evaluations)
- **Qdrant** (self-hosted on ECS or EC2) — vector embeddings, per-pipeline collection isolation
- **Amazon S3** — raw document ingestion and pipeline snapshot storage

Managing three distinct data services introduced operational complexity: separate connection pools, individual IAM policies, separate backup and retention schedules, and three distinct client SDK integration points across the codebase.

---

## Decision

Replace RDS PostgreSQL 15, Qdrant, and Amazon S3 with **Supabase** — a single managed platform providing:

| Supabase Service         | Replaces              | Purpose                                                            |
| ------------------------ | --------------------- | ------------------------------------------------------------------ |
| **Supabase PostgreSQL**  | AWS RDS PostgreSQL 15 | Operational system of record — pipeline configs, audit log, evals  |
| **Supabase Vector**      | Qdrant                | pgvector — per-pipeline table `autorag_{pipeline_id}_{version}`    |
| **Supabase Storage**     | Amazon S3             | Raw document ingestion + pipeline snapshots                        |

All three services are accessed over HTTPS from ECS tasks. Connection strings and API keys are stored in **AWS Secrets Manager** — no secrets in code or task definition YAML.

---

## Rationale

### 1. Operational Simplicity

One platform → one connection string family → one SDK → one billing entity. Eliminates the need to maintain separate ECS task roles for RDS, Qdrant, and S3 access.

### 2. pgvector is Production-Grade

Supabase Vector uses PostgreSQL's `pgvector` extension. It supports HNSW indexing (`m=16, ef_construct=200, ef_search=128`), cosine similarity, and per-table isolation. For the retrieval scale of AutoRAG (per-pipeline isolation, not millions of concurrent tenants), pgvector meets all performance requirements.

### 3. Vector + Relational in One Transaction Boundary

Pipeline metadata and vector embeddings share the same PostgreSQL instance. This enables atomic operations — e.g., marking a pipeline as `decommissioned` and scheduling vector table deletion in the same transaction, reducing the risk of orphaned data.

### 4. Managed Storage with SDK Access

Supabase Storage provides an S3-compatible object store with a Python client. Bucket policies can enforce organization-level isolation. No need to manage IAM roles for S3 bucket access separately from the rest of the data plane.

### 5. Cost and Phase Alignment

For Phase 1 (pilot deployments, limited tenant count), Supabase's managed pricing is competitive with separate RDS + Qdrant + S3 infrastructure. The single-vendor approach also reduces Phase 1 operational risk.

---

## Consequences

### Accepted

- Supabase pgvector replaces Qdrant's dedicated vector engine — HNSW performance is acceptable at AutoRAG's retrieval scale.
- Vector table naming convention is frozen: `autorag_{pipeline_id}_{version}` (same as the previous Supabase Vector table naming).
- All `HNSW` config defaults (`m=16`, `ef_construct=200`, `ef_search=128`) from the Qdrant spec are carried forward as pgvector index parameters.
- Embedding model for all new tables: **Gemini Embedding 2** (768 dimensions) — replaces OpenAI text-embedding-3-large.
- If the embedding model changes, a **new pgvector table must be created** — mutating existing table vectors with a different model is strictly forbidden.

### Redis Retained (Celery Removed)

Redis is **not replaced** by Supabase. Celery has been removed. Supabase PostgreSQL handles persistent `checkpoints` table storage; Redis handles in-flight transient state (LangGraph checkpoint caching, response caching in `llm_service.py`/`embedding_service.py`, job-status lookups in `jobs.py`).

> **Correction (24-Jul-2026, R-052/R-050 investigation)**: the "async task queue for LangGraph workers" language above describes the target production topology (separate ECS Fargate worker service, per CLAUDE.md's architecture diagram and `specs/aws-infrastructure.md`) — it is **not** what the current implementation does. Async work (document ingestion, evaluation runs) is dispatched via FastAPI's in-process `BackgroundTasks`, in the same process as the API, with no Redis-backed queue and no separate worker service anywhere in the codebase (confirmed while removing the dead `RedisQueueDepthHigh` alert, which monitored a Redis key nothing ever wrote to). Building the real queue + separate worker service is tracked as a Version 5 candidate, not current-state architecture.

### Migration Notes

- The previous v2.4 Qdrant vector database ADR is **Superseded** by this decision. ADR-002 has been re-assigned to the Gemini LLM provider decision in v3.0.
- All `qdrant_client` SDK imports must be removed and replaced with Supabase client calls.
- All S3 boto3 storage calls must be replaced with Supabase Storage SDK.
- All `asyncpg` / SQLAlchemy RDS connection strings must point to Supabase PostgreSQL.

---

## Status History

| Date        | Status   | Note                                           |
| ----------- | -------- | ---------------------------------------------- |
| 29-May-2026 | Accepted | Approved by Mahesh Kumar — v3.0 |

---

## See Also

- [rules/30-database-postgres.md](../rules/30-database-postgres.md) — UUID v7 PKs, migrations, soft-delete enforcement
- [specs/database.md](../specs/database.md) — full schema and data lifecycle spec
- [docs/DB_SCHEMA.md](../docs/DB_SCHEMA.md) — frozen schema contract v1.0
- [adr/006-agent-metrics-table.md](006-agent-metrics-table.md) — first schema addition post-ADR-005 (Rule 86 cost tracking)
