# ADR-007 — Host PostgreSQL + pgvector on Supabase (amends ADR-003)

**Status:** Accepted · **Date:** 2026-10-26 · **Amends:** ADR-003 (hosting only; the data design is unchanged)

## Context
The project owner wants to use Supabase. Connection details will be provided later. ADR-003 chose PostgreSQL 16 + pgvector
and listed Supabase as an alternative, because of platform coupling. Supabase is managed PostgreSQL with the `vector` extension,
so it satisfies ADR-003's technical requirements.

## Decision
- Use **Supabase Postgres** as the hosted database (relational + pgvector + LangGraph checkpoints) through a standard
  `DATABASE_URL` (SQLAlchemy async / asyncpg) and Alembic. Use the **session pooler / direct connection** for migrations and
  `PostgresSaver`. If the transaction pooler (port 6543) is used for the app, disable prepared statements (`statement_cache_size=0`).
- **No Supabase-specific coupling** in application code: no `supabase-py`/`supabase-js` data access, no Supabase Auth
  (auth stays DEMO JWT → OIDC Cognito per CLAUDE.md), and no reliance on PostgREST/RLS for authorization. Authorization stays
  in actor-scoped repositories (rules/70). RLS may be enabled as defence-in-depth, with the app role bypassing it.
- **Local and CI** keep Docker `pgvector/pgvector:pg16`, so tests run without Supabase credentials.
- Document storage stays **MinIO / S3** (CLAUDE.md §8). Moving to Supabase Storage needs a separate ADR.
- Credentials only via env (`DATABASE_URL`, `DATABASE_URL_MIGRATIONS`). Never committed. Agents never read `.env`.

## Alternatives
- Local Postgres only: no hosted environment for sharing the demo.
- RDS (ADR-005): remains the AWS production target. Supabase is used for the hosted demo/dev environment until a pilot decides.

## Consequences
- + Hosted Postgres with pgvector, without running infrastructure.
- + Portable: switching between Supabase, local Docker, and RDS is a connection-string change.
- − Pooler mode affects prepared statements and long-lived checkpointer connections; this must be tested in P1-2.
- − Two hosted targets (Supabase for dev/demo, RDS in the Terraform design). P5 docs must state which one is in use.
- − Supabase project region and data residency must be chosen for owner PII (synthetic data only for now).
