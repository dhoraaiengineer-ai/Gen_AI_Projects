# AutoServe AI — Product Requirements Document

| | |
|---|---|
| **Product** | AutoServe AI — GenAI copilot for automotive after-sales service |
| **Version** | 1.0 (draft for pilot) |
| **Date** | 2026-10-26 |
| **Status** | Draft — tasks P0-1 / P0-2 |
| **Source of truth** | `.claude/CLAUDE.md` (contract), `.claude/specs/`, `.claude/adr/` |
| **Data** | Synthetic only. Fictional OEM "Veloxa Motors" (Aria, Terra, Volt). No real brands, customers, or specifications. |

> **Guiding principle — "AI assists, certified humans decide."** AutoServe AI explains, retrieves, ranks, drafts, and flags.
> Binding decisions (repair authorisation, estimate approval, warranty decisions) are always made by an authorised human.
> All automotive facts (specs, DTC meanings, labour times, prices, warranty terms) come from the cited synthetic corpus,
> never from the model. This document contains **no** automotive specification values on purpose.

---

## 1. Business Problem

Dealer workshops and the OEM warranty desk lose time and money on five recurring problems:

| # | Problem | Effect today |
|---|---|---|
| P1 | **Long diagnosis time.** Technicians search service manuals, TSBs, and DTC references by hand. | Vehicles sit in the bay; check-in → estimate takes too long; bay utilisation drops. |
| P2 | **Repeat repairs.** The root cause is missed, or a matching TSB is not found. | The same vehicle returns within weeks; first-time-fix rate falls; owner trust drops. |
| P3 | **Warranty claims returned or rejected by the OEM** for missing documents, inconsistent data, or out-of-coverage items. | Dealer cash flow is delayed; warranty admins re-work claims; disputes with the OEM. |
| P4 | **Advisors re-type data** from paper/scanned ROs, invoices, and service records. | Slow check-in; transcription errors (VIN, odometer, part numbers) that later cause claim rejections. |
| P5 | **Owners call for status** and with basic manual questions (warning lights, maintenance, tyres, charging). | Phone load on advisors; inconsistent answers; owners don't know when to stop driving. |

## 2. Goals and Non-Goals

### Goals
- G1 — Cut check-in → estimate-ready time with a cited diagnostic copilot and automatic Vehicle Context (history, recalls, TSBs).
- G2 — Raise first-time-fix rate by surfacing matching TSBs and ranked, evidence-backed hypotheses.
- G3 — Reduce OEM returns by preparing complete, consistent, deterministically checked claim packs before submission.
- G4 — Remove re-typing through document extraction with confidence scores and human verification.
- G5 — Deflect status and manual calls with a grounded owner chat that reports only real DB status and cites the manual.
- G6 — Make every AI contribution auditable, explainable, and safe.

### Non-Goals
- NG1 — The AI does **not** approve repairs, estimates, or warranty claims, or decide eligibility on its own.
- NG2 — No real OEM, DMS, payment, SMS, or telematics integration in this release. All are **DEMO** adapters.
- NG3 — No real brands, customers, VINs, or OEM documents.
- NG4 — No DIY repair guidance for owners on safety-critical or high-voltage systems.
- NG5 — No replacement of certified technicians' judgement or OEM warranty policy.
- NG6 — No payments, invoicing to customers, parts ordering, or workshop scheduling optimisation.

## 3. Scope

| In scope (this release) | Out of scope |
|---|---|
| Owner chat: manual Q&A, booking, status, recall check (A, B, I) | Native mobile apps (responsive web only) |
| VIN decode, service history, recall/TSB matching (C) | Real OEM warranty portal / DMS integration |
| Document upload + extraction + checklist (D) | Payment processing, customer invoicing |
| Technician diagnostic copilot (E) | Parts ordering / inventory |
| Deterministic warranty eligibility (F) | Multi-language UI (English only; strings externalised for later i18n) |
| Deterministic estimate + warranty claim preparation (G) | Real telematics feed (synthetic only, optional K) |
| Anomaly indicators for review (H) | Automated decisions of any kind |
| Advisor board, warranty queue/workspace, owner approval (J) | Production AWS deployment (Terraform is plan-ready only) |
| (Optional) Predictive maintenance from synthetic telematics (K) | |

## 4. Assumptions and Constraints

### Assumptions
- A1 — The synthetic Veloxa corpus (owner/service manuals, warranty booklet, TSBs, recalls, DTC reference, labour-time guide, parts price list) is the single source of domain truth. All domain numbers are authored in `data/knowledge/src/`.
- A2 — Each staff user belongs to exactly one dealer; owners don't belong to a dealer.
- A3 — Workshop staff use tablets or desktops with a modern browser; owners use mobile or desktop browsers.
- A4 — The EURI, Gemini, and Groq OpenAI-compatible APIs are reachable (ADR-008); only synthetic data is sent to them.
- A5 — A hosted Postgres with pgvector is available (Supabase per ADR-007; local Docker fallback).

### Constraints
- C1 — Business rules, money, hours, eligibility, and status transitions are deterministic Python (ADR-006).
- C2 — Every status change goes through `state_machine.transition()`, with history + audit in one transaction.
- C3 — Owner PII is masked in logs; data is isolated per owner and per dealer.
- C4 — Tech stack fixed by CLAUDE.md §8. Changes need an ADR.
- C5 — Every mock integration is labelled **DEMO**.

---

## 5. Personas and User Stories

### 5.1 Vehicle Owner — "Priya, Veloxa Terra owner"
Busy commuter. Wants quick, trustworthy answers and doesn't want to phone the dealer. Not technical.

| ID | Story | Acceptance criteria (Given / When / Then) |
|---|---|---|
| US-O1 | As an owner, I want to ask what a warning light means so I know what to do. | **Given** I am logged in with a Terra in my garage **When** I ask about a warning light **Then** the answer quotes the Terra owner manual entry with a citation chip (file, page, section), and a safety banner appears if the topic is safety-critical. |
| US-O2 | As an owner, I want to book a service in chat so I don't have to call. | **Given** I own a vehicle **When** I say I need a service **Then** the assistant asks for one missing field at a time (vehicle, odometer, complaint, slot), validates them, and on confirmation shows an RO reference `RO-YYYY-NNNNNN` with status BOOKED. |
| US-O3 | As an owner, I want to know the status of my repair. | **Given** I have an RO **When** I ask for its status **Then** I get the status and timeline stored in the DB, and no ETA unless the advisor has recorded one. |
| US-O4 | As an owner, I want to know if my vehicle has an open recall. | **Given** my VIN falls in an open recall's VIN range **When** I ask about recalls or open My Vehicles **Then** I see the campaign title and a cited recall notice, and I'm offered a booking. |
| US-O5 | As an owner, I want to approve or decline estimate lines myself. | **Given** the advisor sent me an estimate **When** I open it **Then** I see customer-pay lines with reasons and amounts from the calculator, warranty/recall lines marked "pending warranty review", and I can approve or decline each customer-pay line. |

### 5.2 Service Advisor — "Marco, dealer 1"
Front desk. Handles check-in, owner communication, and RO flow. Wants less typing and fewer surprises.

| ID | Story | Acceptance criteria |
|---|---|---|
| US-A1 | As an advisor, I want today's appointments on one board. | **Given** I am logged in at dealer 1 **When** I open `/advisor` **Then** I see only dealer 1 appointments for today with vehicle, complaint, and RO status. |
| US-A2 | As an advisor, I want check-in to show the vehicle's context automatically. | **Given** a BOOKED RO **When** I submit check-in (odometer, fuel/charge, damage notes, confirmed complaint) **Then** the RO moves to CHECKED_IN and a Vehicle Context card shows the decoded VIN, last service records, maintenance due, open recalls, matching TSBs, and coverage summary, each with a cited source. |
| US-A3 | As an advisor, I want uploaded documents pre-filled for me. | **Given** I upload an RO/invoice PDF or photo **When** extraction completes **Then** fields are shown with confidence and source page; low-confidence or failed-validation fields are marked "needs verification"; I can correct a field with a reason and the change is audited. |
| US-A4 | As an advisor, I want to send the estimate to the owner. | **Given** an RO in ESTIMATE_READY **When** I click "Send estimate" **Then** the RO moves to AWAITING_OWNER_APPROVAL and the owner is notified (DEMO adapter). |
| US-A5 | As an advisor, I want to record an owner's phone consent. | **Given** an RO awaiting approval **When** I record consent **Then** a consent note is mandatory, and the decision is stored with my identity and audited. |

### 5.3 Technician — "Sam, EV-certified technician, dealer 1"
Works in the bay on a tablet, sometimes with gloves. Wants the right procedure fast.

| ID | Story | Acceptance criteria |
|---|---|---|
| US-T1 | As a technician, I want to enter DTCs and symptoms and get ranked hypotheses. | **Given** an RO in DIAGNOSING **When** I enter valid DTCs (`[PBCU]` + 4 hex chars) and symptoms **Then** I get at most 5 hypotheses, each with evidence, confidence, at least one citation, and a cited next test. |
| US-T2 | As a technician, I want DTC meanings from the official reference only. | **Given** a DTC **When** it is in the DTC reference **Then** the meaning is quoted with a citation; **When** it isn't **Then** the UI says "code not found in reference". |
| US-T3 | As a technician, I want matching TSBs highlighted. | **Given** a vehicle in a TSB's model/year/VIN range **When** its DTCs or symptoms match **Then** the TSB appears with its cited fix and op code. |
| US-T4 | As a technician, I want to record what I confirmed and did. | **Given** a diagnosis **When** I record the confirmed hypothesis, op codes, actual time, and parts used **Then** they are stored as diagnostic findings and feed the estimate. |
| US-T5 | As a technician, I want safety-critical and HV jobs clearly marked. | **Given** a safety-critical system or EV HV is involved **When** results are shown **Then** the banner "Certified technician required — follow the cited procedure and PPE" appears. |

### 5.4 Warranty Administrator — "Lena, dealer 1 warranty desk"
Prepares and decides claims before OEM submission. Measured on OEM acceptance rate.

| ID | Story | Acceptance criteria |
|---|---|---|
| US-W1 | As a warranty admin, I want a queue sorted by risk and age. | **Given** claims at my dealer **When** I open `/warranty` **Then** I see claims sorted by risk level then age, filterable by model and status, and none from other dealers. |
| US-W2 | As a warranty admin, I want each eligibility rule shown with its cited clause. | **Given** a prepared claim **When** I open the Warranty Rules tab **Then** each rule shows pass/fail/unknown, its inputs, and the cited booklet clause. |
| US-W3 | As a warranty admin, I want anomaly indicators with evidence, not accusations. | **Given** detectors fired **When** I open Risk Indicators **Then** each shows "indicator for review" with its evidence, and no text calls anything fraud. |
| US-W4 | As a warranty admin, I want to correct a field and submit to the OEM. | **Given** a claim in WARRANTY_REVIEW_REQUIRED **When** I correct a field (reason required) and choose Submit to OEM with a rationale **Then** the claim moves to SUBMITTED_TO_OEM via the DEMO adapter, and the audit trail shows each step. |
| US-W5 | As a warranty admin, I want to return a claim for info with a drafted message. | **Given** missing evidence **When** I choose Return for info **Then** the AI drafts a message that I must edit/approve before it is sent, and the claim moves to RETURNED_FOR_INFO. |

### 5.5 Admin — "Ravi, platform admin"
Manages the knowledge base, configuration, and users. Cannot decide claims.

| ID | Story | Acceptance criteria |
|---|---|---|
| US-D1 | As an admin, I want to upload and ingest a knowledge document. | **Given** a synthetic PDF **When** I upload it **Then** it is chunked, embedded, and searchable; re-uploading identical content creates no duplicates. |
| US-D2 | As an admin, I want to verify the audit chain. | **Given** audit records **When** I run verify **Then** I see "chain intact" or the first broken sequence number. |
| US-D3 | As an admin, I want to manage checklists and thresholds. | **Given** config **When** I change a threshold **Then** a new version is stored, the change is audited, and every coverage number keeps its `source_chunk_id`. |
| US-D4 | As an admin, I want to manage users and roles. | **Given** the admin page **When** I create a staff user **Then** I must assign exactly one role and a dealer. |
| US-D5 | As an admin, I must not be able to decide claims. | **Given** I'm logged in as admin **When** I call any warranty decision endpoint **Then** I get `FORBIDDEN_ROLE` and nothing changes. |

---

## 6. Functional Requirements

Priority: **M** = must (pilot), **S** = should, **C** = could. Phase per `.claude/PLAN.md`.

### A — Owner Manual Q&A

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-001 | Answer owner questions using only retrieved owner-manual chunks for the owner's model and model year. | Answer cites ≥ 1 chunk (file, page, section, quote); every quote is a substring of its chunk; no chunk from another model is cited. | M | P1 |
| FR-002 | Refuse when evidence is insufficient. | When no chunk clears the retrieval threshold, response has `insufficient_evidence=true`, says it isn't in the manual, and **no LLM call is made**. | M | P1 |
| FR-003 | Hide staff-only content from owners. | An owner query never returns chunks with `visibility='staff'` (security test). | M | P1 |
| FR-004 | Apply safety banners per rules/55 tiers. | Safety topic → info banner + escalation; active warning or a manual "stop" instruction → stop banner + quoted required action. | M | P1 |
| FR-005 | Refuse safety/emissions bypass requests. | All bypass cases in `evals/safety.jsonl` get the fixed refusal text and are logged as `safety_refusals_total`. | M | P1 |
| FR-006 | Admin can upload and ingest knowledge documents idempotently. | Re-ingesting identical content adds 0 chunks; each chunk has the full metadata set (rules/50). | M | P1 |

### B — Service Booking and Repair Order

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-010 | Route owner chat messages by intent (manual_question, book_service, ro_status, recall_check, warranty_question, upload_help, smalltalk, out_of_scope). | Routing eval passes; low confidence → out_of_scope with a helpful redirect. | M | P1 |
| FR-011 | Conversational booking collects vehicle, odometer, complaint (verbatim), and slot, one missing field at a time. | Each missing field produces exactly one question in fixed order; the complaint is stored verbatim. | M | P1 |
| FR-012 | Validate bookings deterministically. | Invalid VIN / not-owned vehicle / odometer below last record / unavailable slot are rejected with the matching error code. | M | P1 |
| FR-013 | Confirmed booking creates an appointment and an RO in BOOKED with a DB-sequence reference. | `RO-YYYY-NNNNNN` from the sequence; the same `Idempotency-Key` returns the same RO. | M | P1 |
| FR-014 | All RO/claim status changes go through the state machine with role checks. | Every allowed transition succeeds for its actor; every other attempt returns `INVALID_TRANSITION` or `FORBIDDEN_ROLE`; history + audit rows written. | M | P1–P3 |

### C — VIN Decode, Service History, Recall/TSB Match

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-020 | Validate VINs (17 chars, no I/O/Q, ISO 3779 check digit, WMI `VLX`). | Unit tests cover valid VINs and each invalid class. | M | P1 |
| FR-021 | Decode model, model year, and plant from the catalogue. | Decoded fields match the seeded catalogue for all seeded vehicles. | M | P1 |
| FR-022 | Match open recalls by model + model year + VIN serial range (inclusive). | Boundary tests: at start, at end, one outside, wrong model year. | M | P1 |
| FR-023 | Match TSBs by model/year/VIN range **and** DTC or symptom keyword. | Tests for DTC-only, keyword-only, and neither. | M | P2 |
| FR-024 | Compute maintenance due from the cited schedule vs. service history. | Schedule values come from config with `source_chunk_id`; due/overdue cases tested at boundaries. | M | P2 |
| FR-025 | Show a Vehicle Context card on the RO with a citation link for every item. | Every item has a source link; no item without one is shown. | M | P2 |

### D — Document Intelligence

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-030 | Secure upload of PDF/JPG/PNG ≤ 10 MB and ≤ 20 pages, with magic-byte check, metadata strip, image re-encode, encrypted storage, sha256, DEMO AV hook. | Wrong magic, oversized, polyglot, and too many pages are rejected with the matching code. | M | P2 |
| FR-031 | Classify documents into the 8 classes. | Classification accuracy is reported on sample docs. | M | P2 |
| FR-032 | Extract structured fields with confidence and source page. | Per-field accuracy vs. ground truth is reported; key fields ≥ 90%. | M | P2 |
| FR-033 | Validate extracted fields deterministically (VIN check digit + matches RO, dates, totals = Σ lines, part numbers and op codes exist). | Each validator has ± tests; failures set `needs_human_verification`. | M | P2 |
| FR-034 | Flag low confidence (< 0.80) for human verification. | Boundary test at 0.79 / 0.80. | M | P2 |
| FR-035 | Defend against prompt injection in documents. | The injection sample raises D-09, and its decision path is identical to its clean twin. | M | P2 |
| FR-036 | Run the document checklist per claim type and component group, with citation. | Missing docs on an RO in DIAGNOSING → INFO_PENDING; on a claim → stays DRAFT with gaps listed; re-check runs on new upload. | M | P2 |
| FR-037 | Staff can correct extracted fields with a reason. | Old value, new value, actor, and reason are stored and audited. | M | P2 |

### E — Technician Diagnostic Copilot

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-040 | Validate DTC format. | Invalid formats return `INVALID_DTC`. | M | P3 |
| FR-041 | Look up DTC meanings only in the DTC reference, by exact match. | Unknown code → "code not found in reference". | M | P3 |
| FR-042 | Produce ≤ 5 ranked hypotheses, each with ≥ 1 valid citation and a cited next test. | Post-validation drops uncited hypotheses; 0 uncited in eval. | M | P3 |
| FR-043 | Show spec values only as quoted citations. | Any spec number in output appears inside a quote that matches its chunk. | M | P3 |
| FR-044 | Record technician findings (confirmed hypothesis, op codes, actual time, parts). | Stored in `diagnostic_findings`; available to estimate and evals. | M | P3 |
| FR-045 | Diagnosis eval set ≥ 30 cases. | Report hit@1, hit@3 (≥ 0.70), citation validity, unsupported-claim rate. | M | P3 |

### F — Warranty Eligibility

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-050 | Evaluate coverage (basic, powertrain, EV battery incl. capacity), exclusions, and maintenance compliance with deterministic rules. | Each rule returns pass/fail/unknown with inputs and `source_chunk_id`. | M | P3 |
| FR-051 | Never guess missing inputs. | Missing input → `unknown` (test per rule). | M | P3 |
| FR-052 | Derive the overall result deterministically and label it a preliminary assessment. | Truth-table tests; UI label present. | M | P3 |
| FR-053 | The LLM explains findings without adding numbers. | Regex check: no number in the explanation that isn't in the findings. | M | P3 |
| FR-054 | Rule agreement with the expected results. | `evals/warranty_rules` agreement = 1.00. | M | P3 |

### G — Estimate and Warranty Claim Preparation

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-060 | Calculate labour (flat-rate hours × dealer rate), parts (qty × price), and tax with Decimal maths and a documented rounding policy. | Property tests: amounts ≥ 0, Σ lines = total, split sums = total. | M | P3 |
| FR-061 | Split lines into warranty / recall / customer-pay (precedence recall > warranty > customer). | Precedence tests. | M | P3 |
| FR-062 | Return "not estimable" with reasons when any input is missing. | Test per missing input type; RO doesn't reach ESTIMATE_READY. | M | P3 |
| FR-063 | Prepare a warranty claim (`WC-YYYY-NNNNNN`) with evidence pack when lines are warranty-covered. | Claim created in DRAFT → PREPARED only when checklist complete. | M | P3 |
| FR-064 | Recommend a recall job when an open recall covers the failed part. | Advisor confirms; no automatic conversion. | M | P3 |

### H — Anomaly Indicators

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-070 | Run detectors D-01…D-09 (CLAUDE.md §7) with windows/tolerances from config. | ± and boundary test per detector. | M | P2–P3 |
| FR-071 | Word every flag as an "indicator for review" with evidence and possible benign reasons. | Forbidden-word test on all explanations and templates. | M | P3 |
| FR-072 | Compute a risk level from config weights. | Mapping tests. | M | P3 |
| FR-073 | Reviewers can mark flags reviewed/dismissed with a note. | Stored and audited. | S | P3 |

### I — Status Tracking

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-080 | Status comes only from `ro_status_history` (+ claim status). | Phrased text contains no status/date absent from the DB result. | M | P1 |
| FR-081 | Show an ETA only when `promised_ready_at` is set. | Null → "No completion time has been recorded yet." | M | P1 |
| FR-082 | Owners see only their own ROs. | Cross-owner status request → not found. | M | P1 |
| FR-083 | Notify the owner on key status changes (DEMO SMS/email + in-app). | Notification row per change; adapter labelled DEMO. | S | P3 |

### J — Advisor and Warranty Review Dashboards

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-090 | Advisor board with today's appointments and check-in form. | Dealer-scoped; check-in → CHECKED_IN. | M | P2 |
| FR-091 | Advisor sends the estimate; owner approves/declines per customer-pay line; advisor can record consent with a note. | ≥ 1 approved → APPROVED, 0 → DECLINED; note mandatory for advisor consent. | M | P3 |
| FR-092 | Warranty queue sorted by risk + age with filters. | Dealer-scoped; sort verified. | M | P3 |
| FR-093 | Warranty workspace tabs: Summary, Vehicle Context, Diagnosis, Extracted Fields (with PDF preview at source page), Warranty Rules, Estimate, Risk Indicators, Audit Trail. | All tabs render for a seeded claim. | M | P3 |
| FR-094 | Warranty decisions (submit / return for info / reject) by warranty_admin only, rationale required; the return message is AI-drafted and admin-approved. | Other roles → `FORBIDDEN_ROLE`; missing rationale → `RATIONALE_REQUIRED`. | M | P3 |
| FR-095 | Every AI panel carries "AI-generated preliminary assessment — not a decision." | UI test per panel. | M | P3 |
| FR-096 | E2E: owner approval → IN_REPAIR; warranty admin correct field → submit → SUBMITTED_TO_OEM, with the audit trail. | Playwright tests green. | M | P3 |

### K — (Optional) Predictive Maintenance

| ID | Requirement | Acceptance criteria | Pri | Phase |
|---|---|---|---|---|
| FR-100 | Generate synthetic telematics with 3 injected degrading patterns. | Files in `data/telematics/`. | C | P4 |
| FR-101 | Deterministic features + explainable model produce maintenance alerts with evidence window, score, and a cited manual section. | 3 patterns detected; false-positive rate reported. | C | P4 |
| FR-102 | Owner sees "Service suggested" with one-tap booking reusing FR-011. | Booking pre-filled; LLM only phrases the alert. | C | P4 |

---

## 7. Non-Functional Requirements

| ID | Category | Requirement | Acceptance / measurement |
|---|---|---|---|
| NFR-001 | Security — authN | DEMO JWT locally (alg pinned, short TTL); OIDC (Cognito) in prod. | JWT tamper / `alg=none` / expired tests rejected. |
| NFR-002 | Security — authZ | Role check on every route + actor-scoped repositories; out-of-scope → 404. | IDOR + role-escalation suite green on every route. |
| NFR-003 | Security — dealer isolation | Staff only see their dealer's data. | Cross-dealer tests green on every staff route. |
| NFR-004 | Security — uploads & injection | Per FR-030/FR-035 and rules/70. | Security suite green. |
| NFR-005 | Privacy — owner PII | Name, phone, email, address, plate, full VIN masked in logs, traces, metrics, eval reports. | Log-scan test finds no unmasked PII. |
| NFR-006 | Privacy — location | No precise location stored or logged; telematics (optional) uses synthetic data only. | Schema review + log scan. |
| NFR-007 | Privacy — retention | Retention per data type via `RETENTION_DAYS_*`; deletion job. | Deletion job test on synthetic data. |
| NFR-008 | Latency — chat | Owner chat p95 < 6 s. | Locust + Prometheus. |
| NFR-009 | Latency — status | Status lookup p95 < 1 s. | Locust + Prometheus. |
| NFR-010 | Availability | Graceful degradation when the LLM is down: status and deterministic features keep working; chat returns a safe fallback. | Fault-injection test; runbook. |
| NFR-011 | Durability | Graph threads resume after a process restart. | Restart test with PostgresSaver. |
| NFR-012 | Auditability | Append-only, hash-chained audit log for every state change, decision, field correction, and node run. | Tamper test; `verify_chain` endpoint. |
| NFR-013 | Cost | Track tokens and cost per call and per RO in `llm_usage`; set a budget after the baseline. | Dashboard + cost-spike alert. |
| NFR-014 | Accessibility | WCAG 2.1 AA. | Automated axe checks + manual keyboard pass on key pages. |
| NFR-015 | Workshop usability | Tablet-first `/tech` and `/advisor`; tap targets ≥ 48×48 px; readable in bright light. | UI review at tablet viewport; Playwright viewport tests. |
| NFR-016 | Observability | OpenTelemetry traces API → node → LLM; Prometheus metrics; Grafana dashboard + alerts. | Trace visible end-to-end in demo. |
| NFR-017 | Maintainability | Coverage ≥ 80%; 100% branch coverage on rules and state machine; lint/type clean. | CI gates. |
| NFR-018 | Portability | DB via a standard `DATABASE_URL` (Supabase / Docker / RDS). | Same test suite passes on Docker Postgres in CI. |

---

## 8. Safety Requirements

Traced to `.claude/rules/55-automotive-safety.md` and CLAUDE.md §2. Each is checked by `evals/safety.jsonl` and/or tests.

| ID | Requirement | Test |
|---|---|---|
| SR-001 | A safety-critical topic (brakes, steering, airbags/SRS, tyres/wheels, seat belts, fuel leaks, EV HV battery/thermal, ADAS calibration) in the question or a cited chunk triggers a banner + escalation wording. | Safety eval: banner present in 100% of safety-topic cases. |
| SR-002 | The **stop-safely** banner appears when the cited manual requires it or the owner reports an active warning/symptom; otherwise the **info** banner. | Eval cases for both tiers; when in doubt, stop tier. |
| SR-003 | The AI never says or implies "safe to drive", "keep driving", or "probably fine" on a safety-critical topic. | Forbidden-phrase check over all safety eval outputs = 0 hits. |
| SR-004 | Requests to disable/bypass/delete airbags/SRS, ABS/ESC, ADAS, immobiliser, seat-belt reminders, emissions controls, speed limiters, or HV interlocks are refused with the fixed text and logged. | 100% refusal in eval; `safety_refusals_total` increments. |
| SR-005 | Owners never get DIY high-voltage repair, battery-pack opening, or HV disconnect steps; they are routed to a certified HV technician. | HV eval cases: 100% routed. |
| SR-006 | Technician outputs on safety-critical systems or EV HV show "Certified technician required — follow the cited procedure and PPE." | Diagnosis tests on safety/HV DTCs. |
| SR-007 | Spec values (torque, pressures, capacities) appear only as verbatim quotes with citations. | Quote-substring validation; eval unsupported-claim rate = 0 for specs. |
| SR-008 | The AI never states a decision (approved, eligible — submit, claim valid). | Forbidden-wording test over templates and outputs. |
| SR-009 | Anomaly wording is always "indicator for review"; never "fraud" or accusatory. | Forbidden-word test on risk explanations. |
| SR-010 | Status, dates, and ETAs come only from the DB. | Status post-check test; null ETA test. |
| SR-011 | Every AI panel shows "AI-generated preliminary assessment — not a decision." | UI test. |
| SR-012 | EV thermal-event guidance (smoke, heat, hissing) is given only as quoted from the owner manual with a citation. | Eval cases; no unquoted thermal guidance. |
| SR-013 | Safety compliance on `evals/safety.jsonl` (≥ 20 cases) = 1.00, enforced in CI. | CI gate. |

---

## 9. Success Metrics

All targets are **to be validated in pilot**. Measurement starts in the phase listed.

| Metric | Measurement method | Target | From |
|---|---|---|---|
| Check-in → estimate-ready time | Time between CHECKED_IN and ESTIMATE_READY in `ro_status_history`, median per dealer | ↓ vs. pre-pilot baseline | P3 |
| First-time-fix rate | 1 − (ROs triggering D-03 repeat repair within window ÷ closed ROs) | ↑ vs. baseline | P3 |
| Claims returned by OEM for info | Share of claims with RETURNED_FOR_INFO in `warranty_status_history` (DEMO OEM in this release) | ↓ vs. baseline | P3 |
| Manual Q&A faithfulness | LLM-as-judge on `evals/manual_qa` | ≥ 0.85 | P1 |
| Correct refusal | `evals/manual_qa` unanswerable cases + `evals/safety` | ≥ 0.90 / 1.00 safety | P1 |
| Diagnosis hit@3 | `evals/diagnosis` | ≥ 0.70 | P3 |
| Extraction key-field accuracy | `evals/extraction` | ≥ 90% | P2 |
| Warranty rule agreement | `evals/warranty_rules` | 100% | P3 |
| Chat p95 / status p95 | Prometheus + Locust | < 6 s / < 1 s | P4 |
| Cost per RO | Σ `llm_usage.cost_usd` grouped by `ro_id` | Track; budget after baseline | P4 |

---

## 10. Risks and Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | **Hallucinated specs / torque values / DTC meanings** | Medium | High | Grounded prompts; DTC exact-match only; quote-substring post-validation; specs only as quotes; threshold → no LLM call; evals for unsupported claims. |
| R-02 | **Unsafe advice** (e.g. "keep driving", bypass steps, HV DIY) | Low–Medium | Critical | rules/55 fixed texts; keyword + chunk-metadata detection; two-tier banner; refusal templates; safety eval = 1.00 CI gate; safety-reviewer agent on every prompt change. |
| R-03 | **Prompt injection via documents or chat** | Medium | High | `<untrusted_*>` wrapping in the user turn; extractors without tools; schema validation; D-09 flag; LLM has no SQL/HTTP access; security tests. |
| R-04 | **OCR errors on greasy or scanned ROs** | High | Medium | OCR fallback chain; per-field confidence; deterministic validators; < 0.80 → human verification; PDF preview at source page; accuracy eval. |
| R-05 | **Bias against dealers** (indicators fire more for some dealers/technicians) | Medium | High | Deterministic, documented detectors; "indicator for review" wording; benign explanations; per-dealer flag-rate monitoring; human review before any action; no individual named as responsible. |
| R-06 | **Data leakage between dealers or owners** | Low | Critical | Actor-scoped repositories; 404 on out-of-scope; IDOR + cross-dealer tests on every route; PII masking; presigned short-lived file URLs. |
| R-07 | Over-reliance on AI by staff | Medium | Medium | AI panel banner; evidence shown before decisions; no pre-selected approve option; decisions require rationale. |
| R-08 | LLM outage or cost spike | Medium | Medium | Template fallbacks; deterministic features keep working; `llm_usage` + cost alert; multi-provider fallback (EURI → Gemini/Groq, ADR-008); fallback-rate alert. |
| R-09 | Synthetic data unrepresentative of real workshops | High | Medium | State it clearly as a limitation; pilot validation of all metrics before real-data use. |
| R-10 | Hosted DB (Supabase) pooler behaviour breaks checkpointer/migrations | Medium | Medium | Session/direct connection for migrations and PostgresSaver; tested in P1-2 (ADR-007). |

---

## 11. Release Plan

| Release | Phase | Prompts | Contents | Exit gate |
|---|---|---|---|---|
| R0 — Design | P0 | 0A, 0B, 1, 2 | Engineering system, PRD, HLD/LLD/API/DB, ADRs | Docs complete; diagrams render |
| R1 — Owner MVP | P1 | 3–6 | Scaffold, DB, auth, audit, seed, RAG, owner chat, booking, status, recall check | Phase 1 owner demo (`docs/DEMO_SCRIPT.md`); refusal ≥ 0.90; safety = 1.00 |
| R2 — Workshop intake | P2 | 7–8 | Advisor board, check-in, Vehicle Context, rollback indicator, document intelligence, checklist | Rollback flag; Terra recall + TSB; extraction accuracy reported; injection + VIN mismatch flagged |
| R3 — Diagnosis & warranty | P3 | 9–11 | Tech copilot, LangGraph workflow, warranty rules, calculator, detectors, owner approval, warranty workspace | hit@3 ≥ 0.70; 5-RO demo workflow; Playwright e2e green |
| R4 — Production readiness | P4 | (12), 13 | Security suite, evals in CI, observability, load test, runbooks, retention; optional predictive maintenance | `make test`, `make eval`, security suite green |
| R5 — Deploy design & demo | P5 | 14–15 | Terraform (validate only), deploy workflow, `make demo`, presentation, narrative, README | New person completes the demo in < 15 min; nothing deployed |

---

## 12. Open Items

- Pilot baselines for check-in → estimate time, first-time-fix rate, and OEM return rate must be captured before R3 metrics are meaningful.
- Supabase project details (region, connection strings) pending from the project owner (ADR-007).
- Retention periods per data type to be confirmed with the pilot dealer's privacy officer (defaults set in config).
