# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Fix Issue Command

Analyzes and resolves bugs in the AutoRAG platform.

## Instructions

1. **Root Cause Analysis**:
   - For RAG issues, identify the specific agent failure (using the 6-part F-01..F-06 taxonomy).
   - For Infra issues, check the ECS Fargate logs or Supabase PostgreSQL migration state.
2. **Architectural Guardrails**:
   - Ensure the fix does not introduce **state pollution** in the LangGraph loop.
   - Verify that any new database column follows the **UUID v7** standard.
3. **Verification**:
   - Implement unit tests for the specific node failure.
   - Confirm the **Unified Score** does not regress after the fix.
