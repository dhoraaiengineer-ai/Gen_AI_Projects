# AutoRAG Architect — Test Data Requirements

**Version**: v1.0 | **Updated**: 05-Jul-2026
**Owner**: Team 2 (Evaluation) + Team 10 (Governance)

---

## Purpose

This document defines the test datasets required for validating the AutoRAG Architect platform during development, integration testing, evaluation, demonstrations, and user acceptance testing.

The test data should represent realistic enterprise knowledge sources across multiple business domains to ensure the platform can accurately ingest, index, retrieve, and cite information from heterogeneous document collections.

---

## Objectives

The test dataset should allow validation of:

- Document ingestion pipeline
- Chunking and indexing strategies
- Embedding generation
- Vector search accuracy
- Hybrid retrieval performance
- Citation generation
- Multi-document question answering
- Hallucination reduction
- Access control and permissions
- Agent orchestration workflows

---

## Quick Reference — Domain Coverage Table

| Domain | Document Types | Example Files | Why Useful for RAG Testing |
|--------|---------------|---------------|---------------------------|
| HR / Policies | Employee handbooks, leave policies, code of conduct | employee_handbook.pdf, leave_policy.docx | Tests policy lookup, eligibility questions, citation accuracy |
| Finance | Annual reports, expense policies, financial statements | annual_report_2024.pdf, expense_policy.pdf | Tests numerical retrieval, financial terminology, summarization |
| Legal | Contracts, NDAs, compliance docs, regulations | vendor_contract.pdf, nda_template.pdf | Tests clause extraction, legal citations, precise retrieval |
| Technical | API docs, architecture guides, runbooks, SOPs | api_specification.pdf, production_runbook.docx | Tests technical Q&A, procedural instructions, multi-doc retrieval |
| Product | PRDs, feature specs, release notes, user guides | product_requirements.pdf, feature_spec_v2.docx | Tests requirements understanding, feature comparison, roadmap queries |
| IT Operations | Incident reports, deployment guides, monitoring playbooks | incident_report.pdf, deployment_guide.docx | Tests operational knowledge and troubleshooting workflows |
| Customer Support | FAQs, knowledge base, support playbooks | customer_faq.pdf, troubleshooting_manual.pdf | Tests conversational support and resolution recommendations |
| Sales & Marketing | Sales playbooks, pricing guides, competitor analysis | sales_playbook.pdf, competitor_analysis.docx | Tests business queries and content summarization |
| Healthcare | Clinical guidelines, patient instructions, treatment protocols | clinical_guidelines.pdf, patient_instructions.pdf | Tests domain-specific terminology and compliance-sensitive retrieval |
| Research & Education | Research papers, whitepapers, training materials | research_paper.pdf, training_manual.pdf | Tests semantic search, long-context retrieval, summarization quality |

---

## MVP Dataset — Recommended Quantities

| Category | Documents |
|----------|-----------|
| HR Policies | 5–10 |
| Technical Documentation | 10–15 |
| Product Requirements | 5–10 |
| Legal Documents | 3–5 |
| Finance Documents | 3–5 |
| **Total** | **20–50 documents (50–200 pages)** |

---

## Domain Coverage

### 1. HR / Policies

**Document Types**
- Employee Handbooks
- Leave Policies
- Code of Conduct
- Onboarding Guides
- Benefits Documentation

**Example Files**
- `employee_handbook.pdf`
- `leave_policy.docx`
- `code_of_conduct.pdf`

**Validation Goals**
- Policy retrieval
- Eligibility queries
- Employee FAQ generation
- Citation accuracy

---

### 2. Finance

**Document Types**
- Annual Reports
- Expense Policies
- Invoices
- Financial Statements
- Budget Guidelines

**Example Files**
- `annual_report_2024.pdf`
- `expense_policy.pdf`
- `quarterly_financials.xlsx`

**Validation Goals**
- Numeric information retrieval
- Financial summarization
- Trend identification
- Cross-document analysis

---

### 3. Legal

**Document Types**
- Vendor Contracts
- NDAs
- Compliance Documents
- Terms & Conditions
- Regulatory Guidelines

**Example Files**
- `vendor_contract.pdf`
- `nda_template.pdf`
- `gdpr_compliance.pdf`

**Validation Goals**
- Clause extraction
- Compliance lookup
- Legal citation validation
- Contract question answering

---

### 4. Technical Documentation

**Document Types**
- API Specifications
- Architecture Guides
- Runbooks
- SOPs
- Troubleshooting Manuals

**Example Files**
- `api_specification.pdf`
- `architecture_guide.pdf`
- `production_runbook.docx`

**Validation Goals**
- Technical Q&A
- Procedure retrieval
- Architecture understanding
- Multi-step instruction generation

---

### 5. Product Management

**Document Types**
- Product Requirement Documents
- Feature Specifications
- Release Notes
- User Guides

**Example Files**
- `product_requirements.pdf`
- `feature_spec_v2.docx`
- `user_guide.pdf`

**Validation Goals**
- Feature discovery
- Requirement traceability
- Product roadmap queries
- Feature comparison

---

### 6. IT Operations

**Document Types**
- Incident Reports
- Deployment Guides
- Infrastructure Documentation
- Monitoring Playbooks

**Example Files**
- `incident_report.pdf`
- `deployment_guide.docx`
- `monitoring_playbook.pdf`

**Validation Goals**
- Incident investigation
- Deployment support
- Infrastructure retrieval
- Operational troubleshooting

---

### 7. Customer Support

**Document Types**
- FAQs
- Knowledge Base Articles
- Troubleshooting Guides
- Support Procedures

**Example Files**
- `customer_faq.pdf`
- `support_guide.docx`
- `troubleshooting_manual.pdf`

**Validation Goals**
- Customer support automation
- Resolution recommendations
- FAQ retrieval
- Support workflow guidance

---

### 8. Sales & Marketing

**Document Types**
- Sales Playbooks
- Pricing Guides
- Marketing Materials
- Competitor Analysis Reports

**Example Files**
- `sales_playbook.pdf`
- `pricing_guide.pdf`
- `competitor_analysis.docx`

**Validation Goals**
- Product positioning queries
- Pricing retrieval
- Competitive analysis
- Sales enablement support

---

### 9. Healthcare (Optional)

**Document Types**
- Clinical Guidelines
- Patient Instructions
- Medical Policies
- Treatment Protocols

**Example Files**
- `clinical_guidelines.pdf`
- `patient_instructions.pdf`

**Validation Goals**
- Medical information retrieval
- Guideline lookup
- Compliance validation

---

### 10. Research & Education

**Document Types**
- Research Papers
- Whitepapers
- Training Manuals
- Course Materials

**Example Files**
- `research_paper.pdf`
- `training_manual.pdf`
- `course_notes.docx`

**Validation Goals**
- Semantic search evaluation
- Research summarization
- Knowledge extraction
- Long-context retrieval

---

## Recommended MVP Dataset

| Category | Recommended Documents |
|----------|-----------------------|
| HR | 5–10 |
| Technical | 10–15 |
| Product | 5–10 |
| Legal | 3–5 |
| Finance | 3–5 |

**Total Documents:** 20–50  
**Total Content Size:** 50–200 Pages

---

## Success Criteria

The platform should successfully:

- Ingest all supported documents
- Generate embeddings without errors
- Retrieve relevant chunks with high accuracy
- Provide source citations
- Answer multi-document questions
- Support semantic and keyword search
- Demonstrate low hallucination rates
- Maintain acceptable response latency

---

## Acceptance Criteria

1. At least 95% successful document ingestion
2. Citation links generated for all retrieved answers
3. Average response time under 5 seconds
4. Retrieval relevance score above defined evaluation threshold (Unified Score >= 0.85)
5. Successful execution of cross-domain queries
6. No critical failures during ingestion or retrieval workflows

---

## Deliverable

A curated enterprise test corpus containing 20–50 representative documents across multiple business domains for validating AutoRAG Architect ingestion, retrieval, evaluation, and demonstration workflows.

Store test documents in: `autorag-server/tests/fixtures/test-corpus/`

---

*Related: [DB_SCHEMA.md](DB_SCHEMA.md) | [AGENTS.md](AGENTS.md) | [autorag-server/tests/fixtures/adversarial_qa.json](../../autorag-server/tests/fixtures/adversarial_qa.json)*
