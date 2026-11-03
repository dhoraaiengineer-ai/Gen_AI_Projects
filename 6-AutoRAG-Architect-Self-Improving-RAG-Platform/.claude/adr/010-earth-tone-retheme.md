# ADR-010: Frontend Theme — Earth-Tone Palette (Implements ADR-008, Closes ADR-009)

**Status**: Accepted — Mahesh Kumar (session authorization), 24-Jul-2026 | **Date**: 24-Jul-2026
**Proposer**: Session AI (user-supplied palette)
**Deciders**: Mahesh Kumar
**Affects**: Frontend design system — `.claude/docs/frontend_design.md`, `.claude/rules/25-frontend-ui-design.md`, `autorag-client/app/globals.css`, `autorag-client/tailwind.config.ts`, all `autorag-client/` components, new `autorag-client/components/theme/` (ThemeProvider, ThemeToggle)

---

## Context

The user supplied a 5-color earth-tone palette (tea_green, beige, cornsilk, papaya_whip,
light_bronze) and requested a full site re-theme. Investigation before implementing found a real
code/documentation drift:

- **ADR-008** (12-Jul-2026, accepted) mandates light-first as the platform default — this remains
  the only accepted theme decision on record.
- **ADR-009** (18-Jul-2026, drafted) proposed reversing ADR-008 back to dark-first. ADR-009's own
  header states plainly: *"Not accepted... never carried into the governing rule file."* It was
  never signed off.
- Despite that, `autorag-client/app/globals.css` and `tailwind.config.ts` had **unilaterally
  implemented ADR-009's unaccepted proposal** — every CSS custom property, every shared class
  (`.panel-card`, `.kpi-tile`, `.d2-hero`, etc.), and the shadcn/ui alias tokens were hardcoded to
  dark values, while `.claude/docs/frontend_design.md` and `.claude/rules/25-frontend-ui-design.md`
  continued to correctly document light-first as governing. ~117 of 217 `autorag-client` component
  files additionally hardcoded dark hex literals directly in JSX (both Tailwind arbitrary-value
  classes and inline `React.CSSProperties` objects), bypassing the token system entirely.

This ADR is therefore a **conformance fix implementing ADR-008**, not a new design direction: it
brings the code back in line with the only decision that was ever actually accepted, using the
user's earth-tone palette as the concrete token values ADR-008 needed but never fully got (ADR-008
shipped with an indigo-based palette that itself was significantly reverted before this ADR).

## Decision

1. **Adopt the 5-color earth-tone palette** as the platform's token source, replacing the prior
   indigo-based light tokens from ADR-008 and the dark hex ADR-009 had unilaterally introduced:

```js
{
  tea_green:    { DEFAULT: '#ccd5ae', 100: '#2d331a', 200: '#5b6635', 300: '#88994f', 400: '#acbb7b', 500: '#ccd5ae', 600: '#d6debe', 700: '#e1e6cf', 800: '#ebeedf', 900: '#f5f7ef' },
  beige:        { DEFAULT: '#e9edc9', 100: '#3d4216', 200: '#79842c', 300: '#b3c146', 400: '#ced788', 500: '#e9edc9', 600: '#edf1d4', 700: '#f2f4df', 800: '#f6f8ea', 900: '#fbfbf4' },
  cornsilk:     { DEFAULT: '#fefae0', 100: '#5d5103', 200: '#baa206', 300: '#f8dc27', 400: '#fbeb84', 500: '#fefae0', 600: '#fefbe7', 700: '#fefced', 800: '#fffdf3', 900: '#fffef9' },
  papaya_whip:  { DEFAULT: '#faedcd', 100: '#533e08', 200: '#a57b10', 300: '#eab227', 400: '#f2d079', 500: '#faedcd', 600: '#fbf1d6', 700: '#fcf4e0', 800: '#fdf8eb', 900: '#fefbf5' },
  light_bronze: { DEFAULT: '#d4a373', 100: '#32210f', 200: '#64411f', 300: '#96622e', 400: '#c58341', 500: '#d4a373', 600: '#dcb68f', 700: '#e5c8ab', 800: '#eedac7', 900: '#f6ede3' },
}
```

   Note the scale is inverted from normal Tailwind convention (`500`/`DEFAULT` = saturated
   mid-tone, `900` = near-white, `100` = near-black) — deliberate, not a defect, per the source
   material supplied.

2. **Reaffirm ADR-008's structural decisions, unchanged**: light is the explicit default (not
   `prefers-color-scheme`-driven — `next-themes`' `enableSystem={false}`), dark is a real opt-in via
   `darkMode: "class"` (the mechanism ADR-008 specified and that was configured in
   `tailwind.config.ts` but never actually wired to a toggle until this ADR), and `/login` keeps its
   documented dark exception (`frontend_design.md` §16) untouched.

3. **Formally close ADR-009** as superseded/moot — it was never accepted, and this ADR's
   implementation of real light-first behavior makes its proposal irrelevant going forward. ADR-009
   itself is left as a historical record (not deleted, not rewritten) with this ADR as the pointer
   to what actually shipped.

4. **Implement a real theme toggle** for the first time — `next-themes`, `ThemeProvider` wrapping
   `app/layout.tsx`, `ThemeToggle` in `components/layout/DashboardTopbar.tsx` (rendered on every
   authenticated page). Token mechanism: CSS custom properties in `app/globals.css`, light values on
   `:root`, dark values in a `.dark { }` override block; shared classes and shadcn/ui aliases
   (`bg-card`, `text-foreground`, `border-border`, etc.) read the vars so both themes are served by
   one class definition each.

5. **Kept independent of the earth-tone palette**: functional status colors (success/warning/error/
   info — `#10B981`/`#F59E0B`/`#EF4444`/`#06B6D4`) and the 9-agent/6-stage loop colors
   (`frontend_design.md` §11) — these are semantic signals, not brand, and substituting earth hues
   would collapse `tea_green`/`beige`'s visual distinctiveness against each other. The Evaluator
   agent's stage color changed from Indigo (`#5B5CE2`, no longer a defined token) to Primary Bronze
   (`#c58341`), since Indigo was both the old primary brand accent and the Evaluate-stage color —
   Bronze now fills both roles, consistent with the prior 1:1 mapping.

### Token mapping (light default / dark opt-in)

| Role | Light | Dark |
|---|---|---|
| Canvas | `#fffdf3` (`cornsilk-800`) | `#32210f` (`light_bronze-100`) |
| Surface / card | `#fefbf5` (`papaya_whip-900`) | `#64411f` (`light_bronze-200`) |
| Border | `#eedac7` (`light_bronze-800`) | `rgba(255,255,255,0.08)` |
| Text primary | `#2d331a` (`tea_green-100`) | `#fffef9` (`cornsilk-900`) |
| Text secondary | `#64411f` (`light_bronze-200`) | `#fcf4e0` (`papaya_whip-700`) |
| Primary accent | `#c58341` (`light_bronze-400`) | `#acbb7b` (`tea_green-400`) |

**Dark canvas candidate selection**: two candidates were prototyped per this ADR's own verification
requirement — `light_bronze-100/200` (warm near-black) vs `tea_green-100/200` (olive near-black).
`light_bronze` was selected as the cleaner, less-muddy dark neutral; `tea_green`'s darkest tiers read
as murky olive rather than a legible dark surface.

## Consequences

- **Closes the code/doc drift this session's audit found**: `globals.css` and `tailwind.config.ts`
  now match `frontend_design.md` and `rules/25-frontend-ui-design.md` for the first time since
  ADR-009's draft caused them to diverge. Future ADR proposals to change the theme must go through
  the same accept/reject process ADR-009 skipped — a drafted-but-unaccepted ADR must never be
  unilaterally implemented in code again.
- **A real, working dark mode exists for the first time** — previously "dark mode" meant "the only
  mode," with no toggle and no light mode actually implemented despite `darkMode: "class"` being
  configured since at least ADR-008.
- Two large mechanical sweeps were required across `autorag-client` (Tailwind arbitrary-hex classes
  and inline `React.CSSProperties` objects) — future components must use the semantic token classes
  (`bg-card`, `text-foreground`, `border-border`, `text-text-2`/`text-text-3`, or the `tea_green`/
  `beige`/`cornsilk`/`papaya_whip`/`light_bronze` scale directly) rather than hardcoded hex, or this
  drift will recur.
- `/login` is unaffected — it renders no `ThemeToggle`, uses zero shared theme classes, and stays
  visually dark regardless of the platform default or toggle state, exactly as ADR-008 carved out.
