"""Dashboard read models (SWR-cached per tenant) and system status.

Data comes from the analytics snapshot (already SWR-cached), execution records, the model cards
and — for markets, news and fraud — the same registry tools the agents use (so tool RBAC and
auditing apply to the UI too).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from src.config.settings import REPO_ROOT
from src.container import Container
from src.core.cache import SWRCache
from src.core.errors import Forbidden, NotFound, ProviderUnavailable
from src.data.repositories.payments import recent_fraud_alerts
from src.security.auth import Principal
from src.security.rbac import CLASSIFICATION_ACCESS
from src.tools.base import ToolContext

_CACHE = SWRCache("dashboard", ttl=60.0, stale_ttl=600.0)
MODEL_KINDS = ("fraud", "risk", "prediction")
DISCLAIMER = "Decision support only — not investment advice."


class DashboardPresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    async def _cached(self, principal: Principal, name: str, compute: Any) -> Any:
        return await _CACHE.get_or_compute(
            (principal.tenant_id, principal.role.value, name), compute
        )

    async def _tool(self, principal: Principal, tool: str, args: dict[str, Any]) -> Any:
        gateway = await self.container.mcp()
        ctx = ToolContext(
            role=principal.role, tenant_id=principal.tenant_id, user_id=principal.user_id
        )
        result = await gateway.call(tool, args, ctx)
        if not result.ok:
            error = result.error
            code = error.code if error else "failed"
            message = error.message if error else f"{tool} failed"
            raise {"unauthorized": Forbidden, "not_found": NotFound}.get(code, ProviderUnavailable)(
                message
            )
        return result.data

    async def _snapshots(self) -> list[dict[str, Any]]:
        portfolios = await self.container.portfolio_repo.list_all()
        snaps = await asyncio.gather(
            *(self.container.analytics.snapshot(p.code) for p in portfolios),
            return_exceptions=True,
        )
        return [s for s in snaps if isinstance(s, dict)]

    async def overview(self, principal: Principal) -> dict[str, Any]:
        async def compute() -> dict[str, Any]:
            snaps = await self._snapshots()
            activity = self.container.activity
            pending, recent = await asyncio.gather(
                activity.pending_approvals(), activity.recent_audit(8)
            )
            return {
                "portfolios": [
                    {
                        "portfolioId": s["portfolio"],
                        "name": s["name"],
                        "nav": s["nav"],
                        "dailyReturn": s["dailyReturn"],
                        "return1y": s["return1y"],
                        "volatility": s["volatility"],
                        "var95": s["var"]["historical95"]["pct"],
                        "breaches": s["breaches"],
                        "priceDate": s["priceDate"],
                    }
                    for s in snaps
                ],
                "totals": {
                    "nav": round(sum(s["nav"] for s in snaps), 2),
                    "breaches": sum(s["breaches"] for s in snaps),
                    "pendingApprovals": pending,
                },
                "recentActivity": recent,
                "disclaimer": DISCLAIMER,
            }

        result: dict[str, Any] = await self._cached(principal, "overview", compute)
        return result

    async def compliance(self, principal: Principal) -> dict[str, Any]:
        async def compute() -> dict[str, Any]:
            checks = [
                {"portfolioId": s["portfolio"], "name": s["name"], **c}
                for s in await self._snapshots()
                for c in s["limitChecks"]
            ]
            breached = [c for c in checks if c["breached"]]
            return {"checks": checks, "breaches": breached, "disclaimer": DISCLAIMER}

        result: dict[str, Any] = await self._cached(principal, "compliance", compute)
        return result

    async def markets(self, principal: Principal) -> dict[str, Any]:
        async def compute() -> Any:
            return await self._tool(principal, "get_market_summary", {})

        result: dict[str, Any] = await self._cached(principal, "markets", compute)
        return result

    async def news(self, principal: Principal) -> dict[str, Any]:
        async def compute() -> Any:
            return await self._tool(principal, "get_market_news", {"limit": 10})

        result: dict[str, Any] = await self._cached(principal, "news", compute)
        return result

    async def fraud(self, principal: Principal) -> dict[str, Any]:
        """Latest persisted fraud-model scores (written whenever the fraud agent or tool runs)."""
        alerts = await recent_fraud_alerts(self.container.database)
        return {
            "alerts": alerts,
            "flagged": sum(a["riskLevel"] in ("HIGH", "CRITICAL") for a in alerts),
            "note": "ML predictions on synthetic data; a fraud analyst must review before action.",
        }

    async def agents(self, principal: Principal) -> dict[str, Any]:
        server = await self.container.a2a_server()
        stats = {s["agent"]: s for s in await self.container.activity.agent_stats()}
        return {
            "agents": [
                card.model_dump() | {"stats": stats.get(card.name)} for card in server.cards()
            ]
        }

    async def trace(self, request_id: str) -> dict[str, Any]:
        return await self.container.activity.request_trace(request_id)

    async def conversations(self, principal: Principal) -> list[dict[str, Any]]:
        return await self.container.conversations.recent(principal.user_id)

    async def messages(self, principal: Principal, conversation_id: str) -> list[dict[str, Any]]:
        return await self.container.conversations.messages(conversation_id, principal.user_id)

    async def activity(self) -> list[dict[str, Any]]:
        return await self.container.activity.recent_audit(50)

    @staticmethod
    def ml_models() -> list[dict[str, Any]]:
        models = []
        for kind in MODEL_KINDS:
            path = REPO_ROOT / "models" / kind / "card.json"
            if not path.exists():
                continue
            card = json.loads(path.read_text(encoding="utf-8"))
            metrics = {k: v for k, v in card.get("metrics", {}).items() if k.startswith("test_")}
            models.append(
                {
                    "kind": kind,
                    "name": card.get("model") or f"{kind}-lgbm",
                    "version": card.get("version"),
                    "algorithm": card.get("algorithm"),
                    "trainedAt": card.get("trained_at"),
                    "features": len(card.get("features", [])),
                    "testMetrics": metrics,
                    "note": "Trained on synthetic data; metrics on a time-based test split.",
                }
            )
        return models

    async def system_status(self) -> dict[str, Any]:
        c, s = self.container, self.container.settings
        checks: dict[str, str] = {}
        for name, check in c.health_checks.items():
            try:
                await asyncio.wait_for(check(), timeout=3.0)
                checks[name] = "ok"
            except Exception:
                checks[name] = "unavailable"
        try:
            await asyncio.wait_for(c.kv.ping(), timeout=1.0)
            checks["redis"] = "ok" if s.redis_enabled else "disabled"
        except Exception:
            checks["redis"] = "unavailable (in-process fallback)"
        return {
            "checks": checks,
            "kvStore": c.kv.name,
            "circuits": c.circuit_states(),
            "answerChain": [str(m) for m in s.answer_chain],
            "agentChain": [str(m) for m in s.agent_chain],
            "demoMode": s.demo_mode,
            "environment": s.app_env,
        }

    @staticmethod
    def public_config(container: Container) -> dict[str, Any]:
        """Frontend bootstrap config. Contains no secrets (the publishable key is public)."""
        s = container.settings
        key = s.supabase_publishable_key.get_secret_value() if s.supabase_publishable_key else None
        return {
            "supabaseUrl": s.supabase_url,
            "supabasePublishableKey": key,
            "demoMode": s.demo_mode,
            "disclaimer": DISCLAIMER,
            "roles": sorted(r.value for r in CLASSIFICATION_ACCESS),
        }
