# Rule: documentation stays true

- `docs/01-PRD.md` is the source of truth for requirements; HLD, architecture, LLD, ADRs, presentation and
  narrative must stay aligned with it and with the code.
- Every capability is labelled: Implemented + tested offline / Verified live / Planned. Never upgrade a
  label without evidence (a test run or a live transcript).
- Never invent results, metrics, cost savings, integrations or deployments. Evaluation numbers are always
  "offline evaluation on a synthetic test set".
- When a design decision changes, update the relevant ADR (or add one) and the affected docs in the same change.
