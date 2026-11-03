# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Third-Party Integrations — AutoRAG Architect v3.0

This document details the configuration, credentials, and failover boundaries for external service integrations.

---

## 1. AI & LLM Model Providers

| Provider       | Service                    | Integration Type                        | Fallback Policy                |
| -------------- | -------------------------- | --------------------------------------- | ------------------------------ |
| **Google**     | Gemini Flash 3.5           | Primary reasoning, agent node decisions | Fallback to KiMi K2.6          |
| **KiMi**       | K2.6                       | Secondary reasoning fallback            | Fallback to Gemini 3.5         |
| **Google**     | Gemini Embedding 2         | Dense vector embeddings                 | No fallback — required         |
| **Cohere**     | Rerank v3 API              | High-fidelity retrieval re-ranking      | Fallback to BGE-Reranker local |

### LLM Failover Chain

```
Gemini Flash 3.5  →  KiMi K2.6  →  Gemini 3.5
```

### Core Provider Abstraction Rule

No agent node is allowed to directly invoke a raw provider SDK. All LLM interactions must route through the **AutoRAG LLM Abstraction Layer** to ensure seamless failover and provider swapping.

---

## 2. Data Platform — Supabase

All relational data, vector data, and file storage are consolidated in **Supabase**:

| Supabase Service      | Purpose                                            |
| --------------------- | -------------------------------------------------- |
| **Supabase PostgreSQL** | Operational system of record, pipeline configs, audit log |
| **Supabase Vector (pgvector)** | Shared `pipeline_chunks` table, partitioned by `pipeline_version` (Version 4.0, migration 0016) |
| **Supabase Storage**  | Raw document ingestion + pipeline snapshots        |

### Supabase Vector Table Naming (superseded 20-Jul-2026)

The per-pipeline physical table convention below was replaced by a single shared
`pipeline_chunks` table partitioned by a `pipeline_version` column — see
`docs/DB_SCHEMA.md`'s "Immutable Versioned Indexes" addendum.

```
autorag_{pipeline_id}_{version}   # historical only — no longer created
```

---

## 3. PII Masking

### Custom PII Detection & Masking Functions

- **Execution**: Runs at the ingestion boundary before any document reaches the LLM or Supabase Vector
- **Scan Targets**: SSN, Credit Cards, API Keys, Private Emails, Password hashes, phone numbers
- **Failover**: If the custom PII function errors, ingestion fails-safe — stops processing and logs an alert

---

## 4. Telemetry & Experiment Tracking

### MLflow

- **Integration**: Every Builder pipeline combination (chunking, embedding, reranker threshold) triggers a unique MLflow run
- **Logged Parameters**: Chunk size, chunk overlap, embedding model version, retrieval metrics (Hit Rate, MRR)
- **Logged Metrics**: Unified Score, RAGAS Faithfulness, Latency (ms), Query Cost (USD)

### Prometheus + Grafana

- **Prometheus**: Scrapes metrics from FastAPI and LangGraph workers — latency, error rate, queue depth, LLM inference time
- **Grafana**: Dashboards for both LLMOps (model performance, token usage, score trends) and system observability (CPU, memory, throughput)
- **Scope**: Application-level LLMOps monitoring + system observability (CPU, memory, throughput)

---

## 5. Notifications & Real-Time Comms

| Service                    | Purpose                                    |
| -------------------------- | ------------------------------------------ |
| **SendGrid**               | Email notifications for HITL approval gates |
| **WhatsApp (Wati/Twilio)** | WhatsApp alerts for critical pipeline events |

---

## 6. API Testing

### Postman

- **Use**: Validate the REST API (46 endpoints, live-schema verified) during development and CI smoke tests
- **Collections**: Maintain a Postman collection per API domain (configurator, pipeline, evaluation, deployment)
- **Environment**: Separate Postman environments for `local`, `dev`, `staging`

---

## 7. Error Capture & Observability

### Prometheus + Grafana (primary)

- **Scope**: Application-level error tracking via Prometheus counters + Grafana alert rules
- **Security Filter**: Structured logging must never include credentials, passwords, or raw LLM prompt templates in metric labels or log fields

