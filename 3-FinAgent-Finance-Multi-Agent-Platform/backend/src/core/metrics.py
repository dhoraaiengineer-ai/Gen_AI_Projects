"""Prometheus metrics, defined once. Exposed at ``GET /metrics`` (Stage 8/11)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60)

# ---------------------------------------------------------------- LLM
LLM_REQUESTS = Counter(
    "finagent_llm_requests_total", "LLM calls by model and outcome", ["model", "status"]
)
LLM_LATENCY = Histogram(
    "finagent_llm_latency_seconds", "LLM call latency", ["model"], buckets=LATENCY_BUCKETS
)
LLM_TOKENS = Counter("finagent_llm_tokens_total", "LLM tokens", ["model", "direction"])
LLM_COST = Counter("finagent_llm_cost_usd_total", "Estimated LLM cost in USD", ["model"])
LLM_FALLBACKS = Counter(
    "finagent_llm_fallbacks_total", "Calls that failed over to the next model", ["from_model"]
)
CIRCUIT_STATE = Gauge(
    "finagent_circuit_state", "Circuit state (0 closed, 1 half-open, 2 open)", ["key"]
)

# ---------------------------------------------------------------- embeddings
EMBEDDING_REQUESTS = Counter(
    "finagent_embedding_requests_total", "Embedding calls", ["model", "status"]
)
EMBEDDING_LATENCY = Histogram(
    "finagent_embedding_latency_seconds", "Embedding latency", ["model"], buckets=LATENCY_BUCKETS
)

# ---------------------------------------------------------------- tools / MCP
TOOL_CALLS = Counter("finagent_tool_calls_total", "Tool calls by outcome", ["tool", "status"])
TOOL_LATENCY = Histogram(
    "finagent_tool_latency_seconds", "Tool latency", ["tool"], buckets=LATENCY_BUCKETS
)

# ---------------------------------------------------------------- caches
CACHE_EVENTS = Counter("finagent_cache_events_total", "Cache hits/misses/stale", ["cache", "event"])

# ---------------------------------------------------------------- MCP
MCP_CALLS = Counter("finagent_mcp_calls_total", "MCP tool calls", ["server", "tool", "status"])
MCP_LATENCY = Histogram(
    "finagent_mcp_latency_seconds", "MCP call latency", ["server"], buckets=LATENCY_BUCKETS
)

# ---------------------------------------------------------------- A2A
A2A_MESSAGES = Counter("finagent_a2a_messages_total", "A2A envelopes", ["source", "target", "type"])
A2A_LATENCY = Histogram(
    "finagent_a2a_latency_seconds", "A2A round-trip latency", ["target"], buckets=LATENCY_BUCKETS
)
A2A_RETRIES = Counter("finagent_a2a_retries_total", "A2A retries", ["target"])

# ---------------------------------------------------------------- agents / graph
AGENT_RUNS = Counter("finagent_agent_runs_total", "Agent runs by outcome", ["agent", "status"])
AGENT_LATENCY = Histogram(
    "finagent_agent_latency_seconds", "Agent latency", ["agent"], buckets=LATENCY_BUCKETS
)
TTFE = Histogram("finagent_ttfe_seconds", "Time to first streamed event", buckets=LATENCY_BUCKETS)
TTFT = Histogram("finagent_ttft_seconds", "Time to first streamed token", buckets=LATENCY_BUCKETS)

# ---------------------------------------------------------------- decision models (Jev)
DECISION_REQUESTS = Counter(
    "finagent_decision_requests_total", "Decision-model calls", ["provider", "status"]
)
DECISION_LATENCY = Histogram(
    "finagent_decision_latency_seconds",
    "Decision-model latency",
    ["provider"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
DECISION_FALLBACKS = Counter(
    "finagent_decision_fallbacks_total",
    "Decisions served by the fallback path",
    ["purpose", "reason"],
)

# ---------------------------------------------------------------- auth
AUTH_FAILURES = Counter("finagent_auth_failures_total", "Authentication failures", ["reason"])

# ---------------------------------------------------------------- ML models
ML_INFERENCE_LATENCY = Histogram(
    "finagent_ml_inference_latency_seconds",
    "ML inference latency",
    ["model"],
    buckets=LATENCY_BUCKETS,
)
ML_PREDICTIONS = Counter("finagent_ml_predictions_total", "ML predictions", ["model", "label"])

TELEMETRY_DROPPED = Counter(
    "finagent_telemetry_dropped_total", "Execution records (a2a, agent runs, tool calls) not stored"
)

KV_FALLBACKS = Counter(
    "finagent_kv_fallbacks_total", "Redis failures served by the in-process store"
)
RATE_LIMITED = Counter("finagent_rate_limited_total", "Requests rejected by rate limits", ["group"])

# ---------------------------------------------------------------- HTTP
HTTP_REQUESTS = Counter(
    "finagent_http_requests_total", "HTTP requests by route template", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "finagent_http_request_seconds",
    "HTTP request duration (streams: until the last byte)",
    ["method", "route"],
    buckets=LATENCY_BUCKETS,
)
