# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# LangGraph Anti-Patterns

- **Direct Node Calls**: As a default rule, never invoke an agent function directly from another agent; route through the Graph so conditional edges, checkpointing, and retries stay consistent. **Real, sanctioned exception**: `app/routes/ingest.py`'s upload dispatch calls `ingestion_node()` then `builder_node()` directly, deliberately bypassing the full `workflow.ainvoke()` graph -- the graph's unconditional `ingestion -> ... -> evaluator` edges hung forever on upload, since a document upload has no real `raw_query` for Evaluator to score (see `docs/case-study-large-document-ingestion-16jul2026.md`, Symptom 3/bug #3). Direct node calls are acceptable only when the full graph's edges are provably wrong for that specific dispatch path -- not as a general shortcut.
- **State Pollution**: Storing large, raw document objects in the state. Only store URIs and metadata.
- **Missing Checkpoints**: Running async loops without a persistence layer.
- **Opaque Errors**: Swallowing exceptions inside a node; always raise and let the graph handle the `__error__` edge.
- **Manual Retries**: Using `while` loops for LLM retries. **Also avoid LangGraph's built-in `RetryPolicy`** -- MEMORY.md L-001 found it retries without resetting affected `GraphState` fields first, corrupting state on retry. The established, correct pattern is explicit graph edges with a clean state-reset edge (Rule 60) -- never inline retry loops, never the native `RetryPolicy` either.
