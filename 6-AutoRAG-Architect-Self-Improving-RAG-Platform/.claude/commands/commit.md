# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Commit Message Command

Generates a Conventional Commit message for the AutoRAG codebase.

## Instructions

1. **Safety Check**: Verify that the commit message contains **ZERO PII**, raw logs, or provider-specific keys.
2. **Analysis**: Run `git diff --staged` to identify changes in Agents, Infra, or UI.
3. **Format**: `type(scope): description`.
   - Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `ci`, `chore`.
   - Scopes: `agent`, `api`, `ui`, `infra`, `eval`, `security`.
4. **Context**: If the change impacts the **Unified Score**, mention the weight adjustment in the footer.
