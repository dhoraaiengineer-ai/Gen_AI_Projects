# 🤖 .claude/ — AI Engineering Operating System

This folder contains AutoRAG's governance, rules, and architectural guidance for AI development.

> **This is where AI coding agents and engineering teams go to find the rules, specifications, and decisions that guide development.**

## 📋 Table of Contents

1. [Who Should Read This?](#1-who-should-read-this)
2. [Quick Start (First 10 Minutes)](#2-quick-start-first-10-minutes)
3. [Folder Structure](#3-folder-structure)
4. [Quick Navigation Guide](#4-quick-navigation-guide)
5. [Key Files to Know](#5-key-files-to-know)
6. [For AI Assistants](#6-for-ai-assistants-claude-code-github-copilot-etc)

---

## 1. Who Should Read This?

- **All Engineers** — Understand the 18 coding standards before starting work
- **AI Agents** — Read `CLAUDE.md` before generating any code
- **Team Leads** — Reference `PLAN.md` for roadmap and task assignments
- **New Joiners** — Start with the "Quick Start" section below

---

## 2. Quick Start (First 10 Minutes)

**Read these in order:**

1. **[CLAUDE.md](CLAUDE.md)** (5 min) — Master contract: rules, definitions of done, forbidden patterns
2. **[PLAN.md](PLAN.md)** (3 min) — 8-phase roadmap (A–H), which phase you're in, team assignments
3. **[TASK_TRACKER.md](TASK_TRACKER.md)** (2 min) — Find your task ID, acceptance criteria, blockers

**Then reference as needed:**
- Need to understand a tech choice? → Read `adr/`
- Need to know how to code something? → Read `rules/` (specific to your area)
- Need technical deep dive? → Read `specs/`

---

## 3. Folder Structure

```
.claude/
│
├── CLAUDE.md                # MASTER GOVERNANCE CONTRACT (read first)
├── PLAN.md                  # 8-phase roadmap (A–H) + team assignments
├── TASK_TRACKER.md          # Unified execution board (28 people) — includes task naming format
├── MEMORY.md                # Institutional learnings & anti-patterns
│
├── adr/                     # Architectural Decision Records
│   ├── 001-langgraph.md     # Why LangGraph for orchestration
│   ├── 002-gemini.md        # Why Gemini Flash 3.5 + KiMi K2.6 failover chain
│   ├── 003-fargate.md       # Why ECS Fargate for Phase 1
│   ├── 004-unified-score.md # Why weighted Unified Score for gating
│   ├── 005-supabase.md      # Why Supabase replaces RDS + Qdrant + S3
│   ├── 006-agent-metrics-table.md # agent_metrics table for per-node cost tracking
│   ├── 007-observability-stack.md # Prometheus+Grafana retained; OTel/Tempo deferred to Phase 2
│   ├── 008-light-first-theme.md   # Frontend flipped light-first (was dark-first)
│   ├── 009-dark-first-theme-reversal.md # Not accepted -- superseded by 010
│   └── 010-earth-tone-retheme.md  # Earth-tone palette adopted as light-first token source
│
├── rules/                   # 18 CODING STANDARDS (REQUIRED)
│   ├── 00-global-architect.md        # Rule 0: Clean architecture
│   ├── 10-backend-fastapi.md         # Rule 10: FastAPI patterns
│   ├── 20-frontend-nextjs.md         # Rule 20: Next.js standards
│   ├── 30-database-postgres.md       # Rule 30: DB migrations + UUID v7
│   ├── 60-agents.md                  # Rule 60: LangGraph + GraphState
│   ├── 70-security.md                # Rule 70: No hardcoded secrets
│   ├── 80-testing-quality.md         # Rule 80: Test coverage
│   └── ... (rules 00-99)
│
├── specs/                   # TECHNICAL SPECIFICATIONS (Source of Truth)
│   ├── stack.md             # Technology choices
│   ├── database.md          # Supabase PostgreSQL + pgvector
│   ├── api-design.md        # 46 REST endpoints, live-schema verified (5 core flows detailed; Version 4.0 added 4 optimization endpoints)
│   ├── agents/              # 9-agent interface contracts
│   │   ├── 01-ingestion.md
│   │   ├── 05-evaluator.md
│   │   └── ... (agents 1-9)
│   └── ...
│
├── docs/                    # HUMAN-READABLE DOCUMENTATION
│   ├── ARCHITECTURE.md      # System design overview
│   ├── AGENTS.md            # 9-agent loop explained
│   ├── DEPLOYMENT.md        # ECS Fargate process
│   └── ...
│
├── prompts/                 # AI PROMPT TEMPLATES
│   ├── frontend-design-guide.md
│   └── ...
│
├── agents/                  # AI AGENT DEFINITIONS
│   ├── code-reviewer.md     # Behavior rules for code review agent
│   ├── security-auditor.md  # Behavior rules for security agent
│   └── ...
│
├── commands/                # CLI SLASH COMMANDS
│   ├── deploy.md
│   ├── review.md
│   └── ...
│
├── skills/                  # REUSABLE DEVELOPMENT SKILLS
│   ├── create-langgraph-workflow/
│   ├── create-migration/
│   ├── debug-langgraph/
│   └── ... (30+ skills)
│
├── hooks/                   # GIT HOOKS (Pre-commit, post-edit)
│   ├── lint-on-edit.ps1     # Auto-lint on file save
│   └── auto-memory-log.ps1
│
├── scripts/                 # UTILITY SCRIPTS
│   ├── post-edit-check.sh
│   └── post-edit-check.ps1
│
└── settings.json            # Claude Code project config
```

## 4. Quick Navigation Guide

| File | Purpose | Read When |
|------|---------|-----------|
| **CLAUDE.md** | Master governance + 18 coding rules | **First thing** - Everything is here |
| **PLAN.md** | 8-phase roadmap (A–H) with team + task assignments | Need to know your phase or task |
| **TASK_TRACKER.md** | Who's doing what + status (all 28 people) | Need to find a task or your team |
| **adr/** | Why we chose LangGraph, Supabase, Fargate, etc | Question "why this technology?" |
| **rules/** | 18 mandatory engineering standards (00–99) | Before writing code in your area |
| **specs/** | Technical deep-dives (frozen contracts) | Need implementation details |
| **docs/** | Human explanations of architecture + agents | Want to understand how things work |
| **skills/** | Reusable playbooks for common tasks | Need to do a common engineering task |

---

## 5. Key Files to Know

Start with these:
- ✅ **CLAUDE.md** — The authoritative contract (read if unsure about anything)
- ✅ **rules/coding-standards.md** — Quick reference for all 18 rules
- ✅ **PLAN.md** — Your task assignments + phase deadlines
- ✅ **TASK_TRACKER.md** — Find your current task ID and acceptance criteria

Then reference as needed:
- **specs/agents/** — Interface contracts for each of the 9 agents
- **adr/** — Understand why we chose each technology

---

## 6. For AI Assistants (Claude Code, GitHub Copilot, etc.)

**Always follow this sequence before touching code:**

1. ✅ **Read CLAUDE.md** section 6 (AI Agent Operational Instructions)
2. ✅ **Check relevant rules/** file for your tech area:
   - Adding backend? → Rule 10 (FastAPI)
   - Adding frontend? → Rule 20 (Next.js) + Rule 25 (UI Design)
   - Adding database? → Rule 30 (PostgreSQL)
   - Building agents? → Rule 60 (LangGraph)
3. ✅ **Read specs/** for technical source of truth
4. ✅ **Check for forbidden patterns** in CLAUDE.md section 6 (Forbidden Patterns table)

**Never ship code without reading CLAUDE.md first.**
- **For examples**: Review `skills/` for proven techniques

---

## 📚 Cross-Links to Main Documentation

| Need... | Location | Purpose |
|---------|----------|---------|
| **Project overview** | [../README.md](../README.md) | Quick start, team roster, what AutoRAG does |
| **Backend setup** | [../autorag-server/README.md](../autorag-server/README.md) | Python API, LangGraph, local dev |
| **Frontend setup** | [../autorag-client/README.md](../autorag-client/README.md) | Next.js dashboard, components, UI design |
| **Infrastructure** | [../infra/README.md](../infra/README.md) | Terraform, AWS provisioning, deployments |
| **System monitoring** | [../observability/README.md](../observability/README.md) | Prometheus, Grafana, alerts, SLOs |
| **Architecture** | [../architecture/README.md](../architecture/README.md) | System design, decision records, diagrams |
| **Onboarding** | [docs/setup.md](docs/setup.md) | New team member setup, day-1 tasks |
| **Team roster** | [./memory/active_contributors.md](./memory/active_contributors.md) | All 28 contributors, roles, assignments |
