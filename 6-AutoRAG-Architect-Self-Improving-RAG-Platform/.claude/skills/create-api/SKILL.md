# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-api
description: Create a production-grade FastAPI endpoint using this repository's architecture

---

# Create API Skill

## Goal

Create a new FastAPI endpoint that follows the AutoRAG 9-agent architecture.

## Steps

1. Ask for: endpoint purpose, HTTP method, request/response shape, and which service domain it belongs to.
2. Create or update Pydantic request/response schemas in `schemas/`.
3. Create or update repository methods in `repositories/` for data access.
4. Create or update service logic in `services/` for business rules.
5. Create or update the route in `routes/` — keep it thin (max 10-15 lines).
6. Register the route in the appropriate router.
7. Add unit tests for the service layer.
8. Add API tests for the endpoint.
9. Summarize all changes.

## Quality rules

- Keep routes thin — delegate to services.
- Put business logic in services, data access in repositories.
- Use Pydantic for all request/response validation.
- Use async/await for all I/O operations.
- Add structured logging for important flows.
- Handle edge cases: empty results, invalid input, auth failures.
- Add clear error handling with consistent error response format.
- Never hardcode secrets or URLs.
- Do not skip tests.
