---
name: run-safety-suite
description: Run the release-blocking medical safety suite (offline) and, on request, the live safety evaluation. Use after any change to triage, scope, guardrails, answer checks, prompts or templates.
---

# Run the safety suite

1. Offline (always, no quota):
   ```powershell
   cd backend; ..\.venv\Scripts\python -m pytest -m safety -q
   ```
   Every test must pass. A failure is a release blocker: report the failing case and the cause.
2. Live (only when the user approves the call count):
   ```powershell
   cd backend; ..\.venv-eval\Scripts\python evals\run_eval.py --safety          # prints the estimate only
   cd backend; ..\.venv-eval\Scripts\python evals\run_eval.py --safety --yes    # runs + logs to MLflow
   ```
   Tell the user the estimated number of calls before running with `--yes`.
3. Report per-set rates (emergency, dosing, diagnosis, injection, phi, out_of_corpus). Required: 100% each.
