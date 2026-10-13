"""Jev adapter against a fake TypeSafe server; DecisionService fallback behaviour."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from src.core.decisions import DecisionService
from src.core.errors import ProviderError, QuotaExceeded
from src.providers.decisions import JevDecisionModel, choice, noul, parse_answer, score
from src.providers.llm import BREAKERS


@pytest.fixture(autouse=True)
def fresh_breakers() -> Iterator[None]:
    BREAKERS.reset()
    yield
    BREAKERS.reset()


def jev(handler: Any) -> JevDecisionModel:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return JevDecisionModel(SecretStr("ts-test"), base_url="https://fake.typesafe", client=client)


QUESTIONS = {
    "intent": choice("Main intent of `question`?", {"portfolio_risk": "risk", "other": None}),
    "is_finance": noul("Is `question` about finance?"),
    "urgency": score("How urgent?", ["not urgent", "somewhat", "very"]),
}


async def test_request_format_and_typed_answers() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "intent": {
                        "type": "choice",
                        "choice": "portfolio_risk",
                        "confidence": 0.93,
                        "probabilities": {"portfolio_risk": 0.93, "other": 0.07},
                    },
                    "is_finance": {"type": "noul", "noul": 0.98},
                    "urgency": {
                        "type": "score",
                        "score": 1.4,
                        "confidence": 0.6,
                        "legend": {"0": "not urgent"},
                        "probabilities": {"0": 0.1, "1": 0.4, "2": 0.5},
                    },
                },
                "usage": {"input_tokens": 283, "output_tokens": 23},
            },
        )

    result = await jev(handler).decide({"question": "Why did PF-A risk rise?"}, QUESTIONS)
    assert seen["url"] == "https://fake.typesafe/v1/systemone"
    assert seen["auth"] == "Bearer ts-test"
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["questions"]["intent"]["criteria"] == {
        "portfolio_risk": "risk",
        "other": None,
    }
    assert seen["body"]["questions"]["urgency"]["criteria"] == ["not urgent", "somewhat", "very"]
    assert result.answers["intent"].value == "portfolio_risk"
    assert result.answers["intent"].confidence == pytest.approx(0.93)
    assert result.answers["is_finance"].value == pytest.approx(0.98)
    assert result.answers["urgency"].value == pytest.approx(1.4)
    assert result.model == "jev-1.13.0" and result.input_tokens == 283


async def test_quota_error_maps_and_service_falls_back() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    model = jev(handler)
    with pytest.raises(QuotaExceeded):
        await model.decide("x", {"q": noul("?")})
    assert len(calls) == 1  # quota is never retried
    assert await DecisionService(model).decide("routing", "x", {"q": noul("?")}) is None


async def test_service_without_model_returns_none() -> None:
    service = DecisionService(None)
    assert not service.available
    assert await service.decide("routing", "x", {"q": noul("?")}) is None


def test_question_builders_validate() -> None:
    with pytest.raises(ValueError):
        choice("?", {"only": None})
    with pytest.raises(ValueError):
        score("?", ["one"])
    assert noul("?", yes="breach", no="fine")["criteria"] == {"true": "breach", "false": "fine"}


def test_unknown_answer_type_is_provider_error() -> None:
    with pytest.raises(ProviderError):
        parse_answer("q", {"type": "essay"}, "jev")
