"""TypeSafe AI **Jev** decision model adapter (ADR-027).

Jev is a "System One" model: it returns typed decisions instead of text —

* ``noul``   yes/no → ``{"noul": P(yes)}``
* ``choice`` pick a label from ``criteria: {label: description}`` → ``choice``, ``confidence``,
  ``probabilities``
* ``score``  ordered rubric ``criteria: [level0, level1, ...]`` → expected ``score``,
  ``confidence``, ``probabilities``

API (from the official ``@typesafe-ai/sdk`` 0.6 types): ``POST {base}/v1/systemone`` with
``Authorization: Bearer <TYPESAFE_API_KEY>`` and body ``{state, questions, model}``.
Calls get a timeout, one retry for transient errors, a circuit breaker and metrics; callers always
have a deterministic fallback.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from pydantic import SecretStr

from src.core.errors import AppError, ProviderError, map_provider_exception
from src.core.metrics import DECISION_LATENCY, DECISION_REQUESTS
from src.core.ports import Decision, DecisionResult
from src.core.retry import retry_async
from src.providers.llm import BREAKERS

logger = logging.getLogger(__name__)


def noul(instructions: str, *, yes: str | None = None, no: str | None = None) -> dict[str, object]:
    question: dict[str, object] = {"type": "noul", "instructions": instructions}
    if yes or no:
        question["criteria"] = {"true": yes, "false": no}
    return question


def choice(instructions: str, criteria: dict[str, str | None]) -> dict[str, object]:
    if len(criteria) < 2:
        raise ValueError("a choice needs at least two labels")
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, rubric: list[str | None]) -> dict[str, object]:
    if len(rubric) < 2:
        raise ValueError("a score rubric needs at least two levels")
    return {"type": "score", "instructions": instructions, "criteria": rubric}


def parse_answer(name: str, raw: dict[str, Any], provider: str) -> Decision:
    kind = raw.get("type")
    if kind == "noul":
        return Decision("noul", float(raw["noul"]), provider=provider)
    if kind == "choice":
        probs = {str(k): float(v) for k, v in (raw.get("probabilities") or {}).items()}
        return Decision(
            "choice", str(raw["choice"]), float(raw.get("confidence", 0.0)), probs, provider
        )
    if kind == "score":
        probs = {str(k): float(v) for k, v in (raw.get("probabilities") or {}).items()}
        return Decision(
            "score", float(raw["score"]), float(raw.get("confidence", 0.0)), probs, provider
        )
    raise ProviderError(f"unexpected answer type for {name!r}", details={"type": str(kind)})


class JevDecisionModel:
    name = "jev"

    def __init__(
        self,
        api_key: SecretStr,
        *,
        base_url: str = "https://api.typesafe.ai",
        model: str = "jev-latest",
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._key = api_key
        self._url = base_url.rstrip("/") + "/v1/systemone"
        self.model = model
        self._timeout = timeout
        self._client = client
        self._breaker_key = f"typesafe:{model}"

    async def decide(
        self, state: object, questions: dict[str, dict[str, object]]
    ) -> DecisionResult:
        if not questions:
            raise ValueError("at least one question is required")
        body = {"state": state, "questions": questions, "model": self.model}
        breaker = BREAKERS.get(self._breaker_key)

        async def once() -> DecisionResult:
            breaker.before_call()
            started = time.perf_counter()
            try:
                client = self._client or httpx.AsyncClient(timeout=self._timeout)
                try:
                    response = await client.post(
                        self._url,
                        json=body,
                        headers={"Authorization": f"Bearer {self._key.get_secret_value()}"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                finally:
                    if self._client is None:
                        await client.aclose()
                answers = {n: parse_answer(n, a, self.name) for n, a in payload["answers"].items()}
            except Exception as exc:
                error = map_provider_exception(exc, provider="typesafe")
                breaker.record_failure(error)
                DECISION_REQUESTS.labels(provider=self.name, status=error.code).inc()
                raise error from exc
            elapsed = (time.perf_counter() - started) * 1000
            breaker.record_success()
            DECISION_REQUESTS.labels(provider=self.name, status="ok").inc()
            DECISION_LATENCY.labels(provider=self.name).observe(elapsed / 1000)
            usage = payload.get("usage") or {}
            return DecisionResult(
                answers,
                self.name,
                str(payload.get("model", self.model)),
                elapsed,
                int(usage.get("input_tokens", 0)),
            )

        try:
            return await retry_async(once, attempts=2, base=0.2, label="jev")
        except AppError:
            logger.warning("jev decision failed", extra={"questions": sorted(questions)})
            raise
