"""SLO and threshold config loader -- AutoRAG Architect (G-1).

Centralises all deployment gates, SLO targets, cost budgets, and token
limits into a single YAML source (config/production/slo.yaml).

Follows the same pattern as:
  config/model_pricing.yaml   -> loaded in app/services/llm_service.py
  config/token_budgets.yaml   -> loaded in app/services/token_guardrail.py

Usage:
    from app.core.config_loader import slo_config

    gate = slo_config["deployment_gate"]["unified_score_min"]  # 0.85
    latency = slo_config["slo_targets"]["p95_latency_ms"]      # 3000
"""

from __future__ import annotations

import pathlib
from functools import lru_cache
from typing import Any

import yaml

_CONFIG_DIR = pathlib.Path(__file__).parent.parent.parent / "config"


@lru_cache(maxsize=1)
def load_slo_config() -> dict[str, Any]:
    """Load config/production/slo.yaml and return as a nested dict.

    Raises FileNotFoundError if the file is missing (fail-fast at startup).
    Cached after first call -- safe to import at module level.
    """
    slo_path = _CONFIG_DIR / "production" / "slo.yaml"
    if not slo_path.exists():
        raise FileNotFoundError(
            f"SLO config not found: {slo_path}. "
            "Create config/production/slo.yaml from the provided template."
        )
    with slo_path.open(encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)
    return loaded


# Module-level singleton -- import this in services that need SLO thresholds.
# Loaded once at startup; cached via @lru_cache on load_slo_config.
slo_config: dict[str, Any] = load_slo_config()
