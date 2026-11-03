# AutoRAG Architect — SLO Definitions

**Owner**: Team 6 (DevOps / Platform)
**Updated**: 05-Jul-2026

---

## Service Level Objectives

| SLO                          | Target    | Measurement Window | Rollback Trigger |
| ---------------------------- | --------- | ------------------ | ---------------- |
| p95 query response latency   | < 3000ms  | 5-minute rolling   | ✅ Yes           |
| API error rate (5xx)         | < 1%      | 5-minute rolling   | ✅ Yes           |
| Unified Score (production)   | >= 0.85   | Per pipeline run   | ✅ Yes (drop > 0.10) |
| Faithfulness (per eval)      | >= 0.5    | Per eval run       | ✅ Hard block    |
| Pipeline build time          | < 5 min   | Per 1,000 docs     | ❌ Alert only    |
| Retrieval Recall@5           | >= 0.85   | Per eval run       | ❌ Alert only    |
| Adversarial pass rate        | 100%      | Per eval run       | ✅ Hard block    |

---

## Burn Rate Thresholds

A 1-hour burn rate of **14.4×** means the monthly SLO will be exhausted in 2 days. Alert immediately.

| Window    | Burn Rate | Severity | Action              |
| --------- | --------- | -------- | ------------------- |
| 5 min     | > 14.4×   | Critical | Page + auto-rollback |
| 30 min    | > 6×      | Warning  | Notify Team 6       |
| 6 hours   | > 1×      | Info     | Log to audit trail  |

---

## Error Budget

- Monthly availability target: **99.5%**
- Monthly error budget: **3.6 hours**
- Burn rate tracking resets on the 1st of each month
