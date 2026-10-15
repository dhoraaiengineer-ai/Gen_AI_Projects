"""LLM gateway: routing, token limits, passage budgeting, token accounting and the query-embedding cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.rag_graph import fit_passages
from app.container import build_container
from app.core.kv import InProcessKV
from app.core.metrics import TOKEN_BUDGET_EVENTS
from app.rag.cache import CachedEmbedder
from app.rag.gateway import GatewayPolicy, LLMGateway, TaskProfile, TokenBudgetExceededError, current_task
from app.rag.interfaces import Passage
from app.rag.prompts import AnswerMode, system_prompt
from tests.conftest import make_settings
from tests.fakes import FakeChatModel, FakeEmbedder

CONTAINER_TASKS = {"triage", "scope", "rewrite", "rerank", "judge", "answer", "eval_judge"}


class Recorder:
    def __init__(self, name: str = "fake:rec", reply: str = "ok") -> None:
        self.name = name
        self.reply = reply
        self.max_tokens: list[int | None] = []
        self.tasks: list[str] = []

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        self.max_tokens.append(max_tokens)
        self.tasks.append(current_task.get())
        return self.reply


def _policy(**task: TaskProfile) -> GatewayPolicy:
    return GatewayPolicy(chars_per_token=4, tasks=task)


def _passage(i: int, chars: int = 800) -> Passage:
    return Passage(id=f"p{i}", text="x" * chars, source="s", publisher="SYNTHETIC", title=f"T{i}")


# ---- policy file ---------------------------------------------------------------------------------
def test_policy_file_covers_every_task_and_is_consistent() -> None:
    policy = GatewayPolicy.load()
    assert set(policy.tasks) == CONTAINER_TASKS
    for name, p in policy.tasks.items():
        assert 0 < p.min_output_tokens <= p.max_output_tokens, name
    # Classifiers use the cheap route; the answer and the safety judge use the quality route.
    assert policy.tasks["answer"].route == "quality" and policy.tasks["judge"].route == "quality"
    assert {policy.tasks[t].route for t in ("triage", "scope", "rewrite", "rerank")} == {"fast"}


@pytest.mark.parametrize(
    "yaml_text",
    [
        "tasks: {a: {route: cheap, min_output_tokens: 1, max_output_tokens: 2, max_input_tokens: 3}}",
        "tasks: {a: {route: fast, min_output_tokens: 5, max_output_tokens: 2, max_input_tokens: 3}}",
        "tasks: {a: {route: fast, min_output_tokens: 1, max_output_tokens: 2, max_input_tokens: 0}}",
    ],
)
def test_invalid_policy_is_rejected(tmp_path: Path, yaml_text: str) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ValueError):
        GatewayPolicy.load(path)


def test_estimate_rounds_up() -> None:
    assert _policy().estimate_tokens("abcde", "") == 2


# ---- routing -------------------------------------------------------------------------------------
def test_tasks_are_routed_to_their_model_chain() -> None:
    fast, quality = Recorder("fast:m"), Recorder("quality:m")
    profile = {"min_output_tokens": 1, "max_output_tokens": 50, "max_input_tokens": 100}
    gw = LLMGateway(
        {"fast": fast, "quality": quality},
        _policy(scope=TaskProfile("fast", **profile), answer=TaskProfile("quality", **profile)),
    )
    gw.for_task("scope").complete("s", "u", temperature=0)
    gw.for_task("answer").complete("s", "u", temperature=0.2)
    assert fast.tasks == ["scope"] and quality.tasks == ["answer"]
    assert current_task.get() == "unknown"  # reset after the call
    assert {row["task"]: row["model"] for row in gw.describe()} == {"scope": "fast:m", "answer": "quality:m"}


def test_unknown_task_and_missing_route_fail_fast() -> None:
    with pytest.raises(ValueError):
        LLMGateway({"quality": Recorder()}, _policy())
    with pytest.raises(ValueError):
        LLMGateway({"fast": Recorder(), "quality": Recorder()}, _policy()).for_task("nope")


def test_container_routes_classifiers_to_fast_and_answers_to_quality(client_factory) -> None:
    quality, fast = FakeChatModel(name="quality:m"), FakeChatModel(name="fast:m")
    container = build_container(make_settings(), model=quality, classifier=fast, embedder=FakeEmbedder())
    container.chat.answer("What is hypertension?", user_id="u1")
    assert fast.count("triage") == 1 and fast.count("scope") == 1
    assert quality.count("triage") == 0 and quality.count("scope") == 0
    assert quality.count("answer") == 1 and fast.count("answer") == 0
    assert {row["task"] for row in container.gateway.describe()} == CONTAINER_TASKS


# ---- output token limits -----------------------------------------------------------------------
@pytest.mark.parametrize(("requested", "sent"), [(10, 32), (60, 60), (5000, 80), (None, 80)])
def test_output_budget_is_clamped_to_min_max(requested: int | None, sent: int) -> None:
    model = Recorder()
    gw = LLMGateway({"fast": model, "quality": model}, _policy(triage=TaskProfile("fast", 32, 80, 1000)))
    gw.for_task("triage").complete("s", "u", temperature=0, max_tokens=requested)
    assert model.max_tokens == [sent]


# ---- input token budget ------------------------------------------------------------------------
def test_prompt_over_input_budget_is_not_sent() -> None:
    model = Recorder()
    gw = LLMGateway({"fast": model, "quality": model}, _policy(scope=TaskProfile("fast", 1, 10, 10)))
    before = TOKEN_BUDGET_EVENTS.labels("scope", "input_rejected")._value.get()
    with pytest.raises(TokenBudgetExceededError):
        gw.for_task("scope").complete("s" * 30, "u" * 30, temperature=0)
    assert model.max_tokens == []  # no provider call, no tokens spent
    assert TOKEN_BUDGET_EVENTS.labels("scope", "input_rejected")._value.get() == before + 1


def test_passages_are_trimmed_lowest_ranked_first() -> None:
    model = Recorder()
    gw = LLMGateway({"fast": model, "quality": model}, _policy(answer=TaskProfile("quality", 1, 10, 900)))
    passages = [_passage(i) for i in range(1, 6)]  # ~200 tokens each
    kept = fit_passages(gw.for_task("answer"), system_prompt(AnswerMode.STANDARD), "What is it?", passages)
    assert 1 <= len(kept) < 5
    assert [p.id for p in kept] == [p.id for p in passages[: len(kept)]]  # top-ranked kept, in order


def test_passages_untouched_when_they_fit_or_model_has_no_budget() -> None:
    passages = [_passage(i, 50) for i in range(3)]
    model = Recorder()
    gw = LLMGateway({"fast": model, "quality": model}, _policy(answer=TaskProfile("quality", 1, 10, 6000)))
    assert fit_passages(gw.for_task("answer"), "sys", "q", passages) == passages
    assert fit_passages(Recorder(), "sys", "q", passages) == passages


# ---- query-embedding cache ---------------------------------------------------------------------
def test_query_embeddings_are_cached_without_storing_text() -> None:
    inner, kv = FakeEmbedder(), InProcessKV()
    emb = CachedEmbedder(inner, kv, ttl_seconds=60)
    first = emb.embed_query("What is hypertension?")
    second = emb.embed_query("What is hypertension?")
    assert first == second and inner.query_calls == 1
    emb.embed_query("What is asthma?")
    assert inner.query_calls == 2
    assert not any("hypertension" in key for key in kv._data)  # keys are hashes, never the text


def test_embedding_cache_outage_falls_through() -> None:
    class BrokenKV:
        def get(self, key: str) -> str | None:
            raise RuntimeError("redis down")

        def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
            raise RuntimeError("redis down")

    inner = FakeEmbedder()
    emb = CachedEmbedder(inner, BrokenKV(), ttl_seconds=60)  # type: ignore[arg-type]
    assert len(emb.embed_query("x")) == inner.dimensions and inner.query_calls == 1


def test_documents_are_never_cached() -> None:
    inner, kv = FakeEmbedder(), InProcessKV()
    CachedEmbedder(inner, kv, ttl_seconds=60).embed_documents(["a", "b"])
    assert inner.embedded_texts == ["a", "b"] and not kv._data
