---
name: create-api
description: Checklist for adding an AutoServe AI FastAPI endpoint with RBAC, actor-scoped repositories, the response envelope, idempotency, error codes, and security tests.
---

# Create an API endpoint

Read first: `.claude/rules/10-backend-fastapi.md`, `.claude/rules/70-security.md`, `.claude/specs/api-design.md`.

## Checklist
1. [ ] The endpoint exists in `specs/api-design.md` (add it there first, with roles + error codes) and in `docs/API_SPEC.md`.
2. [ ] Request/response Pydantic schemas in `autoserve-server/app/schemas/` (`extra="forbid"` on input).
3. [ ] Route in `autoserve-server/app/api/v1/<area>.py` with `Depends(require_role(...))` and `response_model=Envelope[...]`.
4. [ ] Business logic in a service; data access through a repository that takes `actor` and applies the owner/dealer filter (out of scope → 404).
5. [ ] State changes only via `state_machine.transition()`; audit via `AuditService`.
6. [ ] State-creating POST → `Idempotency-Key` handling (`idempotency_keys` table).
7. [ ] Map domain exceptions to error codes from the spec; no internals leaked.
8. [ ] Rate limit if the route is login, chat, or upload.
9. [ ] Tests: happy path, validation error, each forbidden role (403), out-of-scope owner/dealer (404), idempotent replay, invalid transition (409).
10. [ ] Frontend: add a Zod schema in `autoserve-client/src/api/schemas.ts` matching the response.
11. [ ] Run tests + lint; paste output; update TASK_TRACKER.
