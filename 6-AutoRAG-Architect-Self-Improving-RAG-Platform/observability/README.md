# 📊 AutoRAG Architect — Observability

**Owner**: Team 6 (DevOps / Platform)  
**Stack**: Prometheus + Grafana + AWS CloudWatch  
**Status**: v4.0 | **Updated**: 21-Jul-2026

## 📋 Table of Contents

1. [Who Should Read This?](#who-should-read-this)
2. [Overview](#1-overview)
3. [Folder Structure](#2-folder-structure)
4. [Local Development](#3-local-development)
5. [Production Setup (Team 6)](#4-production-setup-team-6)
6. [Key Alert Thresholds](#5-key-alert-thresholds-enforced-by-deployer-agent-auto-rollback)
7. [Incident Runbooks](#6-incident-runbooks)

---

## Who Should Read This?

- **DevOps / SRE Engineers** — Setting up monitoring, dashboards, and alerts
- **On-Call Engineers** — Understanding alert thresholds and rollback triggers
- **Backend Engineers** — Understanding what metrics are tracked and how to instrument code
- **New Joiners** — Learning how the system is monitored and debugged

---

## 1. Overview

| Layer   | Tool                          | Purpose                                                          |
| ------- | ----------------------------- | ---------------------------------------------------------------- |
| Metrics | Prometheus → Grafana          | FastAPI latency, LangGraph node throughput, Redis queue depth    |
| Errors  | AWS CloudWatch (ECS native)              | Error rate, structured JSON logs, LangGraph node exceptions |
| Logs    | AWS CloudWatch (ECS native)   | Structured JSON logs from FastAPI + LangGraph workers            |
| Tracing | X-Trace-ID propagation        | End-to-end request trace through all 9 agent nodes               |
| Alerts  | Prometheus Alertmanager       | Auto-rollback triggers + on-call paging                          |

---

## 2. Folder Structure

```
observability/
├── README.md                                      ← this file
├── prometheus/
│   ├── prometheus.local.yml                       ← local dev config (Docker container targets)
│   └── prometheus.yml.example                     ← ECS production template (fill before deploy)
│   (prometheus.yml itself is gitignored — real ECS config, never committed)
├── grafana/
│   ├── dashboards/
│   │   ├── autorag-overview.json                  ← System Overview dashboard (auto-provisioned)
│   │   └── autorag-aiops.json                     ← 8-panel AIOps dashboard (Phase G, added 10-Jul-2026)
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml                     ← Auto-wires Prometheus datasource on boot
│       └── dashboards/
│           └── dashboard-provider.yml             ← Tells Grafana where to load dashboard JSON
├── alerts/
│   └── autorag-alerts.yml                         ← Alert rules (rollback triggers + SLO breaches)
├── runbooks/                                       ← Incident response playbooks (Phase G, added 10-Jul-2026)
│   ├── rollback.md                                 ← ECS Blue/Green rollback procedure
│   ├── high-latency.md                             ← p95 > 3s diagnosis + resolution
│   ├── low-unified-score.md                        ← Unified Score < 0.85 diagnosis
│   ├── cost-breach.md                              ← Cost budget spike response
│   └── pii-incident.md                             ← Unmasked PII containment procedure
└── slo/
    └── slo-definitions.md                         ← SLO targets and burn rate thresholds
```

---

## 3. Local Development

Prometheus and Grafana run automatically via `docker compose up -d`.

| Service    | URL                        | Credentials                     |
| ---------- | -------------------------- | -------------------------------- |
| Prometheus | http://localhost:9090      | none                             |
| Grafana    | http://localhost:3001      | admin / `GRAFANA_PASSWORD` (.env) |

The **AutoRAG System Overview** dashboard auto-loads on Grafana first boot — no manual import needed.

### What is monitored locally

| Job              | Target                 | Metrics                                          |
| ---------------- | ---------------------- | ------------------------------------------------ |
| `autorag-api`    | `autorag-api:8000/metrics`    | p95 latency, request rate, error rate       |
| `autorag-redis`  | `redis-exporter:9121`  | Queue depth, connected clients, memory usage     |
| `prometheus`     | `localhost:9090`       | Self-monitoring                                   |

---

## 4. Production Setup (Team 6)

1. Copy `prometheus/prometheus.yml.example` → `prometheus/prometheus.yml`
2. Fill in ECS service discovery endpoints from Terraform outputs
3. Deploy via Terraform (`infra/modules/`) — Prometheus and Grafana run as ECS Fargate services
4. Alert rules in `alerts/autorag-alerts.yml` are loaded automatically by the Prometheus container

> ⚠️ **Never commit `prometheus.yml`** (contains internal ECS IPs). Only `prometheus.local.yml` and `prometheus.yml.example` are committed.

---

## 5. Key Alert Thresholds (enforced by Deployer Agent auto-rollback)

| Metric                      | Warning     | Critical / Rollback Trigger       |
| --------------------------- | ----------- | --------------------------------- |
| p95 query latency           | > 2 000 ms  | > 3 000 ms                        |
| Error rate (5xx)            | > 0.5%      | > 1%                              |
| Unified Score drop          | > 0.05      | > 0.10 (auto-rollback)            |
| Redis queue depth           | > 500 tasks | > 1 000 tasks                     |
| LangGraph node failure rate | > 2%        | > 5%                              |

---

## 6. Incident Runbooks

Step-by-step response procedures for the alert conditions above, added in Phase G (10-Jul-2026):

| Runbook | When to Use |
|---------|-------------|
| [runbooks/rollback.md](runbooks/rollback.md) | Any critical SLO breach during the 10-minute canary window |
| [runbooks/high-latency.md](runbooks/high-latency.md) | p95 latency > 3s |
| [runbooks/low-unified-score.md](runbooks/low-unified-score.md) | Unified Score < 0.85, HITL queue backing up |
| [runbooks/cost-breach.md](runbooks/cost-breach.md) | Agent cost spike, `CostGuardrail` blocking Improver |
| [runbooks/pii-incident.md](runbooks/pii-incident.md) | Unmasked PII detected — compliance-critical, act immediately |

---

## 📚 Quick Links to Related Docs

| Need... | Read... | Purpose |
|---------|---------|---------|
| **Project overview** | [../README.md](../README.md) | System architecture, tech stack, quick start |
| **Backend development** | [../autorag-server/README.md](../autorag-server/README.md) | How to instrument code, logging, metrics |
| **Infrastructure setup** | [../infra/README.md](../infra/README.md) | How Prometheus and Grafana are deployed |
| **Architecture & design** | [../architecture/README.md](../architecture/README.md) | System design, data flow, components |
| **AI Engineering OS** | [../.claude/CLAUDE.md](../.claude/CLAUDE.md) | Governance rules, monitoring requirements |
| **Deployment process** | [../.claude/specs/deployment.md](../.claude/specs/deployment.md) | How observability triggers auto-rollback
