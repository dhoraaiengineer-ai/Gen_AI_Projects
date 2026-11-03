# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Frontend Design Guide — AutoRAG Architect v3.0

UI/UX standards for the AutoRAG Architect dashboard and configurator. All frontend work must follow these rules.

**Standards:** `.claude/rules/20-frontend-nextjs.md` · `.claude/rules/25-frontend-ui-design.md`

---

## Stack (mandatory)

```
Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui
```

```bash
# Setup for any new frontend component
npx shadcn@latest add button card input dialog sheet sidebar badge
npm install lucide-react
```

---

## Colour System

⚠️ CORRECTED 16-Jul-2026: this section previously mandated a dark-first
"Dark + Purple" palette (`#0A0A0A` background, `#7C3AED` accent). That was
superseded by **ADR-008 (12-Jul-2026)** — the platform is now **light-first**.
Dark mode remains supported as an opt-in, not the default; `/login` is the one
documented dark-mode exception.

⚠️ CORRECTED AGAIN 24-Jul-2026: the indigo-based light tokens this section
listed after the first correction (`#F6F8FC` canvas, `#5B5CE2` accent) were
themselves superseded by **ADR-010** — a 5-color earth-tone palette. Table
below updated to match.

The authoritative token set lives in **[`.claude/docs/frontend_design.md`](../docs/frontend_design.md)**
— read it before building any component. Summary:

| Role              | Hex       | Usage                    |
| ----------------- | --------- | ------------------------ |
| Canvas            | `#fffdf3` | Page background          |
| Card surface      | `#fefbf5` | Cards, panels             |
| Secondary surface | `#f6f8ea` | Nested/alt surfaces      |
| Border            | `#eedac7` | Card borders, dividers   |
| Primary text      | `#2d331a` | Headings, labels         |
| Secondary text    | `#64411f` | Descriptions, captions   |
| Primary accent    | `#c58341` | Buttons, active states   |

Success/Warning/Danger stay `emerald-500` / `amber-500` / `red-500` per the score
thresholds below. Functional stage colors (Build/Evaluate/Observe/Diagnose/
Improve/Deploy) are defined in `frontend_design.md` §11 — do not invent new ones.

---

## Typography

**Font stack:** Inter (body) — load via `next/font/google`

```tsx
import { Inter } from 'next/font/google';
const inter = Inter({ subsets: ['latin'] });
```

| Element          | Size | Weight   | Class                    |
| ---------------- | ---- | -------- | ------------------------ |
| Page title       | 30px | Bold     | `text-3xl font-bold`     |
| Section header   | 24px | Semibold | `text-2xl font-semibold` |
| Card title       | 20px | Semibold | `text-xl font-semibold`  |
| Body text        | 16px | Normal   | `text-base`              |
| Secondary text   | 14px | Normal   | `text-sm text-gray-400`  |
| Caption / label  | 12px | Medium   | `text-xs font-medium`    |
| Code / monospace | 14px | Normal   | `font-mono text-sm`      |

---

## Spacing

Always use Tailwind scale — never arbitrary values:

```
p-1 (4px)   p-2 (8px)   p-3 (12px)  p-4 (16px)
p-6 (24px)  p-8 (32px)  p-10 (40px) p-12 (48px)
gap-2       gap-4       gap-6       gap-8
```

---

## AutoRAG Dashboard Components

⚠️ The code snippets below still use pre-ADR-008 dark surface classes
(`bg-gray-900`, `border-gray-800`, etc. — carried over from before the
12-Jul-2026 light-first flip). The score-threshold colors (emerald/amber/red)
and structural pattern are still correct; swap the surface/border/text classes
for the light tokens in `frontend_design.md` §5 (Surface & Card Patterns)
before using these as a starting point.

### Score Display Card

```tsx
// Unified Score — color coded by threshold
function UnifiedScoreCard({ score }: { score: number }) {
  const color =
    score >= 0.85
      ? 'text-emerald-500' // deploy eligible
      : score >= 0.7
        ? 'text-amber-500' // improve needed
        : 'text-red-500'; // hard block

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
      <p className="text-sm text-gray-400">Unified Score</p>
      <p className={`text-4xl font-bold mt-1 ${color}`}>{score.toFixed(3)}</p>
      <p className="text-xs text-gray-500 mt-1">
        {score >= 0.85 ? 'Deploy Eligible' : score >= 0.7 ? 'Improve' : 'Blocked'}
      </p>
    </div>
  );
}
```

### Agent Status Node

```tsx
// Shows current agent in the 9-agent loop
function AgentNode({
  name,
  status,
}: {
  name: string;
  status: 'idle' | 'running' | 'done' | 'error';
}) {
  const colors = {
    idle: 'border-gray-700 text-gray-400',
    running: 'border-violet-500 text-violet-400 animate-pulse',
    done: 'border-emerald-500 text-emerald-400',
    error: 'border-red-500 text-red-400',
  };
  return (
    <div className={`border rounded-xl px-4 py-2 text-sm font-medium ${colors[status]}`}>
      {name}
    </div>
  );
}
```

### Approval Badge

```tsx
function ApprovalBadge({ tier }: { tier: 'auto' | 'human_in_loop' | 'mandatory_gate' }) {
  const config = {
    auto: { label: 'Auto-Approve', color: 'bg-emerald-900 text-emerald-300' },
    human_in_loop: { label: 'Human-in-Loop', color: 'bg-amber-900 text-amber-300' },
    mandatory_gate: { label: 'Mandatory Gate', color: 'bg-red-900 text-red-300' },
  };
  const { label, color } = config[tier];
  return <span className={`px-2 py-1 rounded-md text-xs font-medium ${color}`}>{label}</span>;
}
```

---

## Key Screens

### 1. Configurator Wizard

- 6-step form (one question per screen)
- Progress indicator at top
- Back / Next navigation
- Final step shows YAML preview before submitting
- POST to `/api/v1/configurator`

### 2. Pipeline Dashboard

- List of pipelines with status badge (draft / active / archived)
- Unified Score trend sparkline per pipeline
- Quick action buttons: Evaluate · Improve · Deploy

### 3. Score & Evaluation Dashboard

- 3 panels: Unified Score · RAGAS metrics · Adversarial result
- Color-coded pass/improve/block status per metric
- Judge reasoning expandable text (from Gemini Flash 3.5 CoT)

### 4. Approval Queue

- Table of pending experiments
- Approval tier badge (Auto / HITL / Mandatory Gate)
- Score delta column (vs baseline)
- Approve / Reject buttons for HITL and Mandatory Gate items

### 5. Experiment Tracking View

- List of all variants from Improver Agent
- MLflow run ID, score delta, hyperparameter diff
- Status: pending / approved / rejected / deployed

### 6. Audit Log Viewer

- Paginated table of audit events (INSERT-ONLY, read-only view)
- Filter by event_type, resource_id, date range
- Trace ID column � links to Grafana trace

---

## Responsive Design

Mobile-first. Use Tailwind breakpoints:

```tsx
// Stack on mobile, grid on desktop
<div className="flex flex-col md:flex-row gap-6">

// Full width mobile, 1/3 desktop
<div className="w-full md:w-1/3">

// Responsive text
<h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold">

// Page container — never wider than 1280px
<div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
```

---

## Animations

Subtle only — fade-in on scroll, hover glow. No jarring transitions.

```tsx
// Fade-in on scroll
function useFadeIn() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setVisible(true),
      { threshold: 0.1 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return {
    ref,
    className: `transition-all duration-700 ${
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
    }`,
  };
}

// Glow on hover (for score cards)
<div className="relative group">
  <div className="absolute -inset-0.5 bg-gradient-to-r from-violet-600 to-blue-600 rounded-2xl blur opacity-0 group-hover:opacity-50 transition duration-500" />
  <div className="relative bg-gray-900 rounded-2xl p-6">{/* card content */}</div>
</div>;
```

---

## Performance Checklist

- [ ] Images use `next/image` with `width`, `height`, `priority` for above-fold
- [ ] Fonts loaded via `next/font` — no layout shift
- [ ] `"use client"` only on components that use state, effects, or events
- [ ] Below-fold sections lazy-loaded with `dynamic(() => import(...))`
- [ ] No hardcoded API URLs — use `process.env.NEXT_PUBLIC_API_URL`
- [ ] Loading skeletons shown while data fetches — not spinners
- [ ] Error boundaries wrap every async UI section

---

## Rules for AI Assistants (enforce these)

1. Light theme by default (ADR-008, earth-tone tokens per ADR-010) — canvas `#fffdf3`, card `#fefbf5`; dark mode is opt-in only (`/login` excepted)
2. Mobile-first — build for phone, scale up with `md:` and `lg:`
3. Tailwind classes only — never inline styles
4. Spacing: always Tailwind scale — never arbitrary values like `p-[13px]`
5. Icons: Lucide React only (`import { CheckCircle } from 'lucide-react'`)
6. Never hardcode API URLs or keys in components
7. TypeScript everywhere — no `any` at component boundaries
8. Score colors: emerald = pass (≥0.85), amber = improve (0.70–0.84), red = block (<0.70)
9. Sidebar navigation: absolute positioning for icons — flex gap breaks alignment
10. `"use client"` only when the component uses state, effects, or event handlers

