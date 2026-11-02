---
name: create-test-suite
description: Checklist for building AutoServe AI test suites (unit, integration, graph, security, evals, e2e) with fixtures sourced from the synthetic corpus and config rather than invented numbers.
---

# Create a test suite

Read first: `.claude/rules/80-testing-quality.md`, the relevant `specs/agents/*.md` "Tests required" section.

## Checklist
1. [ ] Pick the layer: `tests/unit` (pure), `tests/integration` (real Postgres via compose/CI service), `tests/graph` (FakeLLM + checkpointer), `tests/security`, `evals/`, `autoserve-client/e2e` (Playwright).
2. [ ] Fixtures load values from `config/rules.yaml`, `labour_time_guide.csv`, `parts_price_list.csv`, and seeded synthetic data. **No hand-typed specs or prices.**
3. [ ] Cover the boundary, boundary+1, missing input (`unknown`), and invalid input for every rule.
4. [ ] For each route: allowed role, forbidden role (403), out-of-scope owner/dealer (404).
5. [ ] For state changes: every allowed transition and a representative forbidden one per state; history + audit row written.
6. [ ] Graph: route selection per scenario, interrupt raised, resume (correct/wrong role), restart resume, idempotent re-run.
7. [ ] Safety: add cases to `evals/safety.jsonl` for every new AI-facing surface.
8. [ ] Property tests (hypothesis) for calculator and VIN.
9. [ ] No real LLM calls outside `evals/` (assert via the FakeLLM / network guard fixture).
10. [ ] Run: `uv run pytest -q --cov=app --cov-branch` (+ `npm run test`, `npx playwright test` when relevant). Paste output; coverage ≥ 80% overall, 100% branch on `app/rules` + `state_machine`.
