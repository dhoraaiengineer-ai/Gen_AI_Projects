# 🔒 AutoRAG Architect — Security & Scanning

**Version**: v4.0 | **Updated**: 21-Jul-2026  
**Owner**: Team 8 (Compliance / Security)

> This folder contains security scanning configs, dependency policies, and AI safety guardrails.
> Security scans run automatically in CI via `.github/workflows/security.yml`.
> AI guardrails protect the LLM pipeline with input/output validation and PII masking.
> They can also be run locally — see commands below.

## 📋 Table of Contents

1. [What's in This Folder](#tools-in-this-folder)
2. [Running Locally](#running-locally)
3. [CI Integration](#ci-integration)
4. [Adding New Packages](#adding-new-packages)
5. [AI Guardrails](#-ai-guardrails)
6. [Related Documentation](#-related-documentation)

---

## Tools in This Folder

| File | Tool | What It Catches |
|------|------|----------------|
| `.gitleaks.toml` | Gitleaks | Secrets, API keys, tokens committed to git |
| `bandit.yaml` | Bandit | Python SAST — insecure code patterns |
| `dependency-policy.md` | Policy doc | Rules for adding new packages |
| `guardrails/` | **Folder** | AI safety governance, policies, adversarial test datasets |
| `guardrails/policies/` | Policy files | PII masking, hallucination, compliance rules |
| `guardrails/test-datasets/` | Test data | Adversarial Q&A (10-question hallucination gate) — jailbreak/injection red-team datasets are open gap **G-7** (`.claude/TASK_TRACKER.md`), see `guardrails/README.md` |

---

## Running Locally

```bash
# ── Secret Scanning (gitleaks) ────────────────────────────────────────
# Install: https://github.com/gitleaks/gitleaks#installation
gitleaks detect --source . --config security/.gitleaks.toml

# ── Python SAST (bandit) ──────────────────────────────────────────────
cd autorag-server
uv run bandit -r app -c ../security/bandit.yaml

# ── Python Dependency Vulnerabilities ────────────────────────────────
cd autorag-server
uv run pip-audit                    # checks all installed packages

# ── Node Dependency Vulnerabilities ──────────────────────────────────
npm audit --workspace=autorag-client      # checks frontend packages
# (vscode-extension workspace removed 17-Jul-2026 -- F-10 backlog, scaffold
#  had zero real dependencies; recreate this line if the workspace returns)

# ── Run everything (mirrors CI security.yml) ─────────────────────────
make security                       # (after Makefile target is added)
```

---

## CI Integration

All checks run automatically via `.github/workflows/security.yml`:
- On every push and pull request
- On a daily schedule at 02:00 UTC (catches new CVEs in existing dependencies)

**Severity thresholds:**
- Gitleaks: any secret found = **block** (no threshold — zero tolerance)
- Bandit: HIGH severity = **block**; MEDIUM = **warning**
- pip-audit / npm audit: HIGH or CRITICAL CVE = **block**

---

## Adding New Packages

Before adding any new Python or Node package, read [`dependency-policy.md`](dependency-policy.md).

**Quick rule**: Run `pip-audit` or `npm audit` after adding. If it reports HIGH or CRITICAL, find an alternative or get lead approval.

---

## 🛡️ AI Guardrails

The `guardrails/` folder contains governance policies and test datasets for the LLM pipeline:

| Folder | Purpose |
|--------|---------|
| `guardrails/policies/` | Enforce PII masking, hallucination detection, compliance rules |
| `guardrails/test-datasets/` | Adversarial Q&A (10 unanswerable questions) — the only committed dataset today; jailbreak/injection prompt datasets are open gap **G-7** (`.claude/TASK_TRACKER.md`), see `guardrails/README.md` |

**Implementation**: The 3-layer runtime pipeline is in `autorag-server/app/guardrails/`:
- **Input layer**: PII detection + masking, prompt injection detection
- **Retrieval layer**: Source validation, poisoning detection
- **Output layer**: Hallucination scoring, moderation, citation validation

See [.claude/rules/ai-guardrails.md](../.claude/rules/ai-guardrails.md) for mandatory safety rules.

---

## 📚 Related Documentation

| Need... | Read... |
|---------|---------|
| **AI safety policies** | [../.claude/rules/ai-guardrails.md](../.claude/rules/ai-guardrails.md) |
| **Deployment security** | [../.claude/rules/deployment-policies.md](../.claude/rules/deployment-policies.md) |
| **Backend guardrails implementation** | [../autorag-server/app/guardrails/](../autorag-server/app/guardrails/) |
| **Governance contracts** | [../.claude/CLAUDE.md](../.claude/CLAUDE.md) |
| **Architecture overview** | [../architecture/README.md](../architecture/README.md)
