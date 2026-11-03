# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-webhook-handler
description: Build a secure inbound webhook handler for external service events

---

# Create Webhook Handler Skill

## Goal

Build a production-grade inbound webhook handler for processing external events.

## Steps

1. Ask for: source service, event types, signature validation method, and processing requirements.
2. Create the webhook handler:
   - `webhooks/{source}/handler.py` — endpoint that receives and validates events
   - `webhooks/{source}/validator.py` — signature verification logic
   - `webhooks/{source}/processor.py` — event processing by type
   - `webhooks/{source}/schemas.py` — event payload Pydantic models
3. Implement signature validation (HMAC, RSA, etc.) — reject unsigned payloads.
4. Implement idempotent event processing using event IDs.
5. Route events by type to appropriate processors.
6. Add dead-letter handling for failed events.
7. Add structured logging: event type, source, processing outcome.
8. Add tests: signature validation, each event type, duplicate handling, error scenarios.
9. Summarize the webhook endpoint and supported events.

## Quality rules

- Validate signatures before any processing — fail fast on invalid payloads.
- Process events idempotently — handle duplicate deliveries gracefully.
- Return 200 quickly, process heavy work async (FastAPI `BackgroundTasks`, in-process -- no Redis-backed task queue exists today, see `adr/005-supabase.md`'s R-052/R-050 correction).
- Log every webhook with event type, source, and processing result.
- Use dead-letter queues for events that fail repeatedly.
- Never expose internal errors in webhook responses.
- Mock external payloads in tests — use real provider payload examples.
