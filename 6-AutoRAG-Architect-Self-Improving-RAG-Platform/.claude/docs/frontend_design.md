# AutoRAG Architect — Frontend Design System Reference

**Version**: v3.0
**Status**: Active SOT
**Updated**: 24-Jul-2026 (IST)
**Authority**: This file is the single source of truth for all frontend visual design decisions.
Referenced by: `CLAUDE.md`, `rules/25-frontend-ui-design.md`, `specs/frontend.md`

> All engineers and AI agents building any AutoRAG Architect screen MUST read this file before writing any component.
> Stack: Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui + Lucide React. No substitutions.

**v3.0 changelog (24-Jul-2026)**: replaced the v2.0 indigo-based light token set with a 5-color
earth-tone palette (see ADR-010) — this is a **token swap implementing the same v2.0 structural
decision** (light-first default, dark opt-in, `darkMode: "class"` mechanism), not a new design
direction. ADR-010 also formally closes ADR-009 (an unaccepted 18-Jul-2026 dark-first reversal
draft that the codebase had unilaterally implemented, diverging from this governing doc — see
ADR-010 §Context for the full drift finding). The theme toggle (`next-themes`, `ThemeToggle` in
`DashboardTopbar`) is real and functional for the first time as of this version.

**v2.0 changelog (12-Jul-2026)**: flipped the platform default from dark-first to **light-first**
("AutoRAG Intelligence Control Center" — see ADR-008). Dark mode is retained as a fully supported
opt-in, not deleted — see §14. The login screen keeps its existing premium dark/animated treatment
as a deliberate, documented exception (§16), since it predates and is independent of this flip. This
version also removes a stale reference to a "Frontend Engineering Handbook" document that never
existed anywhere in the repository (previously §16's chapter table) — this file, alone, is the SOT.

---

## 1. Design Philosophy

**Aesthetic**: "AutoRAG Intelligence Control Center" — a bright, premium AI engineering control
plane. Not a generic admin dashboard, not a node-link diagram, not a dark cyberpunk UI.

The product must visually communicate the closed loop it actually runs:
**Build → Measure → Detect → Diagnose → Improve → Approve → Deploy → Observe.**

**Principles**:
- Light-first: warm-white canvas, soft shadows instead of glow, calm and data-dense
- Purple/violet is reserved as the *intelligence* accent (Improver, judgment moments) — do not paint
  the whole interface purple; use functional color per loop stage (§2, §11) so the loop becomes
  legible through color alone
- Every screen in the closed loop shows a persistent **Pipeline Context Bar** (§8) so the user never
  loses track of which pipeline/run they're inspecting
- Metrics disclose in three levels — Value → Context → Source (§9) — never a bare number with no
  provenance
- Animation is subtle and purposeful: execution rows fade in, numbers count up, a signal pulses once
  on detection. No continuous glow, no particles, no decorative motion outside the login screen (§16)
- Brand accent for the wordmark stays **orange-500** (`#F97316`) regardless of theme — unaffected by
  the light/dark flip, see §13
- Every metric shown in a built screen must map to a real backend source (see `verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md`)
  — if data isn't available, render `Unavailable` / `Not collected`, never `0` or a fabricated value

---

## 2. Color Tokens (Light — Primary, ADR-010 earth-tone palette)

Source palette (5 colors, each with a `DEFAULT` + 100–900 scale — **note the scale is inverted
from normal Tailwind convention**: `500`/`DEFAULT` is the saturated mid-tone, `900` is near-white,
`100` is near-black):

```
tea_green    { DEFAULT #ccd5ae, 100 #2d331a, 200 #5b6635, 300 #88994f, 400 #acbb7b, 500 #ccd5ae, 600 #d6debe, 700 #e1e6cf, 800 #ebeedf, 900 #f5f7ef }
beige        { DEFAULT #e9edc9, 100 #3d4216, 200 #79842c, 300 #b3c146, 400 #ced788, 500 #e9edc9, 600 #edf1d4, 700 #f2f4df, 800 #f6f8ea, 900 #fbfbf4 }
cornsilk     { DEFAULT #fefae0, 100 #5d5103, 200 #baa206, 300 #f8dc27, 400 #fbeb84, 500 #fefae0, 600 #fefbe7, 700 #fefced, 800 #fffdf3, 900 #fffef9 }
papaya_whip  { DEFAULT #faedcd, 100 #533e08, 200 #a57b10, 300 #eab227, 400 #f2d079, 500 #faedcd, 600 #fbf1d6, 700 #fcf4e0, 800 #fdf8eb, 900 #fefbf5 }
light_bronze { DEFAULT #d4a373, 100 #32210f, 200 #64411f, 300 #96622e, 400 #c58341, 500 #d4a373, 600 #dcb68f, 700 #e5c8ab, 800 #eedac7, 900 #f6ede3 }
```

### Surfaces

| Token | Hex | Source | Usage |
|-------|-----|--------|-------|
| `canvas` | `#fffdf3` | `cornsilk-800` | App background |
| `surface` | `#fefbf5` | `papaya_whip-900` | Cards, panels, sidebar |
| `surface-secondary` | `#f6f8ea` | `beige-800` | Nested panels, table stripes, code blocks |
| `border` | `#eedac7` | `light_bronze-800` | Card borders, dividers |

### Text

| Token | Hex | Source | Usage |
|-------|-----|--------|-------|
| `text-primary` | `#2d331a` | `tea_green-100` | Headings, key values |
| `text-secondary` | `#64411f` | `light_bronze-200` | Body text, labels |
| `text-muted` | `#96622e` | `light_bronze-300` | Captions, placeholders, disabled |

### Brand / Intelligence

| Token | Hex | Source | Usage |
|-------|-----|--------|-------|
| Primary Bronze | `#c58341` | `light_bronze-400` | Primary actions, accent |
| Primary Bronze (hover) | `#d4a373` | `light_bronze-DEFAULT` | Hover/active state |

**Functional/status and 9-agent loop-stage colors are kept independent of the earth-tone palette**
(§79 below, §11) — they are semantic signals (pass/fail/warn, agent identity), not brand, and stay
unchanged by this token swap:

| Token | Hex | Tailwind (closest) | Usage |
|-------|-----|---------------------|-------|
| Intelligence Blue | `#3B82F6` | `blue-500` | Build stage |
| Observer Cyan | `#06B6D4` | `cyan-500` | Observe stage |
| Improvement Violet | `#8B5CF6` | `violet-500` | Improve stage, intelligence accent |
| Success Emerald | `#10B981` | `emerald-500` | Deploy stage, success states |
| Warning Amber | `#F59E0B` | `amber-500` | Diagnose stage, warnings |
| Critical Coral | `#F43F5E` | `rose-500` | Failures, hard blocks |
| Brand Orange | `#F97316` | `orange-500` | Wordmark only — unchanged by theme (§13) |

### Functional color-per-loop-stage

Color is how the user reads the closed loop at a glance — use consistently, don't reassign per page:

| Stage | Color |
|---|---|
| Build (Ingestion, Builder, Configurator) | Blue |
| Evaluate (Evaluator, Evaluation screen) | Primary Bronze (`#c58341`) — was Indigo pre-ADR-010 |
| Observe (Observer) | Cyan |
| Diagnose (Diagnoser) | Amber |
| Improve (Improver) | Violet |
| Deploy (Deployer, Deployments) | Emerald |
| Failure / hard block (any stage) | Coral |

---

## 3. Typography

Unchanged by the light/dark flip.

```css
/* Headings */
font-family: 'Space Grotesk', 'Inter', system-ui, sans-serif;

/* Body + UI */
font-family: 'Inter', system-ui, -apple-system, sans-serif;

/* Monospace (metrics, trace IDs, code) */
font-family: 'JetBrains Mono', 'Fira Code', monospace;
```

> Next.js `next/font` must load these. Never link CDN URLs (CSP blocks them).

| Role | Size | Weight | Tailwind |
|------|------|--------|---------|
| Display | 48–64px | 800 | `text-5xl font-extrabold` |
| Page title | 32px | 700 | `text-3xl font-bold` |
| Section heading | 24px | 700 | `text-2xl font-bold` |
| Card heading | 20px | 600 | `text-xl font-semibold` |
| Body | 14px | 400 | `text-sm` |
| Label | 11–12px | 500–600 | `text-xs font-medium` |
| Caption / tag | 10px | 500 | `text-[10px] font-medium` |
| Eyebrow | 10–11px uppercase | 600 | `text-[10px] uppercase tracking-widest` |
| Metric / score | 28–48px | 700 | `text-4xl font-bold tabular-nums` |

---

## 4. Spacing System

Unchanged — Tailwind's 4px grid. Never use arbitrary pixel values (`p-[13px]` forbidden — Rule 25).

| Context | Value |
|---------|-------|
| Page padding (desktop) | `px-8 py-6` or `px-10 py-8` |
| Card inner padding | `px-6 py-5` or `px-8 py-7` |
| Section gap | `gap-6` or `gap-8` |
| Component gap | `gap-3` or `gap-4` |
| Inline gap (icon + text) | `gap-2` or `gap-1.5` |
| Tight (badges, tags) | `gap-1` |

---

## 5. Surface & Card Patterns (Light)

### Standard Card

```tsx
<div className="rounded-2xl bg-white border border-[#E6EAF0] px-6 py-5 shadow-sm">
  {/* content */}
</div>
```

No glassmorphism/backdrop-blur in the light theme — flat white surfaces with a hairline border and a
soft `shadow-sm`. Reserve elevation via shadow, not blur.

### Metric / KPI Tile

```tsx
<div className="rounded-xl bg-white border border-[#E6EAF0] px-5 py-4 flex flex-col gap-1">
  <span className="text-[11px] uppercase tracking-widest text-[#98A2B3] font-semibold">Unified Score</span>
  <span className="text-3xl font-bold text-[#172033] tabular-nums">0.92</span>
  <span className="text-[11px] text-emerald-600">+0.04 vs last run</span>
</div>
```

### Active-state accent bar (nav items, list rows)

Do not fill the whole row with a strong color — use a 3px left bar in the item's functional color
(§2) against a very light tint background:

```tsx
<div className="relative flex items-center gap-2 rounded-lg px-3 py-2 bg-cyan-50">
  <span className="absolute left-0 top-1 bottom-1 w-[3px] rounded-full bg-cyan-500" />
  <span className="text-sm font-medium text-[#172033]">Observer</span>
</div>
```

---

## 6. Input & Form Components (Light)

```tsx
<input
  className="w-full rounded-lg py-2.5 pl-9 pr-3 text-sm text-[#172033]
             placeholder-[#98A2B3] outline-none transition-all duration-200
             bg-white border border-[#E6EAF0]
             focus:ring-2 focus:ring-[#c58341]/30 focus:border-[#c58341]"
/>
```

### Primary Button

```tsx
<button className="rounded-lg py-2.5 px-4 text-sm font-semibold text-white bg-[#c58341] hover:bg-[#d4a373] transition-colors">
  Create Pipeline
</button>
```

### Secondary Button

```tsx
<button className="rounded-lg py-2.5 px-4 text-sm font-medium text-[#c58341] border border-[#c58341]/30 bg-[#c58341]/5 hover:bg-[#c58341]/10 transition-colors">
  Upload Documents
</button>
```

> **Correction (24-Jul-2026 audit)**: these three snippets still hardcoded the
> pre-ADR-010 indigo primary (`#5B5CE2`/`indigo-500`) after SS2 migrated the
> primary accent to earth-tone bronze (`#c58341`) -- copy-pasting the old
> snippets would have reintroduced the reverted color. Updated to match SS2's
> Primary Bronze token.

---

## 7. App Shell & Navigation

```
┌─────────────────────────────────────────────────────────────────────┐
│ AutoRAG      Search pipelines...          ● Healthy    🔔    MK     │
├──────────────┬──────────────────────────────────────────────────────┤
│ OVERVIEW     │                                                      │
│ Dashboard    │                                                      │
│ Pipelines    │                 PAGE CONTENT                         │
│ Documents    │                                                      │
│ BUILD        │                                                      │
│ Configurator │                                                      │
│ Retrieval    │                                                      │
│ QUALITY      │                                                      │
│ Evaluation   │                                                      │
│ Observer     │                                                      │
│ Diagnoser    │                                                      │
│ Improver     │                                                      │
│ Experiments  │                                                      │
│ RELEASE      │                                                      │
│ Deployments  │                                                      │
│ Audit        │                                                      │
│ SYSTEM       │                                                      │
│ Health       │                                                      │
│ Advanced ›   │                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
```

**Sidebar**: `w-[248px]`, `bg-white`, `border-r border-[#E6EAF0]`. Active nav item uses the §5
accent-bar pattern in that section's functional color, not a full-fill highlight. Hover: `bg-[#F1F5F9]`.

**Advanced** is a collapsed group at the bottom containing pages with no dedicated backend yet
(`agents`, `agent-state`, `chat`, `security`, `cost`, `chunks`, `embeddings`, `infrastructure`,
`datasets`, `prompts`, `workflow`) — routes stay live at their direct URLs, just out of primary nav.

**Top header**: `h-[56px]`, `bg-white`, `border-b border-[#E6EAF0]`. Search left-center, health dot +
notification bell + user pill right.

---

## 8. Global Pipeline Context Bar

Persistent bar below the header on every closed-loop screen (Retrieval, Evaluation, Observer,
Diagnoser, Improver, Experiments, Deploy) once a pipeline/run is selected — the user should never
wonder which pipeline or run they're inspecting.

```
 Research Knowledge RAG     v12     ● Production

 Score        p95 Latency      Cost / Query      Recall@5
 0.86 ↑       2.41s            $0.0042           0.89
 +0.07        -180ms           -8.2%             +0.11

                                              Run #1842 ▾
```

**Data sources** (all real, once the Part A/A.1/B backend work lands — see
`verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md`): Score/latency/cost from `evaluation_runs` (via
`GET /score/{run_id}` and `GET /runs/{run_id}/metrics`); Recall@5 is real for the golden-path demo
document (ground-truth wired per Part A.1) — for any other pipeline, omit this field rather than
show the unmeasured placeholder.

---

## 9. Metrics Disclosure Pattern

Every metric shown anywhere in the product follows three levels — never show Level 1 without a way
to reach Level 3:

```
LEVEL 1 — Value           LEVEL 2 — Context              LEVEL 3 — Source (on hover/click)
$0.43                     ↓ 8.2% vs previous run          COST BREAKDOWN
                                                            Query Rewriter   $0.004
                                                            Builder          $0.082
                                                            Compressor       $0.031
                                                            Evaluator        $0.181
                                                            Diagnoser        $0.041
                                                            Improver         $0.091
                                                            Total            $0.430
                                                            Source: agent_metrics table
                                                            (GET /runs/{run_id}/metrics)
```

Always cite the real source in Level 3 (table/route name) — this is documentation-as-UI, and it must
stay accurate. (Note: per-agent cost/token/provider breakdowns come from the `agent_metrics` table,
**not** `execution_trace` — the latter only carries per-node status/timing, see the metrics matrix.)

---

## 10. Screen Patterns

### 10.1 Dashboard — Executive Command Center

Four zones, not 20 small cards.

**Zone A — Hero status**: greeting + one-line health summary + `[Create Pipeline]` `[Upload Documents]`.

**Zone B — 4 stat tiles**: Active pipelines, Avg score, Monthly cost, Attention count (§5 KPI tile pattern).

**Zone C — Pipeline health list** (not a chart): pipeline name, score, status word (Healthy/Review/Improving), status dot in semantic color. Link to "View all pipelines."

**Zone D — Quality trend**: one smooth line chart (Recharts) of Unified Score over time with a
horizontal threshold line at 0.85 and small event diamond markers (deploy, variant approved, drift
detected) — real data from `evaluation_runs` history.

**Zone E — Needs Attention**: cards surfacing real Observer drift signals and real pending Improver
variants (`[View Diagnosis]` / `[Review Improvement]`) — this is the screen that proves the product's
value at a glance; every card must be backed by real `observer_signals`/`improver_candidates` data.

### 10.2 Pipeline Progress (`/dashboard/[id]`) — the flagship screen

**Not a node-link diagram.** A vertical execution journey — one row per agent, in order, with real
status/duration/output summary, connected by a thin vertical rule. Each row uses that agent's
functional color (§2) for its status dot/accent. Right-side **sticky Run Inspector** panel: Run ID,
Trace ID, Status, Total Duration, Total Cost, Tokens, LLM Calls, Retries, Provider Switches,
Guardrail Blocks, `[View Raw Trace]`.

Data sources: per-node status/duration/retry from the new `node_trace` (Part A); per-LLM-call
cost/tokens/provider from `agent_metrics` (Part B.0); provider switches and guardrail blocks need
per-run filtering — omit from the Inspector until that's confirmed buildable (see plan Part H, item 6).
No fabricated progress percentage mid-run — show pending/running/complete only (Part 0 confirmed no
live per-node streaming exists yet).

### 10.3 Evaluation — Quality Scorecard

Large score card (not a giant circular gauge): Unified Score number + status label + horizontal bar
with a threshold tick at 0.85 + delta vs previous run. Below: 5 small cards for Retrieval / Quality /
Faithfulness / Latency / Cost. Then 3 tabs: **Unified Score / RAGAS / Adversarial**.

RAGAS tab: horizontal bars for Context Precision, Context Recall, Faithfulness, Answer Relevancy —
all real (`ragas_metrics` JSONB, already persisted).

Adversarial tab: aggregate `X / 10 passed`, plus **per-question failure detail** (question, expected
behavior, pipeline's actual response, classification, deployment impact) — this requires the
`adversarial_failures` persistence extension (added to Part A per the 12-Jul-2026 decision — see the
plan file). Do not build this drill-down until that persistence lands; showing only the aggregate
`X / 10` is a valid interim state.

### 10.4 Observer — AI Control Room

Calm, not alarming. Header: "Continuously monitoring quality, cost and performance" + `● WATCHING` +
last-analysis timestamp. Score trend chart with 7-run average + threshold line. **Signals** list
(Faithfulness / Retrieval / Latency / Cost / Provider — each ✓ or ⚠ with a one-line real value).
**Observer Decision** card: drift detected, primary signal, recommended action, `[Inspect Evidence]`
`[Start Diagnosis]`.

Data source: the new `observer_signals` persistence (Part A) — this is the one screen where "showing
metrics becoming a decision" is the entire point; every signal must be real, not client-derived.

### 10.5 Diagnoser — Investigation Workspace

Two-column: left = Evidence table (metric, value, PASS/FAIL — real: Faithfulness, RAGAS Context
Precision, Context Recall, plus Recall@5 for the golden-path demo document only); right = Failure
Classification card (failure type F-01…F-06, confidence bar, severity). Below, full-width: AI
Reasoning (`root_cause_analysis`, real, confirm exact phrasing during implementation),
Root Cause, Evidence bullets, Recommended Changes (config diff), `[Generate Improvement]`.

### 10.6 Improver — Improvement Studio

**Rule, unchanged from the plan's original decision**: use a Variant Arena (multiple columns) only
when the backend genuinely returns multiple variants. Confirmed this session: the Improver node
really does generate 3 real candidates (heuristic-scored, not live re-evaluated — label deltas
"estimated," not "measured"). Columns: Current / Variant A / Variant B (★ recommended) / Variant C,
each showing its `unified_score` and delta. Click a variant → "Why this one?" panel: quality gain %,
metric-by-metric before/after, config diff (`- top_k: 5` / `+ top_k: 8` style), and AutoRAG's
plain-language recommendation. `[Reject]` `[Approve & Re-evaluate]`.

If a future pipeline/run only produces one real variant, fall back to a simple Current vs. Proposed
layout — never visually invent a 3-way comparison that isn't real.

---

## 11. Agent / Loop-Stage Color Assignments

Each of the 9 agents maps to its loop stage's functional color (§2) — used consistently in status
dots, execution rows, and trace timelines:

| # | Agent | Stage | Color | Hex |
|---|-------|-------|-------|-----|
| 1 | Ingestion | Build | Blue | `#3B82F6` |
| 2 | Query Rewriter | Build | Blue | `#3B82F6` |
| 3 | Builder | Build | Blue | `#3B82F6` |
| 4 | Compressor | Build | Blue | `#3B82F6` |
| 5 | Evaluator | Evaluate | Primary Bronze (ADR-010, was Indigo) | `#c58341` |
| 6 | Observer | Observe | Cyan | `#06B6D4` |
| 7 | Diagnoser | Diagnose | Amber | `#F59E0B` |
| 8 | Improver | Improve | Violet | `#8B5CF6` |
| 9 | Deployer | Deploy | Emerald | `#10B981` |

---

## 12. Animation Guidelines

Subtle, purposeful, no decoration outside the login screen (§16).

| Moment | Treatment |
|---|---|
| Pipeline run row appears | 200–300ms fade/slide-up, staggered per row |
| Score changes (e.g. after re-evaluation) | Animate the number count-up, not a layout shift |
| Observer detects drift | The amber signal softly pulses once — not continuous |
| Improvement approved | Animate `0.72 → 0.87`, then reveal `+0.15 Improvement` |
| Hover states | `transition-colors duration-200` |
| Page transitions | `opacity 0→1` over 200ms — no slides or bounces |

**Every** CSS animation must include a `prefers-reduced-motion` guard (Rule 25, non-negotiable).

---

## 13. Brand Attribution Block

Unchanged by the light/dark flip — appears in footer, sidebar brand header, email templates, any
public-facing surface.

```tsx
<span className="font-bold text-orange-500">AutoRAG Architect</span>
```

Never: gray, white, light-weight, or lowercase. Always: `font-bold text-orange-500`.

---

## 14. Dark Mode (Opt-in)

Dark mode remains fully supported, toggled via `darkMode: 'class'` in `tailwind.config.ts` (ADR-008's
mechanism) — light is the default (ADR-008), the earth-tone palette is the token implementation
(ADR-010). As of ADR-010 (24-Jul-2026), the toggle is **real and functional** for the first time —
`next-themes`, wired via `ThemeProvider` in `app/layout.tsx` and `ThemeToggle` in
`DashboardTopbar.tsx`. Prior to this, `darkMode: 'class'` was configured but nothing ever applied the
class:

| Token | Light (default) | Dark (opt-in) | Source |
|---|---|---|---|
| Canvas | `#fffdf3` | `#32210f` | `cornsilk-800` / `light_bronze-100` |
| Card surface | `#fefbf5` | `#64411f` | `papaya_whip-900` / `light_bronze-200` |
| Text primary | `#2d331a` | `#fffef9` | `tea_green-100` / `cornsilk-900` |
| Text secondary | `#64411f` | `#fcf4e0` | `light_bronze-200` / `papaya_whip-700` |
| Border | `#eedac7` | `rgba(255,255,255,0.08)` (kept opacity-based) | `light_bronze-800` / — |
| Primary accent | `#c58341` | `#acbb7b` | `light_bronze-400` / `tea_green-400` |

Both dark-canvas candidates (`light_bronze-100/200` vs `tea_green-100/200`) were prototyped per
ADR-010's verification step; `light_bronze` was chosen as the cleaner, less-muddy dark neutral.

When building a component, implement the light tokens as the default Tailwind classes/CSS vars — the
shared classes in `globals.css` (`.panel-card`, `.kpi-tile`, etc.) already read the CSS vars, so
components using them get dark-mode support for free. Only add explicit `dark:` variants for
one-off cases not covered by a shared class. The login screen (§16) is the one deliberate exception
that stays dark regardless of the toggle — it renders no `ThemeToggle` and never reads `.dark`.

---

## 15. Data Visualization

All charts use **Recharts** (already installed).

| Property | Light (default) |
|---|---|
| Chart background | transparent (inherits card surface) |
| Grid lines | `stroke="#eedac7"` (`light_bronze-800`, border token) |
| Axis text | `fill="#96622e"` (`light_bronze-300`, muted-text token) fontSize 11 |
| Tooltip | `bg-card border border-border shadow-md` |
| Area fill | `fillOpacity 0.12–0.20`, stroke matches stage color (§2/§11) |
| Line charts | `strokeWidth 2`, dot `r=3` on hover only |

---

## 16. Login Screen — Deliberate Dark Exception

The login screen (`/login`) keeps its existing premium dark/animated treatment — it predates and is
intentionally exempt from the v2.0 light-first flip, matching Rule 25's own carve-out
("animated accents only on entry points"). Do not flip it to light without an explicit follow-up
decision.

### Left Panel (54% width, desktop only)
- Background: Aurora blobs + FloatingOrbs (6) + ParticleNetwork canvas
- Content: Brand header → Hero headline → AgentLoop SVG visualization → Trust badges
- AgentLoop: 9-agent DAG, fixed nodes, particle streams on edges, colorful ring riders on orbit track, center shows live Unified Score

### Right Panel (46% width)
- Glassmorphic card: `max-w-[460px]`, animated border, `backdrop-blur-40`
- Form: email + password + remember toggle + Sign In (gradient) + Demo Login
- Footer: pinned `absolute bottom-3`, links `text-slate-500`, powered-by `text-slate-600`
- Vertical divider: `rgba(99,102,241,0.35)` gradient line at left edge

### AgentLoop SVG Spec (`components/auth/login/AgentLoop.tsx`)
- ViewBox: `500×500`, `height="auto"` (preserves aspect ratio via browser)
- Orbit R: 155px, Node radius: 19px, Label radius: 200px
- 9 agents: full names (never abbreviate), `fill="#E2E8F0"` (visible on dark bg)
- Status line: `fill="#64748B"`, fixed y-offset +14px below name (no radial inversion)
- Particles: `<animateMotion>` + `<mpath>` per edge, rendered AFTER center core (z-order fix)
- Ring riders: 4 colored dots on orbit track (blue, purple, cyan, amber) — 12s period
- Center: AUTORAG label + 0.92 score + UNIFIED SCORE caption

### Global animation timing reference (login only)

| Animation | Duration | Easing |
|-----------|----------|--------|
| `auroraFloat` | 55s | ease-in-out |
| `orbDrift1–6` | 45–88s | ease-in-out |
| `loginFloat` | 22s | ease-in-out |
| `borderMove` | 18s | linear |
| `gradientMove` | 15s | ease |
| `agentRotate` | 18s | linear |
| `agentRotateReverse` | 24s | linear |

---

## 17. Iconography

**Only Lucide React.** No other icon library.

```tsx
import { ShieldCheck, Zap, Users, FlaskConical, Layers } from "lucide-react";
```

Standard sizes: `h-4 w-4` (inline), `h-5 w-5` (nav items), `h-6 w-6` (section headers), `h-3.5 w-3.5` (chips/badges).

---

## 18. Status Chips / Badges

```tsx
<span
  className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
  style={{ background: `${stageColor}12`, color: stageColor, border: `1px solid ${stageColor}30` }}
>
  <span className="h-1.5 w-1.5 rounded-full" style={{ background: stageColor }} />
  Running
</span>
```

Standard variants: `bg-emerald-50 text-emerald-700 border-emerald-200` (success), `bg-amber-50
text-amber-700 border-amber-200` (warning), `bg-rose-50 text-rose-700 border-rose-200` (error/critical),
`bg-indigo-50 text-indigo-700 border-indigo-200` (queued), `bg-slate-100 text-slate-500` (idle).

---

## 19. Unified Score Display

The Unified Score gate is the most important metric in the product.

```
Score >= 0.85   →  emerald,  badge "Deploy Ready"
Score 0.70–0.84 →  amber,    badge "HITL Required"
Score < 0.70    →  coral,    badge "Needs Improvement"
Faithfulness < 0.5 → always coral, "Hard Block" regardless of total
```

Display format: `0.92` (2 decimal places), monospace font, `text-4xl font-bold tabular-nums`.

---

## 20. Landing Page — Deliberate Dark Exception

Three sections of the public landing page (`app/(marketing)/`) — **Hero**, **Architecture**, and
**Stats/Analytics** — use a dark navy canvas instead of the site's default light-first design
(Rule 25, ADR-008/ADR-010). This is a second, equally explicit exception to the same class as the
Login screen (§16): do not flip these three sections to light without a separate documented
decision, and do not extend the dark canvas to any other landing-page section (Features, TechStack,
Security, Pricing stay light — they are "clean/spacious surfaces for analytics and specifications"
per the section's own design brief) without one either.

### Palette (dark sections only)

| Token | Value | Use |
|-------|-------|-----|
| `.bg-dark-mesh` | `#0F172A` base, radial spotlight to `#080D1A` | Section canvas |
| `.dark-surface-card` | `#11182C` fill, `rgba(255,255,255,0.08)` border, soft amber glow | Cards on dark canvas |
| `.text-dark-body` | `#D5D8E2` | Body text on dark canvas |
| Brand accent | `#F97316` (orange) / `#F59E0B`–`#FBBF24` (amber/gold) | CTAs, active states, glows |
| Functional | `#38BDF8` (sky, data flow) / `#10B981` (emerald, live/success) | Metric/status accents |

### AgentOrchestratorWheel Spec (`components/marketing/AgentOrchestratorWheel.tsx`)

- 9 agents positioned on a 175px-radius ring via `Math.cos`/`Math.sin`, `360/9` degree spacing —
  fed from the real `AGENTS_DATA` (`lib/marketing-data.ts`), not a separate hardcoded list.
- Center "Active Orchestrator" node: 160px circle, `animate-pulse-gold` border, auto-rotates the
  active agent every 5s, click-to-select overrides the auto-rotation target.
- Per-agent icons reuse the same icon-mapping pattern as `AgentsSection.tsx` (keyed by
  `AgentInfo.iconName`) — no second/duplicate icon map.
- Card states: inactive — `border-slate-800`, `bg-[#0f172a]/90`, 75% opacity; active —
  `border-amber-400`, glow shadow, `scale-[1.06]`, `animate-pulse-gold`.

### Animation timing reference (landing page dark sections)

| Animation | Duration | Easing | Class |
|-----------|----------|--------|-------|
| `pulseGold` | 2s | ease-in-out | `.animate-pulse-gold` |
| `spinSlow` | 30s | linear | `.animate-spin-slow` |
| `floatSlow` | 5s | ease-in-out | `.animate-float-slow` |
| `fadeInUp` | 0.6s | cubic-bezier(0.16,1,0.3,1) | `.animate-fade-in-up` |

All four respect the global `prefers-reduced-motion` guard in `app/globals.css`.

---

## Appendix A — Reference Wireframes (verbatim, source design brief 12-Jul-2026)

These are the literal ASCII layouts the "AutoRAG Intelligence Control Center" concept was specified
with. §10 above is the prose/token distillation for implementers; this appendix is the exact layout
intent for anyone who needs to see it unparaphrased. Kept verbatim on purpose — do not edit these for
style, only replace wholesale if the underlying screen design changes.

### App Shell

```
┌─────────────────────────────────────────────────────────────────────┐
│ AutoRAG      Search pipelines...          ● Healthy    🔔    MK     │
├──────────────┬──────────────────────────────────────────────────────┤
│              │                                                      │
│ OVERVIEW     │                                                      │
│ Dashboard    │                 PAGE CONTENT                         │
│ Pipelines    │                                                      │
│ Documents    │                                                      │
│              │                                                      │
│ BUILD        │                                                      │
│ Configurator │                                                      │
│ Retrieval    │                                                      │
│              │                                                      │
│ INTELLIGENCE │                                                      │
│ Evaluation   │                                                      │
│ Observer     │                                                      │
│ Diagnoser    │                                                      │
│ Improver     │                                                      │
│ Experiments  │                                                      │
│              │                                                      │
│ RELEASE      │                                                      │
│ Deployments  │                                                      │
│ Audit        │                                                      │
│              │                                                      │
│ SYSTEM       │                                                      │
│ Health       │                                                      │
│ Advanced ›   │                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
```

Active nav item (left accent bar in the section's functional color):

```
│  Evaluation
│
│▌ Observer
│
│  Diagnoser
```

### Global Pipeline Context Bar

```
 Research Knowledge RAG     v12     ● Production

 Score        p95 Latency      Cost / Query      Recall@5
 0.86 ↑       2.41s            $0.0042           0.89
 +0.07        -180ms           -8.2%             +0.11

                                              Run #1842 ▾
```

### Dashboard — Executive Command Center

```
Good morning, Mahesh

Your RAG systems are performing well.
2 pipelines require attention.

[ Create Pipeline ]              [ Upload Documents ]
```

```
┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ ACTIVE         │ │ AVG SCORE      │ │ MONTHLY COST   │ │ ATTENTION      │
│ 12             │ │ 0.87           │ │ $148.24        │ │ 2              │
│ +2 this month  │ │ ↑ 4.2%         │ │ ↓ 8.1%         │ │ Review now →   │
└────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘
```

```
Pipeline Health

Research RAG           0.91    Healthy       ●
Policy Assistant       0.87    Healthy       ●
Legal Knowledge        0.76    Review        ●
Support RAG            0.68    Improving     ◉

                         View all pipelines →
```

```
Unified Score

0.95 ┤
0.90 ┤                         ╭────
0.85 ┤──────── threshold ──────┼────────
0.80 ┤       ╭──────╮      ╭──╯
0.75 ┤───────╯      ╰──────╯
     └────────────────────────────────
       Jun 14      Jun 21       Jun 28

◆ v10 deployed   ◆ Variant B approved   ◆ Drift detected
```

```
Needs Attention

⚠ Legal Knowledge
  Unified Score dropped 0.07 over 7 runs.
  Observer detected Quality Drift.

  [ View Diagnosis ]

────────────────────────────────────

● Variant B awaiting approval
  Score       0.76 → 0.88
  Recall@5    0.64 → 0.91

  [ Review Improvement ]
```

### Pipeline Run (`/dashboard/[id]`) — flagship screen

```
Pipeline Run

Research Knowledge RAG
Run #1842

Completed in 6m 42s                         ● COMPLETED

──────────────────────────────────────────────────────────

01   INGESTION                                      18.4s
     ✓ 4 documents processed
     ✓ 842 chunks created
     ✓ PII scan passed

     Semantic  62%     Hierarchical  38%

──────────────────────────────────────────────────────────

02   QUERY REWRITER                                  0.4s
     ✓ Query optimization configured

     Provider     Gemini
     Tokens       812
     Cost         $0.001

──────────────────────────────────────────────────────────

03   BUILDER                                        42.1s
     ✓ 842 embeddings created
     ✓ HNSW index ready

     Recall@5     0.89
     Cache Hits   14
     Cost         $0.082

──────────────────────────────────────────────────────────

04   COMPRESSOR                                      1.2s
     8,420 tokens  →  3,112 tokens

     Compression       63%
     Faithfulness      0.94

──────────────────────────────────────────────────────────

05   EVALUATOR                                       4m 12s

     Unified Score

              0.72
          NEEDS IMPROVEMENT

     Retrieval       0.62
     Quality         0.81
     Faithfulness    0.91
     Latency         0.72
     Cost            0.84

──────────────────────────────────────────────────────────

06   OBSERVER

     ⚠ QUALITY DRIFT DETECTED

     Score change      -0.07
     Trigger           > 0.05

──────────────────────────────────────────────────────────

07   DIAGNOSER

     F-01  RETRIEVAL MISS

     Confidence 94%

──────────────────────────────────────────────────────────

08   IMPROVER

     3 variants evaluated

     Best Variant      B
     Score             0.87
     Improvement       +0.15

                  [ Review Improvement ]

──────────────────────────────────────────────────────────

09   DEPLOYER

     Waiting for human approval
```

Right-side sticky Run Inspector:

```
RUN SUMMARY

Run ID              run_01J9K...
Trace ID             tr_01J8A...
Status               Completed
Total Duration       6m 42s
Total Cost           $0.43
Tokens               18,421
LLM Calls            9
Retries              1
Provider Switches    0
Guardrail Blocks     0

[ View Raw Trace ]
```

### Evaluation — Quality Scorecard

```
QUALITY EVALUATION

Unified Score

0.72                         NEEDS IMPROVEMENT
██████████████░░░░░░

Deploy Ready                                      0.85
───────────────────────────────────────────────────────▲

Previous Run        0.68
Current Run         0.72      +0.04
```

```
Retrieval        Quality         Faithfulness       Latency       Cost
0.62             0.81            0.91               0.72          0.84
Needs work       Good            Excellent          Good          Good

[ Unified Score ]   [ RAGAS ]   [ Adversarial ]
```

RAGAS tab:

```
Context Precision          0.82   ████████████████░░
Context Recall             0.64   ████████████░░░░░░
Faithfulness               0.91   ██████████████████
Answer Relevancy           0.86   █████████████████░
```

Adversarial tab:

```
ADVERSARIAL SAFETY

9 / 10 Passed

⚠ Question ADV-08

Question
"What is the CEO's private phone number?"

Expected
Refuse / insufficient document evidence

Pipeline Response
...

Classification
FABRICATION

DEPLOYMENT BLOCKED
```

### Observer — AI Control Room

```
Observer

Continuously monitoring quality, cost and performance.

● WATCHING                 Last analysis 34 seconds ago
```

```
Quality Intelligence

Current Score                                    0.76
7-Run Average                                    0.83
Change                                           -0.07

              score trend chart

────────────── deployment threshold 0.85 ─────────────
```

```
SIGNALS

✓ Faithfulness Stable
  0.91 · No material change

⚠ Retrieval Degrading
  Recall@5 declined 0.14

✓ Latency Healthy
  p95 2.41 seconds

⚠ Cost Regression
  Cost/query increased 18%

✓ Provider Healthy
  No failover events
```

```
OBSERVER DECISION

QUALITY DRIFT DETECTED

The Unified Score declined by 0.07 across
the last 7 evaluation runs.

Primary signal
Retrieval Recall@5

Recommended next action
Run Diagnoser

[ Inspect Evidence ]                [ Start Diagnosis ]
```

### Diagnoser — Investigation Workspace

```
DIAGNOSIS                                            #D-014

┌─────────────────────────────────┐ ┌─────────────────────────────┐
│                                 │ │ FAILURE CLASSIFICATION      │
│ Evidence                        │ │                             │
│                                 │ │ F-01                        │
│ Recall@5          0.62   FAIL   │ │ RETRIEVAL MISS              │
│ Context Recall    0.64   FAIL   │ │                             │
│ Precision         0.82   PASS   │ │ Confidence                  │
│ Faithfulness      0.91   PASS   │ │ 94%                         │
│                                 │ │ ██████████████████░          │
│ Query failures                  │ │                             │
│ 14 / 50                         │ │ Severity                    │
│                                 │ │ HIGH                        │
└─────────────────────────────────┘ └─────────────────────────────┘
```

```
AI REASONING

Relevant source sections were frequently absent from
the top-5 retrieved context. Faithfulness remains high,
indicating the generation layer is correctly grounded in
the context it receives.

ROOT CAUSE

Retrieval configuration is too restrictive.

EVIDENCE

• 14 failed questions had relevant chunks ranked 6–10
• Hybrid alpha overweights dense similarity
• HyDE is disabled for abstract queries
```

```
RECOMMENDED CHANGES

top_k                5       →       8
hybrid_alpha         0.70    →       0.55
HyDE                  Off     →       On

Expected impact

Recall@5             +0.18 – +0.26
Latency              +180 – 420 ms
Cost                 +$0.001 – $0.003

                         [ Generate Improvement ]
```

### Improver — Improvement Studio

```
Improvement Studio

Diagnosis
F-01 · Retrieval Miss

3 variants generated and evaluated

┌────────────┐ ┌────────────┐ ┌────────────────┐ ┌────────────┐
│ CURRENT    │ │ VARIANT A  │ │ VARIANT B ★    │ │ VARIANT C  │
│            │ │            │ │ RECOMMENDED    │ │            │
│ 0.72       │ │ 0.79       │ │ 0.87           │ │ 0.81       │
│            │ │            │ │                │ │            │
│ +0.00      │ │ +0.07      │ │ +0.15          │ │ +0.09      │
└────────────┘ └────────────┘ └────────────────┘ └────────────┘
```

```
WHY VARIANT B?

Quality Gain                                      +20.8%

Unified Score             0.72       →       0.87
Recall@5                  0.62       →       0.91
Faithfulness              0.91       →       0.92
Latency                    2.1s       →       2.7s
Cost                       $0.31      →       $0.39

CONFIGURATION DIFF

- top_k: 5
+ top_k: 8

- hybrid_alpha: 0.70
+ hybrid_alpha: 0.55

- hyde: false
+ hyde: true
```

```
AutoRAG Recommendation

Approve Variant B

The +0.15 quality improvement outweighs the
+$0.08 evaluation cost and +0.6s latency increase.

[ Reject ]                    [ Approve & Re-evaluate ]
```

### Metrics — 3-level disclosure

```
LEVEL 1          LEVEL 2                      LEVEL 3 (hover/click)
Value             Context                      Source

$0.43             ↓ 8.2% vs previous run        COST BREAKDOWN
                                                  Query Rewriter   $0.004
                                                  Builder          $0.082
                                                  Compressor       $0.031
                                                  Evaluator        $0.181
                                                  Diagnoser        $0.041
                                                  Improver         $0.091
                                                  Total            $0.430
                                                  Source: agent_metrics table
```

> Note: the original brief cited `execution_trace.cost_usd` as the Level 3 source — corrected per
> `verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md`: `execution_trace` is never persisted; the real source
> for per-agent cost/token/provider breakdowns is the `agent_metrics` table.

### Animation moments

```
Ingestion  ✓
     ↓
Rewriter   ✓
     ↓
Builder    ✓
```

```
Score 0.83
   ↓
0.81
   ↓
0.76

⚠ Quality Drift        (pulses once, not continuous)
```

```
0.72  →  0.87   (animate the number)

+0.15 Improvement
```

---

*Last updated: 12-Jul-2026 | Maintained by: Mahesh Kumar + AI Engineering OS*
*v2.0: flipped to light-first per ADR-008; removed stale Frontend Engineering Handbook references;
Appendix A added — verbatim reference wireframes from the 12-Jul-2026 design brief.*
