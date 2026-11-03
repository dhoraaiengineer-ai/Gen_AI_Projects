# Runbook: High Latency (p95 > 3s)

**Alert**: `HighP95Latency` / `AgentLatencyBreach`
**Severity**: Critical
**Auto-rollback**: Yes — triggers within 10-minute canary window
**Owner**: Team 1 (DevOps) + Team 6 (Platform)

---

## Trigger Conditions

- Prometheus: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 3`
- Prometheus: `histogram_quantile(0.95, sum by(le)(rate(autorag_agent_latency_ms_bucket[5m]))) > 3000`
- Either condition persists for 2 minutes

---

## Symptoms

- p95 API response time > 3 seconds in Grafana `autorag-overview` dashboard
- Pipeline runs queuing up in Redis (`redis_list_length{key="autorag:task:queue"} > 50`)
- Users seeing slow responses in `/chat` or `/retrieve` pages
- ECS task CPU or memory near limits

---

## Diagnosis Steps

### Step 1 — Check ECS task health
```bash
aws ecs describe-services \
  --cluster autorag-production \
  --services autorag-api autorag-workers \
  --query 'services[*].{name:serviceName,running:runningCount,desired:desiredCount}'
```

### Step 2 — Identify the slow agent
Check `autorag_agent_latency_ms` by `agent_name` in Grafana. The 9 agents are:
`ingestion`, `query_rewriter`, `builder`, `compressor`, `evaluator`, `observer`, `diagnoser`, `improver`, `deployer`

### Step 3 — Check LLM provider latency
```
autorag_provider_timeout_total{provider=~"gemini.*|kimi.*"}
autorag_provider_failures_total
```
High timeouts → provider degradation → check https://status.google.com and https://status.kimi.com

### Step 4 — Check Redis queue depth
```bash
redis-cli llen autorag:task:queue
redis-cli info clients
```

### Step 5 — Check Supabase Vector query time
In Supabase dashboard: check slow query log for pgvector `<->` searches. HNSW index may need `ef_search` tuning.

---

## Resolution

| Root Cause | Action |
|------------|--------|
| LLM provider slow | Failover chain auto-handles. If all 3 providers slow, open incident with providers |
| ECS under-provisioned | Scale ECS workers: `aws ecs update-service --desired-count 8 --cluster autorag-production --service autorag-workers` |
| Redis queue backed up | Increase worker count (above) or flush stale jobs: `redis-cli lrange autorag:task:queue 0 -1` then delete stale entries |
| pgvector slow | Reindex HNSW on the shared `pipeline_chunks` table (Version 4.0, migration 0016 — replaces the old per-version physical table naming): `REINDEX INDEX CONCURRENTLY ix_pipeline_chunks_embedding;` in Supabase |
| Chunk too large (token overflow) | Check `MAX_CONTEXT_TOKENS` env var — reduce if > 64000 |

---

## Escalation

- **Auto-rollback fires**: Deployer Agent reverts to last healthy ECS task ARN
- **If rollback doesn't clear alert**: Page Mahesh Kumar (Team 10 lead)
- **SLO burn rate > 14.4x**: Declare incident, notify all team leads

---

## Post-Incident

1. Update `observability/slo/slo-definitions.md` if threshold was wrong
2. Add `audit_log` entry with event type `latency_slo_breach`
3. Run Diagnoser Agent (`POST /api/v1/diagnose`) to classify failure type (F-03 Latency Regression)
