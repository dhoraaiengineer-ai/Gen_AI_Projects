"""Stage 6: metrics, audit log, and the monitoring config files."""

from __future__ import annotations

import json
import logging
import re

import yaml

from app.config import PROJECT_ROOT
from tests.fakes import FakeChatModel


def _capture(caplog, action) -> None:
    """create_app() reconfigures the root logger; re-attach pytest's handler while the action runs."""
    root = logging.getLogger()
    root.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO):
            action()
    finally:
        root.removeHandler(caplog.handler)


def _metric(text: str, name: str, **labels: str) -> float:
    total = 0.0
    for line in text.splitlines():
        if not line.startswith(name + "{") and not line.startswith(name + " "):
            continue
        if all(f'{k}="{v}"' in line for k, v in labels.items()):
            total += float(line.rsplit(" ", 1)[1])
    return total


def test_metrics_endpoint_and_route_templates(client_factory, token_factory) -> None:
    client, _ = client_factory(retrieval_backend="memory")
    user = {"Authorization": f"Bearer {token_factory('user')}"}
    client.delete(
        "/api/documents/doc_0123456789abcdef01234567", headers=user
    )  # 404, but labelled by template
    text = client.get("/metrics").text
    assert _metric(text, "medinfo_http_requests_total", route="/api/documents/{doc_id}", status="404") >= 1
    assert "doc_0123456789abcdef01234567" not in text  # no raw ids / free text in labels
    assert "medinfo_http_request_seconds_bucket" in text


def test_metrics_token_required_when_configured(client_factory) -> None:
    client, _ = client_factory(metrics_token="scrape-secret-123")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer scrape-secret-123"}).status_code == 200


def test_safety_metrics_increment(client_factory, auth_header) -> None:
    client, _ = client_factory(FakeChatModel(answer="Hypertension is caused by stress."))
    before = client.get("/metrics").text
    client.post("/api/chat", headers=auth_header, json={"question": "I have crushing chest pain"})
    client.post(
        "/api/chat", headers=auth_header, json={"question": "What is hypertension?"}
    )  # uncited -> blocked
    after = client.get("/metrics").text
    for name, labels in [
        ("medinfo_triage_events_total", {"category": "chest_pain"}),
        ("medinfo_hallucination_flags_total", {"check": "citations"}),
        ("medinfo_refusals_total", {"reason": "citations"}),
    ]:
        assert _metric(after, name, **labels) > _metric(before, name, **labels), name


def test_one_audit_line_per_request_without_phi(client_factory, auth_header, caplog) -> None:
    client, _ = client_factory(FakeChatModel(answer="NOT_COVERED"))
    question = "My name is Priya Sharma. What is the survival rate for pancreatic cancer?"
    _capture(caplog, lambda: client.post("/api/chat", headers=auth_header, json={"question": question}))
    audit = [r for r in caplog.records if r.name == "audit"]
    requests = [r for r in audit if r.audit_action == "http.request"]
    actions = [r for r in audit if r.audit_action == "chat.answer"]
    assert len(requests) == 1 and len(actions) == 1
    assert (
        requests[0].user_id == "user-123" and requests[0].route == "/api/chat" and requests[0].status == 200
    )
    dumped = json.dumps([r.__dict__ for r in audit], default=str)
    assert "Priya" not in dumped and "pancreatic" not in dumped


def test_audit_can_be_switched_off(client_factory, auth_header, caplog) -> None:
    client, _ = client_factory(FakeChatModel(answer="NOT_COVERED"), audit_log_enabled=False)
    _capture(
        caplog, lambda: client.post("/api/chat", headers=auth_header, json={"question": "What is asthma?"})
    )
    assert caplog.records, "log capture is not working"
    assert not [r for r in caplog.records if r.name == "audit"]


# ---- monitoring config --------------------------------------------------------------------------------
MON = PROJECT_ROOT.parent / "monitoring"


def test_alert_rules_cover_required_signals_and_known_metrics() -> None:
    rules = yaml.safe_load((MON / "prometheus" / "alerts.yml").read_text(encoding="utf-8"))
    alerts = {r["alert"]: r["expr"] for g in rules["groups"] for r in g["rules"]}
    for required in (
        "TriageSpike",
        "RefusalRateShift",
        "SafetyCheckFailures",
        "CircuitOpen",
        "HighLatencyP95",
    ):
        assert required in alerts, required
    metrics_src = (PROJECT_ROOT / "app" / "core" / "metrics.py").read_text(encoding="utf-8")
    for expr in alerts.values():
        for name in re.findall(r"(medinfo_[a-z_]+?)(?:_bucket|_count|_sum)?\b", expr):
            base = re.sub(r"_(bucket|count|sum)$", "", name)
            assert f'"{base}"' in metrics_src, f"alert uses unknown metric {base}"


def test_grafana_dashboard_is_valid_and_uses_known_metrics() -> None:
    dash = json.loads((MON / "grafana" / "dashboards" / "medinfo.json").read_text(encoding="utf-8"))
    exprs = [t["expr"] for p in dash["panels"] for t in p.get("targets", [])]
    assert len(dash["panels"]) >= 8 and exprs
    metrics_src = (PROJECT_ROOT / "app" / "core" / "metrics.py").read_text(encoding="utf-8")
    for expr in exprs:
        for name in re.findall(r"medinfo_[a-z_]+", expr):
            base = re.sub(r"_(bucket|count|sum|total)$", "", name)
            assert f'"{base}' in metrics_src, f"dashboard uses unknown metric {name}"
    assert any("histogram_quantile(0.99" in e for e in exprs)
