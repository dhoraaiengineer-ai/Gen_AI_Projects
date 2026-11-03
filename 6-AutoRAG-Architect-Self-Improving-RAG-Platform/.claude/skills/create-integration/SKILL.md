# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-integration
description: Add a new third-party integration (CRM, helpdesk, messaging, payment, ERP)

---

# Create Integration Skill

## Goal

Add a new third-party integration using the adapter/gateway pattern.

## Steps

1. Ask for: integration name, provider, API docs reference, sync direction (inbound/outbound/bidirectional), key data entities.
2. Create the integration module:
   - `integrations/{name}/adapter.py` — implements the common integration interface
   - `integrations/{name}/client.py` — HTTP client with auth, retries, circuit breaker
   - `integrations/{name}/schemas.py` — API request/response models and field mappings
   - `integrations/{name}/webhook.py` — inbound webhook handler (if applicable)
   - `integrations/{name}/config.py` — endpoints, credentials reference, feature flags
3. Implement field mapping between external and internal data models.
4. Add circuit breaker and retry logic with exponential backoff.
5. Add webhook signature validation for inbound events.
6. Add idempotent event processing for webhooks.
7. Add tests: mock all external APIs, test error scenarios (timeout, rate limit, auth failure).
8. Summarize the integration capabilities and configuration.

## Quality rules

- Use adapter pattern — never leak external API models into core services.
- Never hardcode API endpoints or credentials.
- Keep credentials in secrets manager references.
- Add circuit breakers and explicit timeouts on all outbound calls.
- Log all outbound calls with status, latency, and error details.
- Validate webhook signatures — reject unsigned payloads.
- Process webhook events idempotently.
- Use dead-letter queues for failed webhook processing.
- Mock all external APIs in tests — never call real services in CI.
