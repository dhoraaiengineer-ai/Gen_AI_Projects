"""Repository — agent_metrics table (per-LLM-call cost and latency).

Rule 86 §2: cost calculation only happens in llm_service.py.
This repository is the single write path to the agent_metrics table.

No PII may enter this table — Rule 86 §4.
All fields are non-PII operational metrics only.

F-12: Vishal Prasad (Team 5) | Approved: ADR-006 (Mahesh Kumar, 02-Jul-2026)
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


class AgentMetricsRepository:
    """Data-access layer for agent_metrics table.

    Uses raw SQL (sa.text) — no ORM model required.
    Follows the same session-injection pattern as AuditLogRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None,
        x_trace_id: str,
        agent_name: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        latency_ms: int,
    ) -> None:
        """Insert a per-LLM-call metric record.

        Called exclusively from llm_service.py — never from agent nodes.
        No PII in any field (Rule 86 §4).
        """
        await self._session.execute(
            sa.text(
                """
                INSERT INTO agent_metrics (
                    id, organization_id, run_id, x_trace_id,
                    agent_name, provider,
                    prompt_tokens, completion_tokens, total_tokens,
                    cost_usd, latency_ms
                ) VALUES (
                    gen_random_uuid(), :organization_id, :run_id, :x_trace_id,
                    :agent_name, :provider,
                    :prompt_tokens, :completion_tokens, :total_tokens,
                    :cost_usd, :latency_ms
                )
                """
            ),
            {
                "organization_id": organization_id,
                "run_id": run_id,
                "x_trace_id": x_trace_id,
                "agent_name": agent_name,
                "provider": provider,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
            },
        )

    async def list_by_org(
        self,
        *,
        organization_id: uuid.UUID,
        agent_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[dict]:
        """List agent metrics for an org, newest first.

        Returns raw dicts — no ORM model.
        """
        query = """
            SELECT id, run_id, x_trace_id, agent_name, provider,
                   prompt_tokens, completion_tokens, total_tokens,
                   cost_usd, latency_ms, created_at
            FROM agent_metrics
            WHERE organization_id = :organization_id
              AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        params: dict = {
            "organization_id": organization_id,
            "limit": limit,
            "offset": offset,
        }
        if agent_name is not None:
            query = query.replace(
                "AND deleted_at IS NULL",
                "AND deleted_at IS NULL\n              AND agent_name = :agent_name",
            )
            params["agent_name"] = agent_name

        result = await self._session.execute(sa.text(query), params)
        return [dict(row._mapping) for row in result]

    async def list_by_run(
        self,
        *,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Sequence[dict]:
        """List all per-LLM-call metric rows for one evaluation run, oldest first.

        Added 12-Jul-2026 (Part B.0) — this table was already real and
        populated (ADR-006) but nothing queried it by run_id; it's the
        cheapest real data source for Pipeline Progress / Metrics Rail
        per-agent cost/token/provider detail. See METRICS_WIRING_MATRIX.md.
        """
        result = await self._session.execute(
            sa.text(
                """
                SELECT id, agent_name, provider,
                       prompt_tokens, completion_tokens, total_tokens,
                       cost_usd, latency_ms, created_at
                FROM agent_metrics
                WHERE run_id = :run_id
                  AND organization_id = :organization_id
                  AND deleted_at IS NULL
                ORDER BY created_at ASC
                """
            ),
            {"run_id": run_id, "organization_id": organization_id},
        )
        return [dict(row._mapping) for row in result]
