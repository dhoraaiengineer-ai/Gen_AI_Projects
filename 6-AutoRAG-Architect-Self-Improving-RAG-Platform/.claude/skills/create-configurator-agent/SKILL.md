# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Configurator Wizard Skill

## Purpose

Build the 6-step UI wizard (`/api/v1/configurator`) that translates user requirements into a system configuration. (Note: Configurator is NOT part of the 9-agent LangGraph loop.)

## The Core Questions

> **Note (24-Jul-2026 audit)**: this section lists 5 questions while the wizard is
> documented elsewhere (this file's own title, API_SPEC.md's `POST /configurator`,
> CLAUDE.md) as a 6-step flow -- e.g. document upload (step 2 per
> `docs/roadmap/VERSION_5_ROADMAP.md` SS2) isn't captured as one of the 5 below. Treat
> this list as the scoring/config-relevant questions, not the complete step sequence;
> verify the real step count against `autorag-client/app/configurator/` before building.

1. **Domain**: (Legal/Medical/General) -> Sets `scoring_profile`.
2. **End Users**: (Expert/Consumer) -> Sets `answer_style`.
3. **Primary Concern**: (Faithfulness/Speed/Cost) -> Sets `scoring_weights`.
4. **Improvement Mode**: (Auto/HITL) -> Sets `approval_mode`.
5. **Deployment Target**: (Local/Cloud) -> Sets `inference_mode`.

## Output

A validated YAML file stored in the `pipelines` table.

## Anti-Patterns

- **Invalid YAML**: Generating configurations that fail Pydantic validation.
- **Vague Prompts**: Not providing enough instructions for the `system_prompt_template`.
