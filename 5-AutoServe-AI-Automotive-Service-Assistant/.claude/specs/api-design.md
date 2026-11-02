# Spec — API Design

> Base path `/api/v1`. Full request/response schemas go in `docs/API_SPEC.md` (Prompt 2).
> All responses use the envelope `{status: "ok"|"error", data, error: {code, message, details?} | null, request_id}`.
> State-creating POSTs accept `Idempotency-Key`. Out-of-scope resources return **404**.

## Roles legend
O = vehicle_owner · SA = service_advisor · T = technician · WA = warranty_admin · AD = admin · P = public

## Endpoints

| Method | Path | Roles | Purpose | Prompt |
|---|---|---|---|---|
| GET | `/health`, `/ready` | P | Liveness / readiness | 3 |
| POST | `/auth/login` | P | DEMO JWT login (rate-limited) | 4 |
| GET | `/auth/me` | all | Current actor | 4 |
| POST | `/chat/messages` | O | Owner chat turn (intent router → node); SSE stream | 6 |
| POST | `/chat/manual-question` | O, SA, T | Grounded manual Q&A (owner sees owner-visible chunks only) | 5 |
| GET | `/vehicles` | O (own), SA/T/WA (dealer) | List vehicles | 6 |
| GET | `/vehicles/{id}` | O (own), staff (dealer) | Vehicle + decoded VIN | 6 |
| GET | `/vehicles/{id}/recalls` | O (own), staff | Open recalls (deterministic VIN-range match) | 6 |
| GET | `/vehicles/{id}/context` | SA, T, WA | Vehicle Context card | 7 |
| POST | `/appointments` | O, SA | Create booking → RO BOOKED (Idempotency-Key) | 6 |
| GET | `/appointments?date=` | SA | Advisor board | 7 |
| GET | `/repair-orders` | O (own), staff (dealer) | List/filter ROs | 6 |
| GET | `/repair-orders/{id}` | O (own), staff | RO detail + timeline | 6 |
| GET | `/repair-orders/{id}/status` | O (own), staff | Status from `ro_status_history` (+ claim) | 6 |
| POST | `/repair-orders/{id}/check-in` | SA | Check-in → CHECKED_IN; runs Vehicle Context + D-01 | 7 |
| POST | `/repair-orders/{id}/transition` | SA (per table) | Generic allowed transition (e.g. IN_REPAIR, QUALITY_CHECK, CLOSED, CANCELLED with reason) | 10 |
| POST | `/repair-orders/{id}/documents` | SA, T, O (own; limited classes) | Secure upload → pipeline | 8 |
| GET | `/repair-orders/{id}/documents` | O (own), staff | List docs + extraction status | 8 |
| GET | `/documents/{id}/file` | staff, O (own) | Short-lived presigned URL | 8 |
| PATCH | `/documents/{id}/fields/{field_id}` | SA, WA | Correct extracted field (reason required) | 8 |
| POST | `/repair-orders/{id}/diagnosis` | T | Submit DTCs/symptoms/tests → Diagnosis node | 9 |
| POST | `/repair-orders/{id}/findings` | T | Record confirmed hypothesis, op codes, time, parts | 9 |
| POST | `/repair-orders/{id}/workflow/run` | SA | Run warranty/estimate graph | 10 |
| GET | `/repair-orders/{id}/estimate` | O (own), staff | Estimate lines + split | 10 |
| POST | `/repair-orders/{id}/estimate/decision` | O (own), SA (consent + note) | Line-by-line approve/decline → resume interrupt | 11 |
| GET | `/warranty/claims` | WA, SA (read) | Queue sorted by risk + age; filters | 11 |
| GET | `/warranty/claims/{id}` | WA, SA (read) | Workspace data (all tabs) | 11 |
| PATCH | `/warranty/claims/{id}` | WA | Edit claim fields (reason) | 11 |
| POST | `/warranty/claims/{id}/decision` | WA | SUBMIT_TO_OEM / RETURN_FOR_INFO / REJECT_BY_DEALER + rationale → resume | 11 |
| POST | `/warranty/claims/{id}/return-message/draft` | WA | AI draft of return message (admin must approve) | 11 |
| GET | `/review/pending` | SA, WA | Pending interrupts for the actor's role/dealer | 11 |
| GET | `/repair-orders/{id}/audit` | SA, WA | Audit trail for RO + claims | 11 |
| POST | `/admin/knowledge` | AD | Upload + ingest knowledge doc | 5 |
| GET/PUT | `/admin/config/{name}` | AD | Checklists, thresholds (versioned, audited) | 13 |
| GET/POST | `/admin/users` | AD | Manage users | 4 |
| GET | `/admin/audit/verify` | AD | `verify_chain()` result | 4 |
| GET | `/notifications` | all | Own notifications | 11 |
| GET | `/metrics` | internal network only | Prometheus | 13 |

## Error codes

| HTTP | `error.code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Schema / field validation failed |
| 400 | `INVALID_VIN` | VIN format or check digit invalid |
| 400 | `INVALID_DTC` | DTC not `[PBCU][0-9A-F]{4}` |
| 401 | `UNAUTHENTICATED` | Missing / invalid / expired token |
| 403 | `FORBIDDEN_ROLE` | Role not allowed for this action (resource is in scope) |
| 404 | `NOT_FOUND` | Missing **or out of the actor's scope** |
| 409 | `INVALID_TRANSITION` | State machine rejects from→to |
| 409 | `IDEMPOTENCY_CONFLICT` | Same key, different request body |
| 409 | `ODOMETER_REGRESSION` | Booking odometer < last recorded (owner flow) |
| 409 | `SLOT_UNAVAILABLE` | DEMO capacity full |
| 413 | `FILE_TOO_LARGE` | > 10 MB or > 20 pages |
| 415 | `UNSUPPORTED_MEDIA` | Not PDF/JPG/PNG or magic-byte mismatch |
| 422 | `NOT_ESTIMABLE` | Calculator missing input (reason in details) |
| 422 | `RATIONALE_REQUIRED` | Decision/cancel/consent without note |
| 429 | `RATE_LIMITED` | Rate limit hit |
| 502 | `LLM_UNAVAILABLE` | Provider failed after retries (safe fallback message) |
| 503 | `NOT_READY` | Dependency down |
| 500 | `INTERNAL_ERROR` | Unexpected; no internals leaked |
