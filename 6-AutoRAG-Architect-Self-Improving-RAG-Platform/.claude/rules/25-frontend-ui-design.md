# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 12-Jul-2026 (IST)

---

# Rule 25 — Frontend UI Design System

> **Scope:** All AutoRAG Architect frontend pages (`autorag-client/`).
> Applies on top of Rule 20 (Frontend Next.js architecture). Rule 20 covers _structure_, this rule covers _visual design_.

---

## Source of Truth — Read This First

**For every exact design value — colors, typography, spacing, layout, icons, motion, design tokens — `.claude/docs/frontend_design.md` is the single authoritative document, not this file:**

`.claude/docs/frontend_design.md`

| Section | Covers |
| ------- | ------ |
| 2 | Color Tokens (light-first, §14 for dark opt-in) |
| 3 | Typography |
| 4 | Spacing System |
| 5 | Surface & Card Patterns |
| 6 | Input & Form Components |
| 7 | App Shell & Navigation |
| 8 | Global Pipeline Context Bar |
| 9 | Metrics Disclosure Pattern |
| 10 | Screen Patterns (per-screen layout specs) |
| 11 | Agent / Loop-Stage Color Assignments |
| 12 | Animation Guidelines |

> **12-Jul-2026**: this file previously pointed to `project-guides/Frontend-Engineering-Handbook-v2.0.md`
> (a "36-chapter" document referenced across multiple project docs) — that file never existed anywhere
> in the repository. Removed as a stale/phantom reference; consolidated to the one real design doc.
> Also see ADR-008 for the light-first flip decision, and ADR-010 (24-Jul-2026) for the earth-tone
> token implementation that brought the codebase back in line with this rule after ADR-009 (an
> unaccepted dark-first reversal draft) was found to have been unilaterally implemented in code.

**This file (Rule 25) states non-negotiable guardrails**; `frontend_design.md` owns the actual
pixel/hex/rem values and per-screen layout patterns. If they ever conflict, **Rule 25 wins** per
CLAUDE.md's precedence order (`CLAUDE.md > adr/ > rules/ > specs/ > docs/ > PRD docx`).

---

## Non-Negotiable Guardrails

1. **Stack**: Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui — no substitutions without ADR.
2. **Light mode by default** (flipped 12-Jul-2026, ADR-008; earth-tone tokens per ADR-010,
   24-Jul-2026 — supersedes the prior dark-first rule) — `darkMode: 'class'` in `tailwind.config.ts`,
   wired to a real toggle (`next-themes`, `ThemeToggle` in `DashboardTopbar`) as of ADR-010; dark
   mode is the opt-in, not the other way around.
   Exceptions (deliberate, documented — do not flip either without a separate decision):
   - the `/login` screen keeps its existing dark/animated treatment (`frontend_design.md` §16)
   - the public landing page's **Hero**, **Architecture**, and **Stats/Analytics** sections
     (`app/(marketing)/`) use a dark navy canvas (`frontend_design.md` §20); every other
     landing-page section (Features, TechStack, Security, Pricing) stays light
3. **Mobile-first** — build for phone width first, scale up with `sm:`/`md:`/`lg:`/`xl:` breakpoints.
4. **Tailwind spacing scale only** — never arbitrary pixel values (`p-[13px]` forbidden); always multiples of 4px via Tailwind tokens (`p-1`…`p-8`…).
5. **Brand accent** — `text-orange-500` / `font-bold` for "AutoRAG Architect" wherever it appears (footer, headers, decks) — see `rules/coding-standards.md` Rule 25 brand block for the exact pattern. Never gray, never unbolded.
6. **Icons**: Lucide React only — no other icon library.
7. **Animations**: subtle only (fade-in on scroll, hover states); every `transition-*` needs a `motion-safe:` or `prefers-reduced-motion` guard.
8. **No inline styles** — Tailwind classes only.
9. **No hardcoded URLs or API endpoints** in components — use `services/api-client.ts`.
10. **Accessibility & performance**: `next/image` with explicit `width`/`height`, `next/font` (no layout shift), `"use client"` only when state/effects/events are needed, Lighthouse 90+ target.

---

## Recommended Tools

| Tool | Use |
| ---- | --- |
| shadcn/ui | Copy-paste component library |
| Lucide React | Icon set |
| Framer Motion | Advanced animations |
| Recharts | Already installed — use for all charts/graphs |
