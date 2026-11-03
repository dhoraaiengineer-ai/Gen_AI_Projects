# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Ingestion Agent Skill

## Purpose

Build the node responsible for raw document intake, PII masking, and advanced chunking.

## Requirements

- **OCR**: Handle multi-page PDFs using `pypdf` or `Camelot`.
- **PII Scan**: Mandatory Custom PII Functions pass; flag results in `audit_log`.
- **Strategy Choice**:
  - Narrative -> Semantic.
  - > 50 Pages -> Hierarchical (Parent/Child).
  - Cross-reference -> Late Chunking.

## Anti-Patterns

- **Unlabeled Chunks**: Storing chunks without `source_uri` or `page_number`.
- **Plain Text**: Ignoring table structures in financial/legal docs.
