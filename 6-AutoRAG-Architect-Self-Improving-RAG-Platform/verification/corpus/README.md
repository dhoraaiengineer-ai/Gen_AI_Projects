# AutoRAG Architect — Test Corpus

**Date**: 06-Jul-2026 (created) | moved under `evaluation/` 26-Jul-2026
**Purpose**: End-to-end AutoRAG workflow testing — ingest -> chunk -> embed -> retrieve -> evaluate
**Status**: Corpus ready (10 domains, 23 documents)
**Tracked in git** — this folder lives under `evaluation/`, which is not gitignored (moved from a
formerly-gitignored `testing/corpus/` at the user's explicit request — see `.claude/MEMORY.md` L-018).

---

## What Is In This Folder

```
evaluation/
  corpus/
    README.md           <- this file
    hr/                 <- 5 HR policy documents
    technical/          <- 5 technical documentation files
    product/            <- 2 product documents
    legal/              <- 3 legal/compliance documents
    finance/            <- 3 finance documents
    it_operations/      <- 1 IT operations document (incident report)
    customer_support/   <- 1 customer FAQ document
    sales_marketing/    <- 1 sales playbook
    research_education/ <- 2 research and training documents (incl. attention-is-all-you-need.pdf)
    healthcare/         <- 1 clinical guidelines document
```

---

## Document Inventory (23 documents across 10 domains)

### Domain 1: HR (5 documents)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 1 | `hr/employee_handbook.txt` | Employment classifications, work hours, compensation, leave summary, disciplinary process | Policy lookup, eligibility questions |
| 2 | `hr/leave_policy.txt` | Annual leave: 18/21/25 days by tenure; sick 12 days; maternity 26 weeks; paternity 4 weeks | Specific number retrieval, eligibility rules |
| 3 | `hr/code_of_conduct.txt` | Integrity, confidentiality, anti-bribery (gift limits: SGD 50 gifts, SGD 150 hospitality) | Policy compliance Q&A |
| 4 | `hr/onboarding_guide.txt` | Day 1 checklist, week-by-week 30-day plan, contacts, FAQ | Procedural question answering |
| 5 | `hr/benefits_guide.txt` | Medical (SGD 100k hospitalization), wellness (SGD 80/month), ESOP, L&D (SGD 2,500/yr) | Benefits eligibility, specific amounts |

### Domain 2: Technical Documentation (5 documents)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 6 | `technical/api_specification.txt` | Full 14-endpoint REST API spec with request/response schemas, error codes, JWT auth | API usage Q&A, endpoint lookup |
| 7 | `technical/architecture_guide.txt` | 9-agent loop, Supabase, ECS Fargate, Redis, LLM failover chain, security, observability | Architecture questions, component lookup |
| 8 | `technical/production_runbook.txt` | On-call scenarios: high latency, rollback, Redis outage, LLM provider failure | Operational troubleshooting, multi-step procedures |
| 9 | `technical/developer_setup_guide.txt` | Prerequisites, git clone, .env setup, docker compose, migrations, common errors | Developer Q&A, setup procedures |
| 10 | `technical/sop_data_ingestion.txt` | Supported formats, size limits, ingestion API steps, chunking strategy guide, error codes | Procedural instructions, format/limit lookup |

### Domain 3: Product (2 documents)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 11 | `product/prd_autorag_v3.txt` | v3.0 PRD: 9-agent features, Unified Score formula, HITL flow, non-functional requirements, success metrics | Requirements lookup, feature comparison |
| 12 | `product/release_notes_v3.txt` | v3.0 breaking changes (Supabase, Gemini, custom PII), new features, upgrade guide | Change history, migration questions |

### Domain 4: Legal & Compliance (3 documents)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 13 | `legal/vendor_contract_template.txt` | Vendor agreement: payment (30-day terms, 1.5%/month late fee), IP, confidentiality (5 yr), breach notification 24h | Contract clause lookup |
| 14 | `legal/nda_template.txt` | Mutual NDA: definition of confidential info, obligations, 2-year term + 3-year survival, Singapore law | NDA term retrieval |
| 15 | `legal/gdpr_compliance_policy.txt` | Data protection principles, legal bases, subject rights (30-day response), breach notification (72h) | Compliance Q&A, specific obligations |

### Domain 5: Finance (3 documents)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 16 | `finance/expense_policy.txt` | Expense limits: domestic hotel SGD 250/night, meals SGD 80/day; approval matrix up to CFO for >SGD 10k | Limit lookup, approval chain |
| 17 | `finance/annual_report_summary_2025.txt` | FY2025: SGD 8.4M revenue (+140%), SGD 0.3M net income, 47 customers, 0.89 avg Unified Score | Financial metric retrieval |
| 18 | `finance/budget_guidelines_2026.txt` | FY2026 targets: SGD 18M revenue, 55 FTE, SaaS SGD 95k, infrastructure SGD 720k | Budget/headcount lookup |

### Domain 6: IT Operations (1 document)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 19 | `it_operations/incident_report_template.txt` | Real post-mortem (INC-2026-0034): missing HNSW index, 7.2s p95 latency, 340 queries affected, timeline and remediation | Incident analysis, root cause, procedure |

### Domain 7: Customer Support (1 document)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 20 | `customer_support/customer_faq.txt` | 15 Q&As: getting started, chunking strategies, Unified Score targets, Faithfulness block, security, billing, trial | Customer-facing Q&A, feature explanations |

### Domain 8: Sales & Marketing (1 document)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 21 | `sales_marketing/sales_playbook.txt` | ICP (500-10k employees), pricing (Standard SGD 4.5k/mo, Pro SGD 12k/mo, Enterprise custom), objection handling | Pricing lookup, positioning, ICP questions |

### Domain 9: Research & Education (2 documents)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 22 | `research_education/rag_systems_research_paper.txt` | Comprehensive survey: 4-stage retrieval stack, chunking strategies, Unified Score formula, autonomous optimization results | Long-context retrieval, technical deep-dives, summarization |
| 23 | `research_education/llm_fundamentals_training_manual.txt` | Transformer architecture, pre-training/RLHF phases, inference parameters, prompt engineering for RAG | Technical training Q&A, concept lookup |

### Domain 10: Healthcare (1 document)

| # | File | Content | Good for testing |
|---|------|---------|-----------------|
| 24 | `healthcare/clinical_guidelines_ai_systems.txt` | Clinical AI governance: approved use cases, prohibited uses, Faithfulness threshold 0.90, audit requirements, governance board | High-stakes Q&A, policy compliance, threshold differences |

---

## Suggested Test Queries by Domain

### HR queries
- "How many days of annual leave do I get after 5 years?"
- "What is the maternity leave policy?"
- "What are the gift limits in the code of conduct?"
- "What is the wellness allowance amount per month?"

### Technical queries
- "How do I roll back a deployment?"
- "What endpoint do I use to upload a document?"
- "What happens when Gemini Flash 3.5 is unavailable?"
- "What is the maximum file size for PDF ingestion?"

### Legal / Finance queries
- "What is the late payment penalty in the vendor contract?"
- "How long does the NDA confidentiality obligation survive termination?"
- "What is the hotel expense limit for international travel in Tier 1 cities?"
- "What was AutoRAG's revenue growth in FY2025?"

### Research / Healthcare queries
- "What is the optimal alpha parameter for hybrid retrieval in technical corpora?"
- "Why does HyDE improve retrieval on short queries?"
- "What Faithfulness score is required for clinical AI deployment?"
- "What use cases are prohibited for clinical AI systems?"

### Cross-domain queries (test multi-document retrieval)
- "What is the notice period for resignation and what is the rollback window for deployments?" (HR + Technical)
- "What is the L&D budget and how do I set up my local environment?" (HR Benefits + Technical)
- "What Unified Score does the research paper recommend and what does the customer FAQ say about it?" (Research + Customer)
- "What happened in incident INC-2026-0034 and how does it relate to HNSW indexing?" (IT Ops + Research)

---

## How to Run the Test

1. Start the backend: `cd autorag-server && uv run uvicorn app.main:app --reload`
2. Start the frontend: `npm run dev --workspace=autorag-client`
3. Open http://localhost:3000 and log in
4. Create a new pipeline via the Configurator (6-step wizard)
5. Upload documents from `evaluation/corpus/` (start with hr/ folder — 5 files, then expand)
6. Run retrieval queries from the list above via the Retrieval Explorer (/retrieve)
7. Check Unified Score on the Evaluation Dashboard (/evaluation)
8. Target: Unified Score >= 0.85, Faithfulness >= 0.80

### Recommended ingestion order
1. `hr/` (5 docs) — well-structured, clean prose, good baseline for chunking calibration
2. `technical/` (5 docs) — structured with headers, tests hierarchical chunking
3. `legal/` + `finance/` (6 docs) — precise numbers, tests exact retrieval
4. `research_education/` (2 docs) — long-form, tests late chunking and long-context retrieval
5. `healthcare/` + `customer_support/` + `sales_marketing/` + `it_operations/` (4 docs) — mixed formats

---

## Test Results Log

| Run # | Date | Domain(s) | Documents | Chunking Strategy | Unified Score | Faithfulness | Notes |
|-------|------|-----------|-----------|------------------|---------------|-------------|-------|
| — | — | — | — | — | — | — | Pending first run |

*(Update this table after each test run)*
