# Compliance Policy — AutoRAG v4.0

**Classification**: Internal — Security Governance
**Owner**: Team 8 (Compliance)
**Updated**: 21-Jul-2026

---

## Audit Requirements

| Requirement              | Implementation                                              |
| ------------------------ | ----------------------------------------------------------- |
| Immutable audit trail    | `audit_log` PostgreSQL table — INSERT ONLY (no UPDATE/DELETE) |
| 14 approved event types  | Enumerated in `autorag-server/app/models/audit_log.py` (`APPROVED_EVENT_TYPES` + matching DB `CheckConstraint`). Rule 86 added `cost_limit_exceeded` (task D-19, done); `guardrail_blocked` added 03-Jul-2026 (migration 0007); `pii_redacted` added 13-Jul-2026 (migration 0011, P0.7-2) |
| PII-free audit records   | All payloads PII-masked before INSERT                       |
| Multi-tenant isolation   | Every query scoped by `organization_id`                     |
| Secret management        | AWS Secrets Manager — no secrets in code or ECS task defs  |

---

## SOC2 Readiness (Target: Phase 3)

| Control                  | Status    | Owner   |
| ------------------------ | --------- | ------- |
| PII masking              | ✅ Active | Team 8  |
| Prompt injection defense | ✅ Active | Team 8  |
| Audit log (INSERT-ONLY)  | ✅ Active | Team 3  |
| Red-team dataset review  | 🔄 Ongoing| Team 8  |
| Penetration testing      | ⬜ Phase 3| External|
| Data residency (EU/US)   | ⬜ Phase 3| Team 1  |
| Access control review    | ⬜ Phase 3| Team 1  |

---

## Data Residency

- All production data resides in Supabase (managed) and AWS (`ap-south-1` — Mumbai region)
- Customer data never leaves the designated region
- Team members do NOT have direct Supabase console access — only via env-injected credentials from AWS Secrets Manager
