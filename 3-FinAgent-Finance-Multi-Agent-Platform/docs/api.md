# API

Base URL `http://localhost:8020`. All business routes live under `/api/v1`, use Pydantic request
and response models (camelCase on the wire, mirroring `frontend/types/index.ts`), and require a
Supabase JWT (`Authorization: Bearer …`). Errors return
`{"error": {"code", "message", "requestId"}}` — never a stack trace.

Status: ✅ implemented · ⏳ planned (stage)

## Public (deliberate exceptions)

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/health` | Liveness | ✅ |
| GET | `/health/ready` | Readiness (database) | ✅ |
| GET | `/metrics` | Prometheus | ⏳ 11 |
| GET | `/api/v1/config/public` | Frontend config (Supabase URL + publishable key, demo flag) | ✅ |

## Base-brief endpoints

| Method | Path | Permission (roles) | Status |
|---|---|---|---|
| POST | `/api/v1/chat` | `agents:run` (analyst+) | ✅ |
| POST | `/api/v1/chat/stream` (SSE) | `agents:run` | ✅ |
| POST | `/api/v1/analyze/portfolio` | `agents:run` | ✅ |
| POST | `/api/v1/analyze/risk` | `risk:analyze` | ✅ |
| POST | `/api/v1/analyze/compliance` | `agents:run` | ✅ |
| POST | `/api/v1/analyze/rebalance` | `portfolio:propose` (PM, risk) | ✅ |
| POST | `/api/v1/analyze/fraud` | `fraud:analyze` | ✅ |
| POST | `/api/v1/research` | `agents:run` | ✅ |
| POST | `/api/v1/predict` | `risk:analyze` | ✅ |
| GET | `/api/v1/portfolios`, `/api/v1/portfolio/{id}` | `dashboard:read` (viewer+) | ✅ |
| GET | `/api/v1/risk/{portfolio_id}` | `dashboard:read` | ✅ |
| GET | `/api/v1/audit/{request_id}` | `audit:read` (compliance, admin) | ✅ |
| GET | `/api/v1/me` | any signed-in user | ✅ |

Analysis bodies (camelCase): `{"portfolioId"?, "ticker"?, "transactionId"?, "customerId"?,
"question"?, "conversationId"?}`; the response is `{"requestId", "report", "conversationId"}`.

## Build-spec additions

| Method | Path | Permission | Status |
|---|---|---|---|
| POST | `/api/v1/agents/run` | `agents:run` | ✅ |
| GET | `/api/v1/approvals[?status=]`, `/api/v1/approvals/{id}` | `portfolio:propose` | ✅ |
| POST | `/api/v1/approvals/{id}/decision` `{"approve", "note"?}` | `approvals:decide` (PM, compliance; not the requester) | ✅ |
| POST | `/api/v1/rag/query` `{"question", "k"?, "docTypes"?, "ticker"?, "searchOnly"?}` | `agents:run` | ✅ |
| GET | `/api/v1/documents` | `dashboard:read` (filtered by classification) | ✅ |
| POST | `/api/v1/documents` (multipart: `file`, `docType`, `classification`, `ticker`, `fiscalPeriod`, `effectiveDate`) | `documents:write` | ✅ |
| DELETE | `/api/v1/documents/{id}` | `documents:write` | ✅ |
| GET | `/api/v1/dashboard/overview`, `/compliance`, `/markets`, `/news`, `/agents`, `/activity`, `/ml/models`, `/system/status` | `dashboard:read` | ✅ |
| GET | `/api/v1/dashboard/fraud` | `fraud:analyze` | ✅ |
| GET | `/api/v1/conversations`, `/api/v1/conversations/{id}/messages` | `agents:run` (own only) | ✅ |
| GET | `/.well-known/agent-card/{agent}`, `/a2a/agents`; POST `/a2a/{agent}` | `agents:run` | ✅ |
| GET | `/api/v1/dashboard/fundamentals`, `/notifications`, `/analytics` | — | not implemented (fundamentals are reachable through `/research`) |

## Rate limits

Per user and endpoint group, fixed one-minute windows in Redis (in-process fallback):
`RATE_LIMIT_CHAT` (chat, rag), `RATE_LIMIT_ANALYZE` (analysis, decisions), `RATE_LIMIT_READ`
(dashboards, lists), `RATE_LIMIT_UPLOAD` (documents). Every guarded response carries
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`; over the limit: `429` with
`Retry-After`.

## Streaming events (`/api/v1/chat/stream`)

`start`, `conversation`, `step`, `guard`, `classification`, `plan`, `agent_start`, `agent_end`,
`token`, `approval`, `report`, `error`, `done`. TTFE (first event) and TTFT (first token) are recorded as histograms.
