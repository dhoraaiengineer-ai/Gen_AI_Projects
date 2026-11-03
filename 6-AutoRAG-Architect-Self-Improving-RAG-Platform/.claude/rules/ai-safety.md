# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

---

paths:

- autorag-server/app/ai/\*\*
- autorag-server/app/rag/generation.py

---

# AI Safety and Prompt Standards

## 1. 3-Layer Evaluation Stack

All pipeline runs must traverse the full evaluation chain:

1.  **Unified Score**: Primary deployment gate (`0.25R + 0.35Q + 0.25F - 0.10L - 0.05C`).
2.  **RAGAS Layer**: Component-level diagnostics (Context Precision, Recall, Relevancy).
3.  **Adversarial Q&A**: 10 unanswerable questions to test hallucination resistance.

## 2. Hard Safety Rules

- **Faithfulness Gate**: `Faithfulness < 0.5` blocks deployment (non-bypassable).
- **Adversarial Block**: Any fabricated answer to an unanswerable question = **Hallucination failure**.
- **Model Governance**: Upgrades (models/embeddings) are strictly **Mandatory Gate** changes.
- **Local Mode**: If `inference_mode: local`, all cloud LLM suggestions are hard-blocked.

## 3. Prompt Management

- **Versioning**: Mandatory `vX.Y.Z` tagging.
- **Separation**: No hardcoded prompts; use Jinja2 templates in `/prompts`.
- **Negative Constraints**: Every prompt must include: "Do not invent facts if the context is empty."
- **Masking**: PII stripping via Custom PII Detection & Masking Functions before LLM dispatch.
