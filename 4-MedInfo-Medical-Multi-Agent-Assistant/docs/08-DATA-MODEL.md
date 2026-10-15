# 08 - Data Model

All application tables live in Supabase Postgres (schema created by `backend/scripts/db_init.py`,
verified live on 2026-10-14: pgvector 0.8.2, tables below, `tsv` column present). Redis holds only
expiring data. All bundled data is SYNTHETIC.

## Vector store (langchain-postgres PGVector)
| Table | Key columns | Notes |
|---|---|---|
| `langchain_pg_collection` | uuid, name | Two collections per embedding model: `medinfo_trusted__euri_text_embedding_3_small_1536`, `medinfo_user__...` (models never mixed: a new model means new collections + re-ingest) |
| `langchain_pg_embedding` | id (UUID from content hash), collection_id, embedding vector(1536), document, cmetadata JSONB, **tsv** tsvector (generated, GIN) | `cmetadata`: doc_id, source, collection, trusted, owner_id, title, publisher, publication_date, version, evidence_level, jurisdiction, licence, doc_type, source_url, series, page/sheet/slide/section, ocr, injection_flagged, kind, parent_id, chunk_hash |

## Application tables
| Table | Columns | Purpose |
|---|---|---|
| `medinfo_ingest_registry` | doc_id PK, collection, filename, file_hash, chunk_hashes JSONB, provenance JSONB, trusted, owner_id, updated_at | Incremental upsert, document lists, ownership |
| `medinfo_parent_chunks` | parent_id PK, doc_id FK, text | Parent-child chunking context |
| `medinfo_conversations` | id, user_id, title_enc, created_at, updated_at | Owner-scoped; title encrypted (Fernet) |
| `medinfo_messages` | id, conversation_id FK, role, text_enc, meta JSONB, created_at | Redacted + encrypted text; meta = kind, scope, citation provenance, limitations, warnings |
| `medinfo_review_items` | id, created_at, source, question, answer_json, status, verdict, notes, reviewer_id, reviewed_at | Clinician review (redacted content) |
| `medinfo_eval_runs` | id, created_at, label, params JSONB, metrics JSONB | Evaluation history shown to admins |

## Redis keys (all with TTL)
| Key | Content |
|---|---|
| `medinfo:answer:<sha256>` | Cached clean `ChatAnswer` JSON |
| `medinfo:llm:<sha256>` | Prompt-cache entries: plain AI text only |
| `medinfo:conv:<id>:turns` | Recent turns (redacted) |
| `medinfo:rl:<bucket>:<user>` | Fixed-window rate-limit counters |
| `medinfo:corpus_version`, `medinfo:user_docs_version:<user>` | Cache invalidation counters |

## Retention and deletion
Conversations older than `CONVERSATION_RETENTION_DAYS` (30) are purged (`MemoryService.purge_expired`,
to be scheduled as a job). Users can delete one or all conversations and their own uploads; admins delete
trusted documents (chunks, parents and registry rows).
