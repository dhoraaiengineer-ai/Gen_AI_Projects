# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create ECS Service Skill

> **Note (24-Jul-2026 audit)**: `autorag-worker` below describes a separate worker ECS
> service that is a **planned target architecture, not implemented today** -- LangGraph
> nodes currently run in-process inside `autorag-api` via FastAPI `BackgroundTasks`, with
> no separate worker service or Redis-backed task queue (see `docs/DEPLOYMENT.md`'s
> correction and `adr/005-supabase.md`'s R-052/R-050 note). Building a real `autorag-worker`
> service is Version 5 scope, not something to deploy against the current codebase.

## Purpose

Deploy and scale AutoRAG components on AWS ECS Fargate.

## Task Sizing (v3.0)

- **autorag-api**: 1 vCPU / 2 GB RAM (Min: 2, Max: 10).
- **autorag-worker**: 2 vCPU / 4 GB RAM (Min: 2, Max: 20).

## Requirements

- **Auto-scaling**: Scale out if `CPU > 70%` for 5 minutes.
- **Service Discovery**: Internal gRPC/HTTP communication between nodes.
- **Logging**: Mandatory `awslogs` driver targeting CloudWatch (native ECS logs).

## Anti-Patterns

- **Under-Sizing**: Using 0.5 vCPU for the LangGraph Worker (causes task timeout and stalled graph nodes).
- **Static Tasks**: Running with a fixed task count in production.
