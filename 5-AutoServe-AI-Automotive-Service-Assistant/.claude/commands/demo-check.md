---
description: Verify the current phase's demo/exit gate actually works end-to-end and report pass/fail per step with real output.
---

1. Read `.claude/PLAN.md` and `.claude/TASK_TRACKER.md` to find the latest phase with tasks in progress or just completed.
   If $ARGUMENTS names a phase (P1…P5) or prompt number, use that.
2. List that phase's Exit Gate steps (and `docs/DEMO_SCRIPT.md` steps if it exists).
3. For each step, run the real check: `docker compose ps`, `curl` against `/health`, `/ready`, and the API, `make test`, `make eval`,
   `scripts/demo_workflow.py`, Playwright. Use demo logins from the seed, never real data.
4. Output a table: step · command · expected · actual (trimmed output) · PASS/FAIL.
5. On a FAIL, give the likely cause and file, but don't fix it unless asked.
6. Don't mark tracker rows DONE from this command. Report only.
