"""Prometheus scrape endpoint.

PUBLIC BY DESIGN (listed in the architecture test): Prometheus scrapes without a user JWT. It is
reachable only on the cluster network (the Ingress does not route it); set ``METRICS_TOKEN`` to
also require ``Authorization: Bearer <token>``. Metrics carry counts and latencies only — no
tenant data, no user ids.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.deps import get_container
from src.container import Container

router = APIRouter(prefix="/metrics", tags=["observability"])


@router.get("", include_in_schema=False)
async def metrics(
    container: Annotated[Container, Depends(get_container)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    token = container.settings.metrics_token
    if token is not None:
        expected = f"Bearer {token.get_secret_value()}"
        if not hmac.compare_digest((authorization or "").encode(), expected.encode()):
            return JSONResponse({"error": {"code": "unauthorized"}}, status_code=401)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
