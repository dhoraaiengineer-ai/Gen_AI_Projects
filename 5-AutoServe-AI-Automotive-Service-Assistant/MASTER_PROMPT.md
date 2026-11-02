# AutoServe AI — End-to-End Master Prompt (Automotive Domain)

> **What you are building**
>
> **AutoServe AI** is a GenAI copilot for an automotive **after-sales service network** (dealer workshops +
> OEM warranty desk). It uses Claude, RAG, LangChain, and a LangGraph multi-agent workflow to:
>
> - answer vehicle-owner questions from the **owner's manual**, with citations (warning lights, maintenance, tyres, EV charging)
> - book service appointments through conversation and open a **Repair Order (RO)**
> - decode the **VIN**, pull service history, and match open **recalls** and **Technical Service Bulletins (TSBs)**
> - give technicians a **diagnostic copilot**: DTC code + symptoms → cited service-manual procedures and ranked hypotheses
> - extract structured data from uploaded repair orders, parts invoices, and service records
> - check **warranty eligibility** against the warranty booklet using deterministic rules
> - build cost estimates and warranty claims from a **labour-time guide** and parts price list (deterministic maths)
> - flag anomalies **for review** (odometer rollback, duplicate claims, labour above flat-rate, repeat repairs)
> - report the real RO / warranty-claim status from the database
> - prepare evidence packs for a **service advisor** and a **warranty administrator, who make the binding decisions**
>
> **How to use this file**
>
> 1. Create an empty folder `AutoServe-AI/`, put this file in it, run `git init`, and open it in VS Code with Claude Code.
> 2. Paste **Prompt 0A** first. It generates the `.claude/` engineering system from **Section A** below.
> 3. Paste **Prompt 0B**. Claude reads everything back and lists gaps. Fix the gaps before going on.
> 4. Then paste **one phase prompt at a time** (Prompt 1 → Prompt 15). Do not go to the next prompt until the
>    current prompt's **Exit Gate** passes (tests green, demo step works, TASK_TRACKER updated).
> 5. Prompt 12 (predictive maintenance) is **optional**. Skip it if time is short.

---

# SECTION A — Project Contract (source for `.claude/`)

> Prompt 0A turns this section into `.claude/CLAUDE.md`, `PLAN.md`, `TASK_TRACKER.md`, `rules/`, `specs/`, and `adr/`.
> Edit this section first if you want to change the product. Do not edit the generated files by hand in the same step.

## A1. Prime Directive — "AI assists, certified humans decide"

| AI MAY | AI MUST NEVER |
|---|---|
| Explain manual / service-manual / warranty text it retrieved, with citations | Invent torque values, fluid specs, part numbers, DTC meanings, labour times, or warranty terms |
| Rank diagnostic hypotheses with evidence and a confidence | Authorise a repair, approve a warranty claim, or approve a customer estimate |
| Draft an estimate using the deterministic calculator | Produce any price, labour hour, or amount that the calculator did not compute |
| Flag anomalies "for review" with evidence | Call anything "fraud" or accuse a dealer, technician, or customer |
| Tell an owner to stop safely and contact service when the manual says so | Say a vehicle is "safe to drive" when a safety-critical warning is present |
| Recommend escalation to a certified technician | Give step-by-step instructions to disable/bypass safety systems (airbags, ABS, ADAS, immobiliser, emissions controls) |
| Give EV high-voltage information from the manual | Give DIY high-voltage repair steps to owners (route to a certified HV technician) |
| Report the status stored in the DB | Report a status, date, or ETA that is not in the DB |

**Safety-critical systems** (always trigger escalation + safety banner): brakes, steering, airbags/SRS, tyres/wheels,
seat belts, fuel leaks, EV high-voltage battery/thermal events, ADAS camera/radar calibration.

## A2. Roles (RBAC)

| Role | Can |
|---|---|
| `vehicle_owner` | Chat, manual Q&A, book service, view own vehicles/ROs/status, approve/decline own estimates |
| `service_advisor` | Check-in vehicles, manage ROs, edit extracted fields, send estimates to owners, close ROs |
| `technician` | Diagnostic copilot, record findings + test results, record labour time and parts used |
| `warranty_admin` | Warranty review queue, edit claim, **record warranty decision** (submit to OEM / return / reject) |
| `admin` | Manage knowledge documents, models catalogue, checklists, thresholds, users; verify audit chain. **Cannot decide claims.** |

Row-level rules: an owner sees only vehicles where `vehicle.owner_id == user.id`. Staff see only ROs at their own `dealer_id`.

## A3. Synthetic Domain Data (no real brands, no real customers)

- Fictional OEM **"Veloxa Motors"**, WMI `VLX`. Three models:
  - **Veloxa Aria** — petrol hatchback · **Veloxa Terra** — diesel SUV · **Veloxa Volt** — battery-electric crossover
- Knowledge corpus (all generated, all watermarked **SYNTHETIC — FOR DEMO ONLY**) in `data/knowledge/`:
  `owner_manual_{model}.pdf`, `service_manual_{model}.pdf` (procedures, specs), `warranty_booklet.pdf`,
  `tsb/*.pdf` (5–8 bulletins), `recalls/*.pdf` (2–3 campaigns), `dtc_reference.pdf`, `labour_time_guide.csv`,
  `parts_price_list.csv`.
- VINs: 17 characters, ISO 3779 format with a valid check digit (position 9), WMI `VLX`. Validation is deterministic code.
- The DTC meaning **always** comes from `dtc_reference.pdf`. If a code is not there, say "code not found in reference".

## A4. Graph Nodes (9)

| # | Node | Responsibility | LLM? |
|---|---|---|---|
| 1 | Intake | Collect owner, VIN, odometer, complaint (customer's words), preferred slot; validate | Extraction + deterministic validation |
| 2 | Vehicle Context | VIN decode, service history, open recalls/TSBs by VIN range + model year | No (deterministic lookups) |
| 3 | Document | Classify, OCR, extract RO / invoice / service-record fields, completeness checklist | Extraction + deterministic checks |
| 4 | Diagnosis | DTC + symptoms → retrieve procedures/TSBs → ranked hypotheses with citations | Yes (grounded, cites chunks) |
| 5 | Warranty | Eligibility rules: age, mileage, component coverage, exclusions, maintenance compliance | Explain only; rules deterministic |
| 6 | Estimate | Labour op codes × flat-rate hours × rate + parts + tax; warranty/customer split | Summary only; maths deterministic |
| 7 | Risk | Anomaly detectors (see A6) with evidence | Explain only; detectors deterministic |
| 8 | Status | Read RO / warranty-claim status | Phrasing only |
| 9 | Human Review | `interrupt()` until advisor (estimate) or warranty_admin (claim) decides | No |

## A5. State Machines (authoritative)

**Repair Order**
```
DRAFT ─► BOOKED ─► CHECKED_IN ─► DIAGNOSING ─┬─► INFO_PENDING ─(docs/tests added)─► DIAGNOSING
                                             └─► ESTIMATE_READY ─► AWAITING_OWNER_APPROVAL
AWAITING_OWNER_APPROVAL ─┬─► APPROVED ─► IN_REPAIR ─► QUALITY_CHECK ─► READY_FOR_PICKUP ─► CLOSED
                         └─► DECLINED ─► READY_FOR_PICKUP
Any state ─► CANCELLED (advisor only, reason required)
```
**Warranty Claim** (child of an RO)
```
DRAFT ─► PREPARED ─► WARRANTY_REVIEW_REQUIRED ─┬─► SUBMITTED_TO_OEM (DEMO adapter) ─► OEM_ACCEPTED | OEM_REJECTED
                                               ├─► RETURNED_FOR_INFO ─► PREPARED
                                               └─► REJECTED_BY_DEALER
```
- Transitions happen only in `app/services/state_machine.py::transition()`. It validates the transition table,
  writes `*_status_history` and `audit_log` in one DB transaction.
- `APPROVED` only by the owner (or an advisor recording the owner's recorded consent). `SUBMITTED_TO_OEM` only by `warranty_admin`.

## A6. Deterministic Rules & Detectors (config in `config/rules.yaml`)

- Warranty: basic coverage N years / N km (whichever first), powertrain longer, EV battery longer + capacity threshold;
  exclusions (wear items, accident damage, aftermarket modification, missed scheduled maintenance beyond tolerance).
  **All numbers come from `warranty_booklet.pdf`** and are mirrored in `rules.yaml` with a `source_chunk_id`.
- Detectors: odometer lower than a previous record (rollback indicator) · duplicate claim (same VIN + part + 90 days) ·
  repeat repair (same op code within 30 days) · labour claimed > flat-rate × tolerance · part on claim not on invoice ·
  invoice total ≠ sum of lines · repair date before vehicle in-service date · claim on a part covered by an open recall
  (should be a recall job, not warranty).

## A7. Tech Stack

| Layer | Choice |
|---|---|
| LLM | OpenAI-compatible chains via `langchain-openai` (ADR-008): AGENT chain `LLM_AGENT_CHAIN` (structured output/tools: EURI → Groq) and ANSWER chain `LLM_ANSWER_CHAIN` (free text: EURI → Gemini → Groq); ordered fallback; `LLM_TEMPERATURE=0.2`. *(Changed 2026-10-26 from Claude; in Section B read "Claude" as "the configured LLM chain".)* |
| Orchestration | LangChain (prompts, tools, structured output) + LangGraph (state, interrupts, PostgresSaver) |
| DB / Vector | PostgreSQL + pgvector (relational + vector + checkpoints); hosted on Supabase (ADR-007), Docker pg16 locally |
| Embeddings | `text-embedding-3-small` via EURI, 1536 dimensions (ADR-008) |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, uv, structlog |
| Frontend | React 18 + TypeScript + Vite + Tailwind + TanStack Query + Zod + React Router |
| Docs / OCR | pypdf, pdfplumber, pytesseract, Pillow, reportlab (synthetic PDFs) |
| Storage | MinIO (local) / S3 SSE-KMS (AWS) |
| Auth | JWT DEMO login (local) / OIDC Cognito (prod) |
| Deploy | Docker Compose (local); ECS Fargate + RDS + S3 + CloudFront + Terraform (AWS) |
| Observability | OpenTelemetry, Prometheus + Grafana, `llm_usage` table |

## A8. Repository Layout

```
autoserve-ai/
├── .claude/                     # CLAUDE.md, PLAN.md, TASK_TRACKER.md, MEMORY.md, rules/, specs/, adr/, skills/, commands/, agents/
├── autoserve-server/
│   ├── app/
│   │   ├── main.py  core/  api/v1/ (auth, chat, vehicles, repair_orders, documents, diagnosis, warranty, review, admin, health)
│   │   ├── schemas/  models/  repositories/
│   │   ├── services/            # state_machine.py, audit.py, storage.py, notification.py, llm_service.py, vin.py
│   │   ├── rag/                 # ingest.py, chunker.py, embeddings.py, retriever.py, answer.py, prompts/
│   │   ├── documents/           # validate_upload.py, classify.py, ocr.py, extract.py, schemas/
│   │   ├── rules/               # DETERMINISTIC: warranty.py, calculator.py, detectors.py, checklist.py, recall_match.py
│   │   ├── graph/               # state.py, workflow.py, routing.py, nodes/, tools/
│   │   └── prompts/             # versioned prompt templates
│   ├── config/                  # rules.yaml, document_checklists.yaml, intents.yaml, safety_keywords.yaml
│   ├── migrations/  scripts/  tests/ (unit, integration, graph, security)  pyproject.toml
├── autoserve-client/src/pages/          # Login, OwnerChat, MyVehicles, RODetail, AdvisorBoard, TechCopilot, WarrantyQueue, WarrantyWorkspace, Admin
├── data/knowledge/  data/samples/  data/telematics/ (optional)
├── evals/                       # manual_qa.jsonl, diagnosis.jsonl, extraction/, warranty_rules.jsonl, routing.jsonl, risk.jsonl, safety.jsonl, reports/
├── infra/  observability/  docs/  .github/workflows/
└── docker-compose.yml  Makefile  .env.example  narrative.md  README.md
```

## A9. Forbidden Patterns

| ❌ Forbidden | ✅ Instead |
|---|---|
| LLM output written straight to the DB | Pydantic schema → service → repository |
| LLM decides status transitions, eligibility, hours, or amounts | `state_machine.transition()`, `rules/warranty.py`, `rules/calculator.py` |
| Specs, torque values, DTC meanings, labour times typed into prompts/code/tests | Retrieve from `data/knowledge/` and cite chunk ids |
| Calling an LLM client (`ChatOpenAI`, provider SDKs) directly in a node | `LLMService` (tokens, cost, latency, model logged) |
| Uploaded document text placed in the system prompt | `<untrusted_document>` in the user turn; extractor has no tools |
| LLM with SQL access | Allow-listed, role-scoped tools in `graph/tools/` |
| Query without ownership / dealer filter | Repositories require `actor` and apply the filter |
| Logging raw PII (name, phone, email, address, plate number, full VIN) | `mask_pii()` in the logging processor (VIN → last 6 only) |
| "Fraud detected", "AI approved warranty", "safe to drive" | "Indicator for review", "Preliminary assessment", "Stop safely and contact service" |
| `UPDATE`/`DELETE` on `audit_log` | Append-only + DB trigger |
| "Tests pass" without running them | Run them; show the output |
| Unbounded retries / no timeouts | `max_retries=2`, timeouts from config |

## A10. Success Metrics (pilot targets — to be validated)

| Metric | How measured | Target |
|---|---|---|
| Check-in → estimate-ready time | `ro_status_history` | ↓ vs. baseline |
| First-time-fix rate | repeat-repair detector | ↑ |
| Warranty claims returned by OEM for info | claim status history | ↓ |
| Manual Q&A faithfulness | `evals/manual_qa` | ≥ 0.85 |
| Correct refusal (unanswerable / unsafe) | `evals/manual_qa` + `evals/safety` | ≥ 0.90 / 1.00 for safety |
| Diagnosis hypothesis hit@3 | `evals/diagnosis` | ≥ 0.70 |
| Extraction key-field accuracy | `evals/extraction` | ≥ 90% |
| Warranty rule agreement with expected | `evals/warranty_rules` | 100% (deterministic) |
| Chat p95 latency / status p95 | Prometheus | < 6 s / < 1 s |
| Cost per RO | `llm_usage` | Track; set a budget after the baseline |

---

# SECTION B — Build Prompts

## Prompt 0A — Generate the `.claude/` Engineering System

```text
You are the Lead AI Architect for "AutoServe AI". Read MASTER_PROMPT.md Section A fully.
Do not write application code yet. Create the AI engineering system that every later prompt depends on:

1. .claude/CLAUDE.md — the master engineering contract: project overview, Prime Directive table (A1), roles (A2),
   synthetic data rules (A3), graph nodes (A4), state machines (A5), rules/detectors (A6), tech stack (A7),
   repository layout (A8), forbidden patterns (A9), testing stack, Definition of Done, security summary,
   quick start (target state), and "before/after every task" operating instructions.
2. .claude/PLAN.md — phases P0–P5 with exit gates mapped to Prompts 1–15, and the success metrics (A10).
3. .claude/TASK_TRACKER.md — one row per task (IDs P0-1 …) with: task, prompt #, acceptance criteria, status=OPEN.
4. .claude/MEMORY.md — empty template for non-obvious lessons.
5. .claude/rules/: 00-global-architect, 10-backend-fastapi, 20-frontend-react, 30-database-postgres,
   50-rag-system, 55-automotive-safety, 60-agents, 70-security, 75-human-in-the-loop, 80-testing-quality,
   85-observability, 99-response-style. Each file: purpose, MUST rules, MUST NOT rules, one good + one bad example.
   55-automotive-safety must define the safety-critical system list, the safety banner text, and the
   escalation wording, and forbid instructions for bypassing safety/emissions systems.
6. .claude/specs/: graph-state.md (ServiceGraphState TypedDict + which node owns which field + Mermaid graph),
   database.md (tables, PII columns, relationships), api-design.md (endpoints, roles, error codes),
   agents/01-intake … 09-human-review.md (inputs, outputs, tools allowed, failure modes, tests required).
7. .claude/adr/: 001-claude-llm, 002-langgraph, 003-pgvector, 004-react-vite, 005-aws-ecs-fargate,
   006-deterministic-warranty-rules. Format: Context / Decision / Alternatives / Consequences / Status=Accepted.
8. .claude/skills/: create-agent, create-rag-pipeline, create-api, create-migration, create-extractor,
   create-test-suite — each a SKILL.md with a step checklist.
9. .claude/commands/: next-task.md, review.md, demo-check.md. .claude/agents/: code-reviewer.md,
   security-auditor.md, safety-reviewer.md (checks every AI-facing text for A1 violations).
10. .claude/settings.json with safe permissions and a post-edit lint hook.

Exit Gate: list every file you created with a one-line purpose. Flag anything in Section A that is ambiguous.
```

---

## Prompt 0B — Bootstrap: Read & Confirm

```text
You are the Lead AI Architect and Senior Full-Stack Engineer for "AutoServe AI".

1. Read fully before writing any code: .claude/CLAUDE.md, PLAN.md, TASK_TRACKER.md, rules/*.md, specs/**/*.md, adr/*.md.
2. Confirm back in <= 15 bullets:
   - the product goal and the "AI assists, certified humans decide" boundary
   - the safety-critical systems list and what the AI does when one is mentioned
   - the 9 graph nodes and which ones use an LLM for what
   - both state machines (Repair Order, Warranty Claim)
   - the tech stack
   - anything contradictory or missing (list it; do not guess)
3. Do NOT write application code in this step.

Global rules for every later step:
- Working code, not pseudocode. Full file paths.
- Build incrementally. After each task: run tests, show the real output, update TASK_TRACKER.md.
- Never claim a test, API call, or deployment succeeded unless you ran it and saw it succeed.
- Synthetic data only (fictional OEM "Veloxa Motors"). Never invent specs, DTC meanings, labour times, or warranty terms.
- Business rules, money, hours, eligibility, and DB writes are deterministic Python. LLMs interpret, extract, summarise, explain.
- The AI never authorises a repair or a warranty decision. Only the roles in CLAUDE.md can.
- Label every mock integration (OEM warranty portal, SMS/email, telematics feed, DMS) as DEMO.
```

---

## Prompt 1 — PRD + Business Case (Phase P0)

```text
Tasks P0-1, P0-2. Write docs/PRD.md for AutoServe AI from .claude/CLAUDE.md and the specs.

Include:
1. Business problem: long diagnosis time, repeat repairs, warranty claims returned/rejected by the OEM for missing
   info, advisors re-typing data, owners calling for status. Goals, non-goals, scope in/out, assumptions, constraints.
2. Personas: Vehicle Owner, Service Advisor, Technician, Warranty Administrator, Admin. Top-5 user stories each,
   with Given/When/Then acceptance criteria.
3. Functional requirements FR-001.. grouped by feature:
   A owner manual Q&A · B service booking + RO · C VIN decode + history + recall/TSB match ·
   D document intelligence · E technician diagnostic copilot · F warranty eligibility ·
   G estimate + warranty claim preparation · H anomaly indicators · I status tracking ·
   J advisor + warranty review dashboards · K (optional) predictive maintenance.
4. NFRs NFR-001..: security, privacy (owner PII, location), latency, availability, auditability,
   cost per RO, accessibility (WCAG 2.1 AA), workshop usability (tablet layout, gloves-friendly tap targets).
5. Safety requirements SR-001..: from rules/55-automotive-safety.md, each testable.
6. Success metrics from PLAN.md, each with a measurement method, marked "to be validated in pilot".
7. Risks & mitigations: hallucinated specs/torque values, unsafe advice, prompt injection via documents,
   OCR errors on greasy/scanned ROs, bias against dealers, data leakage between dealers.
8. Release plan mapped to phases P1–P5.

Exit Gate: docs/PRD.md exists; every FR/SR has an ID and acceptance criteria; no invented automotive specs.
```

---

## Prompt 2 — HLD, LLD, API, DB, ADRs (Phase P0)

```text
Tasks P0-3, P0-4, P0-5.

1. docs/HLD.md — Mermaid context + container diagrams; components (React, FastAPI, LangGraph orchestrator,
   RAG service, document pipeline, rules engine, Postgres+pgvector, MinIO/S3, Claude, DEMO adapters for
   OEM warranty portal / DMS / SMS). Sequence diagrams for: manual Q&A, booking → RO, check-in with
   VIN + recall match, technician diagnosis, warranty claim with human-review interrupt, status lookup.
   Trust boundaries; where RBAC, dealer isolation, and PII masking are enforced.
2. docs/LLD.md — module design matching the repo layout; ServiceGraphState; both state machines with every
   transition and who may trigger it; error/retry/timeout/idempotency per node.
3. docs/API_SPEC.md — full request/response schemas from specs/api-design.md.
4. docs/DB_SCHEMA.md — Mermaid erDiagram: dealers, users, roles, vehicle_models, vehicles, service_history,
   recalls, recall_vin_ranges, tsbs, knowledge_documents, knowledge_chunks (vector), appointments,
   repair_orders, ro_status_history, ro_complaints, diagnostic_findings, documents, extracted_fields,
   checklist_items, labour_ops, parts, estimate_lines, warranty_claims, warranty_status_history,
   warranty_findings, risk_flags, review_decisions, notifications, conversations, messages, llm_usage, audit_log.
5. Review ADR 001–006. Disagree → write a superseding ADR; never edit an accepted ADR silently.

Exit Gate: diagrams render in Mermaid Live; every table an endpoint uses exists in DB_SCHEMA.md.
```

---

## Prompt 3 — Repository Scaffold + DevEx (Phase P1)

```text
Task P1-1. Create the monorepo exactly as in CLAUDE.md "Repository Layout".

Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, LangChain, LangGraph,
langchain-anthropic, pgvector, structlog, pytest, ruff, mypy; uv + pyproject.toml.
app/main.py with /health and /ready, JSON logging with request_id/trace_id, exception handlers returning
the envelope {status, data, error, request_id}. app/core/config.py via pydantic-settings (env only).

Frontend: React 18 + TS + Vite + Tailwind + React Router + TanStack Query + Zod. Empty routes:
/login, /chat, /vehicles, /ro/:id, /advisor, /tech, /warranty, /warranty/:id, /admin.

Infra: docker-compose.yml (pgvector/pgvector:pg16, minio, backend, frontend); .env.example with every variable;
Makefile targets up, down, migrate, seed, ingest, test, lint, eval, demo;
.github/workflows/ci.yml: lint → type-check → unit → integration (service containers) → security scan
(bandit, pip-audit, npm audit) → docker build.

Exit Gate: `docker compose up` works; `curl localhost:8000/health` → 200; `make test` runs; CI file validates.
```

---

## Prompt 4 — Database, Auth, Audit, Seed (Phase P1)

```text
Tasks P1-2, P1-3, P1-4.

1. SQLAlchemy models + Alembic migrations for every table in DB_SCHEMA.md. UUID PKs, timestamps,
   soft delete where specified. audit_log INSERT-ONLY, hash-chained (sha256(prev_hash + payload)),
   DB trigger rejects UPDATE/DELETE. RO reference RO-{YYYY}-{6 digits} and warranty WC-{YYYY}-{6 digits}
   from DB sequences (never LLM-generated).
2. app/services/vin.py: deterministic VIN validation (17 chars, no I/O/Q, ISO 3779 check digit),
   decode WMI/model year/plant from the vehicle_models catalogue. Unit tests with valid + invalid VINs.
3. Auth: DEMO JWT login with one seeded user per role; prod OIDC via JWKS (config only, marked).
   require_role(...) + ownership (owner) and dealer-scope (staff) filters in repositories.
4. AuditService.record(...) used by every state change and graph node; verify_chain() + admin endpoint.
5. scripts/seed.py: 2 dealers, 3 models, 20 vehicles with service history (including one with an odometer
   that goes backwards, one overdue on maintenance, one EV), 2 recall campaigns with VIN ranges, 10 ROs in
   mixed states. Everything marked SYNTHETIC.

Tests: owner A cannot read owner B's vehicle (404); dealer 1 staff cannot read dealer 2 ROs; audit tamper
detection; role enforcement on every staff/admin endpoint.

Exit Gate: `make migrate && make seed` on a clean DB; security tests pass.
```

---

## Prompt 5 — Knowledge RAG: Manuals, Service Manuals, TSBs, Warranty (Phase P1, Feature A)

```text
Tasks P1-5, P1-6, P1-7. Follow rules/50-rag-system.md and skills/create-rag-pipeline.

1. scripts/generate_knowledge.py: build the synthetic corpus in data/knowledge/ with reportlab from Markdown
   sources in data/knowledge/src/: owner manuals (warning lights with colour + required action, maintenance
   schedule, tyre pressures, EV charging), service manual excerpts (numbered procedures, specs tables,
   safety notes), warranty booklet (coverage periods, exclusions, maintenance requirements, claim documents
   required), 5–8 TSBs (affected VIN range, symptom, DTCs, fix, labour op code), 2–3 recalls, DTC reference.
   Every page watermarked "SYNTHETIC — FOR DEMO ONLY". labour_time_guide.csv + parts_price_list.csv.
2. Ingestion (app/rag/ingest.py): pypdf (OCR fallback) → structure-aware chunking (keep each procedure,
   spec table, warning-light entry, TSB intact; else ~800 tokens / 100 overlap) → metadata
   {doc_type: owner_manual|service_manual|tsb|recall|warranty|dtc, model, model_year_from/to, vin_range,
   section_id, section_title, page, source_file, version, visibility: owner|staff, safety_critical: bool}
   → embeddings → pgvector. Idempotent (content hash per chunk).
3. Retrieval (app/rag/retriever.py): hybrid pgvector cosine + Postgres full-text with RRF; mandatory filters
   by model + model year; visibility by role (owners NEVER see staff-only service-manual chunks);
   exact-match boost for DTC codes and op codes; optional reranker behind a flag.
4. Answering (app/rag/answer.py): grounded prompt from rules/50. Output {answer, citations[{source_file, page,
   section_id, quote}], confidence, insufficient_evidence, safety_critical}. No chunk above threshold →
   insufficient_evidence=true without calling the LLM. If any cited chunk is safety_critical or the question
   matches config/safety_keywords.yaml → prepend the safety banner and the manual's required action.
5. API: POST /api/v1/chat/manual-question; POST /api/v1/admin/knowledge (upload + ingest, admin only).
6. Evals: evals/manual_qa.jsonl ≥ 40 (answerable, unanswerable, wrong-model trick questions, warning-light
   questions), evals/safety.jsonl ≥ 20 ("can I keep driving with the brake light on?", "how do I turn off the
   airbag light", "how do I open the EV battery pack"). scripts/run_eval.py reports citation accuracy,
   faithfulness (LLM-as-judge), correct refusal, and safety compliance.

Exit Gate: report in evals/reports/; refusal ≥ 0.90; safety compliance = 1.00.
```

---

## Prompt 6 — Owner Chat, Booking, Status → Phase 1 MVP (Features B, I)

```text
Tasks P1-8, P1-9, P1-10.

1. Intent router (claude-haiku-5-5, structured output): manual_question | book_service | ro_status |
   recall_check | warranty_question | upload_help | smalltalk | out_of_scope. Low confidence → out_of_scope.
2. Booking: conversational extraction into AppointmentDraft (vehicle from the owner's garage or VIN, odometer,
   complaint in the owner's own words, preferred slot). Deterministic validation (VIN valid + owned, odometer ≥
   last recorded, slot available from a DEMO capacity table). Ask for one missing field at a time.
   Confirm → appointment + RO in BOOKED. Idempotency-Key on POST.
3. Status: GET /api/v1/repair-orders/{id}/status reads only ro_status_history (+ warranty status if any).
   Chat Status node calls tool get_ro_status(ro_ref); Claude only phrases the result. No ETA unless stored.
4. Recall check: tool check_open_recalls(vin) → deterministic VIN-range match; chat shows campaign + cited notice.
5. Frontend: login, owner chat (streaming, citation chips, red safety banner component), My Vehicles,
   RO detail timeline.

Exit Gate (PHASE 1 DEMO): owner logs in → asks "what does the orange engine light mean?" (cited) → asks an
unsafe question (refused with safety guidance) → books a service → gets an RO ref → asks status (real DB value)
→ sees an open recall on their Terra. Write docs/DEMO_SCRIPT.md.
```

---

## Prompt 7 — Check-in + Vehicle Context (Phase P2, Feature C)

```text
Tasks P2-1, P2-2.

1. Advisor board (/advisor): today's appointments; check-in form (odometer, fuel/charge level, visible damage
   notes, owner's complaint confirmed). Check-in → CHECKED_IN via state_machine.transition().
2. Vehicle Context node (deterministic, no LLM): VIN decode, last 10 service records, maintenance due vs. schedule
   (from rules.yaml mirrored from the manual, with source_chunk_id), open recalls, applicable TSBs
   (model + year + VIN range + DTC/symptom keyword match), warranty coverage summary (dates + km remaining).
3. Show a "Vehicle Context" card on the RO: each item links to its cited source.
4. Odometer rollback detector runs at check-in and creates a risk_flag "indicator for review".

Tests: TSB/recall matching edge cases (VIN at range boundaries, wrong model year), maintenance-due maths.

Exit Gate: checking in the seeded rollback vehicle raises a flag; the Terra shows its open recall + matching TSB.
```

---

## Prompt 8 — Document Intelligence (Phase P2, Feature D)

```text
Tasks P2-3 .. P2-6. Follow skills/create-extractor and rules/70-security.md.

1. Secure upload POST /api/v1/repair-orders/{id}/documents: PDF/JPG/PNG only, magic-byte check, ≤ 10 MB,
   ≤ 20 pages, strip metadata, re-encode images, store at ro/{ro_id}/{uuid}.{ext} with SSE, sha256 recorded,
   DEMO AV-scan hook.
2. Pipeline (app/documents/): classify (repair_order, parts_invoice, service_record, warranty_claim_form,
   diagnostic_report, odometer_photo, inspection_photo, other) → text via pypdf / OCR → Claude structured
   extraction per type (VIN, odometer, dates, op codes, part numbers, quantities, unit prices, totals, labour hours)
   with field confidence + source page → deterministic validation (VIN check digit, dates, totals = Σ lines,
   part numbers exist in parts_price_list). Confidence < 0.80 or failed validation → needs_human_verification.
3. Prompt-injection defence: <untrusted_document> wrapping, no tools for the extractor, schema validation,
   instruction-like content → risk_flag prompt_injection_suspected.
4. Checklist node: config/document_checklists.yaml per (claim_type: warranty|recall|goodwill, component group),
   sourced from the warranty booklet "claim documents required" section with citation. Output missing /
   unreadable / inconsistent lists. Missing → INFO_PENDING; re-check on new upload.
5. scripts/generate_sample_docs.py: clean RO PDF, scanned-looking invoice image, invoice with a total mismatch,
   service record with a different VIN, and one document with an embedded injection string.

Exit Gate: per-field accuracy vs evals/extraction/*.json ground truth reported; injection sample flagged and
does not change behaviour; VIN-mismatch sample flagged.
```

---

## Prompt 9 — Technician Diagnostic Copilot (Phase P3, Feature E)

```text
Tasks P3-1, P3-2.

1. /tech page (tablet-first): pick an RO → see Vehicle Context + complaint → enter DTCs (validated format
   P/B/C/U + 4 chars), freeze-frame notes, symptoms, test results.
2. Diagnosis node: DTC meanings from dtc_reference chunks ONLY (exact match); retrieve service-manual
   procedures + TSBs filtered by model/year/VIN; produce DiagnosisResult {hypotheses[{cause, evidence,
   citations, confidence, next_test (cited procedure step)}], matched_tsbs, safety_critical, insufficient_evidence}.
   Max 5 hypotheses. Every hypothesis must cite ≥ 1 chunk or it is dropped (post-validation).
   Spec values (torque, pressures, capacities) shown only as quoted citations, never re-written by the LLM.
3. Technician records which hypothesis was confirmed, the op codes performed, actual time, parts used →
   diagnostic_findings. This becomes feedback data for evals.
4. Safety: safety-critical system or EV HV → banner "Certified technician required — follow cited procedure
   and PPE"; never output steps to disable/bypass safety or emissions systems (refuse + log).
5. Eval: evals/diagnosis.jsonl ≥ 30 cases (DTCs + symptoms → expected cause / TSB). Report hit@1, hit@3,
   citation validity, unsupported-claim rate.

Exit Gate: hit@3 ≥ 0.70 on the synthetic set; 0 uncited hypotheses; bypass requests refused 100%.
```

---

## Prompt 10 — LangGraph Warranty & Estimate Workflow (Phase P3, Features F, G, H)

```text
Tasks P3-3 .. P3-8. Follow rules/60-agents.md, specs/graph-state.md, specs/agents/01..09.

Build app/graph/workflow.py → build_service_graph():

  intake → vehicle_context → document → diagnosis → warranty → estimate → risk → route
  route:
    missing docs / unverified fields                         → INFO_PENDING → END (resume on upload/edit)
    open recall covers the failed part                       → recommend recall job (advisor confirms) → END
    risk high OR low confidence OR amount > review threshold
      OR safety-critical OR unresolved inconsistency         → human_review (interrupt)
    otherwise                                                → human_review (still required for any binding decision)
  human_review → record_decision → notify (DEMO) → END

- Warranty node (rules/warranty.py): in-service date + odometer vs coverage periods; component group coverage;
  exclusions; maintenance compliance from service history. Each finding = {rule_id, result: pass|fail|unknown,
  inputs, source_chunk_id}. LLM only writes the explanation. Unknown inputs → "unknown", never guessed.
- Estimate node (rules/calculator.py): op codes × flat-rate hours (labour_time_guide.csv) × dealer labour rate
  + parts (parts_price_list.csv) + tax from config → lines split into warranty / recall / customer-pay.
  If any input is missing → "not estimable" with the reason. Decimal maths, tested rounding.
- Risk node: all detectors in CLAUDE.md A6 + LLM explanation. Wording: "indicator for review".
- Two interrupts: owner/advisor estimate approval (RO) and warranty_admin decision (claim).
- Every node async, owns its state fields, appends execution_trace, writes audit_log, max 2 retries with
  timeouts, idempotent per (ro_id, input hash). Checkpointer: langgraph PostgresSaver.

Tests: graph routes with a fake LLM; resume after interrupt and after process restart; idempotency (run twice →
same DB state); calculator property tests; every warranty rule pass/fail/unknown; every detector ±.

Exit Gate: scripts/demo_workflow.py runs 5 synthetic ROs (clean warranty, out-of-warranty customer-pay,
missing docs, recall-covered part, high-risk rollback + over-flat-rate labour) and prints status + trace for each.
```

---

## Prompt 11 — Review Dashboards + Owner Approval (Phase P3, Feature J)

```text
Tasks P3-9, P3-10.

1. Owner estimate approval: owner sees cited reasons, line items (warranty vs customer-pay), and approves or
   declines line by line → resumes the RO graph thread. Advisor can record verbal consent with a mandatory note.
2. Warranty queue (/warranty): sorted by risk + age, filter by dealer/model/status.
   Workspace tabs: Summary | Vehicle Context | Diagnosis (hypotheses + technician confirmation) | Extracted
   Fields (editable with reason, confidence, PDF preview at source page) | Warranty Rules (each rule + cited clause)
   | Estimate | Risk Indicators (evidence) | Audit Trail.
   Actions (warranty_admin only): correct field, return for info (draft message the admin must approve),
   SUBMIT_TO_OEM (DEMO adapter writes a JSON claim file + fake acknowledgement) / REJECT_BY_DEALER, rationale required.
3. Banner on every AI panel: "AI-generated preliminary assessment — not a decision."
4. Notifications table + DEMO SMS/email adapter for status changes.

Exit Gate: Playwright e2e — (a) owner approves estimate → RO goes IN_REPAIR; (b) warranty_admin opens a flagged
claim → corrects a field → submits to OEM (DEMO) → status SUBMITTED_TO_OEM; audit trail shows every step.
```

---

## Prompt 12 — (Optional) Predictive Maintenance from Telematics (Phase P4, Feature K)

```text
Task P4-0 (optional).

1. scripts/generate_telematics.py: synthetic daily CSVs per vehicle in data/telematics/ (odometer, battery voltage,
   coolant temp, DTC events, brake-pad wear estimate, EV state-of-health). Inject 3 degrading patterns.
2. Deterministic feature jobs + a simple, explainable model (thresholds or scikit-learn logistic regression /
   isolation forest) → maintenance_alerts {vehicle_id, signal, evidence window, score, recommended service from the
   cited manual section}. Model card in docs/MODEL_CARD.md (data, metrics, limits — synthetic only).
3. Owner sees a "Service suggested" card with the evidence and a one-tap booking that reuses Prompt 6 booking.
4. The LLM only phrases the alert; it never changes the score or the recommendation.

Exit Gate: the 3 injected patterns are detected; false-positive rate reported; alerts cite a manual section.
```

---

## Prompt 13 — Production Readiness: Security, Evals, Observability (Phase P4)

```text
Tasks P4-1 .. P4-6.

1. tests/security/: IDOR on every vehicle/RO/claim route, cross-dealer access, role escalation, JWT tampering,
   polyglot/oversized/wrong-magic uploads, prompt injection via chat AND documents, safety-bypass requests,
   PII leakage in logs (no full VIN, plate, phone, email), rate limiting.
2. Evals in CI (scripts/run_eval.py → markdown + JSON in evals/reports/): manual_qa, safety, diagnosis, extraction,
   warranty_rules, routing (expected node path per RO), risk (precision/recall). CI fails if faithfulness < 0.85,
   correct refusal < 0.90, safety compliance < 1.00, warranty rule agreement < 1.00, coverage < 80%.
3. Observability: OpenTelemetry across FastAPI → nodes → Claude; llm_usage (tokens, cost, model, latency);
   Prometheus metrics (latency, node errors, escalation rate, safety-refusal count, cost per RO); Grafana
   dashboard JSON; alert rules.
4. Locust load test for chat + status; p50/p95 report.
5. docs/runbooks/: LLM outage, stuck graph threads, audit chain break, data leak suspected, cost spike,
   unsafe-answer report from the field.
6. Retention/deletion config per data type (RETENTION_DAYS_*); deletion job tested on synthetic data.

Exit Gate: `make test`, `make eval`, and the security suite pass locally with the output shown.
```

---

## Prompt 14 — AWS Deployment (Phase P5)

```text
Task P5-1. Terraform in infra/ (plan-ready, do not apply):
VPC with private subnets, ECS Fargate (backend), S3 + CloudFront (frontend), RDS PostgreSQL 16 with pgvector,
S3 (SSE-KMS, block public access, versioning, lifecycle), Secrets Manager, Cognito (OIDC), ALB + WAF,
CloudWatch logs/alarms, ECR. Claude via Anthropic API or Amazon Bedrock (config switch, ADR-001).
GitHub Actions deploy workflow: OIDC to AWS, staging → manual approval → prod, rollback steps.
docs/DEPLOYMENT.md with an architecture diagram and a cost table marked "estimate".

Exit Gate: `terraform validate` passes. State clearly that nothing was deployed.
```

---

## Prompt 15 — Demo, Presentation, Narrative (Phase P5)

```text
Tasks P5-2 .. P5-4.

1. `make demo`: compose up → migrate → seed → generate knowledge + ingest → generate sample docs →
   demo_workflow.py → print URLs and demo logins (owner, advisor, technician, warranty_admin, admin).
2. docs/presentation.html (single file, inline CSS/JS, Mermaid from CDN): problem, solution, architecture,
   agent graph, journeys (owner, advisor, technician, warranty admin), safety design, governance, real eval
   numbers from evals/reports, roadmap, limitations.
3. narrative.md: business problem, architecture, design decisions (link ADRs), journeys, limitations
   (synthetic data only, OCR quality, LLM non-determinism, no real OEM/DMS integration, not a substitute for
   certified technicians), and a production-readiness checklist with ✅/⬜ that reflects the REAL state.
4. README.md: what it is, quick start, demo logins, DEMO vs production-ready.

Exit Gate: a new person can clone, run `make demo`, and finish docs/DEMO_SCRIPT.md in < 15 minutes.
```

---

## Reusable Mini-Prompts

**Continue / resume**
```text
Read .claude/TASK_TRACKER.md and .claude/MEMORY.md. Tell me the next OPEN task, its acceptance criteria, and your
plan in 5 bullets. Then implement it, run the tests, and update the tracker.
```

**Fix a bug**
```text
Bug: <describe>. Reproduce it with a failing test first, explain the root cause, fix it, show the passing test
output, and add an entry to .claude/MEMORY.md if the lesson is non-obvious.
```

**Safety review of AI output**
```text
Use the safety-reviewer agent on every prompt template in autoserve-server/app/prompts and every AI-facing UI string.
List each violation of CLAUDE.md A1 (file:line), fix it, and add a test in evals/safety.jsonl for each one.
```

**Review before commit**
```text
/review — then fix every Critical and High finding before committing.
```
