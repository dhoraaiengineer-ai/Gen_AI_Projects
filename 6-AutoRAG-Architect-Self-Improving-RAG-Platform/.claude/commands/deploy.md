# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Deploy Command

This command triggers the deployment process for the AutoRAG production stack.

## Instructions

1. **Pre-flight Quality Gates**:
   - Run `npm run lint` and `npm run test` (Backend & Frontend).
   - Verify LangGraph traversal coverage is >= 90%.
   - Verify Unified Score on golden dataset is >= 0.85.
2. **Infrastructure Verification**:
   - Confirm AWS ECS Fargate target cluster is responsive.
   - Verify Supabase Vector connection status.
3. **Trigger Pipeline**:
   - Initiate the 8-stage gate chain (Build -> Security Scan -> Integration -> Canary).
4. **Post-Deployment**:
   - Emit the `workflow.completed` webhook (per `specs/agents/09-deployer.md`) and write the
     matching `audit_log` entry using one of the 13 real approved event types
     (`app/models/audit_log.py`'s `APPROVED_EVENT_TYPES` — not an invented name).
