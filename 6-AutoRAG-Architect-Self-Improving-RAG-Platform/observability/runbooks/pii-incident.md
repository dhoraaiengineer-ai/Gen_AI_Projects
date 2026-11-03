# Runbook: PII Incident (Unmasked PII Detected)

**Alert**: Custom — triggered by PII detection audit log entries
**Severity**: Critical (compliance)
**Auto-rollback**: Immediate — pipeline blocked until PII path audited
**Owner**: Team 7 (PII Masking) + Team 8 (Security/Compliance)

---

## Trigger Conditions

- `audit_log` entry with `event_type = guardrail_blocked` and a PII-related
  `guardrail_block_reason` (the real 14 `APPROVED_EVENT_TYPES` in
  `app/models/audit_log.py` have no dedicated `pii_detected` type — masking
  failures surface via the guardrail pipeline's block event; a successful
  redaction is the separate `pii_redacted` event)
- `GraphState` checkpoint contains raw email, phone, access token, or credential
- Guardrail Rule 6 (`ai-guardrails.md`) fires: PII enters LangGraph state unmasked

---

## Symptoms

- `/security` dashboard shows PII Detections with `masked=false` column
- Ingestion Agent logs: `[WARN] PII detected in chunk BEFORE masking`
- Evaluation runs failing with `guardrail_blocked=True` and `guardrail_block_reason: pii_in_state`
- Supabase Vector rows contain un-anonymized content (email `@` or phone patterns)

---

## Immediate Containment (Do First)

### Step 1 — Block the affected pipeline
There is no dedicated pause endpoint or "paused" `PipelineStatus` value in the
real backend (`PipelineStatus` is `draft | pending | running | ready | failed
| decommissioned` — `app/models/pipeline.py`). The real, available emergency
containment action is the soft-delete route (never hard-deletes; sets
`deleted_at` — `app/services/pipeline_service.py`), which stops the pipeline
from being selectable for any further evaluation/deploy dispatch:
```bash
curl -X DELETE http://localhost:8000/api/v1/pipelines/{pipeline_id} \
  -H "X-Trace-ID: <x_trace_id>"
```

### Step 2 — Identify scope
```sql
-- Find guardrail blocks with a PII-related reason (see Trigger Conditions above --
-- there is no dedicated pii_detected event type; guardrail_blocked is the real one)
SELECT id, run_id, payload, created_at
FROM audit_log
WHERE event_type = 'guardrail_blocked'
  AND payload->>'guardrail_block_reason' ILIKE '%pii%'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

### Step 3 — Isolate affected chunk rows
Version 4.0 (migration 0016) replaced per-pipeline-version physical tables
with a single shared `pipeline_chunks` table, partitioned by
`pipeline_version_id` + `organization_id` (see `docs/DB_SCHEMA.md` addendum
"Immutable Versioned Indexes") — there is no longer a per-pipeline table to
rename. Quarantine by marking the affected version's rows unqueryable at the
application layer (never delete — Rule 30 soft-delete discipline) rather than
a table-level rename:
```sql
-- Identify the affected version's row scope first
SELECT pipeline_version_id, organization_id, COUNT(*)
FROM pipeline_chunks
WHERE pipeline_version_id = '<affected_pipeline_version_id>'
GROUP BY pipeline_version_id, organization_id;
```
Then roll back the pipeline to a prior, unaffected version via
`POST /api/v1/pipelines/{pipeline_id}/rollback` (real, reversible — never
touches vector rows directly) so the affected version's rows are no longer
served, while a fix is developed for permanently removing them.

---

## Diagnosis Steps

### Step 4 — Trace the PII entry point
Check the Ingestion Agent node in the execution trace:
```bash
curl http://localhost:8000/api/v1/jobs/{job_id}
# Look for execution_trace[0].node = "ingestion" and status = "success"
# If PII was detected AFTER ingestion, the masking step was bypassed
```

### Step 5 — Identify the PII type
The real `audit_log` column is `payload` (JSONB, GIN-indexed), not `metadata`.
From `audit_log.payload`:
- `email` — email address leaked
- `phone` — phone number leaked
- `credential` — API key or token leaked
- `name` — personal name leaked

### Step 6 — Verify masking functions
The canonical PII masking function is `app.guardrails.input.pii_detector.mask_pii()`
(a thin async wrapper over the pure-Python engine in `app.services.pii_engine`):
```python
from app.guardrails.input.pii_detector import mask_pii
# Verify this is called BEFORE any Supabase write
```

---

## Resolution

| Issue | Action |
|-------|--------|
| Masking function not called | Add `mask_pii()` / `mask_pii_with_counts()` call (`app/guardrails/input/pii_detector.py`) before `builder` node write |
| Masking pattern missed new PII type | Update PII regex in `security/guardrails/policies/pii-policy.md` |
| PII in checkpoints | Clear LangGraph `checkpoints` table entries for the affected `thread_id` |
| PII in `pipeline_chunks` | Roll back to a prior version (Step 3 above), fix masking, then re-ingest as a new version — never delete the affected rows directly (Rule 30 soft-delete discipline) |

---

## Escalation

- Any PII breach: Notify Mahesh Kumar immediately
- If customer PII: Notify legal/compliance team within 1 hour
- If credentials leaked: Rotate all API keys immediately (AWS Secrets Manager)

---

## Post-Incident

1. Write `audit_log` entry: `event_type = pii_redacted` (the real approved type
   for successful redaction evidence — there is no dedicated `*_resolved` event
   type) with scope, resolution, reviewer in the `payload`
2. Update `security/guardrails/policies/pii-policy.md` with new PII pattern if applicable
3. Add PII type to `security/guardrails/test-datasets/adversarial-qa.json` test set
4. Run full re-ingestion of affected pipeline with masking verified
5. Confirm `PII_MASKING_ENABLED=true` in all non-local environments
