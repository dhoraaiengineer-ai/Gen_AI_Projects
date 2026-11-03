# AutoRAG Architect — Extended UAT Results (production build)
Run at: 2026-07-26T11:14:17.723Z
Test document: Ardenmoor_Annual_Report_FY2025.pdf
Frontend: production build (next build && next start)
Pipeline ID (if captured): not captured from URL

| Phase | Status | Notes |
|---|---|---|
| 1 — Platform Startup | PASS | Login succeeded, redirected to /dashboard. Sidebar pipeline link visible: true. |
| 2 — Pipeline Studio (create) | PASS | Pipeline creation step advanced. URL: http://localhost:3000/configurator |
| 3 — Document Management (upload) | PASS | Ardenmoor PDF uploaded. Reached "indexed" state within poll window: true. |
| 3b — Corrupted file handling | PARTIAL | Corrupted file upload attempted. Error/failed state visible: false. |
| 2b — Pipeline Studio (config persists after refresh) | FAIL | After hard refresh, pipeline name/step content still present: false. |
| 4 — Knowledge Base | PARTIAL | Overview + Semantic Search tab tested. A results/empty-state signal rendered: false. |
| 5 — Retrieval Explorer | PASS | Retrieval run attempted. Stage names rendered: true. |
| 6 — Query Playground | PASS | Playground run attempted. "Answer" section rendered: true. |
| 7 — Evaluation | PASS | Evaluation completed with real band result: "Hard Block — Deployment Not Allowed". |
| 7b — Golden Dataset | PASS | Page loaded, expected content markers present: true. |
| 8a — Observer | PASS | Page loaded, expected content markers present: true. |
| 8b — Diagnoser | PASS | Page loaded, expected content markers present: true. |
| 8c — Improver | PASS | Page loaded, expected content markers present: true. |
| 8d — Experiments | PASS | Page loaded, expected content markers present: true. |
| 8e — Evolution History | PASS | Page loaded, expected content markers present: true. |
| 9 — Deployment | PASS | Deploy Center loaded, expected content markers present: true. |
| 10a — Audit Logs | PASS | Page loaded, expected content markers present: true. |
| 10b — System Health | PASS | Page loaded, expected content markers present: true. |
| 10c — Settings (Profile) | PASS | Page loaded, expected content markers present: true. |
| 10d — Settings (Organization) | PASS | Page loaded, expected content markers present: true. |
| 10e — Settings (Notifications) | PASS | Page loaded, expected content markers present: true. |
| 10f — Settings (Theme) | PASS | Page loaded, expected content markers present: true. |