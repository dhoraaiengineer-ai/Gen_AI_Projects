# 85 — Observability

**Purpose:** See latency, cost, quality, and safety behaviour in real time, without leaking PII.

## MUST
- OpenTelemetry tracing from FastAPI → graph node → `LLMService` → DB. Propagate `trace_id` into logs and `llm_usage`.
- `llm_usage` row per LLM call: `request_id, trace_id, ro_id?, node, purpose, model, provider, input_tokens, output_tokens, cache_read_tokens, cost_usd (Decimal, from a config price table), latency_ms, outcome`.
- Prometheus metrics (names fixed):
  `http_request_duration_seconds` (route, method, status) · `graph_node_duration_seconds` (node) ·
  `graph_node_errors_total` (node, error_type) · `llm_tokens_total` (model, direction) · `llm_cost_usd_total` (model) ·
  `safety_refusals_total` (reason) · `escalations_total` (kind) · `human_review_pending` (kind) ·
  `risk_flags_total` (detector) · `ro_cost_usd` (histogram).
- Structured JSON logs (structlog) with `request_id`, `trace_id`, `actor_role`, `dealer_id`; PII masked.
- `/health` (liveness, no deps) and `/ready` (DB, MinIO, and LLM provider config checks).
- Grafana dashboard JSON + alert rules in `observability/`: chat p95 > 6 s, status p95 > 1 s, node error rate, cost spike, audit chain break, safety-eval regression.

## MUST NOT
- Log prompts or completions containing PII. Store prompt/response bodies only behind a config flag, masked, with retention.
- Use high-cardinality labels (VIN, user id, RO id) on Prometheus metrics.
- Swallow exceptions without logging and a metric.

## Good
```python
with tracer.start_as_current_span("node.diagnosis", attributes={"ro.ref": ro_ref}):
    NODE_DURATION.labels(node="diagnosis").observe(elapsed)
```

## Bad
```python
logger.info(f"LLM prompt: {prompt}")                 # PII + unbounded size
LLM_COST.labels(vin=vin).inc(cost)                   # high-cardinality + PII label
```
