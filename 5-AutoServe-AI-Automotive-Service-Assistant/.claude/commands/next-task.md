---
description: Pick the next OPEN task from TASK_TRACKER, state its acceptance criteria and plan, then implement, test, and update the tracker.
---

1. Read `.claude/TASK_TRACKER.md`, `.claude/PLAN.md`, `.claude/MEMORY.md`, and `.claude/CLAUDE.md`.
2. Find the first row with status `OPEN` or `IN_PROGRESS` whose phase prerequisites are `DONE`. Skip `P4-0` unless the user asked for it.
   If an argument was given ($ARGUMENTS), use that task ID instead.
3. Report: task ID, prompt #, acceptance criteria, relevant rules/specs/skills, and a plan in ≤ 5 bullets.
   If anything is ambiguous, ask **one** focused question and stop.
4. Set the row to `IN_PROGRESS`, then implement it, following the matching `skills/*/SKILL.md`.
5. Run the tests/linters/evals the acceptance criteria need. Paste the real output.
6. Set the row to `DONE` only if every criterion is met with evidence; otherwise leave it `IN_PROGRESS`/`BLOCKED` with the reason.
7. Add a `MEMORY.md` entry if a lesson was non-obvious. Finish with the summary format from `rules/99-response-style.md`.
