# 50 — RAG System

**Purpose:** Grounded, cited, role-filtered answers from the synthetic Veloxa corpus.

## MUST
- Structure-aware chunking: keep each procedure, spec table, warning-light entry, TSB, and recall intact. Otherwise ~800 tokens with 100 overlap.
- Chunk metadata: `doc_type, model, model_year_from, model_year_to, vin_range, section_id, section_title, page,
  source_file, version, visibility (owner|staff), safety_critical, content_hash`.
- Idempotent ingestion keyed by `content_hash`.
- Hybrid retrieval: pgvector cosine + Postgres FTS, fused with RRF. Exact-match boost for DTC codes and op codes.
- **Mandatory filters:** model + model year (from the VIN when known). Owners get `visibility='owner'` only.
- The score threshold comes from config. If no chunk clears it → `insufficient_evidence=true`, **without calling the LLM**.
- Grounded prompt: answer only from the `<context>` chunks, cite `[chunk_id]` for every claim, quote specs verbatim,
  otherwise say "I don't have that in the manual."
- Output schema: `{answer, citations[{chunk_id, source_file, page, section_id, quote}], confidence, insufficient_evidence, safety_critical}`.
- Post-validate: every cited `chunk_id` was in the retrieved set, and every quote is a substring of that chunk. Drop or flag violations.
- `safety_critical = any(c.safety_critical for c in cited) or matches(config/safety_keywords.yaml)` → prepend the banner (rules/55).
- DTC meaning: exact-match lookup in `doc_type='dtc'` chunks only. Not found → "code not found in reference".

## MUST NOT
- Let owners retrieve `visibility='staff'` chunks (this must have a test).
- Answer across models (Aria content for a Volt question).
- Paraphrase a numeric spec. Quote it with its citation.
- Use model memory for automotive facts.

## Good
```
Q (Volt owner): What does the orange battery symbol mean?
A: "<verbatim quote from manual>" [owner_manual_volt p.12 §4.3] — confidence 0.82
```

## Bad
```
A: That's the 12V battery light; it usually means the alternator is failing.
   ← no citation, invented, and wrong for the model
```
