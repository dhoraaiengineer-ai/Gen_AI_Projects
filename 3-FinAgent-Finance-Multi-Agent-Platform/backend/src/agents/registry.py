"""Builds the specialist agents and publishes them on the A2A transport with agent cards.

The supervisor reaches agents only through A2A envelopes; nothing imports an agent directly except
this composition module.
"""

from __future__ import annotations

from typing import Any

from src.a2a.client import InProcessTransport
from src.a2a.messages import A2AEnvelope, AgentCard
from src.agents.base import AgentDeps, AgentTask, BaseAgent
from src.agents.compliance.agent import ComplianceAgent
from src.agents.fraud.agent import FraudAgent
from src.agents.market.agent import MarketAgent
from src.agents.portfolio.agent import PortfolioAgent
from src.agents.prediction.agent import PredictionAgent
from src.agents.research.agent import ResearchAgent
from src.agents.risk.agent import RiskAgent
from src.core.domain import Role
from src.tools.base import ToolContext


def build_agents(deps: AgentDeps, *, approval_threshold: float) -> dict[str, BaseAgent]:
    agents: list[BaseAgent] = [
        PortfolioAgent(deps),
        MarketAgent(deps),
        RiskAgent(deps),
        ComplianceAgent(deps, approval_threshold=approval_threshold),
        FraudAgent(deps),
        ResearchAgent(deps),
        PredictionAgent(deps),
    ]
    return {a.name: a for a in agents}


def _handler(agent: BaseAgent) -> Any:
    async def handle(envelope: A2AEnvelope) -> dict[str, Any]:
        ctx = ToolContext(
            role=Role(envelope.context.role),
            tenant_id=envelope.context.tenant_id,
            user_id=envelope.context.user_id,
            request_id=envelope.context.request_id,
            trace_id=envelope.context.trace_id,
        )
        task = AgentTask.model_validate(envelope.payload)
        result = await agent.run(task, ctx)
        return result.model_dump(mode="json")

    return handle


def publish(agents: dict[str, BaseAgent], transport: InProcessTransport) -> InProcessTransport:
    for agent in agents.values():
        card = AgentCard(
            name=agent.name,
            description=agent.description.strip(),
            tasks=list(agent.tasks),
            tools=list(agent.llm_tools),
        )
        transport.register(card, _handler(agent))
    return transport
