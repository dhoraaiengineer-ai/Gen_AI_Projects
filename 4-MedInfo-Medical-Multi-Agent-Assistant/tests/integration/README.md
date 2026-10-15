# Integration tests (cross-service)

Run against a live stack; they skip automatically when no stack is configured.

```bash
docker compose up --build -d
MEDINFO_STACK_URL=http://127.0.0.1:8080 .venv/Scripts/python -m pytest tests/integration -q
```

Unit, API and safety tests live in `backend/tests`; browser tests live in `frontend/tests`.
