"""Document API: admin-only trusted ingestion, private user uploads, and chat over ingested documents."""

from __future__ import annotations

from app.config import PROJECT_ROOT
from tests.fakes import FakeChatModel, cited

CORPUS = PROJECT_ROOT / "data" / "synthetic" / "corpus"
PUBLISHER = "Synthetic Health Guidance Board (SYNTHETIC)"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload_trusted(client, headers, name: str, **form: str):
    data = {"title": f"{name} (SYNTHETIC)", "publisher": PUBLISHER, "publication_date": "2024-01-01", **form}
    return client.post(
        "/api/admin/documents",
        headers=headers,
        data=data,
        files={"file": (name, (CORPUS / name).read_bytes())},
    )


def test_trusted_ingest_is_admin_only(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    user = bearer(token_factory("user"))
    clinician = bearer(token_factory("clinician"))
    assert upload_trusted(client, user, "label_zentoril.docx").status_code == 403
    assert upload_trusted(client, clinician, "label_zentoril.docx").status_code == 403
    assert client.get("/api/admin/documents", headers=user).status_code == 403


def test_admin_ingest_list_delete(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    admin = bearer(token_factory("admin", sub="admin-1"))
    res = upload_trusted(client, admin, "label_zentoril.docx", version="2.1")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "added" and body["chunks_total"] > 0

    again = upload_trusted(client, admin, "label_zentoril.docx", version="2.1").json()
    assert again["status"] == "unchanged" and again["embedded"] == 0

    docs = client.get("/api/admin/documents", headers=admin).json()
    assert docs[0]["publisher"] == PUBLISHER and docs[0]["licence"] == "CC0 (synthetic test data)"
    assert client.delete(f"/api/admin/documents/{body['doc_id']}", headers=admin).status_code == 200
    assert client.get("/api/admin/documents", headers=admin).json() == []


def test_admin_ingest_rejects_unlisted_publisher_and_bad_types(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    admin = bearer(token_factory("admin"))
    assert upload_trusted(client, admin, "label_zentoril.docx", publisher="Random Blog").status_code == 422
    res = client.post(
        "/api/admin/documents",
        headers=admin,
        data={"title": "x", "publisher": PUBLISHER},
        files={"file": ("tool.exe", b"MZ")},
    )
    assert res.status_code == 415


def test_upload_size_limit(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory", max_upload_mb=1)
    res = client.post(
        "/api/documents",
        headers=bearer(token_factory("user")),
        files={"file": ("big.txt", b"a" * (1024 * 1024 + 10))},
    )
    assert res.status_code == 413


def test_user_uploads_are_private(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    a = bearer(token_factory("user", sub="user-A"))
    b = bearer(token_factory("user", sub="user-B"))
    note = (PROJECT_ROOT / "data" / "synthetic" / "uploads" / "case_note_synthetic_001.txt").read_bytes()
    up = client.post("/api/documents", headers=a, files={"file": ("note.txt", note)}).json()

    assert [d["doc_id"] for d in client.get("/api/documents", headers=a).json()] == [up["doc_id"]]
    assert client.get("/api/documents", headers=b).json() == []
    assert client.delete(f"/api/documents/{up['doc_id']}", headers=b).status_code == 404
    assert client.get("/api/documents", headers=a).json()[0]["trusted"] is False
    assert client.delete(f"/api/documents/{up['doc_id']}", headers=a).status_code == 200


def test_chat_cites_ingested_docx_section(client_factory, token_factory) -> None:
    model = FakeChatModel(
        answer=cited(
            'The label states "Zentoril should not be used during pregnancy" {a}.\nLIMITATIONS: Label only.',
            a="should not be used during pregnancy",
        )
    )
    client, _ = client_factory(model, retrieval_backend="memory", retrieval_min_similarity=0.05)
    admin = bearer(token_factory("admin"))
    assert upload_trusted(client, admin, "label_zentoril.docx", doc_type="drug_label").status_code == 200

    res = client.post(
        "/api/chat",
        headers=bearer(token_factory("user")),
        json={"question": "Can Zentoril be used during pregnancy?"},
    )
    body = res.json()
    assert body["kind"] == "answer", body
    assert body["citations"][0]["location"] == "4.6 Pregnancy"
    assert body["citations"][0]["title"] == "label_zentoril.docx (SYNTHETIC)"
    assert body["safety"]["checks"]["faithfulness"] is True  # pregnancy -> high risk -> judge ran


def test_user_upload_cited_as_user_provided(client_factory, token_factory) -> None:
    model = FakeChatModel(
        answer=cited("The note records tiredness and thirst for 3 weeks {a}.", a="tiredness and thirst")
    )
    client, _ = client_factory(model, retrieval_backend="memory", retrieval_min_similarity=0.05)
    a = bearer(token_factory("user", sub="user-A"))
    note = b"SYNTHETIC case note. Presenting complaint: tiredness and thirst for 3 weeks."
    client.post("/api/documents", headers=a, files={"file": ("note.txt", note)})
    body = client.post(
        "/api/chat", headers=a, json={"question": "What does my note say about tiredness and thirst?"}
    ).json()
    assert body["citations"][0]["user_provided"] is True
    assert body["citations"][0]["publisher"].endswith("(user-provided)")
