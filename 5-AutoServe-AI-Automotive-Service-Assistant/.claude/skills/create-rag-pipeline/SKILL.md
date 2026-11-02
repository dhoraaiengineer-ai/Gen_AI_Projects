---
name: create-rag-pipeline
description: Checklist for building or changing AutoServe AI knowledge ingestion, chunking, hybrid retrieval, and grounded cited answering over the synthetic Veloxa corpus.
---

# Create / change the RAG pipeline

Read first: `.claude/rules/50-rag-system.md`, `.claude/rules/55-automotive-safety.md`, `.claude/adr/003-pgvector.md`.

## Checklist
1. [ ] Source content is authored only in `data/knowledge/src/*.md` (synthetic, Veloxa). Regenerate PDFs with `scripts/generate_knowledge.py`; every page watermarked "SYNTHETIC — FOR DEMO ONLY".
2. [ ] Chunker (`app/rag/chunker.py`): structure-aware units (procedure, spec table, warning-light entry, TSB, recall, DTC entry) kept whole; fallback ~800 tokens / 100 overlap.
3. [ ] Metadata complete: `doc_type, model, model_year_from/to, vin_range, section_id, section_title, page, source_file, version, visibility, safety_critical, content_hash`.
4. [ ] Ingestion (`app/rag/ingest.py`) is idempotent on `content_hash`; re-running doesn't duplicate.
5. [ ] Embeddings (`app/rag/embeddings.py`) use `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` (1536, ADR-008); startup fails on a dimension mismatch with the migration.
6. [ ] Retriever (`app/rag/retriever.py`): vector + FTS → RRF; mandatory model/year filter; owner → `visibility='owner'`; DTC/op-code exact boost; reranker behind a flag.
7. [ ] Threshold from config; below it → `insufficient_evidence` with **no LLM call**.
8. [ ] Answer (`app/rag/answer.py`): grounded prompt, citations, post-validation of chunk ids and quotes, safety banner logic.
9. [ ] Tests: owner never gets staff chunks; wrong-model filter; idempotent ingest; quote-substring validation; threshold → no LLM call.
10. [ ] Evals: extend `evals/manual_qa.jsonl` / `evals/safety.jsonl`; run `scripts/run_eval.py`; report in `evals/reports/`; thresholds refusal ≥ 0.90, safety = 1.00, faithfulness ≥ 0.85.
11. [ ] Paste the test + eval output; update TASK_TRACKER.
