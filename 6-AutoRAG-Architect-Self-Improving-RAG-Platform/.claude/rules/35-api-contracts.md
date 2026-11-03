# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 35: AutoRAG API Contracts

## Enforces:

1.  **Wrapper**: All responses must use the `{ "status": str, "data": dict, "error": dict, "request_id": uuid }` structure.
2.  **Tracing**: Mandatory `X-Trace-ID` propagation from API to LangGraph to Audit Log.
3.  **Versioning**: `/api/v1/` prefix for all production endpoints.
4.  **Jobs**: Pollable status for long-running LangGraph sessions via `/api/v1/jobs/{id}`.

## Anti-Patterns:

- Returning raw Pydantic models without the standard wrapper.
- Missing `request_id` in error responses.
- Inconsistent HTTP status codes (e.g., using 200 for logical failures).
