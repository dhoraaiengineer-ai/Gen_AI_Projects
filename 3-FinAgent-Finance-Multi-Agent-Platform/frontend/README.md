# FinAgent UI (Next.js 16)

Enterprise UI for FinAgent. Model-View-Presenter (ADR-025): `lib/` holds the model (API client,
mock fixtures, formatting), `presenters/` the hooks that load and shape data, `components/` and
`app/` the views. The UI never computes financial numbers; it formats what the API returns.

## Run

```bash
npm install
npm run dev          # http://localhost:3020 — needs the API on :8020 (backend: scripts.dev_server)
npm run build && npm start
```

Configuration comes from the **repo-root `.env`** (loaded in `next.config.ts`): `SUPABASE_URL`,
`SUPABASE_PUBLISHABLE_KEY` (publishable, browser-safe), `API_PORT`. Optional:

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_MODE` | `proxy` | `proxy`: browser → `/api/proxy/*` (Next route handler) → API; SSE streams through unbuffered. `direct`: browser → `NEXT_PUBLIC_API_URL` (needs CORS). `mock`: fixtures + simulated agent stream, no backend or Supabase. |
| `API_INTERNAL_URL` | `http://127.0.0.1:$API_PORT` | Where the proxy forwards (server side only). |

Mock mode for demos: `NEXT_PUBLIC_API_MODE=mock npm run dev` (PowerShell:
`$env:NEXT_PUBLIC_API_MODE="mock"; npm run dev`), then pick a role on the sign-in screen.

## Pages

| Route | Who sees it | What |
|---|---|---|
| `/` | everyone | AUM, breaches, pending approvals, portfolios, recent activity |
| `/assistant` | `agents:run` | streaming multi-agent chat (timeline, report, approval card, follow-ups) |
| `/portfolios` | everyone | holdings, sector weights, risk metrics, limit checks; risk review / rebalance buttons by role |
| `/approvals` | proposers and approvers | draft-order proposals; approve / reject with a note |
| `/knowledge` | everyone (answers: `agents:run`) | grounded answers with citations; documents; upload/delete with `documents:write` |
| `/markets` | everyone | benchmark, sector performance, news |
| `/fraud` | `fraud:analyze` | latest fraud-model scores; on-demand fraud review |
| `/agents` | everyone | agent cards and stats, ML models, system status |
| `/audit` | `audit:read` | recent decisions; full trace of one request |

Navigation hides what a role cannot use; the API enforces every permission regardless.

## Tests

```bash
npm run lint && npm run typecheck
npm run test:e2e     # Playwright 1.62 against mock mode on :3030 (no backend, no quota)
```
