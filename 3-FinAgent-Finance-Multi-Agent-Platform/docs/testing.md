# Testing

```bash
uv run pytest                      # offline suite (never reads .env, never calls the network)
uv run pytest -m live              # opt-in live checks; each stage states call count first
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Layout

| Folder | What |
|---|---|
| `tests/architecture/` | Layering, provider/SQL isolation, auth on every route, encoding, secret scan |
| `tests/unit/` | Pure services, settings, errors, tool validation, chunkers, guardrails |
| `tests/integration/` | Repositories against a database (skipped without `TEST_DATABASE_URL`) |
| `tests/agents/` | Each agent with fake LLM + fake MCP: required tools, fallback plan, confidence |
| `tests/a2a/` | Envelope validation, timeout, retry/backoff, error mapping, authorization |
| `tests/mcp/` | Server ↔ client round trips (in-memory), RBAC denial, malformed output |
| `tests/rag/` | Loaders, chunking, upsert idempotency, fusion, golden evidence verbatim |
| `tests/ml/` | Feature pipeline, training on small samples, output schema, reason codes |
| `tests/api/` | Routes, auth, rate limits, error envelope, SSE events |
| `tests/security/` | JWT verification, RBAC matrix, PII redaction, injection attacks |
| `tests/e2e/` | Full graph with fakes: the eight sample use cases |

## Required scenarios (base brief §39 + Build spec)

Valid/invalid requests · agent failure · MCP failure · A2A failure · timeouts · retries ·
malformed tool output · hallucination protection (ungrounded numbers) · unauthorized access ·
PII leakage · model failure · all LLMs down · prompt injection (6+ types) · no false positives on
financial values · limit-breach anchor · VaR value · rebalance quantities · interrupt and resume.

## Rules

- Offline by default: fakes for LLMs, MCP, Redis, providers. `FINAGENT_TESTING=1` stops settings
  from reading `.env`.
- Live tests carry `@pytest.mark.live` and are excluded unless asked for.
- Frontend: `tsc --noEmit`, `eslint`, Playwright smoke/responsive/streaming tests (Stage 9).
