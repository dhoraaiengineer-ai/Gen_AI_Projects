---
name: release-checklist
description: Pre-push / pre-release gate - lint, all tests, safety suite, browser tests, secret+PHI scan, infra validation, docs sync.
---

# Release checklist

Run in order and stop at the first failure (report it with the error):
1. `cd backend; ..\.venv\Scripts\ruff check .; ..\.venv\Scripts\ruff format --check .`
2. `cd backend; ..\.venv\Scripts\python -m pytest -q` and `-m safety -q`
3. `cd frontend; npm run lint; npm test`
4. `cd backend; ..\.venv\Scripts\python scripts\prepush_scan.py` -> must print `clean`
5. `cd infra\terraform; terraform validate` and `kubectl kustomize deploy\k8s`
6. Confirm `.env` is not tracked and binaries are marked in `.gitattributes`.
7. Update docs/narrative/presentation status labels for anything newly implemented or verified.
Never push, tag, apply Terraform or push images without the user's explicit approval.
