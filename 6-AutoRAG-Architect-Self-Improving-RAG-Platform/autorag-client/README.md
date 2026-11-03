# 🎨 autorag-client — Next.js 15 Dashboard Frontend

This folder contains the React UI dashboard for AutoRAG — where users configure pipelines, monitor runs, and approve deployments.

## 📋 Table of Contents

1. [Who Should Read This?](#who-should-read-this)
2. [Quick Start](#quick-start)
3. [Structure](#structure)
4. [Key Files & Folders](#key-files--folders)
5. [Getting Started](#getting-started)
6. [Key Rules](#key-rules)
7. [Related Docs](#related-docs)

---

## Who Should Read This?

- **Frontend Engineers** — Building UI components, pages, or hooks
- **UI/UX Designers** — Understanding the component library and design system
- **Full-Stack Developers** — Connecting frontend to backend APIs
- **New Joiners** — Learning the frontend architecture and folder organization

## Quick Start

**I want to...**
- Run the frontend locally → `npm run dev` (see [project root README](../README.md#4-quick-start))
- Build a new page → Check `app/` structure + [Rule 20: Frontend Next.js](../.claude/rules/20-frontend-nextjs.md)
- Create a reusable component → Follow patterns in `components/` (check `components/layout/` for examples)
- Connect to the backend API → Use `services/api-client.ts` + `hooks/use-health.ts` / `use-pipelines.ts`
- Check UI design system → See [Rule 25: Frontend UI Design](../.claude/rules/25-frontend-ui-design.md)

## Structure

```
autorag-client/
│
├── app/                     # Next.js 15 App Router (server components by default)
│   ├── page.tsx             # Home page (redirects into /dashboard)
│   ├── layout.tsx           # Root layout (Tailwind, dark mode, providers)
│   ├── (auth)/              # Authentication route group (login, signup, forgot-password)
│   └── dashboard/, documents/, pipelines/, ...  # Flat top-level route directories (no
│                              (dashboard)/ route group -- each screen is its own folder)
│
├── components/              # Reusable React UI components
│   ├── configurator/        # 6-step wizard UI
│   ├── pipeline/            # Pipeline list, status, details
│   ├── evaluation/          # Eval results, charts
│   ├── layout/              # Sidebar, header, footer
│   └── ...
│
├── hooks/                   # Custom React hooks
│   ├── use-health.ts        # API health check hook
│   ├── use-pipelines.ts     # Pipeline list + state management
│   └── ...
│
├── lib/                     # Utilities (formatters, chart/score helpers) + colocated *.test.ts
│
├── types/                   # Shared TypeScript types
│   └── index.ts             # Hand-written; OpenAPI-generated types live in types/generated-api.ts
│
├── public/                  # Static assets (images, icons, fonts)
│
├── __tests__/, test-utils/  # Vitest component tests + shared fixtures
├── e2e/                     # Playwright specs (see playwright.config.ts)
│
└── package.json             # Dependencies
```

> For shared dev/staging/production work, real, pre-filled `.env` files are distributed directly
> by project leads. For individual local testing, copy the root [`.env.example`](../.env.example)
> template instead. See root [CLAUDE.md](../.claude/CLAUDE.md) §5.

## Key Files & Folders

| File | Purpose |
|------|---------|
| `app/layout.tsx` | Root layout (Tailwind setup, dark mode, providers) |
| `components/` | All UI components (keep <200 lines each, single responsibility) |
| `ui/` | General-purpose UI components |
| `hooks/use-health.ts` | Health check hook (wraps API health endpoint) |
| `hooks/use-pipelines.ts` | Pipeline list + state management hook |
| `services/api-client.ts` | Typed API client — all backend calls go through here |
| `types/index.ts` | TypeScript types for API responses (OpenAPI-generated preferred) |

## Getting Started

1. **Install dependencies**
   ```bash
   npm install                           # Install packages
   ```
   Then copy the real, pre-filled `.env` file distributed by the project leads into
   `autorag-client/.env` (no template to `cp` from — see [CLAUDE.md](../.claude/CLAUDE.md) §5).

2. **Start dev server**
   ```bash
   npm run dev                           # http://localhost:3000
   ```

3. **Check health**
   - http://localhost:3000 → should load dashboard
   - Open DevTools (F12) → check Network tab for API calls

## Key Rules

- **TypeScript strict mode**: All files fully typed, no `any`
- **Small components**: Keep under 200 lines, focus on single responsibility
- **Server components first**: Use `app/` routes; client components only when needed (`"use client"`)
- **No hardcoded URLs**: API endpoints via config (`lib/api.ts`)
- **Dark mode support**: Tailwind dark mode enabled by default

## Related Docs

- [.claude/CLAUDE.md](../.claude/CLAUDE.md) — Engineering rules
- [.claude/rules/20-frontend-nextjs.md](../.claude/rules/20-frontend-nextjs.md) — Next.js standards
- [.claude/rules/25-frontend-ui-design.md](../.claude/rules/25-frontend-ui-design.md) — UI/UX design system
- [.claude/docs/setup.md](../.claude/docs/setup.md) — Team setup

---

## 📚 Quick Links to Related Docs

| Need... | Read... | Purpose |
|---------|---------|---------|
| **System overview** | [../README.md](../README.md) | Project intro, tech stack, workflow |
| **Backend API** | [../autorag-server/README.md](../autorag-server/README.md) | FastAPI endpoints, data models, LangGraph |
| **API specification** | [../.claude/specs/api-design.md](../.claude/specs/api-design.md) | All 46 endpoints, live-schema verified, request/response contracts |
| **Component design** | [../.claude/rules/25-frontend-ui-design.md](../.claude/rules/25-frontend-ui-design.md) | Design system, colors, typography, spacing |
| **Next.js standards** | [../.claude/rules/20-frontend-nextjs.md](../.claude/rules/20-frontend-nextjs.md) | Component patterns, server/client rules |
| **Database schema** | [../.claude/specs/database.md](../.claude/specs/database.md) | Data models, what the API returns |
| **Infrastructure** | [../infra/README.md](../infra/README.md) | How frontend is deployed via ECS Fargate |
| **Architecture** | [../architecture/README.md](../architecture/README.md) | System design, data flow, UI state management