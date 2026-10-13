// Runtime mode, resolved at build time from the root .env (see next.config.ts).
//   proxy  (default) — browser → Next.js /api/proxy → FastAPI (same origin, SSE passthrough)
//   direct            — browser → FastAPI at NEXT_PUBLIC_API_URL (needs CORS)
//   mock              — no backend, no Supabase: fixtures + a simulated agent stream (demos, tests)
export type ApiMode = "proxy" | "direct" | "mock";

const raw = process.env.NEXT_PUBLIC_API_MODE ?? "proxy";
export const API_MODE: ApiMode = raw === "direct" || raw === "mock" ? raw : "proxy";

export const API_BASE =
  API_MODE === "direct" ? (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8020") : "/api/proxy";

export const DISCLAIMER = "Decision support only — not investment advice.";
