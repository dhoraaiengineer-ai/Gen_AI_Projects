"""Prometheus metrics. Labels are low-cardinality enums only; never free text or PHI."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

TRIAGE_EVENTS = Counter(
    "medinfo_triage_events_total", "Urgent-symptom triage firings", ["category", "detector"]
)
SCOPE_DECISIONS = Counter("medinfo_scope_decisions_total", "Scope classification results", ["scope"])
REFUSALS = Counter("medinfo_refusals_total", "Refused or replaced answers", ["scope", "reason"])
SAFETY_CHECK_FAILURES = Counter(
    "medinfo_safety_check_failures_total", "Post-answer safety check failures", ["check"]
)
CLASSIFIER_ERRORS = Counter(
    "medinfo_classifier_errors_total", "LLM classifier failures (rules result used)", ["classifier"]
)
CHAT_LATENCY = Histogram(
    "medinfo_chat_seconds",
    "End-to-end chat latency",
    ["outcome"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
GUARDRAIL_EVENTS = Counter(
    "medinfo_guardrail_events_total", "Guardrail policy matches", ["stage", "rule", "action"]
)
CIRCUIT_STATE = Gauge(
    "medinfo_circuit_state", "Circuit state per model (0 closed, 1 half-open, 2 open)", ["model"]
)
FALLBACKS = Counter(
    "medinfo_model_fallbacks_total", "Calls that fell through to the next model", ["model", "error"]
)
MODEL_CALLS = Histogram(
    "medinfo_model_call_seconds",
    "Model call latency",
    ["model", "outcome"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
RATE_LIMITED = Counter("medinfo_rate_limited_total", "Requests rejected by per-user rate limits", ["bucket"])
CACHE_EVENTS = Counter("medinfo_cache_events_total", "Cache lookups", ["cache", "result"])
HTTP_REQUESTS = Counter("medinfo_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "medinfo_http_request_seconds",
    "HTTP latency by route template (p50/p95/p99 via histogram_quantile)",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
RETRIEVAL_LATENCY = Histogram(
    "medinfo_retrieval_seconds",
    "Retrieval latency by stage",
    ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
HALLUCINATION_FLAGS = Counter(
    "medinfo_hallucination_flags_total", "Answers blocked by grounding/faithfulness checks", ["check"]
)
# LLM gateway (app/rag/gateway.py): token budgets per task. Token counts are integers; labels are enums.
PROMPT_TOKENS = Histogram(
    "medinfo_llm_prompt_tokens_estimated",
    "Estimated prompt tokens per model call, by task (checked against the task's input budget)",
    ["task"],
    buckets=(64, 128, 256, 512, 1024, 2048, 4096, 8192),
)
LLM_TOKENS = Counter(
    "medinfo_llm_tokens_total",
    "Tokens reported by the provider, by task, model and direction (input/output)",
    ["task", "model", "direction"],
)
TOKEN_BUDGET_EVENTS = Counter(
    "medinfo_token_budget_events_total",
    "Gateway budget actions: output_clamped, input_rejected, passages_trimmed",
    ["task", "action"],
)
