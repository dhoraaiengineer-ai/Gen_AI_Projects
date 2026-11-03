# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

> **Screen Engineering Reference:** Before building any frontend page, read
> [`.claude/docs/frontend_design.md`](../docs/frontend_design.md) — the single design system SOT.
> (12-Jul-2026: removed a stale per-chapter reference to `project-guides/Frontend-Engineering-Handbook-v2.0.md`,
> a document that never existed anywhere in this repository.)

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Frontend Application Specification (Next.js) - AutoRAG Architect

This document details the architecture, design themes, and routing configurations for the Next.js App Router visualization dashboard.

> **UI/UX Design System SOT**: `.claude/docs/frontend_design.md`
> Contains: colors (light-first, `#c58341` earth-tone primary accent + functional stage colors —
> flipped from dark-first 12-Jul-2026 (ADR-008), earth-tone palette applied 24-Jul-2026 (ADR-010)),
> typography (Inter + JetBrains Mono), spacing, animation standards
> (`prefers-reduced-motion` required), component patterns, and agent/stage color assignments.
> **AI agents generating frontend code MUST read this file before producing any component.**

---

## 1. Project Organization (`/autorag-client/`)

The frontend application uses the **Next.js 15 App Router** structure:

```
autorag-client/
├── app/
│   ├── layout.tsx         # Global HTML wrapper, metadata, HSL-base theme
│   ├── page.tsx           # Premium landing page and quick-status overview
│   ├── configurator/      # Configurator panel (build new RAG pipelines)
│   └── dashboard/         # Observability dashboard (charts, agent logs)
├── components/            # Reusable UI elements (cards, loaders, charts)
├── lib/                   # API clients, fetch helpers, MLflow state utilities
├── types/                 # TypeScript type definitions for API responses
└── package.json           # Node.js dependencies
```

---

## 2. Core Dashboard Features

### The Configurator Panel (`/configurator`)

An interactive control panel designed for administrators to orchestrate and configure pipelines:

- **Chunking Strategy Configurator**: Drag-and-drop selector to set Chunk Sizes, overlap tokens, and choose between Semantic, Hierarchical, or Late Chunking.
- **Embedding Model Configurator**: Selector for primary models (`gemini-embedding-2`) and fallbacks.
- **Unified Score Weight Slider**: Dynamic sliders allowing authorized admins to adjust weights for Retrieval, Quality, Faithfulness, Latency, and Cost.

### The Agent Observability Dashboard (`/dashboard`)

A live control center showing the 9-agent LangGraph execution flow:

- **Interactive Node Map**: Real-time visual network representing the 9 agents. Nodes glow green when active, yellow when retrying, and red when blocked.
- **Metrics Console**: Displays real-time charts plotting **Unified Score trends over time**, p95 latency graphs, and Prometheus/Grafana exception metrics.
- **Ingestion Monitor**: Visual log showing Custom PII Detection scanning statuses and document chunk relationships.

---

## 3. Design System & Aesthetics

⚠️ CORRECTED 16-Jul-2026: this section previously described a dark-glassmorphism
theme (`#14141a` background, `#4facfe` glow accent) that predates the light-first
flip (ADR-008, 12-Jul-2026) and directly contradicted this file's own header note
above. Do not use those values.

The authoritative color tokens, typography, spacing, component patterns, and
animation rules live in **[`.claude/docs/frontend_design.md`](../docs/frontend_design.md)**
— read it before building any component. Summary: light mode by default
(`#c58341` earth-tone primary accent, ADR-010, + functional stage colors), Inter + JetBrains Mono,
`prefers-reduced-motion`-guarded animations. The `/login` screen is the one
documented dark-mode exception (`frontend_design.md` §16).

