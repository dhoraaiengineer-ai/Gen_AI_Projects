# ADR-009: Frontend Theme — Dark-First (Reversal of ADR-008)

**Status**: **Not accepted** (verified 20-Jul-2026 deep audit) — `.claude/rules/25-frontend-ui-design.md`
still documents light-first (ADR-008) as the active platform default, with only `/login`'s
pre-existing dark/animated treatment kept as a documented exception. This ADR's broader
proposal below (flip the whole platform back to dark, end the `/login` exception) was
never carried into the governing rule file and was not implemented platform-wide. | **Date**: 18-Jul-2026
**Proposer**: Session AI (design review requested by Mahesh Kumar)
**Deciders**: Project Lead (Mahesh Kumar) — no sign-off recorded
**Affects**: Frontend design system — `.claude/docs/frontend_design.md`, `.claude/rules/25-frontend-ui-design.md`, `autorag-client/tailwind.config.ts`, all `autorag-client/` components, `project_docs/3_PRD/AutoRAG_PRD_v3_0.md` §15.2, `project_docs/5_HLD/AutoRAG-HLD-v3_0.md` Key Design Standards

> **This ADR is a draft pending explicit approval from Mahesh Kumar.** ADR-008 was decided at
> that authority level six days prior (12-Jul-2026); reversing it requires the same
> sign-off, not a unilateral doc edit. Do not treat this file's presence as the decision
> itself.

---

## Context

ADR-008 flipped the platform default from dark-first to light-first, on the grounds that
a dark "AI ops command center" aesthetic "reads as generic — indistinguishable from any
Grafana/Datadog-style tool," and that a light, evidence-driven UI better matched
AutoRAG's real differentiator: a self-improving closed loop made legible through
functional color-per-stage (§2/§11 of `frontend_design.md`).

During this session, an external modern-SaaS reference site was reviewed in detail
(hero anatomy, glass card component, KPI stat tiles, section-heading pattern, button
system, navigation, footer, spacing/radius rhythm). Its structural design quality —
independent of its own literal color choices — was judged strong enough to justify
revisiting the theme decision, rather than only adding it as an opt-in dark enhancement
under the existing light-first default.

**Directly addressing ADR-008's original rationale**: the "reads as generic" concern was
about a *monochrome* dark aesthetic with no functional signal — not about darkness
itself. The reference reviewed here is a glass-card, soft-shadow, generously-spaced
dark/light-capable system, not a flat monochrome dashboard. This ADR's position is that
the product's real differentiator — functional color-per-loop-stage (Blue/Indigo/Cyan/
Amber/Violet/Emerald/Coral) — is preserved by carrying those exact hues onto a dark
canvas as the accent system, so the loop stays legible through color exactly as ADR-008
intended; only the canvas/surface treatment reverts to dark.

## Decision

**Flip the platform default back to dark-first.** The mechanism is unchanged
(`darkMode: 'class'` in `tailwind.config.ts`); only which token set is the default vs.
the opt-in swaps back, mirroring exactly what ADR-008 did in the other direction.

```
Canvas (default)         radial-gradient(circle at 25% 18%, #172554 0%, #0f172a 28%,
                                          #020617 60%, #000814 100%)
Card surface (default)   rgba(12,18,35,0.72), backdrop-filter: blur(40px)  -- "Glass Card"
Primary text (default)   #FFFFFF
Secondary text (default) #E2E8F0
Border (default)         rgba(255,255,255,0.06)

Functional stage colors (unchanged assignments, re-tuned for dark contrast):
                          Blue (Build) / Indigo (Evaluate) / Cyan (Observe) /
                          Amber (Diagnose) / Violet (Improve) / Emerald (Deploy) /
                          Coral (Failure/hard block)
```

Full token set, expanded component patterns (Glass Card, Section Heading, dark-tuned KPI
tile, footer, floating AI Assistant/Docs/Support cluster), and per-screen layout specs:
`.claude/docs/frontend_design.md` v3.0.

**`/login` stops being a documented exception.** ADR-008 carved the login screen out of
the light flip because it was already dark and independent of that decision. Under this
reversal, dark is the platform default again, so login simply matches the rest of the
product rather than standing apart from it — its existing AgentLoop/Aurora/FloatingOrbs/
ParticleNetwork treatment is reused as-is, not rebuilt, and now seeds the wider dark
palette instead of being an island.

**Brand accent unaffected.** `text-orange-500`/`font-bold` for the "AutoRAG Architect"
wordmark stays exactly as-is (`coding-standards.md` Rule 25 brand block) — legible on
both light and dark surfaces, not part of either theme decision.

**Functional loop-stage color *assignments* are unchanged.** Only their dark-surface
tuning (contrast/saturation) changes — which agent maps to which hue (§11) is untouched
by this ADR.

## Rationale

- ADR-008's actual objection was to a *generic, monochrome* dark aesthetic, not darkness
  itself. A dark canvas with glass-card surfaces, soft shadow depth, and the existing
  functional color system as accents is a different design proposition than the
  alternative ADR-008 rejected — the loop-stage color signal ADR-008 wanted to protect is
  fully preserved here, just rendered on dark instead of light.
- The login screen's dark treatment was always the product's strongest existing visual
  moment (per ADR-008's own admission — "the fully-built dark login experience... real,
  tested work"). Reverting the rest of the product to match it, rather than keeping it as
  a permanent island, is more consistent than the light-first split ever was.
- A premium dark enterprise aesthetic is a well-established, credible pattern for AI
  engineering platforms specifically (distinct from the "any Grafana/Datadog tool" concern
  ADR-008 raised) when it's built on genuine structural quality — glass cards, generous
  spacing, real component hierarchy — rather than a flat dark background alone, which is
  what the reviewed reference demonstrates and what this ADR asks the team to emulate.

## Consequences

- `frontend_design.md` bumps to v3.0; the light token set from v2.0 §2 is preserved as
  the opt-in set (mirroring how v2.0 preserved the pre-existing dark set in §14) — no
  design work from the light-first period is discarded, only demoted to opt-in.
- Rule 25's guardrail #2 flips back to dark-first; cross-references this ADR the same way
  it currently cross-references ADR-008.
- `project_docs/3_PRD/AutoRAG_PRD_v3_0.md` §15.2 and `project_docs/5_HLD/AutoRAG-HLD-v3_0.md`
  "Key Design Standards" — updated again to match, same discipline ADR-008 required of
  itself, so the project_docs set doesn't silently cite stale tokens a second time.
- All future component work in `autorag-client/` implements dark Tailwind classes as the
  default, with `light:`-equivalent overrides added per `frontend_design.md`'s updated
  §14/§2 swap — the reverse of what ADR-008 specified, using the same `darkMode: 'class'`
  mechanism.
- **No components are retroactively rewritten by this ADR alone.** Existing light-styled
  components built during the light-first period are migrated as part of a separate,
  explicitly scoped execution effort once this ADR is approved — not as a side effect of
  the decision record itself, matching ADR-008's own stated scoping discipline.
- New reusable patterns introduced alongside this flip (Glass Card as a formal component,
  Section Heading pattern, footer, floating AI Assistant/Docs/Support cluster) are
  additive to the design system regardless of theme direction and remain if this ADR is
  ever reversed again.
