"""Call the ML tools against the configured database (no LLM calls).

    uv run python -m scripts.ml_check

Uses the demo tenant (Northwind) and the trained models (registry, else exported bundles).
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from src.config.settings import get_settings
from src.container import Container
from src.core.domain import Role
from src.core.logging import configure_logging
from src.core.tenancy import DEMO_TENANT_ID
from src.tools.base import ToolContext

CALLS: list[tuple[str, dict[str, Any], Role, str]] = [
    ("predict_risk", {"portfolio_id": "PF-A"}, Role.RISK_MANAGER, "risk"),
    ("calculate_risk_score", {"portfolio_id": "PF-C"}, Role.RISK_MANAGER, "risk"),
    ("predict_fraud", {"customer_id": "CU-000123", "days": 183}, Role.FRAUD_ANALYST, "fraud"),
    ("detect_anomaly", {"customer_id": "CU-000123", "days": 183}, Role.FRAUD_ANALYST, "fraud"),
    ("predict_market_trend", {"ticker": "NVTK"}, Role.ANALYST, "prediction"),
    ("predict_financial_metric", {"ticker": "NVTK"}, Role.ANALYST, "prediction"),
]


def _short(data: Any) -> str:
    text = json.dumps(data, default=str)
    return text if len(text) < 700 else text[:700] + " …"


async def run() -> int:
    container = Container.build(get_settings())
    failures = 0
    try:
        for tool, args, role, agent in CALLS:
            ctx = ToolContext(
                role=role, tenant_id=str(DEMO_TENANT_ID), agent=agent, request_id="ml_check"
            )
            result = await container.tools.execute(tool, args, ctx)
            status = "OK " if result.ok else "ERR"
            failures += not result.ok
            print(f"\n[{status}] {tool} {args}")
            print("   " + _short(result.data if result.ok else result.error))
    finally:
        await container.aclose()
    return 1 if failures else 0


def main() -> None:
    configure_logging()
    sys.exit(asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop))


if __name__ == "__main__":
    main()
