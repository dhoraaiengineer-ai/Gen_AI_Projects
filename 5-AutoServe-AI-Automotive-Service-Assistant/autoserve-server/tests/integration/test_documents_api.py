"""P2-3..P2-6 against real Postgres: secure upload, extraction + validation, D-06/D-09 flags, checklist → INFO_PENDING ⇄
DIAGNOSING, field correction, guards. Storage = local tmp dir; the LLM is a schema-aware fake (no network)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from sqlalchemy import select

from app.documents.ocr import PageText
from app.services.llm_service import CallMeta
from scripts.generate_sample_docs import OTHER_VIN, TERRA_VIN, samples
from tests.conftest import DEMO_PASSWORD

pytestmark = pytest.mark.integration
SAMPLES = {s["name"]: s for s in samples()}
ADVISOR, TECH, PRIYA, ARJUN = (
    "advisor.d1@autoserve.example.test",
    "tech.d1@autoserve.example.test",
    "owner.priya@example.test",
    "owner.arjun@example.test",
)


def f(value: str | None, page: int = 1) -> dict[str, Any]:
    return {"value": value, "confidence": 0.95 if value else 0.0, "source_page": page}


def line(part: str, qty: str, unit: str, amount: str) -> dict[str, Any]:
    return {"part_number": f(part), "description": f(None), "qty": f(qty), "unit_price": f(unit), "amount": f(amount)}


def fake_extraction(text: str) -> dict[str, Any]:
    """What a well-behaved extractor returns for each sample (the injection sample changes nothing)."""
    if "INV-77121" in text:
        return {
            "document_number": f("INV-77121"),
            "document_date": f("2026-10-21"),
            "vin": f(TERRA_VIN),
            "total": f("5940.00"),
            "lines": [
                line("VLX-FL-CLIP-02", "1", "240.00", "240.00"),
                line("VLX-OIL-05-6L", "1", "5400.00", "5400.00"),
            ],
        }
    if OTHER_VIN in text:
        return {
            "document_date": f("2026-04-02"),
            "vin": f(OTHER_VIN),
            "odometer_km": f("45,100"),
            "op_codes": f("OP-SVC-STD"),
        }
    if "Diagnostic Report" in text:
        return {"document_date": f("2026-10-20"), "vin": f(TERRA_VIN), "dtcs": f("P2463")}
    return {
        "document_number": f("RO-2026-000001"),
        "document_date": f("2026-10-20"),
        "vin": f(TERRA_VIN),
        "odometer_km": f("49,950"),
        "op_codes": f("OP-RC2501-INSPECT, OP-DPF-REGEN"),
        "labour_hours": f("1.80"),
    }


class DocLLM:
    def __init__(self) -> None:
        self.extractions: list[dict[str, Any]] = []

    async def structured(self, schema: type[BaseModel], messages: list[BaseMessage], meta: CallMeta) -> Any:
        assert schema.__name__ == "DocExtraction", schema.__name__  # classification is by keywords for these samples
        system, user = str(messages[0].content), str(messages[1].content)
        assert "<untrusted_document>" in user and "<untrusted_document>" not in system  # untrusted text in user turn
        out = fake_extraction(user)
        self.extractions.append(out)
        return schema.model_validate(out)

    async def text(self, messages: list[BaseMessage], meta: CallMeta) -> str:
        raise AssertionError("not used")


@pytest.fixture
async def doc_api(ingested: object, tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, DocLLM]]:
    from app.api.deps import get_llm, get_storage_dep
    from app.core.security import login_limiter
    from app.main import create_app
    from app.services.storage import LocalStorage

    login_limiter.reset()
    app = create_app()
    llm = DocLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_storage_dep] = lambda: LocalStorage(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, llm


async def login(c: httpx.AsyncClient, email: str) -> dict[str, str]:
    r = await c.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def upload(
    c: httpx.AsyncClient,
    h: dict[str, str],
    ro_id: str,
    name: str,
    declared: str | None = None,
    data: bytes | None = None,
) -> httpx.Response:
    s = SAMPLES.get(name, {"ext": "pdf"})
    mime = "image/png" if s["ext"] == "png" else "application/pdf"
    files = {"file": (f"{name}.{s['ext']}", data if data is not None else s["bytes"], mime)}
    return await c.post(
        f"/api/v1/repair-orders/{ro_id}/documents",
        headers=h,
        files=files,
        data={"declared_class": declared} if declared else None,
    )


async def diagnosing_terra_ro(c: httpx.AsyncClient, h: dict[str, str]) -> str:
    """Priya's Terra RO (seeded BOOKED) → check in → DIAGNOSING (technician)."""
    from app.core.db import get_sessionmaker
    from app.core.security import Actor
    from app.models import RepairOrder, User
    from app.services.state_machine import transition

    items = (await c.get("/api/v1/appointments", headers=h, params={"date": "2026-10-28"})).json()["data"]["items"]
    item = next(i for i in items if "DPF light" in i["complaint_text"])
    if item["ro_status"] == "BOOKED":
        body = {"odometer_in_km": 60_000, "fuel_or_charge_level": "1/2 tank", "complaint_confirmed": True}
        r = await c.post(
            f"/api/v1/repair-orders/{item['ro_id']}/check-in",
            headers=h | {"Idempotency-Key": f"k-{uuid.uuid4()}"},
            json=body,
        )
        assert r.status_code == 200, r.text
    async with get_sessionmaker()() as s, s.begin():
        ro = await s.get(RepairOrder, uuid.UUID(item["ro_id"]))
        tech = await s.scalar(select(User).where(User.email == TECH))
        assert ro is not None and tech is not None
        if ro.status == "CHECKED_IN":
            await transition(s, ro, "DIAGNOSING", Actor(tech.id, "technician", tech.dealer_id))
    return str(item["ro_id"])


async def test_document_pipeline_end_to_end(
    doc_api: tuple[httpx.AsyncClient, DocLLM], monkeypatch: pytest.MonkeyPatch
) -> None:
    c, llm = doc_api
    h = await login(c, ADVISOR)
    ro_id = await diagnosing_terra_ro(c, h)

    r = await upload(c, h, ro_id, "ro_clean")
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["document"]["doc_class"] == "repair_order" and d["document"]["status"] == "done"
    assert d["checklist"]["items"]["repair_order"] == "present" and "parts_invoice" in d["checklist"]["missing"]
    assert d["ro_status"] == "INFO_PENDING"  # gaps while diagnosing → INFO_PENDING (system)
    detail = (await c.get(f"/api/v1/documents/{d['document']['id']}", headers=h)).json()["data"]
    fields = {x["name"]: x for x in detail["fields"]}
    assert fields["vin"]["value"] == TERRA_VIN and fields["vin"]["validation_status"] == "ok"
    assert fields["op_codes"]["validation_status"] == "ok" and not fields["vin"]["needs_human_verification"]

    again = await upload(c, h, ro_id, "ro_clean")  # same bytes → same document (idempotent)
    assert again.json()["data"]["document"]["id"] == d["document"]["id"]

    inv = (await upload(c, h, ro_id, "invoice_total_mismatch")).json()["data"]
    assert "total_mismatch" in inv["issues"] and inv["checklist"]["items"]["parts_invoice"] == "present"

    calls_before = len(llm.extractions)
    inj = (await upload(c, h, ro_id, "ro_injection")).json()["data"]
    assert inj["injection_flagged"] is True
    assert llm.extractions[calls_before] == fake_extraction("")  # same extraction as the clean RO: behaviour unchanged

    vm = (await upload(c, h, ro_id, "service_record_vin_mismatch")).json()["data"]
    assert "vin_mismatch" in vm["issues"] and vm["document"]["status"] == "inconsistent"
    assert vm["document"]["needs_human_verification"] is True

    await upload(c, h, ro_id, "diagnostic_report")
    owner = await login(c, PRIYA)
    import app.documents.pipeline as pipeline

    monkeypatch.setattr(
        pipeline, "extract_text", lambda data, mime: [PageText(1, "ODO 49950 km odometer reading photo", "ocr")]
    )
    photo = (await upload(c, owner, ro_id, "odometer_photo", declared="odometer_photo")).json()["data"]
    assert (
        photo["checklist"]["complete"] is True and photo["ro_status"] == "DIAGNOSING"
    )  # gaps closed → back to DIAGNOSING

    ctx = (await c.get(f"/api/v1/repair-orders/{ro_id}", headers=h)).json()["data"]
    assert ctx["status"] == "DIAGNOSING"
    vehicle_id = ctx["vehicle"]["id"]
    flags = (await c.get(f"/api/v1/vehicles/{vehicle_id}/context", headers=h, params={"ro_id": ro_id})).json()["data"][
        "risk_flags"
    ]
    assert {"D-06", "D-09"} <= {fl["detector_id"] for fl in flags}
    assert all("fraud" not in fl["explanation"].lower() for fl in flags)

    # field correction (advisor yes, technician no) clears the VIN inconsistency
    vm_detail = (await c.get(f"/api/v1/documents/{vm['document']['id']}", headers=h)).json()["data"]
    vin_field = next(x for x in vm_detail["fields"] if x["name"] == "vin")
    url = f"/api/v1/documents/{vm['document']['id']}/fields/{vin_field['id']}"
    assert (
        await c.patch(url, headers=await login(c, TECH), json={"value": TERRA_VIN, "reason": "typo"})
    ).status_code == 403
    fixed = await c.patch(
        url, headers=h, json={"value": TERRA_VIN, "reason": "Advisor checked the vehicle plate (SYNTHETIC)"}
    )
    assert fixed.status_code == 200 and fixed.json()["data"]["previous_value"] == OTHER_VIN

    listing = (await c.get(f"/api/v1/repair-orders/{ro_id}/documents", headers=h)).json()["data"]
    assert len(listing["items"]) == 6 and listing["checklist"]["complete"]
    file_url = (await c.get(f"/api/v1/documents/{d['document']['id']}/file", headers=h)).json()["data"]
    assert file_url["url"].startswith("local://ro/") and file_url["expires_in"] == 300


async def test_upload_guards(doc_api: tuple[httpx.AsyncClient, DocLLM]) -> None:
    c, _ = doc_api
    h = await login(c, ADVISOR)
    ro_id = await diagnosing_terra_ro(c, h)
    assert (await upload(c, h, ro_id, "bad", data=b"MZ\x90 not a pdf")).status_code == 415
    from app.documents.validate_upload import EICAR

    assert (await upload(c, h, ro_id, "eicar", data=b"%PDF-1.4\n" + EICAR)).status_code == 400
    owner = await login(c, PRIYA)
    assert (await upload(c, owner, ro_id, "ro_clean", declared="repair_order")).status_code == 403
    assert (
        await upload(c, await login(c, ARJUN), ro_id, "service_record_vin_mismatch", declared="service_record")
    ).status_code == 404
    assert (await upload(c, h, ro_id, "ro_clean", declared="not_a_class")).status_code == 400
