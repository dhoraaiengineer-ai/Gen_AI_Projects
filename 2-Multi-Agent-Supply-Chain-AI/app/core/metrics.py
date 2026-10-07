"""Prometheus metrics. One uvicorn worker per container, so per-process metrics are complete."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60)

HTTP_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "route", "status"], buckets=LATENCY_BUCKETS)
HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])

LLM_LATENCY = Histogram("llm_request_duration_seconds", "LLM call latency", ["model", "outcome"], buckets=LATENCY_BUCKETS)
LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens", ["model", "kind"])
LLM_COST = Counter("llm_cost_usd_total", "Estimated LLM cost in USD", ["model"])
LLM_FALLBACKS = Counter("llm_fallbacks_total", "Calls served by a fallback model", ["chain"])
CIRCUIT_STATE = Gauge("circuit_breaker_open", "1 when the circuit for a model is open", ["model"])

STREAM_TTFT = Histogram("stream_time_to_first_token_seconds", "Time to first answer token", ["endpoint"], buckets=LATENCY_BUCKETS)
STREAM_TTFE = Histogram("stream_time_to_first_event_seconds", "Time to first streamed event", ["endpoint"], buckets=LATENCY_BUCKETS)

AGENT_LATENCY = Histogram("agent_step_duration_seconds", "Agent node latency", ["agent", "outcome"], buckets=LATENCY_BUCKETS)
TOOL_LATENCY = Histogram("tool_call_duration_seconds", "Tool latency", ["tool", "outcome"], buckets=LATENCY_BUCKETS)
TOOL_DENIED = Counter("tool_authorization_denied_total", "Tool calls rejected by the registry", ["tool", "agent"])
WORKFLOWS = Counter("agent_workflows_total", "Agent workflows", ["intent", "outcome"])
APPROVALS = Counter("approvals_total", "Human approval decisions", ["decision"])

RETRIEVAL_LATENCY = Histogram("retrieval_duration_seconds", "Knowledge-base retrieval latency", ["stage"], buckets=LATENCY_BUCKETS)
RERANKS = Counter("rerank_total", "LLM rerank calls", ["outcome"])
WEB_SEARCHES = Counter("web_search_total", "Web searches", ["outcome"])
CACHE = Counter("cache_requests_total", "Cache lookups", ["cache", "result"])
HALLUCINATION_FLAGS = Counter("hallucination_flags_total", "Answers flagged by the hallucination guard", ["reason"])
GUARDRAIL_DECISIONS = Counter("guardrail_decisions_total", "Guardrail outcomes", ["layer", "check", "action"])

RATE_LIMITED = Counter("rate_limited_total", "Requests rejected by the rate limiter", ["group"])
AUTH_FAILURES = Counter("auth_failures_total", "Authentication failures", ["reason"])
DOCUMENTS = Counter("documents_ingested_total", "Document ingestion outcomes", ["status"])
