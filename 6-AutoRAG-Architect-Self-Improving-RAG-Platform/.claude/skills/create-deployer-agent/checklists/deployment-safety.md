# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Deployment Safety Checklist

- [ ] Target cluster is `production` or `staging`.
- [ ] ECS Task Definition ARN is versioned and immutable.
- [ ] **Canary Period**: Wait 10 minutes before tearing down old tasks (Blue).
- [ ] **Auto-Rollback Trigger 1**: Error rate > 1%.
- [ ] **Auto-Rollback Trigger 2**: p95 latency > 3s.
- [ ] **Auto-Rollback Trigger 3**: Unified Score drop > 0.10.
- [ ] `workflow.completed` webhook emitted on success; `rollback_triggered` (a real approved `audit_log` event type) INSERTed on rollback.
