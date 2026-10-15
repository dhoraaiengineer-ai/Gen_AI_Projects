---
name: test-runner
description: Runs the full offline quality gate (ruff, backend pytest incl. safety, frontend ESLint + Playwright) and reports results verbatim.
tools: Bash, Read
---

Run from the repository root, in order, and report each command with its pass/fail summary:
1. `cd backend && ../.venv/Scripts/ruff check . && ../.venv/Scripts/ruff format --check .`
2. `cd backend && ../.venv/Scripts/python -m pytest -q`
3. `cd backend && ../.venv/Scripts/python -m pytest -m safety -q`
4. `cd frontend && npm run lint && npm test`
On failure include the failing test names and the error text. Never make live model calls.
