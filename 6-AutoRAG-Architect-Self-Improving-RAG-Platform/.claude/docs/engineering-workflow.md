# Engineering Workflow — AutoRAG Architect

**Version**: v3.0 | **Updated**: 10-Jul-2026 (IST)

> Day-to-day development workflow for all 28 engineers.
> Governance rules → [CLAUDE.md](../CLAUDE.md) | Phase execution → [PLAN.md](../PLAN.md)

---

## 1. Branch Strategy

### Three-Tier Model

```
feature/team-N-description   ← your working branch (always branch from development)
         │
    development              ← integration branch (all PRs target here)
         │
      staging                ← QA / staging validation (Tech Leads promote here)
         │
       main                  ← production only (Tech Leads merge here after ECS gate)
```

### Rules

1. Never push directly to `development`, `staging`, or `main`
2. Always branch from `development` — never from `main` or `staging`
3. Every PR must target `development` as the base branch
4. Only Mahesh Kumar (Project Lead) merges `staging` → `main`

### Branch Naming Convention

```
feature/[TASK-ID]-<short-description>

Examples:
  feature/D-7-langgraph-runtime
  feature/D-6-ingest-pii-masking
  feature/E-4-nextjs-dashboard
```

---

## 2. Daily Development Workflow

```bash
# 1. Sync development before starting any new work
git checkout development
git pull origin development

# 2. Create your feature branch
git checkout -b feature/team-N-your-description

# 3. Write code...

# 4. Stage and commit
git add -A
git commit -m "feat(team-N): short description"

# 5. Push and open PR targeting development
git push -u origin feature/team-N-your-description
gh pr create --base development --title "feat(team-N): short description"

# 6. After PR is merged — clean up
git checkout development
git pull origin development
git branch -d feature/team-N-your-description
git fetch --prune
```

---

## 3. PR Checklist

Before requesting review, verify:

- [ ] `make lint` passes — zero ruff errors, zero mypy errors, zero ESLint errors
- [ ] `make test` passes — backend pytest suite green
- [ ] `Unified Score >= 0.85` if your change affects retrieval or evaluation quality
- [ ] No `.env` files, API keys, or secrets in the diff
- [ ] No PII or raw customer data in logs, tests, or fixtures
- [ ] Alembic migration included for any schema change (`upgrade` + `downgrade`)
- [ ] OpenAPI contract updated if route signatures changed
- [ ] Relevant `specs/` or `docs/` file updated if behavior changed

---

## 4. Automation Shortcuts

These Claude Code commands automate common workflows:

| Command              | What It Does                                                       |
| -------------------- | ------------------------------------------------------------------ |
| `/project:standup`   | Reports your daily progress against PLAN.md phase                  |
| `/project:review`    | Runs AI code audit against the 18 coding rules                     |
| `/project:fix-issue` | Helps debug a specific error with AutoRAG context                  |
| `/project:commit`    | Prepares a v3.0-compliant commit message                           |
| `/project:deploy`    | Triggers ECS Fargate deployment (requires `Unified Score >= 0.85`) |

Full command details: [commands/](../commands/)

---

## 5. Release Flow

```
feature/* ──► development (daily PRs)
                   │
              Code freeze
                   │
              staging (Tech Lead promotes after all Phase exit gates pass)
                   │
              QA validation + smoke tests
                   │
              main (Tech Lead merges — triggers ECS production deployment)
                   │
              AutoRAG vX.Y.Z tag created
```

### Phase Exit Gates Required Before `staging` Promotion

| Phase            | Gate                                                                  |
| ---------------- | --------------------------------------------------------------------- |
| Phase A complete | `/api/v1/evaluate` returns Unified Score + RAGAS + Adversarial        |
| Phase B complete | LangGraph graph loop observable and resumable; Configurator UI live   |
| Phase C complete | Load tests pass; `Unified Score >= 0.85` on production golden dataset |

See [PLAN.md](../PLAN.md) for detailed exit gate checklists per phase task.

---

## 6. Makefile Quick Reference

| Command              | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| `make lint`          | Run ruff + mypy (backend) and ESLint (frontend) |
| `make lint-backend`  | ruff + mypy only                                |
| `make lint-frontend` | ESLint only                                     |
| `make format`        | Run ruff format (backend) + prettier (frontend) |
| `make typecheck`     | mypy (backend) + tsc (frontend)                 |
| `make test`          | Run pytest (backend)                            |

---

## See Also

- [CLAUDE.md](../CLAUDE.md) — engineering constitution and 18 coding rules
- [rules/coding-standards.md](../rules/coding-standards.md) — full enforcement spec
- [PLAN.md](../PLAN.md) — phase execution and team ownership

