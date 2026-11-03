# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-realtime-handler
description: Build a WebSocket handler or Kafka consumer/producer for real-time features

---

# Create Real-Time Handler Skill

## Goal

Build a real-time component (WebSocket handler, Kafka producer/consumer, or event processor).

## Steps

1. Ask for: component type (WebSocket handler / Kafka producer / Kafka consumer), event types, and data flow.
2. For **WebSocket handler**:
   - Create the handler with authentication on handshake.
   - Add heartbeat/ping-pong for connection health.
   - Implement message routing by event type.
   - Store connection state in Redis, not in memory.
   - Add per-connection and per-user rate limiting.
3. For **Kafka producer**:
   - Define the event schema (Avro or JSON schema).
   - Implement production with correlation ID propagation.
   - Add error handling and delivery confirmation.
4. For **Kafka consumer**:
   - Implement idempotent processing with deduplication.
   - Add error handling with dead-letter topic routing.
   - Use consumer groups for horizontal scaling.
5. Add structured logging with correlation IDs.
6. Add tests: WebSocket tests for handlers, unit tests for event processing.
7. Summarize the component behavior and event schema.

## Quality rules

- Never block the event loop in real-time handlers.
- Keep WebSocket handlers stateless — use Redis for state.
- Authenticate WebSocket connections on handshake, not after.
- Define explicit schemas for all Kafka topics.
- Implement idempotent consumers — handle duplicates gracefully.
- Use dead-letter topics/queues for failed processing.
- Target sub-100ms latency for message delivery.
- Handle backpressure: slow consumers must not crash producers.
