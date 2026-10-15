"""Delivery invariants (Docker, compose, Kubernetes, CI) that must not silently regress."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.config import PROJECT_ROOT as BACKEND
from app.config import REPO_ROOT as REPO

K8S = REPO / "deploy" / "k8s"
FRONTEND = REPO / "frontend"


def _docs(path):
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def test_backend_dockerfile_hardening() -> None:
    df = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert df.count("FROM python:3.11-slim") == 2  # multi-stage
    assert "USER 10001:10001" in df and "--uid 10001" in df
    assert "apt-get upgrade" in df and "libgl1" in df and "libglib2.0-0" in df
    assert "HEALTHCHECK" in df and '"--workers", "1"' in df
    assert re.search(r"pip uninstall -y setuptools wheel", df) and "pip uninstall -y pip" in df
    assert "PYTHONDONTWRITEBYTECODE=1" in df  # read-only root filesystem
    assert "|| true \\\n && rm" not in df  # an apt failure must never be masked


def test_backend_dockerignore_is_an_allow_list() -> None:
    lines = [ln.strip() for ln in (BACKEND / ".dockerignore").read_text(encoding="utf-8").splitlines()]
    assert "*" in lines
    assert {ln[1:] for ln in lines if ln.startswith("!")} == {"app/", "requirements.txt"}


def test_frontend_image_is_unprivileged_and_proxies_api() -> None:
    df = (FRONTEND / "Dockerfile").read_text(encoding="utf-8")
    assert "nginx-unprivileged" in df and "USER 10001:10001" in df and "HEALTHCHECK" in df
    assert "NGINX_ENVSUBST_OUTPUT_DIR=/tmp" in df  # read-only root FS: templates render into /tmp
    conf = (FRONTEND / "nginx.conf").read_text(encoding="utf-8")
    assert "pid /tmp/nginx.pid" in conf and "server_tokens off" in conf
    site = (FRONTEND / "default.conf.template").read_text(encoding="utf-8")
    assert "proxy_pass http://${BACKEND_UPSTREAM}" in site and "proxy_buffering off" in site  # SSE
    assert "frame-ancestors 'none'" in site and "script-src 'self'" in site
    assert re.search(r"location ~ \^/\(metrics\|docs", site)  # backend internals not exposed publicly
    ignore = (FRONTEND / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert (
        "*" in ignore
        and "!src/" in ignore
        and "node_modules" not in " ".join(x for x in ignore if x.startswith("!"))
    )


def test_compose_publishes_only_the_frontend_on_localhost() -> None:
    compose = yaml.safe_load((REPO / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    for name, svc in services.items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), (name, port)
    assert "ports" not in services["backend"] and "ports" not in services["redis"]
    for name in ("frontend", "backend"):
        assert services[name]["read_only"] is True and services[name]["user"] == "10001:10001"
    assert services["frontend"]["environment"]["BACKEND_UPSTREAM"] == "backend:8000"
    assert set(services["pgvector"]["profiles"]) == {"pgvector"}
    assert set(services["grafana"]["profiles"]) == {"monitoring"}


def test_k8s_pods_are_restricted() -> None:
    for name in ("backend-deployment.yaml", "frontend.yaml", "redis.yaml"):
        deploy = next(d for d in _docs(K8S / name) if d["kind"] == "Deployment")
        spec = deploy["spec"]["template"]["spec"]
        assert spec["securityContext"]["runAsNonRoot"] is True, name
        assert spec["automountServiceAccountToken"] is False, name
        for c in spec["containers"]:
            sc = c["securityContext"]
            assert sc["readOnlyRootFilesystem"] is True and sc["allowPrivilegeEscalation"] is False
            assert sc["capabilities"]["drop"] == ["ALL"]
    backend = next(d for d in _docs(K8S / "backend-deployment.yaml") if d["kind"] == "Deployment")
    c = backend["spec"]["template"]["spec"]["containers"][0]
    assert (
        c["livenessProbe"]["httpGet"]["path"] == "/healthz"
        and c["readinessProbe"]["httpGet"]["path"] == "/readyz"
    )
    ingress = _docs(K8S / "ingress.yaml")[0]
    assert ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]["name"] == "medinfo-frontend"


def test_network_policies_isolate_backend_and_redis() -> None:
    pols = {d["metadata"]["name"]: d for d in _docs(K8S / "networkpolicies.yaml")}
    assert pols["default-deny-all"]["spec"]["podSelector"] == {}
    backend_from = [rule["from"][0] for rule in pols["backend"]["spec"]["ingress"]]
    assert {"podSelector": {"matchLabels": {"app.kubernetes.io/name": "medinfo-frontend"}}} in backend_from
    assert not any("ipBlock" in f for f in backend_from)  # the backend is not reachable from the ALB/VPC
    assert pols["redis"]["spec"]["ingress"] == [
        {
            "from": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "medinfo-backend"}}}],
            "ports": [{"port": 6379, "protocol": "TCP"}],
        }
    ]


def test_no_secrets_committed_in_manifests() -> None:
    for path in K8S.glob("*.yaml"):
        assert all(d.get("kind") != "Secret" for d in _docs(path)), path
    text = "\n".join(p.read_text(encoding="utf-8") for p in K8S.glob("*.yaml"))
    assert not re.search(r"(euri-|gsk_|tvly-|sb_secret_)[A-Za-z0-9]", text)


VERIFIED_ACTIONS = {  # tags confirmed to exist with `git ls-remote` when the workflows were written
    "actions/checkout@v4",
    "actions/setup-python@v5",
    "actions/setup-node@v4",
    "docker/setup-buildx-action@v3",
    "docker/build-push-action@v6",
    "aquasecurity/trivy-action@v0.36.0",
    "aws-actions/configure-aws-credentials@v4",
    "aws-actions/amazon-ecr-login@v2",
    "azure/setup-kubectl@v4",
    "hashicorp/setup-terraform@v3",
}


def _workflows() -> tuple[Path, Path]:
    """(ci, cd): standalone layout (.github/workflows/ci.yml) or the Gen_AI_Projects monorepo layout, where
    GitHub only reads workflows at the repository root (.github/workflows/p4-ci.yml)."""
    local = REPO / ".github" / "workflows"
    if (local / "ci.yml").exists():
        return local / "ci.yml", local / "cd.yml"
    mono = REPO.parent / ".github" / "workflows"
    return mono / "p4-ci.yml", mono / "p4-cd.yml"


def test_workflows_use_verified_action_tags_and_gate_on_safety() -> None:
    ci_path, cd_path = _workflows()
    for wf in (ci_path, cd_path):
        text = wf.read_text(encoding="utf-8")
        yaml.safe_load(text)
        for used in re.findall(r"uses:\s*([^\s#]+)", text):
            assert used in VERIFIED_ACTIONS, (wf.name, used)
    ci = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
    assert "pytest -m safety" in str(ci["jobs"]["safety-suite"])
    assert set(ci["jobs"]["images"]["needs"]) == {"backend", "safety-suite", "frontend"}
    assert str(ci["jobs"]["images"]).lower().count("trivy") >= 2 and "ignore-unfixed" in str(
        ci["jobs"]["images"]
    )
    assert "terraform apply" not in cd_path.read_text(encoding="utf-8")


def test_repo_hygiene_files() -> None:
    gi = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in (".env", "!.env.example", ".terraform/", "node_modules/"):
        assert entry in gi, entry
    ga = (REPO / ".gitattributes").read_text(encoding="utf-8")
    for ext in ("pdf", "xlsx", "docx", "pptx", "png"):
        assert f"*.{ext} binary" in ga
    assert "terraform apply" in (REPO / "infra" / "terraform" / "versions.tf").read_text(encoding="utf-8")
