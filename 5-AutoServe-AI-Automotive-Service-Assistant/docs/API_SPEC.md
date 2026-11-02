# AutoServe AI — API Specification

| | |
|---|---|
| **Version** | 1.0 · 2026-10-26 · task P0-4 |
| **Base URL** | `/api/v1` (health routes at root) |
| **Spec source** | `.claude/specs/api-design.md` |
| **Format** | JSON, UTF-8. Timestamps ISO 8601 UTC. Money as **decimal strings** (`"123.45"`). IDs are UUIDs. |

Schemas are written in a TypeScript-like notation. `?` = optional; `|` = enum. Pydantic models mirror these names.

---

## 1. Conventions

### 1.1 Envelope

```ts
type Envelope<T> = {
  status: "ok" | "error";
  data: T | null;
  error: { code: ErrorCode; message: string; details?: Record<string, unknown> } | null;
  request_id: string;
};
```

### 1.2 Headers

| Header | Direction | Use |
|---|---|---|
| `Authorization: Bearer <jwt>` | request | All routes except public ones |
| `Idempotency-Key: <uuid>` | request | Required on POSTs marked **(idem)**. Same key + same body → stored response replayed; same key + different body → `409 IDEMPOTENCY_CONFLICT` |
| `X-Request-ID` | response | Same as `request_id` |
| `traceparent` | both | W3C trace context |

### 1.3 Pagination

List endpoints accept `?limit=` (default 25, max 100) and `?cursor=`. They return `{ items: T[], next_cursor: string | null }`.

### 1.4 Shared types

```ts
type Role = "vehicle_owner" | "service_advisor" | "technician" | "warranty_admin" | "admin";
type ROStatus = "DRAFT" | "BOOKED" | "CHECKED_IN" | "DIAGNOSING" | "INFO_PENDING" | "ESTIMATE_READY"
  | "AWAITING_OWNER_APPROVAL" | "APPROVED" | "DECLINED" | "IN_REPAIR" | "QUALITY_CHECK"
  | "READY_FOR_PICKUP" | "CLOSED" | "CANCELLED";
type ClaimStatus = "DRAFT" | "PREPARED" | "WARRANTY_REVIEW_REQUIRED" | "SUBMITTED_TO_OEM"
  | "OEM_ACCEPTED" | "OEM_REJECTED" | "RETURNED_FOR_INFO" | "REJECTED_BY_DEALER";
type Citation = { chunk_id: string; source_file: string; page: number; section_id: string; quote: string };
type SafetyInfo = { safety_critical: boolean; banner_tier: "none" | "info" | "stop" | "technician" };
type Money = string;   // decimal, 2 dp
type MaskedVin = string; // "***" + last 6, used in list views
type StatusEvent = { from_status: string | null; to_status: string; at: string; actor_role: Role | "system"; reason?: string };
```

---

## 2. Error Codes

| HTTP | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Schema/field validation failed (`details.fields`) |
| 400 | `INVALID_VIN` | Format or check digit invalid |
| 400 | `INVALID_DTC` | Not `^[PBCU][0-9A-F]{4}$` |
| 401 | `UNAUTHENTICATED` | Missing/invalid/expired token |
| 403 | `FORBIDDEN_ROLE` | Role not permitted (resource in scope) |
| 404 | `NOT_FOUND` | Missing **or** outside the actor's scope |
| 409 | `INVALID_TRANSITION` | State machine rejected from→to (`details.from`, `details.to`) |
| 409 | `IDEMPOTENCY_CONFLICT` | Key reused with a different body |
| 409 | `ODOMETER_REGRESSION` | Booking odometer < last recorded |
| 409 | `SLOT_UNAVAILABLE` | DEMO capacity full (`details.alternatives`) |
| 413 | `FILE_TOO_LARGE` | > 10 MB or > 20 pages |
| 415 | `UNSUPPORTED_MEDIA` | Not PDF/JPG/PNG or magic-byte mismatch |
| 422 | `NOT_ESTIMABLE` | Calculator inputs missing (`details.missing`) |
| 422 | `RATIONALE_REQUIRED` | Decision/cancel/consent/field edit without reason |
| 429 | `RATE_LIMITED` | Rate limit exceeded (`Retry-After`) |
| 502 | `LLM_UNAVAILABLE` | Provider failed after retries; safe fallback message in `error.message` |
| 503 | `NOT_READY` | Dependency unavailable |
| 500 | `INTERNAL_ERROR` | Unexpected; no internals |

---

## 3. Endpoints

Role legend: O owner · SA service_advisor · T technician · WA warranty_admin · AD admin · P public.

### 3.1 Health

| | |
|---|---|
| `GET /health` (P) | `200 {status:"ok"}`. Liveness, no dependency checks |
| `GET /ready` (P) | `200 {db:"ok", storage:"ok", llm_config:"ok"}`, or `503 NOT_READY` |

### 3.2 Auth

**`POST /auth/login`** (P, rate-limited) — DEMO only (`AUTH_MODE=demo`)
```ts
req:  { email: string; password: string }
res:  { access_token: string; token_type: "bearer"; expires_in: number; user: Me }
errs: VALIDATION_ERROR, UNAUTHENTICATED (uniform message), RATE_LIMITED
```
**`GET /auth/me`** (all)
```ts
type Me = { id: string; display_name: string; role: Role; dealer_id: string | null; dealer_name?: string }
```

### 3.3 Chat

**`POST /chat/messages`** (O) — streamed via SSE when `Accept: text/event-stream`
```ts
req: { conversation_id?: string; vehicle_id?: string; text: string /* ≤ 2000 chars */ }
res: {
  conversation_id: string;
  intent: "manual_question" | "book_service" | "ro_status" | "recall_check" | "warranty_question"
        | "upload_help" | "smalltalk" | "out_of_scope";
  reply: string;
  citations: Citation[];
  safety: SafetyInfo;
  booking_draft?: AppointmentDraft;        // when intent = book_service
  next_question?: string;                  // one missing field at a time
  ro_status?: ROStatusOut;                 // when intent = ro_status
  recalls?: RecallOut[];                   // when intent = recall_check
  insufficient_evidence?: boolean;
}
SSE events: "token" {text} · "meta" {intent, safety} · "final" {Envelope<res>}
errs: VALIDATION_ERROR, RATE_LIMITED, LLM_UNAVAILABLE
```
```ts
type AppointmentDraft = { vehicle_id?: string; odometer_km?: number; complaint_text?: string;
  preferred_slot?: { start: string; end: string }; missing_fields: ("vehicle"|"odometer"|"complaint"|"slot")[] }
```

**`POST /chat/manual-question`** (O, SA, T)
```ts
req: { question: string; vehicle_id?: string; model?: "Aria"|"Terra"|"Volt"; model_year?: number }
     // owners: vehicle_id required; model/year derived from VIN. Staff may pass model + model_year.
res: { answer: string; citations: Citation[]; confidence: number; insufficient_evidence: boolean;
       safety: SafetyInfo; required_action_quote?: Citation }
errs: VALIDATION_ERROR, NOT_FOUND (vehicle), LLM_UNAVAILABLE
```

### 3.4 Vehicles

**`GET /vehicles`** (O own · SA/T/WA vehicles with ROs at their dealer)
```ts
res: Page<{ id: string; vin_masked: MaskedVin; model: string; model_year: number; plate_masked?: string;
            open_recall_count: number; last_odometer_km: number | null }>
```
**`GET /vehicles/{id}`** (O own · staff in scope)
```ts
res: { id; vin: string /* full VIN only for the owner and in-scope staff */; decoded: DecodedVin; model; model_year;
       in_service_date: string | null; last_odometer_km: number | null; plate_number?: string }
type DecodedVin = { wmi: "VLX"; model: string; model_year: number; plant: string; serial: string }
```
**`GET /vehicles/{id}/recalls`** (O own · staff)
```ts
res: { items: RecallOut[] }
type RecallOut = { campaign_code: string; title: string; component_group: string; status: "open"; notice: Citation }
```
**`GET /vehicles/{id}/context?ro_id=`** (SA, T, WA)
```ts
res: VehicleContextOut = {
  decoded: DecodedVin; in_service_date: string | null;
  service_history: { date: string; odometer_km: number; op_codes: string[]; dealer_name: string }[];  // ≤ 10
  maintenance_due: { item: string; due_at_km?: number; due_at_date?: string; overdue_by?: string; source: Citation }[];
  open_recalls: RecallOut[];
  applicable_tsbs: { tsb_code: string; title: string; match_reason: "dtc" | "keyword"; op_code: string; source: Citation }[];
  warranty_coverage: { coverage: string; end_date: string | null; km_remaining: number | null; status: "active"|"expired"|"unknown"; source: Citation }[];
  risk_flags: RiskFlagOut[];
}
```

### 3.5 Appointments

**`POST /appointments`** (O, SA) **(idem)**
```ts
req: { vehicle_id: string; odometer_km: number; complaint_text: string; slot_start: string; dealer_id: string }
res: { appointment_id: string; ro_id: string; ro_ref: string; status: "BOOKED"; slot_start: string; slot_end: string }
errs: VALIDATION_ERROR, NOT_FOUND (vehicle not owned), ODOMETER_REGRESSION, SLOT_UNAVAILABLE, IDEMPOTENCY_CONFLICT
```
**`GET /appointments?date=YYYY-MM-DD`** (SA; own dealer)
```ts
res: Page<{ appointment_id; ro_id; ro_ref; slot_start; vehicle: { model; model_year; vin_masked };
            owner_display_name: string; complaint_text: string; ro_status: ROStatus }>
```
**`GET /appointments/slots?dealer_id=&from=&to=`** (O, SA) — DEMO capacity
```ts
res: { slots: { start: string; end: string; available: number }[]; adapter: "DEMO" }
```

### 3.6 Repair Orders

**`GET /repair-orders?status=&from=&to=`** (O own · staff dealer)
```ts
res: Page<{ id; ro_ref; status: ROStatus; vehicle: { id; model; model_year; vin_masked }; created_at; updated_at }>
```
**`GET /repair-orders/{id}`** (O own · staff)
```ts
res: { id; ro_ref; status: ROStatus; dealer: { id; name }; vehicle: { id; model; model_year; vin_masked };
       complaint: { text: string; confirmed_by_advisor: boolean };
       check_in?: { odometer_in_km: number; fuel_or_charge_level: string; damage_notes: string };
       promised_ready_at: string | null; timeline: StatusEvent[];
       claims: { id; claim_ref; status: ClaimStatus }[]; allowed_actions: string[] /* for the caller's role */ }
```
**`GET /repair-orders/{id}/status`** (O own · staff)
```ts
res: ROStatusOut = { ro_ref: string; ro_status: ROStatus; history: StatusEvent[];
                     claim_status?: { claim_ref: string; status: ClaimStatus };
                     eta: string | null /* only promised_ready_at */; phrased: string }
```
**`POST /repair-orders/{id}/check-in`** (SA) **(idem)**
```ts
req: { odometer_in_km: number; fuel_or_charge_level: string; damage_notes: string; complaint_confirmed: boolean;
       complaint_text_edit?: string }
res: { ro: { id; status: "CHECKED_IN" }; vehicle_context: VehicleContextOut }
errs: INVALID_TRANSITION, FORBIDDEN_ROLE, NOT_FOUND
```
**`POST /repair-orders/{id}/transition`** (SA, T per LLD §3 table) **(idem)**
```ts
req: { to: ROStatus; reason?: string; note?: string; promised_ready_at?: string }
res: { id; status: ROStatus; history_entry: StatusEvent }
errs: INVALID_TRANSITION, FORBIDDEN_ROLE, RATIONALE_REQUIRED
```
**`PATCH /repair-orders/{id}`** (SA) — non-status fields only
```ts
req: { promised_ready_at?: string | null; damage_notes?: string }
```
**`POST /repair-orders/{id}/estimate/send`** (SA) **(idem)** — ESTIMATE_READY → AWAITING_OWNER_APPROVAL
```ts
res: { status: "AWAITING_OWNER_APPROVAL"; notification_id: string }
```
**`GET /repair-orders/{id}/estimate`** (O own · staff)
```ts
res: EstimateOut = {
  estimable: boolean; not_estimable_reason?: string[];
  lines: { id; kind: "labour"|"part"|"tax"; op_code?: string; part_number?: string; description: string;
           qty: string; hours?: string; unit_price: Money; amount: Money;
           pay_type: "warranty"|"recall"|"customer"; display_status: "decision_needed"|"pending_warranty_review"|"recall";
           owner_decision: "approved"|"declined"|null; reasons: Citation[] }[];
  totals: { customer: Money; warranty: Money; recall: Money; tax: Money; grand: Money };
  summary: string; ai_label: "AI-generated preliminary assessment — not a decision."
}
```
**`POST /repair-orders/{id}/estimate/decision`** (O own; SA with consent_note) **(idem)**
```ts
req: { line_decisions: { line_id: string; decision: "approved"|"declined" }[]; approve_all?: boolean;
       consent_note?: string /* required for SA */ }
res: { status: "APPROVED" | "DECLINED"; decision_id: string; replayed: boolean }
// Resumes the RO graph's estimate_approval interrupt (agent spec 09). ≥ 1 approved customer line → APPROVED.
errs: INVALID_TRANSITION, RATIONALE_REQUIRED, VALIDATION_ERROR (non-customer line), FORBIDDEN_ROLE
```
**`POST /repair-orders/{id}/workflow/run`** (SA) **(idem)** — runs entrypoint `warranty`
```ts
res: { thread_id: string; route: "info_pending" | "recall_job" | "human_review"; reasons: string[];
       ro_status: ROStatus; waiting_for: "estimate_approval" | null; claim?: { id; claim_ref; status: ClaimStatus };
       trace: TraceEntry[]; replayed: boolean }
// RO must be DIAGNOSING / INFO_PENDING / ESTIMATE_READY. A thread already waiting at human_review is returned as is.
```
**`POST /repair-orders/{id}/recall-job`** (SA) **(idem)** — advisor confirms a recall job recommendation
```ts
req: { recall_campaign_code: string; note: string }
res: { estimate_lines_updated: number }
```
**`GET /repair-orders/{id}/audit`** (SA, WA)
```ts
res: Page<{ seq: number; occurred_at; actor_role; action; entity_type; entity_id; summary: string }>
```

### 3.7 Documents

**`POST /repair-orders/{id}/documents`** (SA, T, O own: classes service_record|odometer_photo|inspection_photo) **(idem)**
`multipart/form-data`: `file` (PDF/JPG/PNG ≤ 10 MB, ≤ 20 pages), `declared_class?`
```ts
res: { document_id: string; status: "queued"; sha256: string }
errs: FILE_TOO_LARGE, UNSUPPORTED_MEDIA, FORBIDDEN_ROLE, NOT_FOUND
```
**`GET /repair-orders/{id}/documents`** (O own · staff)
```ts
res: { items: { id; doc_class: string; pages: number; status: "queued"|"processing"|"done"|"failed";
                needs_human_verification: boolean; uploaded_at: string }[];
       checklist: { missing: string[]; unreadable: string[]; inconsistent: string[]; source: Citation } }
```
**`GET /documents/{id}`** (staff · O own)
```ts
res: { id; doc_class; pages; fields: { id; name; value: string | null; confidence: number; source_page: number;
       validation_status: "ok"|"failed"|"not_checked"; needs_human_verification: boolean }[]; risk_flags: RiskFlagOut[] }
```
**`GET /documents/{id}/file?page=`** (staff · O own) → `{ url: string; expires_in: number }` (presigned, short TTL)

**`PATCH /documents/{id}/fields/{field_id}`** (SA, WA)
```ts
req: { value: string; reason: string }
res: { id; value; previous_value; edited_by; validation_status }
errs: RATIONALE_REQUIRED, VALIDATION_ERROR
```

### 3.8 Diagnosis

**`POST /repair-orders/{id}/diagnosis`** (T)
```ts
req: { dtcs: string[] /* ≤ 20 */; symptoms: string; freeze_frame_notes?: string;
       test_results?: { name: string; value: string; unit?: string }[] }
res: DiagnosisResult = {
  dtc_meanings: { code: string; meaning_quote: Citation | null; not_found: boolean }[];  // exact match only
  hypotheses: { rank: number; cause: string; evidence: string; citations: Citation[]; confidence: number;
                next_test: Citation | null }[];  // ≤ 5, each ≥ 1 verified citation; next_test null if not verifiable
  matched_tsbs: { tsb_code; title; op_code; match_reason: "dtc"|"keyword"; matched_terms: string[];
                  source: Citation | null }[];
  insufficient_evidence: boolean; safety: SafetyInfo; ai_label: string;
  refusal_reason: "bypass_request" | "no_evidence" | "service_unavailable" | null;
  dropped_hypotheses: number              // removed by post-validation (uncited, quote mismatch, spec value, cap)
}
errs: INVALID_DTC (details.invalid), INVALID_TRANSITION (RO not DIAGNOSING)
// LLM down → 200 with DTC meanings + matched TSBs only, insufficient_evidence=true, refusal_reason="service_unavailable".
// Bypass/disable request → 200, fixed refusal, no LLM call, audit action "safety.refusal".
```
**`POST /repair-orders/{id}/findings`** (T) **(idem)**
```ts
req: { confirmed_hypothesis: string; dtcs?: string[]; symptoms?: string;
       test_results?: { name: string; value: string; unit?: string }[]; op_codes_performed: string[];
       actual_hours: string; parts_used: { part_number: string; qty: string }[]; notes?: string }
res: { finding_id: string; replayed: boolean }
errs: VALIDATION_ERROR (details.unknown_op_codes / unknown_part_numbers), INVALID_DTC,
      INVALID_TRANSITION (RO not between DIAGNOSING and QUALITY_CHECK)
```
**`GET /repair-orders/{id}/findings`** (T, SA, WA)
```ts
res: { id; dtcs: string[]; confirmed_hypothesis; op_codes_performed: string[]; actual_hours: string | null;
       parts_used: { part_number; qty }[]; created_at }[]
```

### 3.9 Warranty

**`GET /warranty/claims?status=&model=&sort=risk_age`** (WA; SA read-only)
```ts
res: Page<{ id; claim_ref; status: ClaimStatus; ro_ref; model; model_year; risk_level: "low"|"medium"|"high";
            age_days: number; total_claimed: Money }>
```
**`GET /warranty/claims/{id}`** (WA; SA read-only) — workspace
```ts
res: { summary: { claim_ref; status; ro_ref; component_group; failed_part_number; total_claimed: Money; ai_label: string };
       vehicle_context: VehicleContextOut; diagnosis: DiagnosisResult & { technician_confirmation?: string };
       extracted_fields: DocumentFieldOut[]; warranty_rules: WarrantyOut; estimate: EstimateOut;
       risk_indicators: RiskFlagOut[]; audit_trail: AuditEntry[]; allowed_decisions: string[] }
type WarrantyOut = { findings: { rule_id: string; result: "pass"|"fail"|"unknown"; inputs: Record<string, unknown>;
                      clause: Citation }[]; overall: "eligible"|"not_eligible"|"partial"|"unknown"; explanation: string;
                      label: "Preliminary assessment" }
type RiskFlagOut = { id; detector_id: string; severity: "low"|"medium"|"high"; evidence: Record<string, unknown>;
                     explanation: string /* "indicator for review" */; status: "open"|"reviewed"|"dismissed" }
```
**`PATCH /warranty/claims/{id}`** (WA)
```ts
req: { field: "component_group" | "failed_part_number" | "notes"; value: string; reason: string }
```
**`POST /warranty/claims/{id}/return-message/draft`** (WA)
```ts
res: { draft: string; ai_label: string }   // never sent automatically
```
**`POST /warranty/claims/{id}/decision`** (WA) **(idem)**
```ts
req: { decision: "submit_to_oem" | "return_for_info" | "reject_by_dealer"; rationale: string;
       approved_message?: string /* required for return_for_info */ }
res: { status: ClaimStatus; decision_id: string; oem_ack?: { adapter: "DEMO"; reference: string; received_at: string } }
errs: FORBIDDEN_ROLE (incl. admin), RATIONALE_REQUIRED, INVALID_TRANSITION
```
**`POST /risk-flags/{id}/review`** (SA, WA)
```ts
req: { status: "reviewed" | "dismissed"; note: string }
```

### 3.10 Review

**`GET /review/pending`** (SA, WA)
```ts
res: { items: { kind: "estimate_approval" | "warranty_decision"; ro_ref: string; claim_ref?: string;
                waiting_since: string; reasons: string[] }[] }
```

### 3.11 Admin

**`POST /admin/knowledge`** (AD) — multipart `file` + `doc_type`, `model?`, `version`, `visibility`
```ts
res: { document_id: string; chunks_added: number; chunks_skipped_duplicate: number }
```
**`GET /admin/knowledge`** (AD) → `Page<{ id; source_file; doc_type; model; version; chunk_count; ingested_at }>`

**`GET /admin/config/{name}`** · **`PUT /admin/config/{name}`** (AD) — `name ∈ rules | document_checklists | intents | safety_keywords`
```ts
put req: { yaml: string; change_note: string }
put res: { version: number; valid: true }   // 422 VALIDATION_ERROR if any number lacks source_chunk_id/adr
```
**`GET /admin/users`** · **`POST /admin/users`** (AD)
```ts
post req: { email: string; display_name: string; role: Role; dealer_id?: string /* required for staff roles */ }
```
**`GET /admin/audit/verify`** (AD) → `{ intact: boolean; checked: number; first_broken_seq: number | null }`

### 3.12 Notifications and metrics

**`GET /notifications`** (all; own) → `Page<{ id; channel; template; created_at; status; adapter: "DEMO" }>`
**`GET /metrics`** — Prometheus. Internal network only (not routed through the public ALB).

---

## 4. Endpoint → Table Matrix

Every table below exists in `docs/DB_SCHEMA.md`. All mutating endpoints also write `audit_log`.

| Endpoint | Tables read | Tables written |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | users, roles, dealers | audit_log |
| `POST /chat/messages` | conversations, messages, vehicles, knowledge_chunks, knowledge_documents, repair_orders, ro_status_history, recalls, recall_vin_ranges, dealer_capacity | conversations, messages, llm_usage, audit_log |
| `POST /chat/manual-question` | vehicles, vehicle_models, knowledge_chunks, knowledge_documents | messages, llm_usage, audit_log |
| `GET /vehicles`, `GET /vehicles/{id}` | vehicles, vehicle_models, repair_orders, recalls, recall_vin_ranges | — |
| `GET /vehicles/{id}/recalls` | vehicles, recalls, recall_vin_ranges, knowledge_chunks | — |
| `GET /vehicles/{id}/context` | vehicles, vehicle_models, service_history, recalls, recall_vin_ranges, tsbs, risk_flags, repair_orders, knowledge_chunks | — |
| `POST /appointments` | vehicles, dealer_capacity, idempotency_keys | appointments, repair_orders, ro_complaints, ro_status_history, dealer_capacity, idempotency_keys, audit_log |
| `GET /appointments`, `/appointments/slots` | appointments, repair_orders, vehicles, users, ro_complaints, dealer_capacity | — |
| `GET /repair-orders`, `/{id}`, `/{id}/status` | repair_orders, ro_status_history, ro_complaints, vehicles, dealers, warranty_claims, warranty_status_history | llm_usage (status phrasing) |
| `POST /repair-orders/{id}/check-in` | repair_orders, vehicles, service_history, recalls, recall_vin_ranges, tsbs | repair_orders, ro_status_history, ro_complaints, risk_flags, idempotency_keys, audit_log |
| `POST /repair-orders/{id}/transition`, `PATCH /repair-orders/{id}` | repair_orders | repair_orders, ro_status_history, notifications, audit_log |
| `POST /repair-orders/{id}/estimate/send` | repair_orders, estimate_lines | repair_orders, ro_status_history, notifications, audit_log |
| `GET /repair-orders/{id}/estimate` | estimate_lines, labour_ops, parts, warranty_findings | — |
| `POST /repair-orders/{id}/estimate/decision` | estimate_lines, repair_orders | estimate_lines, review_decisions, repair_orders, ro_status_history, notifications, idempotency_keys, audit_log |
| `POST /repair-orders/{id}/workflow/run` | repair_orders, vehicles, documents, extracted_fields, diagnostic_findings, labour_ops, parts, service_history, recalls, recall_vin_ranges, warranty_claims | warranty_claims, warranty_status_history, warranty_findings, estimate_lines, risk_flags, checklist_items, repair_orders, ro_status_history, llm_usage, audit_log (+ langgraph checkpoints) |
| `POST /repair-orders/{id}/recall-job` | recalls, estimate_lines | estimate_lines, audit_log |
| `GET /repair-orders/{id}/audit` | audit_log | — |
| `POST /repair-orders/{id}/documents` | repair_orders | documents, extracted_fields, checklist_items, risk_flags, repair_orders, ro_status_history, llm_usage, audit_log |
| `GET /repair-orders/{id}/documents`, `GET /documents/{id}`, `/file` | documents, extracted_fields, checklist_items, risk_flags | — |
| `PATCH /documents/{id}/fields/{field_id}` | extracted_fields | extracted_fields, checklist_items, audit_log |
| `POST /repair-orders/{id}/diagnosis` | repair_orders, vehicles, knowledge_chunks, tsbs | llm_usage, audit_log |
| `POST /repair-orders/{id}/findings` | repair_orders, labour_ops, parts | diagnostic_findings, idempotency_keys, audit_log |
| `GET /repair-orders/{id}/findings` | repair_orders, diagnostic_findings | — |
| `GET /warranty/claims`, `/{id}` | warranty_claims, warranty_findings, warranty_status_history, risk_flags, estimate_lines, extracted_fields, documents, diagnostic_findings, repair_orders, vehicles, audit_log | — |
| `PATCH /warranty/claims/{id}` | warranty_claims | warranty_claims, audit_log |
| `POST /warranty/claims/{id}/return-message/draft` | warranty_claims, checklist_items | llm_usage, audit_log |
| `POST /warranty/claims/{id}/decision` | warranty_claims | warranty_claims, warranty_status_history, review_decisions, notifications, estimate_lines, idempotency_keys, audit_log |
| `POST /risk-flags/{id}/review` | risk_flags | risk_flags, audit_log |
| `GET /review/pending` | repair_orders, warranty_claims | — |
| `POST /admin/knowledge`, `GET /admin/knowledge` | knowledge_documents | knowledge_documents, knowledge_chunks, audit_log |
| `GET/PUT /admin/config/{name}` | config_versions | config_versions, audit_log |
| `GET/POST /admin/users` | users, roles, dealers | users, audit_log |
| `GET /admin/audit/verify` | audit_log | — |
| `GET /notifications` | notifications | — |
