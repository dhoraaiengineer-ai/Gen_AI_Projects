"""The LLM gateway's token limits must never weaken safety: an over-budget call behaves like a failed model
call (triage and scope fall back to the local rules, the faithfulness judge fails closed), and trimmed
passages are exactly what the verifier checks against."""

from __future__ import annotations

import pytest

from app.agents.rag_graph import build_rag_graph
from app.rag.gateway import GatewayPolicy, LLMGateway, TaskProfile
from app.rag.interfaces import Passage
from app.rag.prompts import AnswerMode
from app.safety.answer_checks import FaithfulnessJudge, citations_in
from app.safety.scope import Scope, ScopeClassifier
from app.safety.triage import RedFlagRules, TriageService
from tests.fakes import FakeChatModel

pytestmark = pytest.mark.safety

CHEST = "I have crushing chest pain going down my left arm"
TINY = TaskProfile("fast", 1, 10, 1)  # every prompt is over this input budget


def _tiny_gateway(model: FakeChatModel) -> LLMGateway:
    tasks = {t: TINY for t in ("triage", "scope", "judge", "rerank", "rewrite", "answer", "eval_judge")}
    return LLMGateway({"fast": model, "quality": model}, GatewayPolicy(chars_per_token=4, tasks=tasks))


def test_over_budget_triage_still_fires_on_rules() -> None:
    model = FakeChatModel()
    result = TriageService(RedFlagRules.load(), _tiny_gateway(model).for_task("triage")).assess(CHEST)
    assert result.is_emergency and "rules" in result.detectors
    assert model.count("triage") == 0  # the over-budget call was never sent


def test_over_budget_scope_falls_back_to_rules() -> None:
    model = FakeChatModel()
    decision = ScopeClassifier(_tiny_gateway(model).for_task("scope")).classify(
        "Can I double my dose of Zentoril?"
    )
    assert decision.scope is Scope.PRESCRIBING_OR_DOSING and not decision.llm_ok


def test_over_budget_judge_fails_closed() -> None:
    model = FakeChatModel()
    passage = Passage(id="p1", text="Zentoril label text.", source="s", publisher="SYNTHETIC", title="Label")
    result = FaithfulnessJudge(_tiny_gateway(model).for_task("judge")).judge("Answer [1].", [passage])
    assert result.passed is False and model.count("judge") == 0


def test_trimmed_passages_are_what_the_model_saw_and_the_verifier_checks() -> None:
    """Over the answer budget, only top-ranked passages reach the model, and the graph returns that same
    list - so a citation to a trimmed passage is out of range for the citation check."""
    big = [
        Passage(id=f"p{i}", text="synthetic text " * 150, source="s", publisher="SYNTHETIC", title=f"T{i}")
        for i in range(1, 6)
    ]

    class FixedRetriever:
        def retrieve(self, query, k, filters=None, *, queries=None):
            return big

    model = FakeChatModel(answer="Text [1].")
    policy = GatewayPolicy(chars_per_token=4, tasks={"answer": TaskProfile("quality", 256, 1200, 1500)})
    answer_model = LLMGateway({"fast": model, "quality": model}, policy).for_task("answer")
    graph = build_rag_graph(FixedRetriever(), answer_model, 0.2)
    state = graph.invoke({"question": "What is it?", "mode": AnswerMode.STANDARD, "k": 5})
    kept = state["passages"]
    assert 1 <= len(kept) < len(big) and kept == big[: len(kept)]
    sent = model.prompts[-1]
    assert sent.count("<passage n=") == len(kept)
    assert citations_in(f"Claim [{len(kept) + 1}].") - set(range(1, len(kept) + 1))  # out of range
