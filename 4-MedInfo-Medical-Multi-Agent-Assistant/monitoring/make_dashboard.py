"""Regenerate monitoring/grafana/dashboards/medinfo.json (Grafana dashboard as code).

Usage: python monitoring/make_dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "grafana" / "dashboards" / "medinfo.json"
DS = {"type": "prometheus", "uid": "prometheus"}


def panel(
    pid: int, title: str, exprs: list[tuple[str, str]], x: int, y: int, unit: str = "short", w: int = 12
) -> dict:
    return {
        "id": pid,
        "type": "timeseries",
        "title": title,
        "datasource": DS,
        "gridPos": {"h": 8, "w": w, "x": x, "y": y},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "targets": [
            {"refId": chr(65 + i), "expr": e, "legendFormat": legend, "datasource": DS}
            for i, (e, legend) in enumerate(exprs)
        ],
    }


def q(p: float, metric: str, by: str) -> str:
    return f"histogram_quantile({p}, sum by (le, {by}) (rate({metric}_bucket[5m])))"


PANELS = [
    (
        "Chat latency p50 / p95 / p99",
        [
            (q(0.5, "medinfo_http_request_seconds", "route") + '{route="/api/chat"}', "p50"),
            (q(0.95, "medinfo_http_request_seconds", "route") + '{route="/api/chat"}', "p95"),
            (q(0.99, "medinfo_http_request_seconds", "route") + '{route="/api/chat"}', "p99"),
        ],
        "s",
    ),
    ("Latency p95 by route", [(q(0.95, "medinfo_http_request_seconds", "route"), "{{route}}")], "s"),
    (
        "Requests by route and status",
        [("sum by (route, status) (rate(medinfo_http_requests_total[5m]))", "{{route}} {{status}}")],
        "reqps",
    ),
    ("Model call latency p95 by model", [(q(0.95, "medinfo_model_call_seconds", "model"), "{{model}}")], "s"),
    ("Retrieval latency p95 by stage", [(q(0.95, "medinfo_retrieval_seconds", "stage"), "{{stage}}")], "s"),
    (
        "Triage events by category",
        [("sum by (category) (increase(medinfo_triage_events_total[15m]))", "{{category}}")],
        "short",
    ),
    (
        "Refusals by scope and reason",
        [("sum by (scope, reason) (increase(medinfo_refusals_total[15m]))", "{{scope}} / {{reason}}")],
        "short",
    ),
    (
        "Guardrail events (stage / rule / action)",
        [
            (
                "sum by (stage, rule, action) (increase(medinfo_guardrail_events_total[15m]))",
                "{{stage}} {{rule}} {{action}}",
            )
        ],
        "short",
    ),
    (
        "Hallucination flags by check",
        [("sum by (check) (increase(medinfo_hallucination_flags_total[15m]))", "{{check}}")],
        "short",
    ),
    (
        "Safety check failures by check",
        [("sum by (check) (increase(medinfo_safety_check_failures_total[15m]))", "{{check}}")],
        "short",
    ),
    (
        "Cache hit ratio",
        [
            (
                'sum by (cache) (rate(medinfo_cache_events_total{result="hit"}[15m])) / clamp_min(sum by (cache) (rate(medinfo_cache_events_total{result=~"hit|miss"}[15m])), 0.001)',
                "{{cache}}",
            )
        ],
        "percentunit",
    ),
    (
        "Circuit state by model (0 closed, 1 half-open, 2 open)",
        [("max by (model) (medinfo_circuit_state)", "{{model}}")],
        "short",
    ),
    (
        "Model fallbacks",
        [("sum by (model, error) (increase(medinfo_model_fallbacks_total[15m]))", "{{model}} {{error}}")],
        "short",
    ),
    (
        "Rate-limited requests",
        [("sum by (bucket) (increase(medinfo_rate_limited_total[15m]))", "{{bucket}}")],
        "short",
    ),
    (
        "Classifier errors (rules-only fallback)",
        [("sum by (classifier) (increase(medinfo_classifier_errors_total[15m]))", "{{classifier}}")],
        "short",
    ),
    (
        "Answers by outcome",
        [("sum by (outcome) (rate(medinfo_chat_seconds_count[5m]))", "{{outcome}}")],
        "reqps",
    ),
]


def main() -> None:
    panels = [
        panel(i + 1, t, e, x=(i % 2) * 12, y=(i // 2) * 8, unit=u) for i, (t, e, u) in enumerate(PANELS)
    ]
    dash = {
        "title": "MedInfo Assistant",
        "uid": "medinfo",
        "description": "Latency, safety and reliability signals. Labels contain no PHI.",
        "schemaVersion": 39,
        "version": 1,
        "time": {"from": "now-6h", "to": "now"},
        "refresh": "30s",
        "tags": ["medinfo"],
        "panels": panels,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dash, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
