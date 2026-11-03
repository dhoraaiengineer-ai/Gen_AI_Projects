# PII Detection & Masking Policy — AutoRAG v4.0

**Classification**: Internal — Security Governance
**Owner**: Team 8 (Compliance)
**Updated**: 21-Jul-2026

---

## Scope

This policy governs how Personally Identifiable Information (PII) is detected and masked in AutoRAG Architect. It applies to all data flows: user queries, document ingestion, LLM outputs, and LangGraph state objects.

---

## PII Categories Detected

| Category        | Pattern                              | Masked As      |
| --------------- | ------------------------------------ | -------------- |
| Email addresses | RFC 5322 format                      | `[EMAIL]`      |
| Phone numbers   | US formats (xxx-xxx-xxxx, etc.)      | `[PHONE]`      |
| SSN             | xxx-xx-xxxx                          | `[SSN]`        |
| Credit cards    | 13–16 digit sequences                | `[CREDIT_CARD]`|
| Street addresses| Standard US street format            | `[ADDRESS]`    |

Custom patterns can be added to `autorag-server/app/services/pii_engine.py` by Team 8 only, following a security review. This is the **single canonical PII pattern source** (consolidated 13-Jul-2026, P0.7-1) — `app/guardrails/input/pii_detector.py` and `app/services/pii_service.py` are now thin compatibility wrappers that delegate here; no active code path may define its own PII regex. Before this consolidation, those two files had independent, non-identical pattern sets, meaning PII coverage was silently path-dependent (e.g. a live query masked SSNs/credit cards but a document upload didn't, or vice versa) — do not reintroduce a second pattern source.

---

## Mandatory Enforcement Points

PII masking is **mandatory** (cannot be disabled in dev, staging, or production) at:

1. **Ingestion boundary** — before any document chunk is written to Supabase Vector or Storage
2. **LLM dispatch** — before any user query or context is sent to Gemini Flash 3.5 / KiMi K2.6
3. **LangGraph state** — before any state object is persisted to the checkpoints table
4. **Audit log** — PII must never appear in `audit_log` event payloads

---

## Implementation

- **Runtime**: `autorag-server/app/services/pii_engine.py` (canonical patterns) → `mask_pii()`, exposed via the `app/guardrails/input/pii_detector.py` compatibility wrapper for existing call sites
- **Integration**: All masking goes through `GuardrailPipeline.run_input_guards()`
- **Technology**: Custom regex-based detection — this project's own "Custom PII Detection & Masking Functions" (the v3.0 replacement for the deprecated Presidio-based approach; do not reintroduce Presidio)
- **Logging**: Redaction count is logged at DEBUG; masked content is never logged
