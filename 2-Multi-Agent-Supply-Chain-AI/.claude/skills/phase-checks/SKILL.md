---
name: phase-checks
description: End-of-phase definition-of-done checklist for this project — tests, lint, live verification, docs, and the summary the user expects before approving the next phase.
---

# End-of-phase checks

Run every step and report the results honestly, including any failures and their actual output.

1. Run `uv run pytest`. It must pass offline. Report how many tests passed and how many were skipped.
2. Run `uv run ruff check .` and `uv run ruff format --check .`. Both must be clean.
3. Do live verification only where the phase needs it, and keep it small. **State the number of paid calls
   first.**
4. Run the secret check: confirm `git check-ignore .env` prints `.env`, and grep the staged files for
   `sk-`, `sb_secret_`, `gsk_` and `tvly-`.
5. Update `README.md` (feature status ✅/🔜), `.env.example` (every new setting) and `docs/PLAN.md` (status).
6. Write the summary for the user:
   - what works now
   - what to test, with example questions and expected answers
   - what's still open
   - the next phase
7. **Stop and wait for the user's OK.**
