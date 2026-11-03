"""Prometheus metrics registry — AutoRAG Architect.

Rule 86 enforcement: All 10 metrics MUST be defined here and nowhere else.
These metric names MUST match the alert rules in:
  observability/alerts/autorag-alerts.yml

Metric naming convention:
  autorag_agent_cost_usd_total       → Counter (suffix _total added by prometheus_client)
  autorag_agent_latency_ms           → Histogram
  autorag_agent_tokens_total         → Counter
  autorag_cache_hits_total           → Counter
  autorag_cache_misses_total         → Counter
  autorag_cache_latency_ms           → Histogram
  autorag_provider_failures_total    → Counter
  autorag_provider_switch_total      → Counter
  autorag_provider_rate_limit_total  → Counter
  autorag_provider_timeout_total     → Counter

Usage in agent nodes (via LLMService — never compute cost in nodes directly):
    from app.metrics import AGENT_COST, AGENT_LATENCY, AGENT_TOKENS

    AGENT_COST.labels(agent_name="builder", provider="gemini-flash-3.5").inc(0.00014)
    with AGENT_LATENCY.labels(agent_name="builder").time():
        result = await llm_service.call(...)

Usage for cache tracking (Compressor, Builder):
    from app.metrics import CACHE_HITS, CACHE_MISSES, CACHE_LATENCY

    if cache_hit:
        CACHE_HITS.labels(agent_name="compressor").inc()
    else:
        CACHE_MISSES.labels(agent_name="compressor").inc()

Usage for provider failover (LLMService only):
    from app.metrics import PROVIDER_FAILURES, PROVIDER_SWITCHES

    PROVIDER_FAILURES.labels(provider="gemini-flash-3.5").inc()
    PROVIDER_SWITCHES.labels(from_provider="gemini-flash-3.5", to_provider="kimi-k2.6").inc()
"""

from prometheus_client import Counter, Gauge, Histogram

# ─────────────────────────────────────────────────────────────────────────────
# 1. Core Agent Metrics (Rule 86 §7, primary 3)
# ─────────────────────────────────────────────────────────────────────────────

AGENT_COST = Counter(
    "autorag_agent_cost_usd",
    "Cumulative LLM cost in USD per agent per provider",
    ["agent_name", "provider"],
)
# Note: prometheus_client appends _total → scraped as autorag_agent_cost_usd_total

AGENT_LATENCY = Histogram(
    "autorag_agent_latency_ms",
    "Agent response latency in milliseconds",
    ["agent_name"],
    buckets=[50, 100, 200, 500, 1000, 2000, 3000, 5000],
)

AGENT_TOKENS = Counter(
    "autorag_agent_tokens",
    "Total tokens consumed per agent",
    ["agent_name", "provider", "token_type"],
    # token_type: "prompt_tokens" | "completion_tokens"
)
# Note: prometheus_client appends _total → scraped as autorag_agent_tokens_total

# ─────────────────────────────────────────────────────────────────────────────
# 2. Cache Metrics (Rule 86 §7, cache 3)
# ─────────────────────────────────────────────────────────────────────────────

CACHE_HITS = Counter(
    "autorag_cache_hits",
    "Number of cache hits per agent",
    ["agent_name"],
)

CACHE_MISSES = Counter(
    "autorag_cache_misses",
    "Number of cache misses per agent",
    ["agent_name"],
)

CACHE_LATENCY = Histogram(
    "autorag_cache_latency_ms",
    "Cache lookup latency in milliseconds per agent",
    ["agent_name"],
    buckets=[1, 5, 10, 25, 50, 100],
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Provider Failover Metrics (Rule 86 §7, failover 4)
# ─────────────────────────────────────────────────────────────────────────────

PROVIDER_FAILURES = Counter(
    "autorag_provider_failures",
    "Total LLM provider failures triggering failover",
    ["provider"],
)

PROVIDER_SWITCHES = Counter(
    "autorag_provider_switch",
    "Total provider failover switches",
    ["from_provider", "to_provider"],
)

PROVIDER_RATE_LIMITS = Counter(
    "autorag_provider_rate_limit",
    "Total provider rate limit responses received",
    ["provider"],
)

PROVIDER_TIMEOUTS = Counter(
    "autorag_provider_timeout",
    "Total provider call timeouts",
    ["provider"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Per-Query Cost Gauge (F-11 / Rule 86 §7 — referenced by autorag-alerts.yml)
# ─────────────────────────────────────────────────────────────────────────────

QUERY_COST = Gauge(
    "autorag_cost_per_query_usd",
    "Most recent LLM cost in USD for the last completed query, per provider",
    ["provider"],
)
# Note: Gauge (not Counter) — represents the LAST observed cost for alert thresholds.
# Referenced by ExpensiveLowQualityPipeline alert in observability/alerts/autorag-alerts.yml.

# ─────────────────────────────────────────────────────────────────────────────
# 5. Business / Tenant Metrics (G-3 / Plan v4)
# ─────────────────────────────────────────────────────────────────────────────
# Track per-organization usage for multi-tenant capacity planning and billing.
# Increment these at service layer, never inside LangGraph nodes (Rule 86).
# Label: organization_id (UUID v7 string)

ORG_DOCUMENTS = Counter(
    "autorag_org_documents",
    "Total documents ingested per organization",
    ["organization_id"],
)

ORG_QUERIES = Counter(
    "autorag_org_queries",
    "Total queries executed per organization",
    ["organization_id"],
)

ORG_PIPELINES = Counter(
    "autorag_org_pipelines",
    "Total pipelines created per organization",
    ["organization_id"],
)

ORG_COST_USD = Counter(
    "autorag_org_cost_usd",
    "Cumulative LLM cost in USD per organization",
    ["organization_id"],
)

ORG_SCORE_AVG = Gauge(
    "autorag_org_score_avg",
    # Corrected 24-Jul-2026 (R-051, release audit): previously documented as
    # a "rolling average (last 10 runs)" but was never actually set anywhere
    # in the codebase -- the UnifiedScoreDrop alert queried a *different*,
    # entirely nonexistent metric name (autorag_unified_score) and could
    # never fire. Now genuinely wired in evaluator.py right after
    # compute_unified_score() -- one real value per evaluation run, not a
    # true rolling average (Prometheus's own rate()/avg_over_time() can
    # compute that from this raw series if wanted later).
    "Most recent Unified Score per organization, set on every real evaluation run",
    ["organization_id"],
)

ORG_ADVERSARIAL_PASS_RATE = Gauge(
    "autorag_adversarial_pass_rate",
    # Added 24-Jul-2026 (R-049, release audit): the Grafana "Adversarial Pass
    # Rate" panel (observability/grafana/dashboards/autorag-aiops.json)
    # queried this metric name, but it was never declared or set anywhere --
    # adversarial_result["pass_rate"] was computed in evaluator.py and written
    # to GraphState, but never exported. Wired in evaluator.py right after
    # ORG_SCORE_AVG, same pattern.
    "Most recent adversarial Q&A benchmark pass rate per organization, set on every real evaluation run",
    ["organization_id"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 6. Guardrail Security Metrics (V3 output-layer stubs fix)
# ─────────────────────────────────────────────────────────────────────────────
# Each counter fires when the corresponding guardrail blocks or detects an event.
# These feed the Observer Agent's security signal and complete the
# Guardrails → Observability connection described in ADR-007.
#
# Usage (GuardrailPipeline only — never scatter calls elsewhere):
#   from app.metrics import GUARDRAIL_PII_DETECTIONS
#   GUARDRAIL_PII_DETECTIONS.labels(organization_id=org_id).inc()

GUARDRAIL_PII_DETECTIONS = Counter(
    "autorag_guardrail_pii_detections",
    "PII detected and masked at input or output boundary",
    ["organization_id"],
)

GUARDRAIL_INJECTION_BLOCKS = Counter(
    "autorag_guardrail_injection_blocks",
    "Prompt injection attempts blocked at input boundary",
    ["organization_id"],
)

GUARDRAIL_JAILBREAK_BLOCKS = Counter(
    "autorag_guardrail_jailbreak_blocks",
    "Jailbreak attempts blocked at input boundary",
    ["organization_id"],
)

GUARDRAIL_OUTPUT_BLOCKS = Counter(
    "autorag_guardrail_output_blocks",
    "Output layer hard blocks (hallucination below threshold or unsafe content)",
    ["block_reason"],
    # block_reason: "hallucination" | "unsafe_output"
)
