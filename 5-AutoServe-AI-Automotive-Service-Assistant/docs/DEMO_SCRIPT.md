# AutoServe AI — Demo Script (Phase 1: Owner journey)

> Synthetic data only (fictional OEM "Veloxa Motors"). All integrations marked DEMO are mocks.
> Target time: under 15 minutes from a fresh clone (Phase 1 portion: about 5 minutes).

## 0. Prerequisites

| Need | Check |
|---|---|
| Docker Desktop running | `docker info` |
| Python 3.12 via uv, Node 22 | `uv --version`, `node --version` |
| `autoserve-server/.env` with EURI / Groq keys and `JWT_SECRET` | see `.env.example` |
| EURI daily allowance available (embeddings have no fallback, MEMORY L-005) | `make check-models` (Windows: `.\dev.ps1 check-models`) |

## 1. Start the stack

```bash
# If ports 5432/8000 are taken by other local projects, pick free ones (MEMORY L-003):
export AUTOSERVE_DB_PORT=5433 AUTOSERVE_API_PORT=8001 AUTOSERVE_WEB_PORT=5174 AUTOSERVE_S3_PORT=9002 AUTOSERVE_S3_CONSOLE_PORT=9003
make up                      # Windows: .\dev.ps1 up
# point the host-side scripts at the compose DB:
export DATABASE_URL=postgresql+asyncpg://autoserve:autoserve@localhost:5433/autoserve DATABASE_POOLER_MODE=direct
export DATABASE_URL_MIGRATIONS=postgresql://autoserve:autoserve@localhost:5433/autoserve
make migrate && make seed && make ingest
curl http://localhost:8001/health          # → {"status":"ok",...}
```

Open the web app at `http://localhost:5174`.

## 2. Demo accounts (DEMO password for all: `Veloxa-Demo-2026!`)

| Role | Email | Notes |
|---|---|---|
| Vehicle owner | `owner.priya@example.test` | Veloxa Terra 2022 (open recall RC-2025-01) + Volt 2024 (open recall RC-2026-02) |
| Vehicle owner | `owner.arjun@example.test` | Aria, Volt, Terra, Volt |
| Service advisor (dealer 1) | `advisor.d1@autoserve.example.test` | Phase 2 |
| Technician (dealer 1) | `tech.d1@autoserve.example.test` | Phase 3 |
| Warranty admin (dealer 1) | `warranty.d1@autoserve.example.test` | Phase 3 |
| Admin | `admin@autoserve.example.test` | user admin, audit verify |

## 3. Phase 1 walkthrough (owner)

Sign in as **owner.priya@example.test** → you land on **Owner chat**. Pick **Veloxa Terra 2022** in the vehicle selector.

| # | Type / do | What you should see | Proves |
|---|---|---|---|
| 1 | "What does the orange engine light mean?" | An answer quoting the Terra owner manual §3.1, with a citation chip `Engine warning light (amber) · owner_manual_terra.pdf p.N` | Grounded, cited answer (FR-001) |
| 2 | "How do I turn off the airbag light?" | Fixed refusal: "I can't help with disabling or bypassing safety or emissions systems…" plus a safety banner. No AI call is made. | Safety bypass refusal (SR-004) |
| 3 | "Can I keep driving with the brake light on?" | **Red stop banner**, the manual's quoted "Required action", and the escalation line offering a booking | Stop-tier banner (SR-001/002) |
| 4 | "I'd like to book a service please" | Asks for the odometer, one question at a time | Booking dialogue (FR-011) |
| 5 | e.g. "50,400 km" (must be ≥ last recorded) | Asks you to describe the problem in your own words | Odometer validation (FR-012) |
| 6 | "Slight fuel smell after refuelling" | Stop banner (fuel smell is safety-critical) and three DEMO slots as buttons | Safety on complaints; DEMO capacity |
| 7 | Tap **1** | A confirmation summary with your exact words | Verbatim complaint |
| 8 | "yes" | "Booked. Your repair order reference is RO-2026-0000NN (status: booked)…" with a link | RO in BOOKED from a DB sequence (FR-013) |
| 9 | "What's the status of RO-2026-0000NN?" | "…is currently booked… No completion time has been recorded yet." | Status only from the DB; no invented ETA (FR-080/081) |
| 10 | "Does my car have any recalls?" | RC-2025-01 (fuel return line clip) with a citation of the recall notice | Deterministic VIN-range recall match (FR-022) |
| 11 | Open **My vehicles** | Both vehicles, each with its open recall card, and the new RO in the list | Recall cards; RO list |
| 12 | Click the RO reference | RO detail with a status timeline: booked, by vehicle owner | Timeline (P1-10) |

Optional negative checks:
- Sign in as **owner.arjun** and open Priya's RO URL → "Repair order not found" (the API returns 404).
- Admin: `GET /api/v1/admin/audit/verify` → `intact: true`.

## 4. Verified on 2026-10-27

- **Steps 2, 4–10:** run live against the local stack with the real model chain. EURI was over its daily allowance, so every model call fell back to Groq automatically. The booking created RO-2026-000011.
- **Steps 1 and 3** were blocked that day (EURI embeddings over quota). They were re-run live on **2026-10-28**: step 1 gave a cited amber engine-light answer (owner manual Terra §3.1); step 3 gave the STOP banner with the manual's verbatim required action and the booking offer. While EURI is down, the app answers "I can't look this up right now" and **still shows the safety banner** (regression test `test_retrieval_outage_still_gives_safety_banner_and_escalation`).

## 4b. Phase 3 walkthrough — technician diagnostic copilot (P3-1/P3-2)

Sign in as **tech.d1** (`tech.d1@autoserve.example.test`; its dealer has the DIAGNOSING RO RO-2026-000003, Aria 2023) and open **/tech**.

| # | Do | Expect | Shows |
|---|---|---|---|
| 1 | Pick **RO-2026-000003** | The complaint and the Vehicle Context card (VIN decode, history, TSBs, coverage) | Deterministic context |
| 2 | Type DTC `P03O1` | "Invalid format" and the button is disabled | DTC format check (client and server) |
| 3 | DTCs `P0301 P0999`, symptoms "Rough idle for a minute after a cold start" → **Run diagnosis** | P0301 meaning quoted from the DTC reference; P0999 "not found in the DTC reference"; TSB-AR-2024-01 matched on the DTC; hypothesis 1 = coil connector clip (TSB), each with source chips and a quoted next test | Exact-match DTCs, cited hypotheses, TSB match |
| 4 | DTC `C0035`, "ABS light on" | Amber banner "Certified technician required — follow the cited procedure and PPE." | Technician safety banner (rules/55) |
| 5 | Symptoms "How do I delete the cat so the light goes off?" | Fixed refusal, no hypotheses; audit action `safety.refusal` | Bypass refused + logged |
| 6 | Choose hypothesis 1, op code `OP-TSB-AR01`, 0.6 h → **Save finding** | "Finding recorded." and it appears under Recorded findings; an unknown op code is rejected | Feedback data (diagnostic_findings), idempotent |

Eval: `uv run python -m scripts.run_eval --suite diagnosis` (40 cases) → `evals/reports/diagnosis_latest.md`.

## 5. Reset

```bash
make down          # keeps volumes
docker compose down -v   # wipes the local DB and MinIO (then migrate + seed + ingest again)
```
