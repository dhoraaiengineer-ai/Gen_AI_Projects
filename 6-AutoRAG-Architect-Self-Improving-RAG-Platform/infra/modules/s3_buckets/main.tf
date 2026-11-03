# AutoRAG Architect v4.0 — S3 Buckets Module
#
# ⚠️  LEGACY STUB — NOT USED (unchanged from v3.0 through v4.0)
#
# This module was planned for Amazon S3 in the original v2.4 design.
# Since v3.0, object storage is provided by Supabase Storage (managed) —
# still true in v4.0.
#
# Supabase Storage replaces S3 with:
#   - Managed object storage within the Supabase project
#   - Same SDK (supabase-py) as PostgreSQL and pgvector — no extra AWS credentials needed
#   - Bucket-level RLS (Row-Level Security) for multi-tenant isolation
#   - Pre-signed URLs for direct client uploads (same pattern as S3 presigned URLs)
#
# Supabase Storage is used for:
#   - Raw document uploads during ingestion
#   - Chunked text snapshots per pipeline version
#   - Pipeline configuration exports
#
# See ADR-005 (supabase.md) for the full migration rationale.
# See infra/bootstrap/main.tf for Supabase credentials in Secrets Manager.
#
# DO NOT implement this module. If a separate S3 bucket is ever required
# (e.g., ML artifact archival), create a new dedicated module.
