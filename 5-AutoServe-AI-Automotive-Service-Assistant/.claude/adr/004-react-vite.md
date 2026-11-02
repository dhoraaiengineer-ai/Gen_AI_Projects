# ADR-004 — React 18 + Vite SPA for the frontend

**Status:** Accepted · **Date:** 2026-10-26

## Context
Five role-specific workspaces (owner chat, advisor board, tech copilot, warranty queue/workspace, admin), all behind login, no SEO needs,
and tablet use in workshops. Static hosting on S3 + CloudFront is preferred (ADR-005).

## Decision
React 18 + TypeScript + Vite + Tailwind + TanStack Query + Zod + React Router, built to static assets.
Vitest + Testing Library for units; Playwright for e2e.

## Alternatives
- Next.js (legacy AutoRAG client): SSR/server components are not needed for an authenticated SPA and add a Node runtime to deploy.
- Vue/Svelte: fine, but the team's existing skills and component ecosystem favour React.

## Consequences
- + Simple static deploy, fast dev server, no server runtime for the UI.
- + Zod at the API boundary catches contract drift.
- − No SSR; first-load performance relies on code splitting per route.
- − The legacy `autorag-client` (Next.js) code is not reused (retired in P1-1).
