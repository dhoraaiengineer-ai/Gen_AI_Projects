# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 29-May-2026 (IST)

---

# Database Schema v1.0 Frozen Contract

**Approved: 29-May-2026 (IST)**
**Architecture: AutoRAG Architect v3.0**

This is the definitive database schema for AutoRAG v3.0. All future schema changes require Architecture Review per the Frozen Changes Policy.

---

## Addendum — 20-Jul-2026 (Apply Improvement / Optimizer)

This feature mostly reuses two tables that already existed in the schema
(migration 0002) but were incompletely wired; one small real migration
(0015) was needed to close a genuine missing link between them:

- **`experiment_runs`** (`app/models/experiment_run.py`) — existed since
  migration 0002 with exactly the shape this feature needed
  (`parent_evaluation_run_id`, `result_pipeline_version_id`,
  `variant_config` JSONB, `unified_score`, `score_delta`, `status`), but had
  no repository, service, or route built on it — a real, unused table until
  now. `GET /api/v1/experiments` (a differently-named, already-shipped
  feature) is built on `evaluation_runs`, not this table — confirmed no
  conflict before reusing it. Now the real bookkeeping store for every
  applied Improver variant (`app/repositories/experiment_run_repository.py`,
  `app/services/optimizer_service.py`).
- **`pipeline_versions`** — real rows are now actually inserted (previously,
  neither `PipelineService.create()` nor `create_version()` ever wrote to
  this table — a fresh pipeline had `current_version=1` with zero matching
  version-history rows, and version bumps left the same gap). Fixed as a
  real bug, not a schema change: `config_snapshot`, `chunk_strategy`,
  `chunk_size`, `retrieval_k` columns already existed and are now populated.
- **`pipelines.current_version`** — was computed locally in
  `create_version()` but never persisted back to the row (a repeat call
  recomputed the same number). Now actually written via
  `PipelineRepository.update_current_version()`.
- **`experiment_runs.result_evaluation_run_id`** (new, migration 0015) —
  nullable UUID FK to `evaluation_runs.id`, `ON DELETE SET NULL`. Real gap:
  `result_pipeline_version_id` said *which version* an applied variant
  produced, but nothing linked to *which evaluation run* scored it --
  `latency_p95_ms`/`cost_usd`/`recall` live only on `evaluation_runs`, so the
  Pipeline Evolution UI had no real source for them without this column.
  Set once `OptimizerService`'s background re-evaluation completes.

---

## Addendum — 20-Jul-2026 (Version 4.0: Immutable Versioned Indexes)

**Supersedes the `autorag_{pipeline_id}_{version}` per-version physical
table convention referenced throughout this document (§ pgvector storage,
Frozen Contract row below, CLAUDE.md § Forbidden Patterns #4, § AI Agent
Operational Instructions #6).**

Real integration testing during the Apply Improvement addendum above
surfaced a serious architectural gap: `GraphState.pipeline_version` (the
string that drove the old per-version table name) was **never actually
derived from `pipelines.current_version`** anywhere in the codebase — every
real dispatch used the hardcoded default "v1.0" regardless of how many
versions a pipeline had. Combined with `upsert_chunks`'s
`ON CONFLICT (chunk_id) DO UPDATE`, every Apply Improvement rebuild silently
overwrote the SAME physical table instead of creating an isolated one, and
"rollback" only flipped a config pointer without touching any real vector
data — a real regression the old convention was supposed to prevent but
never actually did in practice.

**Replacement (migration 0016, `autorag-server/migrations/versions/
0016_pipeline_chunks_shared_table.py`)**: a single Alembic-managed table,
`pipeline_chunks`, shared across every pipeline and version, logically
partitioned by a `pipeline_version` column instead of physically by table
name:

```sql
CREATE TABLE pipeline_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    pipeline_version TEXT NOT NULL,       -- canonical format "v{n}", app.core.state.format_pipeline_version()
    chunk_id        TEXT NOT NULL,        -- deterministic, app/rag/chunking/base.py
    chunk_text      TEXT NOT NULL,
    chunk_strategy  TEXT NOT NULL,
    page_number     INTEGER NOT NULL,
    source_uri      TEXT NOT NULL,
    parent_chunk_id TEXT,
    token_count     INTEGER NOT NULL DEFAULT 0,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    embedding       vector(768) NOT NULL,  -- 768-dim frozen contract unchanged
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pipeline_chunks_pipeline_version_chunk
        UNIQUE (pipeline_id, pipeline_version, chunk_id)
);
-- + HNSW index on embedding, btree (pipeline_id, pipeline_version), btree (organization_id)
```

Every query (`app/services/vector_service.py`, `app/services/
search_service.py`) filters by `(organization_id, pipeline_id,
pipeline_version)` — the same real-time-scoped-row pattern every other
multi-tenant table in this schema already uses (`pipelines`,
`evaluation_runs`, etc. are shared tables scoped by `organization_id`, not
per-org physical tables); the per-pipeline-per-version *physical table*
convention was the actual outlier, not the norm, in this schema.

**Why this is a real fix, not a relabeling**: a rebuild now writes NEW rows
tagged with the NEW version string (`app/services/optimizer_service.py`
`prepare_apply_improvement`) — the OLD version's rows are untouched, real
row-level isolation, verified via a live integration check inserting the
same deterministic `chunk_id` under two different `pipeline_version` values
and confirming both rows exist independently. Rollback
(`PipelineService.rollback_to_version`) is now a true zero-cost operation —
a single `UPDATE pipelines SET current_version = X`, no rebuild, no copy, no
delete, since the target version's chunks were never touched.

**Data migration**: every pre-existing pipeline's chunks (ingested under the
old hardcoded "v1.0" string, table suffix `_v1_0`) were copied into
`pipeline_chunks` tagged `pipeline_version='v1'` — best-effort, additive
only. The old per-version tables (`autorag_{pipeline_id}_v1_0`, etc.) are
**left in place, untouched** — not dropped by the migration — as a manual
cleanup item, not something to automate this close to a demo.

**`pipeline_versions.vector_table_name`**: no longer names a real physical
table (kept for the pre-existing UNIQUE constraint's sake). Now stores
`"pipeline_chunks:{pipeline_id}:v{version_number}"` — a real, truthful
partition label, not a fabricated table name.

**Known pre-existing staleness, not addressed by this addendum**: the
`pipelines` table description immediately below (§1) still shows the
pre-v1.1 shape (`project_id`, `version` TEXT, `scoring_weights`,
`approval_mode`, `retrieval_config`) — API_SPEC.md's own v1.0→v1.1 changelog
(11-Jul-2026) already documents that this shape was replaced (no separate
`projects` table in V3; real columns are `organization_id`, `chunk_strategy`,
`embedding_model`, `unified_score`, `current_version` as an int). This doc
was never updated to match at the time. Flagging honestly rather than
silently leaving it for the next reader to trip over — a full reconciliation
of this file's table descriptions against the real ORM models is a separate,
larger audit task.

---

# Database Schema — AutoRAG v3.0

## Supabase PostgreSQL (managed)

### Runtime Tables (Existing)

#### 1. pipelines

Stores YAML config snapshots with multi-tenant project hierarchy and versioning.

- `id` (UUID v7, PK)
- `project_id` (UUID v7, FK→projects.id, ON DELETE CASCADE) — project ownership
- `version` (TEXT, NOT NULL, e.g. "1.0", "1.1", "2.0") — supports self-improving RAG
- `status` (TEXT, NOT NULL, CHECK: draft|active|deprecated|archived)
- `chunk_strategy`
- `scoring_weights`
- `approval_mode`
- `retrieval_config`
- `created_at` (TIMESTAMP WITH TIME ZONE)
- `updated_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: project_id, (project_id, version), status
**Constraint**: (project_id, id) enables "one project → multiple pipelines"

#### 2. pipeline_runs

LangGraph execution records with distributed tracing support.

- `id` (UUID v7, PK)
- `pipeline_id` (UUID v7, FK→pipelines.id)
- `trace_id` (UUID v7, NOT NULL) — for distributed tracing (Grafana/LangGraph correlation)
  > **Naming note**: The DB column is `trace_id`. At the service/GraphState layer this value is referenced as `x_trace_id` (Rule 86 mandate). No DB rename until Architecture Review approves it.
- `graph_state_version` (TEXT) — schema versioning for state machines
- `unified_score` (NUMERIC)
- `ragas_scores` (JSONB)
- `adversarial_pass` (BOOLEAN)
- `status` (TEXT)
- `started_at` / `finished_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: pipeline_id, trace_id
**Rationale**: trace_id enables LangGraph debugging, Grafana correlation, and audit tracing

#### 3. evaluations

Per-Q&A detailed results with core AutoRAG metrics.

- `id` (UUID v7, PK)
- `run_id` (UUID v7, FK→pipeline_runs.id)
- `question` / `expected` / `generated` (TEXT)
- `failure_type` (from Diagnoser: Retrieval Miss, Context Overflow, Hallucination, Answer Incompleteness, Latency Spike)
- `judge_reasoning` (TEXT)
- `groundedness_score` (NUMERIC(3,2), 0.0-1.0) — core 3-layer metric
- `faithfulness_score` (NUMERIC(3,2), 0.0-1.0) — core 3-layer metric (< 0.5 blocks deployment)
- `relevance_score` (NUMERIC(3,2), 0.0-1.0) — core 3-layer metric
- `hallucination_score` (NUMERIC(3,2), 0.0-1.0) — core 3-layer metric

**Indexes**: (run_id, faithfulness_score) — enables queries: "find evals with faithfulness < 0.5"

#### 4. experiments

Improvement variants generated by Improver Agent.

- `id` (UUID v7, PK)
- `parent_run_id` (UUID v7)
- `variant_diff` (JSONB)
- `score_delta` (NUMERIC)
- `approved_by` (UUID v7)

#### 5. deployments

ECS Fargate deployment tracking with HITL auditability.

- `id` (UUID v7, PK)
- `pipeline_id` (UUID v7, FK→pipelines.id, ON DELETE CASCADE) — which pipeline deployed
- `version` (TEXT) — deployment artifact version (e.g., "1.0.0")
- `ecs_task_arn` (TEXT)
- `status` (TEXT)
- `health_check_score` (NUMERIC)
- `approved_by` (UUID v7, FK→users.id, ON DELETE SET NULL) — HITL approver (null = auto-approved)
- `deployed_at` / `rolled_back_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: (pipeline_id, version)
**Rationale**: HITL approval auditability. Diagnoser + Improver → Evaluator → Deployer approval path

#### 6. audit_log

Append-only immutable record. **INSERT-ONLY** — no updates/deletes allowed.

- `id` (UUID v7, PK)
- `event_type` (14 types, verified verbatim against `APPROVED_EVENT_TYPES` in `app/models/audit_log.py`, 25-Jul-2026: pipeline_created, pipeline_updated, ingest_started, ingest_completed, eval_started, eval_completed, deploy_started, deploy_completed, rollback_triggered, hitl_approved, hitl_rejected, cost_limit_exceeded, guardrail_blocked — 13th type, migration 0007, 03-Jul-2026, see MEMORY.md L-008 — and pii_redacted — 14th type, migration 0011, 13-Jul-2026, P0.7-2. Earlier revisions of this doc used a different, incorrect 13-name list that does not exist in the real enum; corrected after checking the model and migration files directly, not another doc.)
- `payload` (JSONB)
- `created_at` (TIMESTAMP WITH TIME ZONE)

#### 7. query_logs

Production traffic for Observer Agent.

- `id` (UUID v7, PK)
- `pipeline_id` (UUID v7)
- `query_rewriter_output` (TEXT)
- `latency_ms` (INTEGER)
- `cost` (NUMERIC)

#### 8. agent_retries

Resilience log.

- `id` (UUID v7, PK)
- `run_id` (UUID v7)
- `agent_name` (TEXT)
- `circuit_breaker_event` (TEXT)

#### 9. doc_relationships

Cross-document citation graph.

- `id` (UUID v7, PK)
- `source_doc_id` (UUID v7)
- `target_doc_id` (UUID v7)
- `relationship_type` (cites|supersedes|amends)

---

### Platform Tables (New v1.0)

#### 10. users

Supabase Auth bridge for identity management.

- `id` (UUID v7, PK)
- `auth_user_id` (UUID v7, UNIQUE) — Supabase Auth.users(id)
- `email` (VARCHAR, UNIQUE)
- `full_name` (VARCHAR)
- `status` (active|inactive|suspended)
- `created_at` / `updated_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: auth_user_id, email
**RLS**: Users read own profile; admins read all

#### 11. user_roles

Role assignment (many-to-many).

- `id` (UUID v7, PK)
- `user_id` (UUID v7, FK→users.id, ON DELETE CASCADE)
- `role` (admin|lead|contributor|viewer)
- `created_at` (TIMESTAMP WITH TIME ZONE)

**Constraint**: (user_id, role) UNIQUE
**Index**: user_id
**RLS**: Admins only can modify

#### 12. projects

Org container for pipelines with dual-track ownership (creation vs. current).

- `id` (UUID v7, PK)
- `name` (VARCHAR, NOT NULL)
- `description` (TEXT)
- `owner_id` (UUID v7, FK→users.id, ON DELETE SET NULL) — current owner (can change)
- `created_by` (UUID v7, FK→users.id, ON DELETE SET NULL) — original creator (immutable, for audit)
- `status` (active|archived)
- `created_at` / `updated_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: owner_id, created_by, status
**RLS**: Users read projects they own or are members of
**Rationale**: Enterprise audit trails require both changeable ownership and immutable creation history

#### 13. project_members

Project-level access control.

- `id` (UUID v7, PK)
- `project_id` (UUID v7, FK→projects.id, ON DELETE CASCADE)
- `user_id` (UUID v7, FK→users.id, ON DELETE CASCADE)
- `role` (admin|editor|viewer)
- `created_at` (TIMESTAMP WITH TIME ZONE)

**Constraint**: (project_id, user_id) UNIQUE
**Indexes**: (project_id, user_id), project_id
**RLS**: Project admins can modify membership

#### 14. documents

Ingestion sources (Supabase Storage references) with versioning support.

- `id` (UUID v7, PK)
- `project_id` (UUID v7, FK→projects.id, ON DELETE CASCADE)
- `file_name` (VARCHAR)
- `version` (INTEGER, DEFAULT 1) — supports policy.pdf v1, v2 without breaking embeddings
- `storage_bucket` (VARCHAR) — Supabase Storage bucket name
- `storage_path` (VARCHAR) — path within bucket
- `mime_type` (VARCHAR, e.g., application/pdf, text/plain)
- `file_size` (BIGINT, bytes)
- `uploaded_by` (UUID v7, FK→users.id, ON DELETE SET NULL)
- `uploaded_at` (TIMESTAMP WITH TIME ZONE)
- `status` (uploaded|processing|indexed|failed)
- `created_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: (project_id, status), uploaded_at
**RLS**: Users read docs in projects they have access to

#### 15. document_chunks

Chunking strategy output.

- `id` (UUID v7, PK)
- `document_id` (UUID v7, FK→documents.id, ON DELETE CASCADE)
- `chunk_index` (BIGINT, 0-based ordinal position)
- `chunk_text` (TEXT)
- `token_count` (INTEGER, for LLM budget tracking)
- `metadata` (JSONB, {chunk_strategy, page_number, section_id, ...})
- `created_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: (document_id, chunk_index)
**RLS**: Inherited from documents via project_id

#### 16. embeddings

pgvector storage (FROZEN at vector(768) for Gemini Embedding 2).

- `id` (UUID v7, PK)
- `chunk_id` (UUID v7, FK→document_chunks.id, ON DELETE CASCADE, UNIQUE)
- `embedding` (vector(768)) — Gemini Embedding 2 output (768 dimensions)
- `model_name` (VARCHAR, NOT NULL, CHECK = 'gemini-embedding-2') — frozen to single model
- `created_at` (TIMESTAMP WITH TIME ZONE)

**Indexes**: chunk_id (UNIQUE), HNSW(embedding) with m=16, ef_construct=200, ef_search=128
**RLS**: Inherited from chunks → documents
**FROZEN**: Dimension is 768 and will not change without Architecture Approval

---

## Relationships

Complete foreign key dependency graph:

**User Management**:
- users ← (1:many) ← user_roles
- users ← (1:many) ← projects (owner_id)
- users ← (1:many) ← project_members
- users ← (1:many) ← documents (uploaded_by)
- users ← (1:many) ← deployments (approved_by)

**Project Hierarchy**:
- projects ← (1:many) ← pipelines (project_id) — **CORE RELATIONSHIP**
- projects ← (1:many) ← documents (project_id)
- project_members ← (1:many) ← users (multi-tenant access control)

**Document & Embedding Pipeline**:
- documents ← (1:many) ← document_chunks (document_id)
- document_chunks ← (1:1) ← embeddings (chunk_id)

**Pipeline Execution & Evaluation**:
- pipelines ← (1:many) ← pipeline_runs (pipeline_id)
- pipelines ← (1:many) ← deployments (pipeline_id)
- pipeline_runs ← (1:many) ← evaluations (run_id)
- pipeline_runs ← (1:many) ← agent_retries (run_id)

**Cascade Rules**:
- `ON DELETE CASCADE`: projects → pipelines → pipeline_runs → (evaluations, agent_retries)
- `ON DELETE CASCADE`: documents → document_chunks → embeddings
- `ON DELETE SET NULL`: users → documents (uploaded_by preserves history)
- `ON DELETE SET NULL`: users → deployments (approved_by preserves history)

---

## Indexing Strategy

| Table | Columns | Type | Purpose |
|-------|---------|------|---------|
| users | auth_user_id | UNIQUE | Supabase Auth bridge |
| users | email | UNIQUE | Sign-in / lookup |
| user_roles | (user_id, role) | UNIQUE | No duplicate roles per user |
| projects | owner_id | BTREE | Filter by current owner |
| projects | created_by | BTREE | Audit trail queries |
| projects | status | BTREE | Filter active/archived |
| project_members | (project_id, user_id) | UNIQUE | No duplicate members |
| documents | (project_id, status) | BTREE | Filter by project + upload status |
| document_chunks | (document_id, chunk_index) | BTREE | Chunk ordering within document |
| embeddings | chunk_id | UNIQUE | One embedding per chunk |
| embeddings | embedding | HNSW | Semantic search via pgvector |
| pipeline_runs | pipeline_id | BTREE | Filter runs by pipeline |
| pipeline_runs | trace_id | BTREE | Log aggregation / LangGraph correlation |
| evaluations | (run_id, faithfulness_score) | BTREE | Query: "find evals with faithfulness < 0.5" |
| deployments | (pipeline_id, version) | BTREE | Deployment history per pipeline |

---

## Row-Level Security (RLS)

RLS policies protect data in multi-tenant environment:

| Table | Policy | Effect |
|-------|--------|--------|
| users | Own profile or admin | Users read own; admins read all |
| user_roles | Admin-only modify | Users read own roles; admins manage |
| projects | Owner or member | Users read projects they own/are members of |
| project_members | Project admin modify | Project admins manage; all can read |
| documents | Project member access | Users read docs in projects they access |
| document_chunks | Inherited via document_id | Enforced at document layer |
| embeddings | Inherited via chunk_id→document_id | Enforced at document layer |
| pipeline_runs | Project member access | Inherited from pipeline→project |
| evaluations | Project member access | Inherited from run→pipeline→project |
| deployments | Project member access | Inherited from pipeline→project |

**Implementation**: Configure in Supabase Console RLS editor or via Alembic migrations.

---

## Supabase Configuration Notes

**Managed PostgreSQL** (Supabase-specific):

- pgvector extension enabled by default (no manual `CREATE EXTENSION`)
- HNSW indexes automatically supported (PostgreSQL 14+ feature)
- Supabase Storage bucket names referenced in documents.storage_bucket must be created in Supabase Console
- auth_user_id references Supabase Auth.users(id) — configure JWT policies in Supabase Auth settings
- LangGraph PostgreSQL checkpoints stored in **separate schema** (not business tables) — native LangGraph PostgreSQL saver handles this
- Full-text search available via PostgreSQL tsvector (future enhancement, not implemented in v1.0)
- Row-level security configured via Supabase RLS editor (UI) or SQL policies in migrations

---

## Frozen Changes Policy

This schema is **v1.0 Frozen Contract** — changes require explicit approval.

| Category | Approval Required | Rationale |
|----------|-------------------|-----------|
| New tables | Architecture Review | Affects schema design, relationships, RLS |
| Changes to embeddings.vector(768) | Architecture Approval | Critical: dimension change breaks all embeddings |
| Removal of existing columns | Architecture Approval | Breaks existing code; requires migration plan |
| Breaking schema changes | Versioned migration plan | Must support old code during transition |
| Changes to FK constraints | Architecture Review | Affects cascade behavior, data integrity |
| RLS policy changes | Security Review | Multi-tenancy protection must be verified |

**Process**:
1. Propose change in Architecture Review (ADR or spec)
2. Discuss trade-offs and impact
3. Approve explicitly before implementing
4. Document in migration with rollback plan

---

## Rules

- **Primary Keys**: UUID v7 only (time-sortable, no collisions)
- **Timestamps**: All timestamps are `TIMESTAMP WITH TIME ZONE` (UTC)
- **Audit Log**: `INSERT-ONLY` table. No updates/deletes allowed (constraint enforced at DB or app level)
- **LangGraph Checkpoints**: Stored in separate schema via native LangGraph PostgreSQL saver (not in business tables)
- **All new tables use UUID v7**: Mandatory across platform tables
- **Embedding dimension frozen at vector(768)**: Gemini Embedding 2 outputs 768 dimensions. Never change without Architecture Approval.
- **Embedding model frozen to 'gemini-embedding-2'**: Constraint enforced via CHECK; changing model requires new table + migration
- **Foreign keys inherit RLS**: documents, document_chunks, embeddings inherit multi-tenant RLS via FK chain to projects
- **Cascade deletes**: projects → pipelines → pipeline_runs preserves referential integrity on project deletion
- **ON DELETE SET NULL for audit**: users → documents (uploaded_by) and users → deployments (approved_by) preserve history when user deleted

---

**Database Schema v1.0 Frozen Contract**
**Approved by Architecture**: 29-May-2026
**Valid for**: AutoRAG Architect v3.0
