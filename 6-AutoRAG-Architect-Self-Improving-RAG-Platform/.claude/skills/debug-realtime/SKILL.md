# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: debug-realtime
description: Debug real-time issues in WebSocket connections, Kafka streams, or async workers

---

# Debug Real-Time Skill

## Goal

Diagnose and fix issues in real-time components (WebSockets, LangGraph workers, Redis queues).

## Steps

1. Ask for: symptom description, affected component, and any error logs.
2. Diagnose by component type:
   - **WebSocket**: Check connection lifecycle, auth, heartbeat, state management, rate limiting.
   - **Kafka**: Check consumer lag, partition assignment, deserialization errors, dead-letter topics.
   - **LangGraph Workers**: Check graph node status, retry edges, timeouts, `BackgroundTasks` completion (no separate worker service or Redis queue exists today -- see `adr/005-supabase.md`'s R-052/R-050 correction; "queue depth" is not a real diagnostic here).
3. Check common real-time issues:
   - Event loop blocking (sync calls in async handlers)
   - Memory leaks (unbounded buffers, connection state not cleaned up)
   - Race conditions (concurrent state mutations)
   - Backpressure (slow consumers, queue overflow)
   - Connection storms (reconnection without backoff)
4. Identify root cause and implement fix.
5. Add or improve logging/monitoring to catch similar issues earlier.
6. Add tests to prevent regression.
7. Summarize the root cause, fix, and prevention measures.

## Quality rules

- Never mask symptoms — find and fix root causes.
- Add correlation ID tracing to diagnose cross-service issues.
- Check for event loop blocking before assuming network issues.
- Verify connection cleanup on disconnect/error paths.
- Add backpressure handling if missing.
