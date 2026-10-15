# CLAUDE.md - MedInfo Assistant (medical multi-agent RAG)

Safety-first medical **information and research** assistant. Patient safety outranks every other goal:
a refusal or referral is always better than a confident wrong answer. Read `docs/01-PRD.md` first; it is
the source of truth for requirements. Rules in `.claude/rules/` are mandatory.

## Repository map
| Path | What lives there |
|---|---|
| `backend/app/` | FastAPI app. `api/` thin routes, `rag/service.py` use case, `agents/` LangGraph graphs, `safety/` medical safety, `guardrails/` policy engine, `core/` infra, `container.py` composition root |
| `backend/app/rag/providers.py` | The ONLY module that imports provider SDKs (OpenAI-compatible models, Postgres, Redis, Tavily) |
| `backend/app/rag/gateway.py`, `llm_gateway.yaml` | LLM gateway: every model call; task routing (fast/quality), min/max output tokens, input budgets, token metrics |
| `backend/app/rag/cache.py` | Answer cache, LLM prompt cache, query-embedding cache |
| `.claude/rules/` | Mandatory rules: medical-safety, data-and-secrets, engineering, documentation, llm-gateway-and-cost |
| `.claude/skills/`, `.claude/agents/` | Skills (run-safety-suite, add-trusted-source, release-checklist, live-verification); agents (safety-reviewer, docs-sync, test-runner) |
| `backend/tests/`, `backend/tests/safety/` | Offline tests with fakes; `-m safety` is the release-blocking suite |
| `backend/evals/` | Golden set, safety suite YAML, `run_eval.py` (MLflow, separate `.venv-eval`) |
| `backend/data/synthetic/` | SYNTHETIC corpus + uploads (fictional drugs/patients) |
| `frontend/src/` | Plain HTML/CSS/JS UI (no build step, strict CSP, text nodes only) |
| `frontend/tests/` | Playwright browser tests (installed Edge) + screenshot generator |
| `tests/integration/` | Cross-service tests against a running compose stack |
| `compose.yaml`, `deploy/k8s/`, `infra/terraform/`, `monitoring/` | Delivery and operations |
| `docs/` | PRD, HLD, architecture, LLD, designs, API, data model, security, tests, Docker, AWS, ADRs |
| `presentation/index.html`, `narrative.md` | Stakeholder deck and project story |

## Commands (Windows, from the repo root)
```powershell
cd backend; ..\.venv\Scripts\python -m pytest -q            # all backend tests (offline)
cd backend; ..\.venv\Scripts\python -m pytest -m safety -q  # release-blocking safety suite
cd backend; ..\.venv\Scripts\ruff check .; ..\.venv\Scripts\ruff format --check .
cd frontend; npm run lint; npm test                          # ESLint + Playwright (installed Edge)
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --port 8030 --workers 1   # local dev (serves frontend/src too)
docker compose up --build                                    # frontend http://127.0.0.1:8080
```
Check that ports are free first (8000/8010/8020 are used by other projects on this machine).

## Non-negotiables (see `.claude/rules/`)
- Never diagnose; never prescribe/choose a medicine/change a dose. Doses only as verbatim cited quotes.
- Every medical statement grounded in a cited passage; otherwise "not covered". Never answer from model memory.
- Urgent-symptom triage runs first on every question; the emergency notice is built in code, never by the model.
- Safety cannot be disabled by request parameters. Only ops config tunes thresholds.
- Synthetic data only. Secrets only via env (`SecretStr`). Never commit `.env`.
- Tell the user the approximate number of live model calls before spending quota.
- Every model call goes through the LLM gateway (`gateway.for_task`); routing and token limits live in
  `llm_gateway.yaml`; token limits never weaken safety (see `.claude/rules/llm-gateway-and-cost.md`).
- Never `terraform apply`, push images or create cloud resources without explicit approval.
- Never claim clinical validation, accuracy or regulatory status. Label evaluation numbers as synthetic offline.
- Keep docs, presentation and narrative in sync with what is implemented vs planned.
