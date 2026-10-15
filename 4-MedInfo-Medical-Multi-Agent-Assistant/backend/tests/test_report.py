"""Evidence report: own conversations only, carries sources + safety wording, never PHI."""

from __future__ import annotations

from tests.fakes import FakeChatModel, cited


def _answer_model() -> FakeChatModel:
    return FakeChatModel(
        answer=cited(
            "Hypertension often causes no symptoms {a}.\nLIMITATIONS: Does not cover treatment.",
            a="no symptoms",
        )
    )


def test_report_contains_question_answer_sources_and_safety_wording(client_factory, auth_header) -> None:
    client, _ = client_factory(_answer_model())
    conv = client.post(
        "/api/chat", headers=auth_header, json={"question": "My name is Priya Sharma. What is hypertension?"}
    ).json()["conversation_id"]
    client.post(
        "/api/chat",
        headers=auth_header,
        json={"question": "I have crushing chest pain. What is hypertension?", "conversation_id": conv},
    )
    res = client.get(f"/api/conversations/{conv}/report", headers=auth_header)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert f'filename="medinfo-report-{conv[:8]}.md"' in res.headers["content-disposition"]
    md = res.text
    assert "## Question 1" in md and "## Question 2" in md
    assert "Hypertension often causes no symptoms [1]." in md
    assert "**Sources**" in md and "Adult Hypertension Guideline v3 (SYNTHETIC)" in md
    assert "Limitations:** Does not cover treatment." in md
    assert "In an emergency call 112" in md and "not medical advice" in md
    assert "Answer (emergency)" in md
    assert "Priya Sharma" not in md and "[NAME]" in md  # built only from redacted text


def test_report_is_private(client_factory, token_factory) -> None:
    client, _ = client_factory(_answer_model())
    a = {"Authorization": f"Bearer {token_factory('user', sub='A')}"}
    b = {"Authorization": f"Bearer {token_factory('user', sub='B')}"}
    conv = client.post("/api/chat", headers=a, json={"question": "What is hypertension?"}).json()[
        "conversation_id"
    ]
    assert client.get(f"/api/conversations/{conv}/report", headers=b).status_code == 404
    assert client.get(f"/api/conversations/{conv}/report").status_code == 401


def test_report_escapes_html_in_stored_text(client_factory, auth_header) -> None:
    client, _ = client_factory(FakeChatModel(answer="NOT_COVERED"))
    conv = client.post(
        "/api/chat", headers=auth_header, json={"question": "What about <script>alert(1)</script> asthma?"}
    ).json()["conversation_id"]
    md = client.get(f"/api/conversations/{conv}/report", headers=auth_header).text
    assert "<script>" not in md and "&lt;script&gt;" in md
