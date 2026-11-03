# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Code Review Command

Performs a comprehensive architectural and security review of current changes.

## Instructions

1. **Context Check**:
   - Verify adherence to the **9-agent LangGraph** stateful pattern.
   - Confirm any new primary keys use **UUID v7**.
2. **AI Logic Check**:
   - Verify the **3-layer evaluation stack** (Unified + RAGAS + Adversarial) is correctly implemented.
   - Check for PII masking before all LLM provider calls.
3. **Operational Check**:
   - Ensure all significant events are recorded in the **INSERT-ONLY audit_log**.
   - Verify p95 latency targets are respected.
4. **Security Check**:
   - Scan for hardcoded credentials or unmasked logs.
