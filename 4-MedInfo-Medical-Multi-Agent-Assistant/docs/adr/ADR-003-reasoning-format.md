# ADR-003 - Reasoning and output format

**Status:** Accepted (2026-10-14)

## Context
Medical answers must be checkable. Free-text "reasoning" from a model is not evidence, may contain PHI or
unsupported claims, and is hard to validate automatically.

## Decision
- **No exposed chain-of-thought.** Models are not asked to show their reasoning; hidden reasoning tokens
  (if a provider produces them) are neither stored nor logged. Reasoning models run with low effort.
- **Classifiers, re-ranker and judges return JSON only** (for example `{"emergency": ...}`,
  `{"scope": ...}`, `{"relevant": [...]}`, `{"faithful": ...}`), parsed defensively. Unparseable output
  counts as a failure: the rules result stands, or the answer is refused.
- **Answers** follow a fixed format: plain sentences, each ending with `[n]` citations; doses only as
  verbatim quotes; a final `LIMITATIONS:` line; or exactly `NOT_COVERED`.
- The "reasoning" a user sees is **evidence**: citations, source cards, version notes, limitations and the
  check results in the `safety` field, all produced or verified in code.
- **Process transparency without chain-of-thought** (added 2026-10-14): the agent trace
  (`safety.trace`, shown as "How this answer was produced") records, per agent, a code-generated outcome,
  short detail, status and duration. It contains decisions and counts only - never model reasoning,
  question, answer or passage text, or upload filenames. See [LLD 4.1.4](../04-LLD.md).

## Alternatives considered
- Show model reasoning to users: rejected, it looks authoritative and is unverifiable.
- Free-form JSON answers: rejected, brittle across providers.

## Consequences
Deterministic validation is possible (citation, number, drug-name and dose checks). Live testing showed
models sometimes write `LIMITATIONS:` inline or quote across sentences; the parser and sentence splitter
were made robust to both, with regression tests.
