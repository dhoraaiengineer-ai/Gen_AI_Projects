# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Adversarial Eval Skill

## Purpose

Implement the hard-gate for hallucination resistance using unanswerable questions.

## Requirements

- **The 10-Question Set**: Must use a curated set of 10 questions that have NO answer in the provided corpus.
- **Pass Condition**: The agent must explicitly state "I don't have enough information" for 100% of these questions.
- **Scoring Penalty**: Any fabricated answer results in a `Unified Score` deduction and an automatic `Hallucination` flag.

## Anti-Patterns

- **Guessing**: Allowing the LLM to use its internal training data to answer a question not in the corpus.
- **Soft-Blocking**: Treating a fabrication as a "warning" instead of a hard block.
