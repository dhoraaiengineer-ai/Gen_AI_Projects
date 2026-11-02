# 20 — Frontend (React 18 + TypeScript + Vite + Tailwind)

**Purpose:** A safe, accessible, workshop-friendly UI that never overstates what the AI decided.

## MUST
- TypeScript `strict`. Zod schemas validate **every** API response before use (`src/api/schemas.ts`).
- TanStack Query for server state. React Router routes: `/login, /chat, /vehicles, /ro/:id, /advisor, /tech, /warranty, /warranty/:id, /admin`.
- Guard routes by role and hide actions the role cannot perform, **and** rely on the backend for enforcement.
- Render `<SafetyBanner>` (red, `role="alert"`) whenever a response has `safety_critical: true`. Its text comes from rules/55.
- Render `<AIAssessmentBanner>` ("AI-generated preliminary assessment — not a decision.") on every AI panel.
- Show citations as chips that open the source (file, page, section).
- Label DEMO integrations visibly ("DEMO — no real OEM submission").
- WCAG 2.1 AA: semantic HTML, labels, visible focus, contrast ≥ 4.5:1. `/tech` and `/advisor` are tablet-first; tap targets ≥ 48×48 px (gloves).
- Send an `Idempotency-Key` (uuid v4) on state-creating POSTs, and disable the button while pending.

## MUST NOT
- Compute money, hours, eligibility, or status client-side. Display what the API returned.
- Store JWTs in `localStorage`. Use in-memory storage, plus an httpOnly refresh cookie in prod.
- Render model output with `dangerouslySetInnerHTML`.
- Use the wording "approved by AI", "fraud", or "safe to drive".

## Good
```tsx
const data = ManualAnswerSchema.parse(await api.post("/chat/manual-question", body));
return (
  <>
    {data.safety_critical && <SafetyBanner />}
    <Answer text={data.answer} citations={data.citations} />
  </>
);
```

## Bad
```tsx
const total = lines.reduce((s, l) => s + l.hours * 95, 0); // client-side maths with a hard-coded rate
<div dangerouslySetInnerHTML={{ __html: llmAnswer }} />
```
