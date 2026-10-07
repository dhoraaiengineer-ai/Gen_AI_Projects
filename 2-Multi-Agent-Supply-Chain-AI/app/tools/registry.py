"""Tool authorization: which agent may call which tool, and the minimum user role for each tool.

Checked on every call. An agent never sees tools outside its allow-list, and a tool call that slips through
(e.g. a hallucinated tool name) is rejected and audited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.metrics import TOOL_DENIED
from app.core.rbac import Role, User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolPolicy:
    agents: frozenset[str]
    min_role: Role


POLICIES: dict[str, ToolPolicy] = {
    # demand
    "get_sales_history": ToolPolicy(frozenset({"demand", "inventory"}), Role.VIEWER),
    "get_demand_forecast": ToolPolicy(frozenset({"demand", "inventory"}), Role.VIEWER),
    "get_product_history": ToolPolicy(frozenset({"demand"}), Role.VIEWER),
    # inventory (read-only)
    "get_inventory": ToolPolicy(frozenset({"inventory"}), Role.VIEWER),
    "get_stockout_risks": ToolPolicy(frozenset({"inventory"}), Role.VIEWER),
    "calculate_reorder_quantity": ToolPolicy(frozenset({"inventory"}), Role.ANALYST),
    # supplier (prices need analyst+)
    "get_suppliers": ToolPolicy(frozenset({"supplier"}), Role.ANALYST),
    "get_supplier_price": ToolPolicy(frozenset({"supplier"}), Role.ANALYST),
    "get_supplier_lead_time": ToolPolicy(frozenset({"supplier"}), Role.ANALYST),
    "get_supplier_score": ToolPolicy(frozenset({"supplier"}), Role.ANALYST),
    "recommend_supplier": ToolPolicy(frozenset({"supplier"}), Role.ANALYST),
    # logistics
    "get_shipments": ToolPolicy(frozenset({"logistics"}), Role.VIEWER),
    "get_delivery_status": ToolPolicy(frozenset({"logistics"}), Role.VIEWER),
    "get_carrier_rates": ToolPolicy(frozenset({"logistics"}), Role.ANALYST),
    "estimate_delivery": ToolPolicy(frozenset({"logistics"}), Role.VIEWER),
    # knowledge / research
    "search_knowledge_base": ToolPolicy(frozenset({"rag", "research", "supplier"}), Role.VIEWER),
    "search_web": ToolPolicy(frozenset({"research"}), Role.ANALYST),
}

AGENT_TOOLS: dict[str, list[str]] = {
    agent: [name for name, p in POLICIES.items() if agent in p.agents]
    for agent in ("demand", "inventory", "supplier", "logistics", "rag", "research")
}


class ToolDenied(Exception):
    def __init__(self, tool: str, agent: str, reason: str) -> None:
        super().__init__(f"{agent} may not call {tool}: {reason}")
        self.tool, self.agent, self.reason = tool, agent, reason


def authorize(tool: str, agent: str, user: User) -> None:
    policy = POLICIES.get(tool)
    if policy is None:
        reason = "unknown tool"
    elif agent not in policy.agents:
        reason = "not in agent allow-list"
    elif not user.role.at_least(policy.min_role):
        reason = f"requires role {policy.min_role.value}"
    else:
        return
    TOOL_DENIED.labels(tool, agent).inc()
    logger.warning("tool call denied", extra={"tool": tool, "agent": agent, "role": user.role.value, "reason": reason})
    raise ToolDenied(tool, agent, reason)


def tools_for(agent: str, user: User) -> list[str]:
    """Tools this agent may use for this user (role-filtered), e.g. viewers' supplier agent gets no price tools."""
    return [t for t in AGENT_TOOLS.get(agent, []) if user.role.at_least(POLICIES[t].min_role)]
