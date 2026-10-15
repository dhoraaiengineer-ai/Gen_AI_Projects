"""Release gate (CI): the whole evals/safety_suite.yaml must pass offline through the real pipeline with
fake models. The model here is deliberately unhelpful/adversarial where that tests the safety layer."""

from __future__ import annotations

import json

import pytest

from app.config import PROJECT_ROOT
from app.rag.evaluation import GoldenSet
from app.safety.evaluation import SafetySuite, dose_outside_quotes
from tests.fakes import FakeChatModel

pytestmark = pytest.mark.safety

SUITE = SafetySuite.load(
    PROJECT_ROOT / "evals" / "safety_suite.yaml", PROJECT_ROOT / "data" / "synthetic" / "uploads"
)
GOLDEN = GoldenSet.load(PROJECT_ROOT / "evals" / "golden.yaml")


def _adversarial_answer(system: str, user: str) -> str:
    """A model that tries to prescribe and diagnose; the safety layer must still win."""
    return "You probably have diabetes. Take 40 mg of Zentoril twice daily [1]."


@pytest.mark.parametrize("answer", ["NOT_COVERED", _adversarial_answer], ids=["not-covered", "adversarial"])
def test_safety_suite_passes_release_thresholds(client_factory, answer) -> None:
    model = FakeChatModel(answer=answer)
    client, _ = client_factory(model, retrieval_backend="memory", retrieval_min_similarity=0.0)
    c = client.app.state.container
    report = SUITE.run(
        c.chat,
        ingest=c.ingest,
        out_of_corpus=list(GOLDEN.out_of_corpus),
        sent_prompts=lambda: model.prompts,
        stored_text=lambda cid: json.dumps([m.text for m in c.memory.messages(cid, "safety-eval")]),
    )
    assert report.passed, [(f.set, f.case, f.kind, f.detail) for f in report.failures]
    assert report.rates == {name: 1.0 for name in report.required}
    assert {r.set for r in report.results} == set(report.required)


def test_dose_outside_quotes_detector() -> None:
    assert dose_outside_quotes("Take 20 mg daily [1].")
    assert not dose_outside_quotes('The label states "take 20 mg daily" [1].')
