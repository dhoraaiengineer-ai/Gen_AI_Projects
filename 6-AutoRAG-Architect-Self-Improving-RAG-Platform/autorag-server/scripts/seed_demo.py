"""Seed one clean demo pipeline by calling the real running API.

Deliberately does NOT insert rows directly into Postgres -- every value ends
up in the database via the exact same code paths a real user's browser
session hits (POST /pipelines -> POST /ingest -> POST /evaluate -> poll
/jobs/{id}), so the seeded state is provably real, not fabricated.

Requires autorag-server to be running locally (uv run uvicorn app.main:app
--port 8000) and reachable at API_BASE_URL.

Usage:
    uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
ORGANIZATION_ID = os.environ.get("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000001")

# Same real fixture used throughout manual verification this session.
DEMO_PDF_PATH = Path(__file__).resolve().parents[2] / "testing" / "cil-annual-report-2025.pdf"

POLL_INTERVAL_S = 3
MAX_POLLS = 100  # ~5 minutes, matches RunEvaluationPanel.tsx's client-side cap


def _headers() -> dict[str, str]:
    return {
        "X-Trace-ID": str(uuid.uuid4()),
        "X-Organization-ID": ORGANIZATION_ID,
    }


async def seed_demo() -> None:
    if not DEMO_PDF_PATH.exists():
        print(f"[ERROR] Demo fixture not found: {DEMO_PDF_PATH}")
        sys.exit(1)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=60.0) as client:
        # 1. Create pipeline -- same call apiClient.createPipeline makes from
        #    the Configurator wizard.
        print("[1/3] Creating demo pipeline...")
        resp = await client.post(
            "/api/v1/pipelines",
            headers=_headers(),
            json={"name": "Local Demo Pipeline", "chunk_strategy": "semantic"},
        )
        resp.raise_for_status()
        pipeline = resp.json()["data"]
        pipeline_id = pipeline["id"]
        print(f"      Pipeline created: {pipeline_id}")

        # 2. Upload the real fixture PDF.
        print("[2/3] Uploading demo document (cil-annual-report-2025.pdf)...")
        with DEMO_PDF_PATH.open("rb") as f:
            files = {"files": (DEMO_PDF_PATH.name, f, "application/pdf")}
            resp = await client.post(
                f"/api/v1/ingest?pipeline_id={pipeline_id}",
                headers=_headers(),
                files=files,
            )
        resp.raise_for_status()
        print("      Document ingested.")

        # 3. Trigger evaluation and poll to completion.
        print("[3/3] Running evaluation...")
        resp = await client.post(
            "/api/v1/evaluate",
            headers=_headers(),
            json={
                "pipeline_id": pipeline_id,
                "query": "What are the key financial highlights described in this document?",
            },
        )
        resp.raise_for_status()
        job = resp.json()["data"]
        run_id, job_id = job["run_id"], job["job_id"]

        for attempt in range(MAX_POLLS):
            resp = await client.get(f"/api/v1/jobs/{job_id}", headers=_headers())
            resp.raise_for_status()
            status = resp.json()["data"]["status"]
            if status in ("completed", "blocked", "pending_approval"):
                break
            if status == "failed":
                print("[ERROR] Evaluation failed -- pipeline created but unscored.")
                sys.exit(1)
            time.sleep(POLL_INTERVAL_S)
        else:
            print("[ERROR] Evaluation timed out after 5 minutes.")
            sys.exit(1)

        resp = await client.get(f"/api/v1/score/{run_id}", headers=_headers())
        resp.raise_for_status()
        score = resp.json()["data"]

    print("\n[DONE] Demo pipeline seeded:")
    print(f"  Pipeline ID:    {pipeline_id}")
    print(f"  Unified Score:  {score.get('unified_score')}")
    print(f"  Status:         {status}")


if __name__ == "__main__":
    asyncio.run(seed_demo())
