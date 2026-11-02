# 10 — Backend (FastAPI, Python 3.12)

**Purpose:** Consistent, typed, secure API and service code.

## MUST
- Python 3.12, fully type-annotated; `mypy --strict` on `app/rules`, `app/services`, `app/graph`.
- Pydantic v2 schemas for every request/response, in `app/schemas/`. `model_config = ConfigDict(extra="forbid")` on inputs.
- Return the envelope `{status, data, error, request_id}` from every endpoint, success and error.
- Every route declares `Depends(require_role(...))`. The only public routes are `/health`, `/ready`, and `/api/v1/auth/login`.
- Pass the `actor` (user_id, role, dealer_id) into services/repositories. Repositories apply ownership/dealer filters.
- Async all the way: SQLAlchemy 2 async sessions, `httpx.AsyncClient`. Blocking OCR/PDF work runs in a threadpool or worker.
- Settings via `pydantic-settings` from env only (`app/core/config.py`). Timeouts and retry counts come from settings.
- `Idempotency-Key` header on state-creating POSTs (booking, check-in, decisions); store and replay the first result.
- structlog JSON logs with `request_id`, `trace_id`, `actor_role`; PII passes through `mask_pii()`.
- Domain errors are typed exceptions mapped to the error codes in `specs/api-design.md`.

## MUST NOT
- Put business logic in route handlers.
- Return ORM objects directly, or leak stack traces / SQL in error responses.
- Catch bare `Exception` without re-raising or mapping to a typed error.
- Use `float` for money or hours. Use `Decimal`.
- Instantiate an LLM client (`ChatOpenAI`, provider SDKs) anywhere except `services/llm_service.py`.

## Good
```python
@router.get("/repair-orders/{ro_id}/status", response_model=Envelope[ROStatusOut])
async def get_status(
    ro_id: UUID,
    actor: Actor = Depends(require_role("vehicle_owner", "service_advisor", "technician", "warranty_admin")),
    svc: ROService = Depends(),
) -> Envelope[ROStatusOut]:
    return Envelope.ok(await svc.get_status(ro_id, actor))  # repo filters by owner/dealer → 404 if out of scope
```

## Bad
```python
@router.get("/repair-orders/{ro_id}/status")
async def get_status(ro_id: str, db=Depends(get_db)):
    return (await db.execute(text(f"SELECT * FROM repair_orders WHERE id='{ro_id}'"))).first()  # no auth, SQLi, no scope
```
