# ADR-008: Frontend Theme — Light-First (Flip from Dark-First)

**Status**: Accepted — Mahesh Kumar, 12-Jul-2026 | **Date**: 12-Jul-2026
**Proposer**: Mahesh Kumar
**Deciders**: Mahesh Kumar
**Affects**: Frontend design system — `.claude/docs/frontend_design.md`, `.claude/rules/25-frontend-ui-design.md`, `autorag-client/tailwind.config.ts`, all `autorag-client/` components

---

## Context

Rule 25 (`25-frontend-ui-design.md`) mandated a dark-first theme (`darkMode: 'class'`, dark as
default, light as opt-in) since the project's original design pass. During this session's frontend
MVP-scoping work, a new design concept — "AutoRAG Intelligence Control Center" — was proposed and
reviewed: a light, premium enterprise theme (canvas `#F6F8FC`, white cards, functional color-per-
closed-loop-stage) intended to make the product's real signal — Build → Evaluate → Observe →
Diagnose → Improve → Deploy — legible through color and layout, rather than through a dark
"AI ops" aesthetic.

Adopting this design as primary directly contradicts the existing dark-first rule. This ADR records
the decision so `CLAUDE.md`, `frontend_design.md`, and the project_docs set (PRD/HLD/LLD, all of
which cited the old dark-first `#030712`/`#7C3AED` tokens) don't silently drift apart the way the
now-removed phantom "Frontend Engineering Handbook" reference did earlier this session.

## Decision

**Flip the platform default to light-first.** Dark mode remains fully supported as an opt-in
(`darkMode: 'class'` stays; the *default* theme changes, not the mechanism).

```
Canvas              #F6F8FC
Card surface        #FFFFFF
Secondary surface   #F1F5F9
Primary text        #172033
Secondary text      #667085
Border              #E6EAF0

Primary accent (Indigo)      #5B5CE2
Functional stage colors:     Blue (Build) / Indigo (Evaluate) / Cyan (Observe) /
                              Amber (Diagnose) / Violet (Improve) / Emerald (Deploy) /
                              Coral (Failure/hard block)
```

Full token set, component patterns, and per-screen layout specs: `.claude/docs/frontend_design.md` v2.0.

**Exception — `/login` stays dark.** The existing login screen's premium animated dark treatment
(AgentLoop SVG, Aurora, FloatingOrbs, ParticleNetwork) is real, already implemented, and independent
of this decision — matches Rule 25's own "animated accents only on entry points" carve-out. It is not
flipped without a separate, explicit decision.

**Brand accent unaffected.** `text-orange-500`/`font-bold` for the "AutoRAG Architect" wordmark stays
exactly as-is (coding-standards.md Rule 25 brand block) — legible on both light and dark surfaces,
not part of this theme decision.

## Rationale

- The dark "AI ops command center" aesthetic (the alternative considered) reads as generic —
  indistinguishable from any Grafana/Datadog-style tool. A light, calm, evidence-driven UI better
  matches AutoRAG's actual differentiator: a self-improving loop with real metrics at every step, not
  a monitoring dashboard.
- Functional color-per-loop-stage (rather than one dominant purple) makes the closed loop legible
  through color alone across all screens — a stronger product signal than a uniform dark palette.
- Reusing the fully-built dark login experience (rather than rebuilding it light) avoids throwing away
  real, tested work for no product benefit — the login screen's job (make a strong first impression)
  is different from the workflow screens' job (make real data legible).

## Consequences

- `frontend_design.md` bumped to v2.0; §14 documents the dark-mode opt-in token set so it isn't lost.
- Rule 25's guardrail #2 flipped; cross-references this ADR.
- `project_docs/3_PRD/AutoRAG_PRD_v3_0.md` §15.2 and `project_docs/5_HLD/AutoRAG-HLD-v3_0.md`'s "Key
  Design Standards" section updated to match — both previously cited the old dark-first tokens
  directly, which would have immediately recreated a source-of-truth conflict if left unchanged.
- All future component work in `autorag-client/` implements light Tailwind classes as the default,
  with `dark:` variants added per `frontend_design.md` §14 — not the reverse.
- No components are retroactively rewritten by this ADR alone; existing dark-styled components (login,
  any already-built dashboard pages) are migrated as part of the separate MVP execution plan, not as
  a side effect of this decision record.
