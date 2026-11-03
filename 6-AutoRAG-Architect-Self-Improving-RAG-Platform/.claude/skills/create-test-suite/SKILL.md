# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-test-suite
description: Generate a comprehensive test suite for a service, endpoint, or feature

---

# Create Test Suite Skill

## Goal

Generate a thorough test suite covering unit, API, integration, and real-time tests.

## Steps

1. Ask for: target module/feature, critical paths to test, and any known edge cases.
2. Analyze the target code to identify testable units and integration points.
3. Create tests by layer:
   - **Unit tests**: Service functions, repository methods, utility functions.
   - **API tests**: Endpoint request/response validation, auth, error handling.
   - **Integration tests**: Multi-step flows, service-to-service interactions.
   - **WebSocket tests**: Connection lifecycle, message handling, reconnection (if applicable).
   - **AI response tests**: Fixture-based assertions, not exact match (if applicable).
4. Cover edge cases: empty results, invalid input, timeouts, rate limits, auth failures.
5. Mock external dependencies: databases, third-party APIs, AI models.
6. Add test fixtures and factory functions for common test data.
7. Verify all tests pass.
8. Summarize test coverage and any gaps.

## Quality rules

- Test behavior, not implementation details.
- Use fixture-based assertions for AI outputs — never exact string match.
- Mock external APIs in unit tests. **AutoRAG exception (Rule 80)**: integration tests MUST use real Supabase PostgreSQL + real Supabase Vector — mocking the RAG pipeline hides retrieval bugs.
- Test error scenarios, not just happy paths.
- Keep tests independent — no shared mutable state between tests.
- Use async test runners for async code.
- Name tests descriptively: `test_{action}_{condition}_{expected_result}`.
