# Rule: engineering conventions

- Layering: routes in `app/api/` stay thin (sync `def`, prefix on `APIRouter`); use cases in
  `app/rag/service.py`; provider SDKs ONLY in `app/rag/providers.py` and `app/container.py`.
- Every route declares `require_user` / `require_clinician` / `require_admin`; public routes are deliberate,
  commented exceptions. Roles only from `app_metadata`; JWTs ES256/RS256 only.
- All new code: type hints, logging (`extra=` fields, no PHI), offline unit tests with fakes.
- Temperatures: answers 0.1-0.3, classifiers/judges 0.
- UI: plain JS, model output only via `textContent`; ESLint forbids innerHTML/eval. Strict CSP, no external assets.
- Never install into `.venv` anything that changes pinned versions (`pip install --dry-run` first); eval
  tooling goes in `.venv-eval`, browser tooling in `.venv-ui` / `frontend/node_modules`.
- Edit files with the editor tools; avoid shell heredocs for content containing `\n` escapes.
- Report failures honestly with the error; never claim something works without running it.
