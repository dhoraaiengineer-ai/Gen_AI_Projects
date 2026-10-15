"""Agent trace: which agent ran, what it decided and how long it took - shown to the user under each answer
("How this answer was produced"). Holds decisions, counts and labels only: never question text, answer
text, passage text or upload filenames (it is returned to the browser and may be cached)."""

from __future__ import annotations

import time

from app.rag.schemas import TraceStep


class AgentTrace:
    def __init__(self) -> None:
        self.steps: list[TraceStep] = []
        self._mark = time.perf_counter()

    def step(self, agent: str, outcome: str, detail: str = "", status: str = "ok") -> None:
        """Record a finished step; duration is measured since the previous step."""
        now = time.perf_counter()
        self.steps.append(
            TraceStep(
                agent=agent,
                outcome=outcome,
                detail=detail,
                status=status,
                ms=round((now - self._mark) * 1000, 1),
            )
        )
        self._mark = now

    def restart_clock(self) -> None:
        self._mark = time.perf_counter()
