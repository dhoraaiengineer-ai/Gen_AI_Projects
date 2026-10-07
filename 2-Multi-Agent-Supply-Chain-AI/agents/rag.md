# RAG Agent (Knowledge Base)

**Code:** `app/rag/service.py` (use case), `app/agents/specialists/rag.py` (graph node), `app/rag/*`

## Responsibility

Answer questions from company documents with citations. The documents are:

- procurement policies
- supplier contracts
- inventory policies
- shipping policies
- SOPs

## Query pipeline

```text
question → input guardrails → (follow-up rewrite) → multi-query
        → metadata pre-filter (user filters + agent filters + mandatory role filter)
        → hybrid search: pgvector cosine ∥ BM25-IDF full-text → RRF fusion → dedupe/parent collapse
        → LLM rerank (top 12 → top_k; skipped in agent mode by default) → context guardrails (fence, injection scan, PII redact)
        → grounded generation ([n] citations, fixed refusal) → hallucination guard → answer + sources
```

The `no_documents` branch skips the LLM and returns the refusal.

## Ingestion pipeline

Ingestion runs separately from queries:

```text
upload (multipart, size limit, per-file status) → loader (PDF/DOCX/XLSX/PPTX/CSV/TXT/MD/JSON; OCR for scans and images)
 → clean (CRLF→LF, whitespace) → metadata (user-supplied + auto-detected SKUs/suppliers/dates)
 → chunk (recursive | semantic | parent_child | table) → deterministic ids → incremental upsert (hash registry)
 → embed (only new chunks) → pgvector + tsvector
```

## Metadata filters

| Field | Example | Who sets it |
|---|---|---|
| `doc_type` | `contract` | user or agent |
| `supplier_id` | `SUP-002` | agent (supplier) |
| `skus` | `["SKU-100"]` | auto-detected, or the user |
| `region` | `APAC` | user |
| `effective_date` / `expiry_date` | exclude expired | agent default |
| `classification` | `internal` | **role-enforced** and cannot be overridden |

## Output

- `answer`
- `citations`: a list of `{n, source, location, chunk_id, score}`. A location looks like `policy.pdf, p. 3`.
- `guard`: `{status, reasons}`

## Access

- **Roles allowed:** all roles. Restricted documents need approver or admin.
