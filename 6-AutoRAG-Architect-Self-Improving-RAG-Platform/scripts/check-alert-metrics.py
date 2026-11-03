#!/usr/bin/env python3
"""Fail if a Prometheus alert rule references a metric name that doesn't exist.

Added 24-Jul-2026 (R-051, release audit): the UnifiedScoreDrop alert queried
autorag_unified_score, a metric that was never declared anywhere in
autorag-server/app/metrics.py -- the alert could never fire, silently, for
the entire time it existed. This check makes that class of drift a CI
failure instead of a finding that only surfaces during a manual audit.

Compares every metric name referenced in observability/alerts/autorag-alerts.yml
`expr:` fields against:
  1. Metric base names declared in autorag-server/app/metrics.py (Counter
     names get an implicit _total suffix; Histogram names get implicit
     _bucket/_sum/_count suffixes -- both per prometheus_client's real
     behavior).
  2. The fixed allowlist of prometheus_fastapi_instrumentator's built-in
     HTTP metrics (these are not declared in app/metrics.py at all, but are
     genuinely exported -- see app/main.py's Instrumentator().instrument(app)).

Usage: uv run python scripts/check-alert-metrics.py
Exit code 0 = all referenced metrics are real. Exit code 1 = drift found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALERTS_FILE = REPO_ROOT / "observability" / "alerts" / "autorag-alerts.yml"
METRICS_FILE = REPO_ROOT / "autorag-server" / "app" / "metrics.py"

# prometheus_fastapi_instrumentator's default exported series -- not declared
# in app/metrics.py, but genuinely real (wired in autorag-server/app/main.py).
INSTRUMENTATOR_BUILTINS = {
    "http_requests_total",
    "http_request_duration_seconds_bucket",
    "http_request_duration_seconds_sum",
    "http_request_duration_seconds_count",
    "http_request_size_bytes",
    "http_response_size_bytes",
}

METRIC_DECL_RE = re.compile(
    r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(Counter|Gauge|Histogram)\s*\(\s*\n?\s*"([a-z_][a-z0-9_]*)"',
    re.MULTILINE,
)

# Matches a PromQL metric identifier: a bare name, optionally followed by
# a `{...}` label selector. Deliberately excludes PromQL functions/keywords
# by requiring the name to start right after a word boundary and contain an
# underscore (every real metric in this codebase is autorag_* or the fixed
# http_* instrumentator set) -- avoids false positives on `rate(`, `sum(`,
# `by`, `le`, etc.
EXPR_METRIC_RE = re.compile(r"\b(autorag_[a-z0-9_]+|http_[a-z0-9_]+)\b")


def load_declared_metrics() -> set[str]:
    text = METRICS_FILE.read_text(encoding="utf-8")
    declared: set[str] = set(INSTRUMENTATOR_BUILTINS)
    for match in METRIC_DECL_RE.finditer(text):
        _var_name, kind, base_name = match.groups()
        if kind == "Counter":
            declared.add(f"{base_name}_total")
        elif kind == "Histogram":
            declared.add(f"{base_name}_bucket")
            declared.add(f"{base_name}_sum")
            declared.add(f"{base_name}_count")
        else:  # Gauge -- exported as-is, no suffix
            declared.add(base_name)
    return declared


def load_referenced_metrics() -> dict[str, list[str]]:
    """Return {metric_name: [alert_names_that_reference_it]}.

    Only scans real `expr:` values -- a single-line `expr: <promql>`, or a
    multi-line `expr: |` block (subsequent more-indented, non-comment lines,
    until indentation returns to the `expr:` level or shallower). Comment
    lines (possibly explaining a past metric-name fix, as in this file) are
    deliberately never scanned, so this can't false-positive on prose.
    """
    text = ALERTS_FILE.read_text(encoding="utf-8")
    referenced: dict[str, list[str]] = {}
    current_alert = "<unknown>"
    in_expr_block = False
    expr_block_indent = 0

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if stripped.startswith("#"):
            continue

        alert_match = re.match(r"\s*-\s*alert:\s*(\S+)", raw_line)
        if alert_match:
            current_alert = alert_match.group(1)
            in_expr_block = False
            continue

        if in_expr_block:
            if stripped and indent <= expr_block_indent:
                in_expr_block = False
            else:
                for name in EXPR_METRIC_RE.findall(raw_line):
                    referenced.setdefault(name, []).append(current_alert)
                continue

        expr_match = re.match(r"(\s*)expr:\s*(.*)", raw_line)
        if expr_match:
            leading, value = expr_match.groups()
            if value.strip() in ("", "|", "|-", ">", ">-"):
                in_expr_block = True
                expr_block_indent = len(leading)
            else:
                for name in EXPR_METRIC_RE.findall(value):
                    referenced.setdefault(name, []).append(current_alert)

    return referenced


def main() -> int:
    declared = load_declared_metrics()
    referenced = load_referenced_metrics()

    unknown = {name: alerts for name, alerts in referenced.items() if name not in declared}

    if unknown:
        print("FAIL: alert rules reference metrics that don't exist:\n", file=sys.stderr)
        for name, alerts in sorted(unknown.items()):
            alert_list = ", ".join(sorted(set(alerts)))
            print(f"  {name}  (referenced by: {alert_list})", file=sys.stderr)
        print(
            f"\nDeclared/known metrics ({len(declared)}): "
            f"{', '.join(sorted(declared))}",
            file=sys.stderr,
        )
        print(
            "\nEither the alert has a typo/stale metric name, or the metric "
            "needs to be declared in autorag-server/app/metrics.py and wired "
            "with a real .set()/.inc()/.observe() call.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: all {len(referenced)} metrics referenced in autorag-alerts.yml are real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
