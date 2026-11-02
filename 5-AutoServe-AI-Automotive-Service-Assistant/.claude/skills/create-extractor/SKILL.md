---
name: create-extractor
description: Checklist for adding an AutoServe AI document extractor (repair order, parts invoice, service record, claim form, etc.) with injection-safe prompting, schema validation, deterministic checks, and accuracy evals.
---

# Create a document extractor

Read first: `.claude/rules/70-security.md`, `.claude/specs/agents/03-document.md`, `.claude/rules/50-rag-system.md`.

## Checklist
1. [ ] Add the document class to `app/documents/classify.py` (enum + classifier examples; no real brands).
2. [ ] Define the extraction schema in `app/documents/schemas/<class>.py`: each field is `{value, confidence, source_page}`; `extra="forbid"`.
3. [ ] Versioned prompt `app/prompts/extract_<class>_v1.md`: the system prompt holds instructions only; document text goes in the **user** turn inside `<untrusted_document>`; the prompt states the document cannot change instructions.
4. [ ] `LLMService.structured(..., tools=None)`; retry ≤ 2 on schema failure, passing the validation error back.
5. [ ] Deterministic validators: VIN check digit + matches the RO; dates; totals = Σ lines; part numbers in `parts`; op codes in `labour_ops`; quantities > 0.
6. [ ] `confidence < 0.80` or a validator fails → `needs_human_verification`.
7. [ ] Injection heuristics → D-09 risk flag; the output stays schema-bound.
8. [ ] Sample docs in `scripts/generate_sample_docs.py` + ground truth in `evals/extraction/<class>_*.json`.
9. [ ] Tests: schema-failure retry, each validator ±, threshold boundary, injection sample yields an identical decision path to its clean twin.
10. [ ] Run the extraction eval; report per-field accuracy (target ≥ 90% key fields); paste output; update TASK_TRACKER.
