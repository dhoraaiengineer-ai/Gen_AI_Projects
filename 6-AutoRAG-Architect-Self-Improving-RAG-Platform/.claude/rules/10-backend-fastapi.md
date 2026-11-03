# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 10: AutoRAG Backend (FastAPI)

## Enforces:

1.  **Endpoints**: Adherence to the REST endpoint spec (`specs/api-design.md`) — 46 live-schema-verified endpoints as of 20-Jul-2026 (see `specs/api-design.md` §1 for why a plain route-decorator grep undercounts by 4).
2.  **Logic**: Thin routes; all agent orchestration delegated to the LangGraph service layer.
3.  **PII Safety**: Mandatory Custom PII Detection & Masking Functions at the request boundary.
4.  **Concurrency**: Strict use of `async/await` for all I/O and graph operations.
5.  **Failover**: Implement the Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 failover chain.

## Anti-Patterns:

- Synchronous LLM calls that block the event loop.
- Exposing raw PII in error messages or logs.
- Mixing RAG retrieval logic directly into route handlers.
