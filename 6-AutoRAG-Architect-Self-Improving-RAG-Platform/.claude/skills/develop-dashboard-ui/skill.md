# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Skill: Develop Dashboard & Configurator UI

## Purpose

Build the **Next.js 15** frontend for the AutoRAG platform, following the **light-first design system (Rule 25, ADR-008)** and implementing the visual requirements for the Configurator Wizard and Agent Monitoring.

> ⚠️ CORRECTED 20-Jul-2026: this skill previously mandated a "Glassmorphism Design
> System" with `backdrop-blur-md` surfaces. That predates ADR-008 (12-Jul-2026), which
> flipped the platform to light-first — `docs/frontend_design.md` §5 explicitly states
> "No glassmorphism/backdrop-blur in the light theme — flat white surfaces with a
> hairline border and a soft `shadow-sm`." Read `docs/frontend_design.md` before
> building any component; it is the authoritative SOT, not this skill.

## 📐 Functional UI Requirements (Internal Reference)

_Note: Visual mockups are proprietary. Refer to the Architecture DOCX for visual guidance._

### 1. Data Source Configurator

- **Requirement**: A grid-based selection interface for data ingestion.
- **Connectors**:
  - File Upload (PDF, DOCX, TXT)
  - Cloud Storage (Supabase Storage)
  - Web (URL crawling)
  - Structured (Database, HTTP API)

### 2. Query Processing Wizard

- **Requirement**: A configuration panel for the Query Rewriter Agent.
- **Techniques to Implement**:
  - Query Rewriting (Semantic paraphrase)
  - HyDE (Hypothetical document embeddings)
  - Multi-query expansion (Sentence-based splitting)
  - Query decomposition (Sub-query emission)
  - Step-back prompting (Abstraction queries)
  - Entity/Intent extraction & Keyword augmentation.

### 3. The 9-Agent Pipeline Visualizer

- **Requirement**: A vertical execution journey tracking the real 9-agent loop (see
  `docs/frontend_design.md` §10.2) — not a node-link diagram, one row per agent in order.
- **Execution Flow** (matches CLAUDE.md's 9-Agent Loop and `app/core/workflow.py`):
  Ingestion -> Query Rewriter -> Builder -> Compressor -> Evaluator -> Observer ->
  Diagnoser -> Improver -> Deployer.
- **Feedback**: Real status/duration/output summary per row (Pending/Running/Complete/Failed)
  from the real `node_trace` data — no fabricated progress percentage mid-run.

### 4. Use-Case Template Library

- **Requirement**: A selection of pre-configured pipeline archetypes.
- **Templates**:
  - **FAQ Chatbot**: Beginner-level, cost-optimized.
  - **Documentation Q&A**: Intermediate, high-accuracy (Hybrid + Rerank).
  - **Code Assistant**: Intermediate, code-aware chunking (model-agnostic).

---

## 🛠️ Implementation Rules

1. **Rule 25 Compliance**: Light-first flat surfaces (`bg-white`, hairline `border-[#eedac7]` (ADR-010 earth-tone), `shadow-sm`) — no backdrop-blur or gradients in the default theme; see `docs/frontend_design.md` §5.
2. **Real-time Updates**: Use WebSockets or Server-Sent Events (SSE) to update the 9-agent execution journey as agents progress.
3. **Stateless UI**: Ensure the frontend reflects the `GraphState` provided by the LangGraph backend.
4. **Consistency**: Icons and terminology must match the 9-agent roster defined in `CLAUDE.md`.

---

## 🚦 Verification Gate

- [ ] Execution journey rows match the 9-agent backend flow perfectly.
- [ ] Light-first flat-surface aesthetic (`docs/frontend_design.md` §5) is applied to all cards and modals.
- [ ] Template selection correctly updates the pipeline configuration state.

---

**Primary Owner**: Team 9 (Dashboard & Integration)
**Support**: Team 1 (Design Standards)
