---
name: add-trusted-source
description: Add a new trusted publisher/document to the corpus safely (licence check, allow-list, provenance, ingest, retrieval check).
---

# Add a trusted source

1. Confirm the publisher's licence permits reuse. Record it; do not guess.
2. Add the publisher to `backend/app/rag/trusted_sources.yaml` (name, licence, jurisdiction, notes).
3. Prepare provenance for each document: title, publisher, publication_date, version, evidence_level,
   jurisdiction, licence, doc_type, and `series` when several versions exist.
4. Dry run to see chunk and embedding-call counts:
   `cd backend; ..\.venv\Scripts\python scripts\ingest_corpus.py <folder> --dry-run` (needs a manifest.yaml).
5. Tell the user the embedding-call count, then ingest (or upload via the admin Documents view).
6. Verify retrieval: add golden items to `backend/evals/golden.yaml` with verbatim evidence quotes and run
   `pytest tests/test_evaluation.py`.
