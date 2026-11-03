# AutoRAG Architect v4.0 — RDS Module
#
# ⚠️  LEGACY STUB — NOT USED (unchanged from v3.0 through v4.0)
#
# This module was planned for AWS RDS PostgreSQL 15 in the original v2.4 design.
# Since v3.0, the relational database is provided by Supabase PostgreSQL (managed) —
# still true in v4.0 (Immutable Versioned Indexes, migration 0016).
#
# Supabase replaces self-hosted RDS with:
#   - Managed PostgreSQL (no EC2, no patching)
#   - Built-in pgvector for vector embeddings
#   - Supabase Storage for object storage
#   - Supabase Auth, Realtime, and Edge Functions
#
# See ADR-005 (supabase.md) for the full migration rationale.
# See infra/bootstrap/main.tf for Supabase credentials in Secrets Manager.
#
# DO NOT implement this module. If RDS is ever needed for a different purpose,
# create a new dedicated module — do not revive this stub.
