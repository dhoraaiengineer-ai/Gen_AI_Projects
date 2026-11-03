# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Supabase Vector Table Skill

> **Superseded 20-Jul-2026 (Version 4.0)**: there is no longer a per-pipeline-version
> table to create. `VectorService.create_table()` was removed — every pipeline/version
> writes into the single, Alembic-managed `pipeline_chunks` table (migration 0016),
> partitioned by a `pipeline_version` column. See `docs/DB_SCHEMA.md`'s "Immutable
> Versioned Indexes" addendum. This skill's steps below describe the old, retired
> workflow — kept as historical record only.

## Purpose (historical)

Initialize and configure vector collections for a new pipeline version.

## Configuration (v3.0, historical)

- **Naming**: `autorag_{pipeline_id}_{version}`.
- **Distance**: `Cosine`.
- **HNSW**: `m=16`, `ef_construct=200`.

## Mandatory Payload Fields (Rule 50)

- `chunk_id` (UUID)
- `source_doc_id` (UUID)
- `chunk_strategy` (e.g., 'hierarchical')
- `source_uri` (TEXT) — origin document path/URL
- `page_number` (INTEGER) — source page for citation
- `embedding_model`

## Anti-Patterns

- **Mutable Collections**: Updating vectors in an active collection; always create a new versioned collection.
- **Missing Filters**: Querying without `organization_id` tenancy filter.
