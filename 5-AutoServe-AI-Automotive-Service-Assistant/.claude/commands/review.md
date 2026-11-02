---
description: Review the current uncommitted changes against the AutoServe AI contract using the code-reviewer, security-auditor, and safety-reviewer subagents; report Critical/High/Medium/Low findings.
---

1. Collect the change set: `git status --short` and `git diff` (+ `git diff --cached`). If $ARGUMENTS names paths or a ref, scope to that.
2. Run these subagents in parallel on the change set:
   - `code-reviewer`: correctness, layering, determinism, tests, CLAUDE.md §10 forbidden patterns
   - `security-auditor`: RBAC/scope, injection, uploads, PII, secrets
   - `safety-reviewer`: any changed prompt, template, eval, or UI string that the AI or the user sees (A1 / rules/55)
3. Merge and de-duplicate findings. For each one: severity (Critical/High/Medium/Low), `file:line`, problem, concrete fix.
4. Critical/High = must fix before commit. List them first.
5. Check that the TASK_TRACKER row and tests match the change; flag claims with no test evidence.
6. Do not modify files unless the user asks you to apply the fixes.
