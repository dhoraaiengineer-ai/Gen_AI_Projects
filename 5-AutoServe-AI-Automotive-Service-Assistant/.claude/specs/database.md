# Spec — Database

> Full erDiagram goes in `docs/DB_SCHEMA.md` (Prompt 2). This spec fixes the table list, PII columns, key constraints,
> and relationships. Conventions: UUID PK `id`, `created_at`, `updated_at` (timestamptz). **PII** = masked in logs, covered by retention.

## Tables

| Table | Key columns | PII | Notes |
|---|---|---|---|
| `dealers` | name, code, labour_rate (NUMERIC), tax_profile, timezone | — | Labour rate per dealer (config-seeded) |
| `roles` | name (enum of 5) | — | Static |
| `users` | email, display_name, phone, role_id → roles, dealer_id → dealers (nullable for owner/admin), password_hash (DEMO), oidc_sub | **email, display_name, phone** | Soft delete |
| `vehicle_models` | name (Aria/Terra/Volt), powertrain (petrol/diesel/bev), vds_code, model_years[], plant_codes | — | VIN decode catalogue |
| `vehicles` | vin (unique), owner_id → users, model_id, model_year, plant_code, plate_number, in_service_date, last_odometer_km | **vin, plate_number** | Soft delete |
| `service_history` | vehicle_id, dealer_id, service_date, odometer_km, op_codes[], notes, source (seed/RO) | — | Read by D-01, maintenance due |
| `recalls` | campaign_code, title, component_group, part_numbers[], remedy_op_code, source_chunk_id, status | — | |
| `recall_vin_ranges` | recall_id, model_id, model_year_from/to, vin_serial_from/to | — | Inclusive bounds |
| `tsbs` | tsb_code, title, model_id, model_year_from/to, vin_serial_from/to, dtcs[], symptom_keywords[], op_code, source_chunk_id | — | |
| `knowledge_documents` | source_file, doc_type, model, version, sha256, visibility, ingested_at | — | |
| `knowledge_chunks` | document_id, content, content_hash (unique), embedding vector(1536), tsv tsvector, metadata jsonb (rules/50 fields) | — | HNSW + GIN |
| `appointments` | vehicle_id, dealer_id, slot_start, slot_end, status, idempotency_key | — | DEMO capacity table `dealer_capacity` |
| `repair_orders` | ro_ref (seq, unique), vehicle_id, dealer_id, appointment_id, status, odometer_in_km, fuel_or_charge_level, damage_notes, cancel_reason, graph_thread_id, promised_ready_at (nullable; set only by service_advisor — the only ETA source, OD-08) | damage_notes (free text) | |
| `ro_status_history` | ro_id, from_status, to_status, actor_id, actor_role, reason, created_at | — | Written by `transition()` only |
| `ro_complaints` | ro_id, complaint_text (owner's words), confirmed_by_advisor | **complaint_text** (free text) | |
| `diagnostic_findings` | ro_id, technician_id, dtcs[], symptoms, test_results jsonb, confirmed_hypothesis, op_codes_performed[], actual_hours, parts_used jsonb | — | Feedback for evals |
| `documents` | ro_id, storage_key, mime, size_bytes, pages, sha256, doc_class, av_status, uploaded_by | — | File contents may hold PII |
| `extracted_fields` | document_id, name, value, confidence, source_page, validation_status, needs_human_verification, edited_by, edit_reason, previous_value | value may be PII (VIN, name) | |
| `checklist_items` | ro_id/claim_id, item_code, status (present/missing/unreadable/inconsistent), source_chunk_id | — | |
| `labour_ops` | op_code, description, model_id, flat_rate_hours NUMERIC(6,2), source_file | — | Loaded from `labour_time_guide.csv` |
| `parts` | part_number, description, unit_price NUMERIC(12,2), component_group, source_file | — | Loaded from `parts_price_list.csv` |
| `estimate_lines` | ro_id, kind, op_code/part_number, qty, hours, unit_price, amount, pay_type, owner_decision (approved/declined/null) | — | Amounts from calculator only |
| `warranty_claims` | claim_ref (seq WC-), ro_id, dealer_id, status, component_group, failed_part_number, total_claimed, oem_ack jsonb (DEMO) | — | |
| `warranty_status_history` | claim_id, from_status, to_status, actor_id, actor_role, reason | — | |
| `warranty_findings` | claim_id, rule_id, result, inputs jsonb, source_chunk_id, explanation | — | |
| `risk_flags` | ro_id/claim_id, detector_id, severity, evidence jsonb, explanation, status (open/reviewed/dismissed), reviewed_by | — | Wording: "indicator for review" |
| `review_decisions` | ro_id/claim_id, kind, actor_id, actor_role, decision, rationale, line_decisions jsonb, evidence_snapshot_hash, idempotency_key | — | |
| `notifications` | user_id, channel (sms/email/in_app), template, payload jsonb, status, adapter ("DEMO") | payload may hold PII | |
| `conversations` | user_id, vehicle_id?, channel, started_at | — | |
| `messages` | conversation_id, role (user/assistant/tool), content, citations jsonb, safety_critical, intent | **content** (free text) | Retention |
| `llm_usage` | request_id, trace_id, ro_id?, node, purpose, chain (agent|answer), fallback_index, model, provider, input/output/cache tokens, cost_usd, latency_ms, outcome | — | |
| `audit_log` | seq (bigserial), occurred_at, actor_id, actor_role, action, entity_type, entity_id, payload jsonb (masked), prev_hash, hash | — | INSERT-only, trigger, hash chain |
| `idempotency_keys` | key, actor_id, route, request_hash, response jsonb, expires_at | — | Supports Idempotency-Key |
| `config_versions` | name, version, yaml_content, sha256, change_note, changed_by, active | — | Versioned admin config (rules, checklists, intents, safety keywords) |
| `dealer_capacity` | dealer_id, date, slot, capacity, booked | — | DEMO |
| `maintenance_alerts` (P4-0 optional) | vehicle_id, signal, window, score, recommended_section_chunk_id | — | |

**Supabase lockdown (migration b7c1d2e3f405, MEMORY L-004):** every public table has RLS enabled with no policies, and `anon`/`authenticated` hold no privileges. New tables must enable RLS too.

LangGraph `PostgresSaver` creates its own checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) in schema `langgraph`.

## Relationships (summary)
`dealers 1─* users(staff)`, `users(owner) 1─* vehicles`, `vehicle_models 1─* vehicles`, `vehicles 1─* service_history`,
`vehicles 1─* appointments 1─1 repair_orders`, `dealers 1─* repair_orders`, `repair_orders 1─* {ro_status_history, ro_complaints,
diagnostic_findings, documents, estimate_lines, risk_flags, review_decisions, checklist_items}`, `documents 1─* extracted_fields`,
`repair_orders 1─* warranty_claims 1─* {warranty_status_history, warranty_findings}`, `recalls 1─* recall_vin_ranges`,
`knowledge_documents 1─* knowledge_chunks`, `users 1─* conversations 1─* messages`.

## Sequences
`ro_ref_seq`, `claim_ref_seq` → formatted `RO-{YYYY}-{000000}` / `WC-{YYYY}-{000000}` in a DB function.

## Retention defaults (config `RETENTION_DAYS_*`, to be confirmed in PRD)
messages · notifications payload · extracted_fields values · documents · llm_usage · audit_log (longest; never deleted by the app job).
