# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 80: AutoRAG Testing & Quality

## Enforces:

1.  **Graph Coverage**: Minimum **90% coverage** of all LangGraph conditional edges.
2.  **Hallucination Gate**: **100% pass rate** on the 10-question Adversarial Q&A set.
3.  **KPIs**: Unified Score >= 0.85; Retrieval Recall@5 >= 0.85.
4.  **Integration**: Mandatory tests using a real Supabase Vector (pgvector) table and Supabase PostgreSQL.
5.  **Failover**: Test verification of the LLM fallback chain.

## Anti-Patterns:

- Mocking the entire RAG pipeline (hides retrieval bugs).
- Skipping adversarial tests for "minor" prompt updates.
- Low-fidelity unit tests that don't verify state persistence.
