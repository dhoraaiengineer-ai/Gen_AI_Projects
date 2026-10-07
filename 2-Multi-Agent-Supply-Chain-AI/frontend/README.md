# SupplyAI — Frontend

Next.js 16 (App Router), TypeScript, Tailwind CSS 4, Radix-based shadcn-style components, Recharts and Framer Motion.

```bash
npm ci
npm run dev            # http://localhost:3000
```

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_DATA_SOURCE` | `mock` (default): realistic demo data, no backend needed. `api`: the FastAPI backend. |
| `BACKEND_URL` | Server-side URL of the FastAPI API used by the `/api` proxy (default `http://localhost:8000`). Read at runtime. |

- `types/index.ts` is the API contract shared with the backend.
- `lib/api.ts` defines the `SupplyApi` interface with an HTTP implementation (SSE streaming for the Copilot) and a mock implementation in `lib/mock/`.
- `app/api/[...path]/route.ts` proxies `/api/*` to the backend without buffering, so LangGraph token streams reach the browser in real time.

```bash
npx tsc --noEmit && npx eslint .
npx playwright test    # smoke + responsive tests against a running app (uses local Chrome)
```
