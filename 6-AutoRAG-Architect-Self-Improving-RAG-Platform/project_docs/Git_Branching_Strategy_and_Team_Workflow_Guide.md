# Git Branching Strategy & Team Workflow Guide

**Project:** AutoRAG Architect
**Audience:** All Contributors
**Version:** v4.0 | **Updated:** 21-Jul-2026 (IST)
**Team:** 10 teams, 28 contributors

---

## Overview

This guide explains how code moves between branches and how team members collaborate safely without affecting production code.

> **Maintenance-phase note (added 17-Jul-2026):** the PR-based flow below is the default,
> required process and remains fully in effect for any active multi-team feature work — including
> if/when V4 development begins. Now that V3 MVP is 107/108 tasks complete and the project is in
> MVP-validation/handover mode, **solo maintenance work** (bug fixes found during validation
> testing, documentation updates, config corrections) has been committing directly to
> `development` rather than going through individual feature branches + PRs — there's no second
> contributor to review against in that mode, and the ceremony doesn't add safety for a single
> person's own fix-verify-commit loop. This is a scoped, temporary exception for the
> single-maintainer stabilization period, not a change to the branching policy itself — the moment
> a second contributor is actively working alongside you, or active multi-person feature
> development resumes, go back to feature branches + PRs as documented below.

> **Version 4.0 note (21-Jul-2026):** the Apply Improvement / Optimizer / Immutable Versioned
> Indexes feature (migration 0016, `OptimizerService`, 4 new API endpoints, `/evolution` frontend)
> was delivered 20-Jul-2026 under exactly this solo-maintenance exception — direct commits to
> `development`, not a feature branch + PR. This is consistent with the policy above, not an
> exception to it: it was single-maintainer work with no second contributor to review against.

---

## Branch Structure

```
        main          ← Live production code
          ↑
       staging        ← QA & UAT testing
          ↑
     development      ← Team integration branch
          ↑
      feature/*       ← Your work goes here
```

| Branch | Purpose | Who Uses It |
|--------|---------|-------------|
| `main` | Live production code | Team Leads / DevOps only |
| `staging` | Testing before release | QA Team / Team Leads |
| `development` | Main integration branch | All Developers (via PR) |
| `feature/*` | Individual feature work | Assigned Developers |

---

## Branch Rules

### `main` — Production
- No direct commits or pushes
- Changes arrive only through Pull Requests from `staging`
- Protected branch — CI/CD checks required

### `staging` — Testing
- No direct development
- Used for QA validation only
- Receives code from `development`

### `development` — Integration
- All feature branches are created from here
- All completed work merges back here via Pull Request
- No direct commits — PR only

### `feature/*` — Your Branch
- Always created from `development`
- Named: `feature/[task-id]-short-description`
- Deleted after merge

---

## Initial Setup (Team Lead — One Time)

```bash
# 1. Get latest main
git checkout main
git pull origin main

# 2. Create development branch
git checkout -b development

# 3. Push to GitHub
git push -u origin development
```

Then set `development` as the default branch for contributors in GitHub Settings.

---

## Developer Workflow

### Rules

**DO ✅**
- Always branch from `development`
- Use task ID in branch name
- Commit frequently with clear messages
- Open PRs into `development`

**DON'T ❌**
- Never push directly to `development`, `staging`, or `main`
- Never work on someone else's feature branch
- Never use vague commit messages like "fix" or "stuff"

---

### Step 1 — Configure Git (First Time Only)

```bash
git config --global user.name "Your Full Name"
git config --global user.email "your.email@example.com"

# Verify
git config --global user.name
git config --global user.email
```

> This name and email will appear on all your commits. Do this once on your laptop.

---

### Step 2 — Sync & Create Branch

> **`git fetch` vs `git pull`**
> - `git fetch` — downloads changes from GitHub but does **not** apply them. Safe to run anytime to check what's new.
> - `git pull` — fetch + merge in one step. Downloads **and** applies changes to your current branch.
> - **Rule:** Use `git pull` to sync before creating a branch. Use `git fetch` just to check what changed.

```bash
# Get latest code
git checkout development
git pull origin development

# Create your feature branch
git checkout -b feature/B-2-ingestion-agent
```

**Branch naming:** `feature/[task-id]-description`
```
feature/B-1-fastapi-shell
feature/C-5-langgraph-workflow
feature/D-2-alembic-migrations
```

---

### Step 3 — Daily Development

```bash
# Check what you've changed
git status
git diff

# Stage and commit
git add app/agents/ingestion.py
git commit -m "feat(ingestion): add PII masking before vector upload"

# Commit message format:
# type(scope): short description
# Types: feat | fix | docs | refactor | test | chore
```

---

### Step 4 — Push & Open PR

```bash
# Push your branch
git push origin feature/B-2-ingestion-agent
```

**Open the Pull Request on GitHub:**

1. Go to the repository on GitHub
2. Click **"Compare & pull request"** (yellow banner after push)
3. Set **Base branch** → `development` ← *(never `main`)*
4. Fill in the PR form:

```
Title:   feat(ingestion): add PII masking and chunking pipeline

Description:
## What this PR does
- Implements semantic chunking for PDF files
- Adds PII masking before vector upload

## How to test
1. Run: pytest autorag-server/tests/test_ingestion.py
2. Verify: no PII in Supabase Vector rows

## Related task
Task B-2 in .claude/TASK_TRACKER.md
```

5. Add your **team lead as Reviewer**
6. Click **"Create Pull Request"**

---

## Pull Request

Include in every PR:

- **Summary** — what you built
- **How to test** — steps to verify
- **Related task** — task ID from TASK_TRACKER.md
- **Checklist** — lint passes, tests pass, no secrets in diff

**Reviewers:** Always tag your team lead.

**Required before merge:**
- [ ] Code review approved
- [ ] CI checks passed
- [ ] No merge conflicts
- [ ] Documentation updated

---

## Release Process

```
Step 1 — Merge Features
feature/* ──► development   (via Pull Request + review)

Step 2 — QA Testing
development ──► staging     (Team Lead merges; QA validates)
                             • Functional testing
                             • Integration testing
                             • Performance testing

Step 3 — Production Release
staging ──► main            (Team Lead merges; CI/CD deploys)
```

---

## Team Lead Workflow

**DO ✅**
- Review and merge Pull Requests
- Manage releases (development → staging → main)
- Monitor CI/CD pipeline
- Set up branch protection rules
- Resolve escalated merge conflicts

**DON'T ❌**
- Never commit directly to `main`
- Never push directly to `main`
- Never allow force pushes
- Never merge without at least one review

---

## Branch Protection Rules

Configure in GitHub → Settings → Branches:

| Branch | Rules |
|--------|-------|
| `main` | Require PR · Require approvals · Require CI · Block force push · Block deletion |
| `staging` | Require PR · Require CI · Block force push |
| `development` | Require PR · Require CI |

---

## Contributor Access

| Branch | Access |
|--------|--------|
| `main` | Team Leads only |
| `staging` | Team Leads only |
| `development` | PR merge only (no direct push) |
| `feature/*` | Individual contributors |

---

## Example Scenarios

Three developers working in parallel on the same project:

```
development
    │
    ├──► feature/B-1-fastapi-shell       (Developer A — Team 1)
    │
    ├──► feature/C-5-langgraph-workflow   (Developer B — Team 5)
    │
    └──► feature/C-8-pii-masking          (Developer C — Team 8)
```

All three open Pull Requests back into `development`.
No one affects anyone else's work.

After all PRs are merged:
```
development ──► staging ──► main
```

---

## Summary

1. Team Lead creates `development` branch from `main`
2. Developers create `feature/*` branches from `development`
3. Developers submit Pull Requests into `development`
4. Team Leads review and merge
5. Team Lead moves tested code to `staging` for QA
6. After QA passes, Team Lead merges `staging` → `main`
7. Protect `main`, `staging`, and `development` via GitHub Branch Protection Rules

---

## Related Documentation

| Need... | Read... |
|---------|---------|
| First-day setup | [.claude/docs/setup.md](../.claude/docs/setup.md) |
| Complete project structure | [PROJECT_TREE.md](PROJECT_TREE.md) |
| Coding standards | [../.claude/rules/coding-standards.md](../.claude/rules/coding-standards.md) |
| Task assignments | [../.claude/TASK_TRACKER.md](../.claude/TASK_TRACKER.md) |

---

*AutoRAG Architect v4.0 — Euron Consulting*
