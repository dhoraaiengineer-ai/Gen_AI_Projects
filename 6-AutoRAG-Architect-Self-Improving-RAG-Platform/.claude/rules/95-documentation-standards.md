# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 95: Documentation Standards (Saffronyx Elite v5.0)

All project documentation must adhere to the **Saffronyx Elite Design System** (codified in `prd_template.js`) to ensure a premium, authoritative brand identity.

## 1. Documentation Lifecycle (The 10-Stage Sequence)

Deliverables in `03-docs/` must follow this sequence:

| Folder              | Stage | Document              | Purpose                                         |
| :------------------ | :---- | :-------------------- | :---------------------------------------------- |
| **00-brd**          | S0    | Business Requirements | Strategic vision, ROI, and market goals.        |
| **01-product**      | S1    | Product Intake        | Core idea, high-level vision, and intake notes. |
| **02-storyboard**   | S2    | Storyboard / UX       | Visual journeys, wireframes, and UX logic.      |
| **03-prd**          | S3    | Product Requirements  | Full technical specs, features, and metrics.    |
| **04-architecture** | S4    | System Architecture   | Agentic design, data flow, and components.      |
| **05-hld**          | S5    | High-Level Design     | Module relationships and infrastructure.        |
| **06-lld**          | S6    | Low-Level Design      | Class diagrams, schemas, and logic.             |
| **07-presentation** | S7    | Pitch Deck            | Slide decks for stakeholders.                   |
| **08-design**       | S8    | UI Design Kit         | Style guides, tokens, and components.           |
| **09-diagrams**     | S9    | System Diagrams       | Mermaid flowcharts and data models.             |

### 95.3 Stage Folder Sequence

The following folder structure is MANDATORY for all projects:

1. `00-brd`: Business Requirements (High-Fidelity DOCX)
2. `01-product`: Product Intake & Vision (MD + HTML Deck)
3. `02-storyboard`: User Journeys & Screen Maps (MD + HTML Deck)
4. `03-prd`: Product Requirements (High-Fidelity DOCX)
5. `04-architecture`: System Design & Orchestration (MD + HTML Deck)
6. `05-hld`: High-Level Design (MD + HTML Deck)
7. `06-lld`: Low-Level Design (MD + HTML Deck)
8. `07-presentation`: Full Project Pitch Deck (HTML)
9. `08-design`: UI/UX Assets & Wireframes
10. `09-diagrams`: Mermaid/C4 Diagrams

### 95.4 The "Markdown-First" Rule (MD → DOCX/Deck)

Every stage in the 03-docs lifecycle follows a "Source → Export" architecture:

1.  **Source (Technical Depth)**: The architect first creates/updates the Markdown (**`.md`**) file as the primary source of truth.
2.  **Export (Executive Clarity)**: High-fidelity formats (**`.docx`**) and Presentation Decks (**`.html`**) are programmatically generated from the `.md` source.

- **Location**: The `.md` source resides in the stage root; all exports reside in the **`export/`** subfolder.
- **Automation**: Use Node.js or Python scripts to parse the `.md` and generate the derived artifacts.

### 95.6 File Naming Convention

All artifacts (Source and Export) MUST follow a standardized naming convention:

- **Format**: `[ProjectName]-v[Version].[Extension]`
- **Examples**:
  - `AutoRAG-v1.0.md`
  - `AutoRAG-v1.0.docx`
  - `AutoRAG-v1.0-Deck.html`
- **Case**: Match the Project Name casing from `product.json`.

- **Colors**:
  - **Primary**: `#7C3AED` (Deep Purple) for highlights and H2.
  - **Secondary**: `#1E1B4B` (Dark Navy) for structural H1 and table headers.
  - **Accent**: `#F97316` (Orange) for branding and key warnings.
- **Typography**: **Arial** (Standard) or **Inter** (Web).
  - **H1**: 36pt, Dark Navy, 40pt purple top border on cover.
  - **H2**: 26pt, Deep Purple.
  - **Body**: 20pt, Gray-800.
- **Layout**:
  - **Cover**: Full-width purple top border (40pt).
  - **Tables**: Dark Navy headers with white text; Light Purple (`#EDE9FE`) alternating rows.
  - **Callouts**: Left-border accents (4px) with shaded backgrounds.

## 3. Formatting Rules

- **Alignment**: All text MUST be left-aligned (no justified text).
- **Density**: High-density consulting-grade layout (McKinsey/Stripe style).
- **Code**: Branded `formula` blocks for logic/math; dark `code` blocks for snippets.

## 4. Folder Structure & Naming

- Each folder (`00-09`) must contain an `export/` sub-folder for `.docx` and `.pdf` deliverables.
- **Naming Convention**: `[ProjectName]-[DocType]-Elite.docx` (e.g., `AutoRAG-PRD-Elite.docx`).
