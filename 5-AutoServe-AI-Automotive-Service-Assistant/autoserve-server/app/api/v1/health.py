"""Liveness and readiness probes (public, no auth — CLAUDE.md §13)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.db import get_engine
from app.core.middleware import get_request_id
from app.schemas.envelope import Envelope

router = APIRouter(tags=["health"])

CheckResult = Literal["ok", "fail"]


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyOut(BaseModel):
    db: CheckResult
    storage: CheckResult
    llm_config: CheckResult


async def check_db(settings: Settings) -> CheckResult:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))
    return "ok"


async def check_storage(settings: Settings) -> CheckResult:
    async with httpx.AsyncClient(timeout=settings.db_connect_timeout_s) as client:
        resp = await client.get(f"{settings.s3_endpoint_url.rstrip('/')}/minio/health/live")
    return "ok" if resp.status_code == 200 else "fail"


async def check_llm_config(settings: Settings) -> CheckResult:
    """Config only (no network call): every provider used in a chain has a key."""
    providers = {e.provider for e in (*settings.agent_chain, *settings.answer_chain)}
    missing = [p for p in providers if settings.provider_credentials(p)[1] is None]
    return "fail" if missing else "ok"


READY_CHECKS: dict[str, Callable[[Settings], Awaitable[CheckResult]]] = {
    "db": check_db,
    "storage": check_storage,
    "llm_config": check_llm_config,
}


async def _run(check: Callable[[Settings], Awaitable[CheckResult]], settings: Settings) -> CheckResult:
    try:
        return await asyncio.wait_for(check(settings), timeout=settings.db_connect_timeout_s + 1)
    except Exception:
        return "fail"


@router.get("/health", response_model=Envelope[HealthOut])
async def health(request: Request) -> Envelope[HealthOut]:
    return Envelope.ok(HealthOut(status="ok"), get_request_id(request))


@router.get("/ready", response_model=Envelope[ReadyOut])
async def ready(request: Request) -> JSONResponse:
    settings = get_settings()
    names = list(READY_CHECKS)
    results = await asyncio.gather(*(_run(READY_CHECKS[n], settings) for n in names))
    out = ReadyOut(**dict(zip(names, results, strict=True)))
    request_id = get_request_id(request)
    if all(r == "ok" for r in results):
        return JSONResponse(Envelope.ok(out, request_id).model_dump(mode="json"))
    body = Envelope[ReadyOut].fail("NOT_READY", "Service is not ready.", request_id, details=out.model_dump())
    return JSONResponse(body.model_dump(mode="json"), status_code=503)
