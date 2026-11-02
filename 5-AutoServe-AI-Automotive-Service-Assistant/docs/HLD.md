# AutoServe AI — High-Level Design

| | |
|---|---|
| **Version** | 1.0 · 2026-10-26 · task P0-3 |
| **Inputs** | `docs/PRD.md`, `.claude/CLAUDE.md`, `.claude/specs/*`, ADR-001…007 |
| **Companion docs** | `docs/LLD.md` (modules, state machines), `docs/API_SPEC.md`, `docs/DB_SCHEMA.md` |

---

## 1. System Context

```mermaid
flowchart LR
    owner["Vehicle Owner<br/>(browser / mobile web)"]
    advisor["Service Advisor<br/>(desktop / tablet)"]
    tech["Technician<br/>(tablet)"]
    wadmin["Warranty Admin<br/>(desktop)"]
    admin["Admin<br/>(desktop)"]

    subgraph sys["AutoServe AI"]
        app["AutoServe AI platform"]
    end

    claude["LLM providers - OpenAI-compatible<br/>EURI primary, Gemini / Groq fallback"]
    emb["Embeddings<br/>(EURI text-embedding-3-small, 1536-d)"]
    oem["OEM Warranty Portal<br/>DEMO adapter"]
    dms["Dealer Management System<br/>DEMO adapter"]
    sms["SMS / Email gateway<br/>DEMO adapter"]
    idp["Identity provider<br/>DEMO JWT / Cognito OIDC"]

    owner -->|chat, booking, status, approvals| app
    advisor -->|check-in, ROs, estimates| app
    tech -->|diagnosis, findings| app
    wadmin -->|claim review, decisions| app
    admin -->|knowledge, config, users, audit| app

    app -->|prompts with retrieved context| claude
    app -->|text to embed| emb
    app -->|claim JSON - DEMO| oem
    app -.->|future: RO sync - DEMO| dms
    app -->|notifications - DEMO| sms
    app -->|token validation| idp
```

**External systems.** Only the LLM providers and the embedding provider are real network dependencies. The OEM portal, DMS, SMS/email,
telematics, and AV scanning are **DEMO adapters** in this release (PRD NG2).

---

## 2. Containers

```mermaid
flowchart TB
    subgraph client["Client tier (untrusted)"]
        spa["React 18 SPA<br/>Vite · TanStack Query · Zod"]
    end

    subgraph edge["Edge"]
        cdn["Static hosting<br/>(Vite dev server / S3 + CloudFront)"]
        alb["Reverse proxy / ALB + WAF"]
    end

    subgraph api["Application tier (trusted)"]
        fastapi["FastAPI app<br/>auth · RBAC · routes · envelope"]
        services["Domain services<br/>state_machine · audit · storage · notification · vin"]
        orchestrator["LangGraph orchestrator<br/>9 nodes + route / record_decision / notify"]
        rag["RAG service<br/>ingest · chunk · embed · hybrid retrieve · grounded answer"]
        docpipe["Document pipeline<br/>validate_upload · classify · OCR · extract"]
        rules["Rules engine (deterministic)<br/>warranty · calculator · detectors · checklist · recall_match"]
        llmsvc["LLMService<br/>AGENT / ANSWER chains · fallback · usage · retries · timeouts"]
        adapters["DEMO adapters<br/>OEM · SMS/email · DMS · AV scan"]
    end

    subgraph data["Data tier"]
        pg[("PostgreSQL 16 + pgvector<br/>Supabase (hosted) / Docker (local)<br/>relational · vectors · FTS · checkpoints · audit")]
        obj[("Object storage<br/>MinIO (local) / S3 SSE-KMS")]
    end

    subgraph ext["External"]
        claude["EURI / Gemini / Groq APIs"]
        emb["Embeddings provider"]
    end

    subgraph obs["Observability"]
        otel["OpenTelemetry collector"]
        prom["Prometheus + Grafana"]
    end

    spa --> cdn
    spa -->|HTTPS JSON + SSE| alb --> fastapi
    fastapi --> services
    fastapi --> orchestrator
    fastapi --> rag
    fastapi --> docpipe
    orchestrator --> rules
    orchestrator --> rag
    orchestrator --> services
    orchestrator --> llmsvc
    docpipe --> llmsvc
    rag --> llmsvc
    rag --> emb
    llmsvc --> claude
    services --> adapters
    services --> pg
    rag --> pg
    orchestrator -->|PostgresSaver| pg
    docpipe --> obj
    fastapi --> otel --> prom
```

| Container | Responsibility | Tech |
|---|---|---|
| React SPA | Role workspaces: owner chat, my vehicles, RO detail, advisor board, tech copilot, warranty queue/workspace, admin | React 18, TS, Vite, Tailwind, TanStack Query, Zod, React Router |
| FastAPI app | AuthN/AuthZ, request validation, envelope, rate limiting, idempotency, SSE streaming | FastAPI, Pydantic v2 |
| Domain services | State transitions, audit chain, storage, notifications, VIN | SQLAlchemy 2 async |
| LangGraph orchestrator | Runs the service graph; interrupts for human decisions; resumable threads | LangGraph + PostgresSaver |
| RAG service | Synthetic corpus ingestion; hybrid retrieval with role/model filters; grounded cited answers | pgvector, Postgres FTS, LangChain |
| Document pipeline | Secure upload, classification, OCR, structured extraction, validation | pypdf, pdfplumber, pytesseract, Pillow |
| Rules engine | Warranty eligibility, estimate maths, anomaly detectors, checklist, recall match | Pure Python + `config/*.yaml` |
| LLMService | The only LLM client: AGENT/ANSWER chains with ordered fallback, structured output, retries, timeouts, `llm_usage` | langchain-openai (OpenAI-compatible) |
| Postgres + pgvector | System of record, vectors, FTS, LangGraph checkpoints, audit log | Supabase / Docker pg16 / RDS |
| Object storage | Uploaded documents + generated corpus PDFs | MinIO / S3 SSE-KMS |

---

## 3. Key Flows (sequence diagrams)

### 3.1 Owner manual Q&A

```mermaid
sequenceDiagram
    autonumber
    actor O as Owner
    participant UI as SPA
    participant API as FastAPI
    participant R as Intent router (AGENT chain)
    participant RAG as RAG service
    participant DB as Postgres+pgvector
    participant L as LLMService → LLM chain

    O->>UI: "What does the orange engine light mean?"
    UI->>API: POST /chat/messages (JWT)
    API->>API: require_role(owner) · rate limit
    API->>R: classify intent
    R-->>API: manual_question (conf ≥ threshold)
    API->>DB: resolve owner's vehicle → model, model year
    API->>RAG: retrieve(query, model, year, visibility=owner)
    RAG->>DB: vector + FTS → RRF
    DB-->>RAG: top-k chunks + scores
    alt no chunk above threshold
        RAG-->>API: insufficient_evidence (no LLM call)
    else evidence found
        RAG->>L: grounded prompt (context chunks, cite ids)
        L-->>RAG: answer + citations (structured)
        RAG->>RAG: validate chunk ids + quote substrings · safety tier
    end
    RAG-->>API: {answer, citations, confidence, safety_critical, banner_tier}
    API->>DB: messages + llm_usage + audit
    API-->>UI: SSE stream (envelope)
    UI-->>O: answer + citation chips (+ safety banner)
```

### 3.2 Booking → Repair Order

```mermaid
sequenceDiagram
    autonumber
    actor O as Owner
    participant API as FastAPI
    participant G as Graph: Intake node
    participant V as vin.py / validators
    participant SM as state_machine
    participant DB as Postgres

    O->>API: POST /chat/messages "I need a service, grinding noise"
    API->>G: run(entrypoint=booking)
    G->>DB: list_my_vehicles(actor)
    G-->>API: ask next missing field (odometer)
    O->>API: "about 42,000 km"
    API->>G: resume
    G->>V: validate VIN owned · odometer ≥ last · slot free (DEMO capacity)
    G-->>API: AppointmentDraft complete → ask confirm
    O->>API: POST /appointments (Idempotency-Key)
    API->>DB: insert appointment + RO (ro_ref from sequence)
    API->>SM: transition(RO, DRAFT→BOOKED, actor=owner)
    SM->>DB: status + ro_status_history + audit_log (one tx)
    API-->>O: RO-2026-000123 · BOOKED
```

### 3.3 Check-in with VIN decode and recall match

```mermaid
sequenceDiagram
    autonumber
    actor A as Advisor
    participant API as FastAPI
    participant SM as state_machine
    participant VC as Graph: Vehicle Context node
    participant RU as Rules: recall_match · detectors
    participant DB as Postgres

    A->>API: POST /repair-orders/{id}/check-in (odometer, fuel/charge, damage, complaint confirmed)
    API->>API: require_role(service_advisor) · dealer scope
    API->>SM: transition(BOOKED→CHECKED_IN)
    SM->>DB: status + history + audit (one tx)
    API->>VC: run(entrypoint=check_in)
    VC->>DB: decode VIN (vehicle_models) · last 10 service records
    VC->>RU: match recalls (model + year + VIN serial range)
    VC->>RU: match TSBs (range + DTC/keyword) · maintenance due · coverage summary
    VC->>RU: D-01 odometer rollback indicator
    RU-->>VC: results with source_chunk_ids
    VC->>DB: risk_flags (if any) + audit
    VC-->>API: VehicleContextOut
    API-->>A: Vehicle Context card (cited) + "indicator for review" if D-01
```

### 3.4 Technician diagnosis

```mermaid
sequenceDiagram
    autonumber
    actor T as Technician
    participant API as FastAPI
    participant D as Graph: Diagnosis node
    participant RAG as RAG (staff visibility)
    participant L as LLMService → LLM chain
    participant DB as Postgres

    T->>API: POST /repair-orders/{id}/diagnosis (DTCs, symptoms, tests)
    API->>API: require_role(technician) · dealer scope · DTC regex
    API->>D: run(entrypoint=diagnosis)
    D->>RAG: lookup_dtc(code) exact match (doc_type=dtc)
    D->>RAG: retrieve procedures + TSBs (model/year/VIN filters, DTC boost)
    alt nothing above threshold
        D-->>API: insufficient_evidence (no LLM call)
    else
        D->>L: rank hypotheses from context only (structured)
        L-->>D: hypotheses
        D->>D: drop uncited · verify quotes · cap 5 · safety/HV banner · refuse bypass
    end
    D->>DB: trace + audit + llm_usage
    D-->>API: DiagnosisResult
    API-->>T: hypotheses with citations + next tests
    T->>API: POST /repair-orders/{id}/findings (confirmed cause, op codes, time, parts)
    API->>DB: diagnostic_findings + audit
```

### 3.5 Warranty claim with human-review interrupt

```mermaid
sequenceDiagram
    autonumber
    actor A as Advisor
    actor W as Warranty Admin
    participant API as FastAPI
    participant G as LangGraph (PostgresSaver)
    participant RU as Rules engine
    participant L as LLMService
    participant SM as state_machine
    participant OEM as OEM adapter (DEMO)
    participant DB as Postgres

    A->>API: POST /repair-orders/{id}/workflow/run
    API->>G: invoke(thread_id=ro:{id})
    G->>G: document → diagnosis(read) → warranty → estimate → risk
    G->>RU: warranty rules · calculator · detectors (deterministic)
    G->>L: explanations / summaries only
    G->>G: route (deterministic)
    alt checklist gaps
        G->>SM: RO DIAGNOSING→INFO_PENDING (system)
    else recall covers failed part
        G-->>API: recommend recall job (advisor confirms)
    else claim path
        G->>SM: claim DRAFT→PREPARED→WARRANTY_REVIEW_REQUIRED (system)
        G->>G: interrupt(kind=warranty_decision, evidence pack)
        G->>DB: checkpoint saved
    end
    W->>API: GET /warranty/claims/{id} (workspace)
    W->>API: POST /warranty/claims/{id}/decision {submit_to_oem, rationale}
    API->>API: require_role(warranty_admin) · dealer scope · rationale
    API->>G: Command(resume=decision)
    G->>SM: transition(→SUBMITTED_TO_OEM, actor=warranty_admin)
    SM->>DB: status + history + review_decisions + audit (one tx)
    G->>OEM: submit claim JSON (DEMO)
    OEM-->>G: fake acknowledgement
    G->>DB: notifications (DEMO)
    API-->>W: SUBMITTED_TO_OEM
```

### 3.6 Status lookup

```mermaid
sequenceDiagram
    autonumber
    actor O as Owner
    participant API as FastAPI
    participant S as Graph: Status node
    participant DB as Postgres
    participant L as LLMService (ANSWER chain)

    O->>API: "Where is my car at?" / GET /repair-orders/{id}/status
    API->>S: get_ro_status(ro_ref, actor)
    S->>DB: repair_orders + ro_status_history (+ claim) via scoped repo
    alt not found / not owner's
        S-->>API: "couldn't find that repair order in your account"
    else
        S->>L: phrase structured result (no new facts)
        L-->>S: sentence
        S->>S: post-check statuses/dates ⊆ DB result (else template)
        S-->>API: status + history + eta only if promised_ready_at set
    end
    API-->>O: answer (p95 < 1 s target)
```

---

## 4. Trust Boundaries and Enforcement Points

```mermaid
flowchart LR
    subgraph U["Untrusted"]
        browser["Browser / SPA"]
        upload["Uploaded files"]
        chat["Chat text"]
    end
    subgraph T1["Boundary 1: API edge"]
        authn["AuthN: JWT/OIDC verify"]
        rl["Rate limit · size limits · CORS"]
    end
    subgraph T2["Boundary 2: Application"]
        rbac["require_role()"]
        repo["Actor-scoped repositories<br/>(owner_id / dealer_id)"]
        sm["state_machine.transition()"]
        mask["mask_pii() log processor"]
    end
    subgraph T3["Boundary 3: LLM"]
        wrap["untrusted_* wrapping in user turn"]
        schema["Structured output + post-validation"]
        notools["No tools for extractors · no SQL/HTTP"]
    end
    subgraph T4["Boundary 4: Data"]
        pg[("Postgres: audit trigger · app role least-privilege")]
        s3[("Object store: SSE · private · presigned")]
    end
    browser --> authn --> rl --> rbac --> repo --> pg
    upload --> rl
    chat --> rl
    rbac --> sm --> pg
    repo --> wrap --> schema
    wrap --> notools
    rl --> s3
```

| Control | Where enforced | Notes |
|---|---|---|
| Authentication | FastAPI dependency (`core/security.py`) | DEMO JWT locally; OIDC JWKS in prod; alg pinned |
| Role-based access (RBAC) | `require_role()` on every route | Admin cannot reach decision endpoints |
| Owner isolation | Repositories (`vehicle.owner_id == actor.user_id`) | Out of scope → 404 |
| Dealer isolation | Repositories (`ro.dealer_id == actor.dealer_id`) | All staff queries; cross-dealer tests |
| State integrity | `state_machine.transition()` | Role + table check, history + audit in one tx |
| PII masking | structlog processor `mask_pii()`; eval report writer; OTel attribute filter | VIN → last 6 |
| Prompt-injection containment | Prompt builder in `LLMService`; extractor has no tools | D-09 flag on suspicious content |
| Upload safety | `documents/validate_upload.py` before storage | Magic bytes, size/pages, re-encode, AV hook (DEMO) |
| Audit immutability | DB trigger + hash chain + app-role grants | `verify_chain()` admin endpoint |
| File access | Presigned URL after authZ, short TTL | Bucket is private |

---

## 5. Deployment Views

| Environment | Frontend | Backend | Database | Storage | LLM |
|---|---|---|---|---|---|
| Local / CI | Vite dev server (compose) | uvicorn container | Docker `pgvector/pgvector:pg16` | MinIO | EURI → Gemini/Groq (FakeLLM in tests) |
| Hosted dev/demo | Static build | Container | **Supabase Postgres** (ADR-007) | MinIO / S3 | EURI → Gemini/Groq |
| AWS (design only, P5) | S3 + CloudFront | ECS Fargate behind ALB + WAF | RDS PostgreSQL 16 + pgvector | S3 SSE-KMS | EURI → Gemini/Groq via NAT egress |

---

## 6. Cross-Cutting Concerns

- **Observability:** OTel spans for HTTP → node → LLM → DB; Prometheus metrics (rules/85); `llm_usage` per call; Grafana dashboard + alerts.
- **Resilience:** LLM timeouts + `max_retries=2`; template fallbacks for explanation/phrasing; deterministic features unaffected by LLM outage.
- **Idempotency:** `Idempotency-Key` on state-creating POSTs; node-level `(ro_id, node, input_hash)`; duplicate resume is a no-op.
- **Configuration:** env (`pydantic-settings`) for infra; versioned YAML for business rules with `source_chunk_id` validated at startup.

---

## 7. ADR Review (P0-5)

| ADR | Review outcome |
|---|---|
| 001 Claude LLM | **Superseded by ADR-008** (OpenAI-compatible EURI/Gemini/Groq chains) on 2026-10-26 at the project owner's request. |
| 002 LangGraph | Agree. Checkpoint tables go in a dedicated `langgraph` schema via the connection `search_path` (implementation note, not a decision change). |
| 003 pgvector | Agree on the data design. Hosting already amended by ADR-007. |
| 004 React + Vite | Agree. No change. |
| 005 AWS ECS Fargate | Agree as the AWS production design. Hosted dev/demo uses Supabase (ADR-007); P5 docs must state both. |
| 006 Deterministic rules | Agree. No change. |
| 008 OpenAI-compatible LLM chains | Accepted 2026-10-26. Safety evals must pass for every AGENT-chain model. |
| 007 Supabase hosting | Accepted 2026-10-26. Pooler/prepared-statement behaviour to be verified in P1-2. |

ADR-001 is superseded by ADR-008; no other superseding ADR is needed.
