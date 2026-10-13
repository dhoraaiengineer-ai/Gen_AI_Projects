"""Decision service (ADR-027): fast typed decisions with a mandatory fallback path.

``decide()`` returns a :class:`DecisionResult` from the decision model (Jev) or ``None`` when it is
not configured or failed; every caller then uses its own deterministic / LLM fallback. Decisions
never override hard rules — callers apply rules first and use the model only where judgement is
needed.
"""

from __future__ import annotations

import logging

from src.core.errors import AppError
from src.core.metrics import DECISION_FALLBACKS
from src.core.ports import DecisionModel, DecisionResult

logger = logging.getLogger(__name__)


class DecisionService:
    def __init__(self, model: DecisionModel | None) -> None:
        self.model = model

    @property
    def available(self) -> bool:
        return self.model is not None

    async def decide(
        self, purpose: str, state: object, questions: dict[str, dict[str, object]]
    ) -> DecisionResult | None:
        if self.model is None:
            DECISION_FALLBACKS.labels(purpose=purpose, reason="not_configured").inc()
            return None
        try:
            result = await self.model.decide(state, questions)
        except AppError as exc:
            DECISION_FALLBACKS.labels(purpose=purpose, reason=exc.code).inc()
            logger.warning(
                "decision model unavailable; using fallback",
                extra={"purpose": purpose, "error": exc.code},
            )
            return None
        logger.info(
            "decision",
            extra={
                "purpose": purpose,
                "provider": result.provider,
                "latency_ms": round(result.latency_ms, 1),
            },
        )
        return result
