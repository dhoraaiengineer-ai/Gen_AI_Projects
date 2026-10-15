"""Stage 7 backend: streamed phases, source listing, evaluation view data, and static UI safety rules."""

from __future__ import annotations

import json
import re

from app.config import REPO_ROOT
from tests.fakes import FakeChatModel, cited

STATIC = REPO_ROOT / "frontend" / "src"


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        ev = re.search(r"^event: (.*)$", block, re.M)
        data = re.search(r"^data: (.*)$", block, re.M)
        if ev and data:
            out.append((ev.group(1), json.loads(data.group(1))))
    return out


def test_stream_emits_real_phases_then_the_same_answer(client_factory, auth_header) -> None:
    model = FakeChatModel(answer=cited("Hypertension often causes no symptoms {a}.", a="no symptoms"))
    client, _ = client_factory(model, answer_cache_ttl_seconds=0)
    res = client.post("/api/chat/stream", headers=auth_header, json={"question": "What is hypertension?"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    events = _events(res.text)
    phases = [d["phase"] for e, d in events if e == "phase"]
    assert phases == ["safety", "searching", "generating", "verifying"]
    kind, answer = events[-1]
    assert kind == "answer" and answer["kind"] == "answer" and "[1]" in answer["answer"]
    plain = client.post("/api/chat", headers=auth_header, json={"question": "What is hypertension?"}).json()
    assert plain["answer"] == answer["answer"]


def test_stream_emergency_and_errors(client_factory, auth_header) -> None:
    from app.core.errors import ProviderQuotaError

    client, _ = client_factory(FakeChatModel(answer=ProviderQuotaError(retry_after=9)))
    events = _events(
        client.post("/api/chat/stream", headers=auth_header, json={"question": "What is hypertension?"}).text
    )
    assert events[-1][0] == "error" and events[-1][1]["status"] == 429 and events[-1][1]["retry_after"] == 9
    events = _events(
        client.post(
            "/api/chat/stream", headers=auth_header, json={"question": "I have crushing chest pain"}
        ).text
    )
    assert events[-1][1]["emergency"]["number"] == "112"


def test_stream_research_mode_is_role_gated(client_factory, token_factory) -> None:
    client, _ = client_factory()
    user = {"Authorization": f"Bearer {token_factory('user')}"}
    res = client.post("/api/chat/stream?mode=research", headers=user, json={"question": "x"})
    assert res.status_code == 403
    clin = {"Authorization": f"Bearer {token_factory('clinician')}"}
    assert (
        client.post("/api/chat/stream?mode=research", headers=clin, json={"question": "x"}).status_code == 503
    )


def test_sources_listing(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    admin = {"Authorization": f"Bearer {token_factory('admin')}"}
    a = {"Authorization": f"Bearer {token_factory('user', sub='A')}"}
    b = {"Authorization": f"Bearer {token_factory('user', sub='B')}"}
    client.post(
        "/api/admin/documents",
        headers=admin,
        data={
            "title": "BP (SYNTHETIC)",
            "publisher": "Synthetic Health Guidance Board (SYNTHETIC)",
            "doc_type": "guideline",
        },
        files={"file": ("bp.md", b"Hypertension text (SYNTHETIC).")},
    )
    client.post("/api/documents", headers=a, files={"file": ("mine.txt", b"SYNTHETIC note.")})
    sa, sb = client.get("/api/sources", headers=a).json(), client.get("/api/sources", headers=b).json()
    assert sa["publishers"] == ["Synthetic Health Guidance Board (SYNTHETIC)"] and sa["doc_types"] == [
        "guideline"
    ]
    assert len(sa["my_uploads"]) == 1 and sb["my_uploads"] == []


def test_evaluation_view_is_labelled_synthetic(client_factory, token_factory) -> None:
    from app.rag.evaluation import EvalRun

    client, _ = client_factory()
    client.app.state.container.eval_runs.add(
        EvalRun(
            "r1",
            "2026-10-14T10:00:00+00:00",
            "x",
            {"answer_model": "m", "items": 14},
            {"safety_emergency": 1.0},
        )
    )
    admin = {"Authorization": f"Bearer {token_factory('admin')}"}
    data = client.get("/api/admin/evaluations", headers=admin).json()
    assert "synthetic test set" in data["label"] and "not a measure of clinical performance" in data["label"]
    assert data["runs"][0]["metrics"]["safety_emergency"] == 1.0
    assert (
        client.get(
            "/api/admin/evaluations", headers={"Authorization": f"Bearer {token_factory('clinician')}"}
        ).status_code
        == 403
    )


def test_static_ui_never_injects_html_and_has_no_external_assets() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert not re.search(r"\.(inner|outer)HTML\s*=|insertAdjacentHTML|document\.write", js)
    assert not re.search(r"\beval\(|new Function\(", js)
    # No external assets: nothing loaded from another origin (plain-text mentions of a URL are fine).
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", html)
    assert not re.search(r"url\(\s*['\"]?https?://|@import", css)
    assert "style=" not in html and "<script>" not in html  # strict CSP: no inline style/script
    assert "Information only, not medical advice." in html


def test_ui_makes_no_validation_claims() -> None:
    text = " ".join((STATIC / n).read_text(encoding="utf-8").lower() for n in ("index.html", "app.js"))
    for banned in (
        "clinically validated",
        "fda approved",
        "fda-approved",
        "ce marked",
        "% accurate",
        "accuracy of",
    ):
        assert banned not in text.replace("not clinically validated", ""), banned


def test_ui_assets_are_always_revalidated(client_factory) -> None:
    client, _ = client_factory()
    for path in ("/", "/static/app.js", "/static/app.css"):
        assert client.get(path).headers["Cache-Control"] == "no-cache", path
    assert client.get("/favicon.ico").status_code == 200
