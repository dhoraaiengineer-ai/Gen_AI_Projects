# Architecture

Companion to [PLAN.md](PLAN.md), which holds the decisions and roadmap. Agent specifications are in
[../agents/](../agents/).

## 1. Layers and dependency direction

```mermaid
flowchart TB
    api[app/api<br/>thin routes, auth deps] --> svc[app/services<br/>use cases, business maths]
    api --> ag[app/agents<br/>LangGraph graphs]
    ag --> tools[app/tools<br/>RBAC tool registry]
    ag --> rag[app/rag<br/>knowledge base]
    ag --> gr[app/guardrails]
    tools --> svc
    tools --> repo[app/db/repositories]
    svc --> repo
    rag --> ifc[(Protocols:<br/>ChatModel, Embeddings,<br/>VectorStore, Cache, OCREngine, WebSearch)]
    root[app/container.py + app/rag/providers.py<br/>composition root] -.implements.-> ifc
    root -.wires.-> api
```

Dependencies point inward only. Concrete providers (LLMs, Redis, Tavily, Tesseract) are constructed in one
place, `app/container.py`. FastAPI hands them to routes through `Depends`. Tests swap in fakes.

## 2. Question flow: "Give me a complete recommendation for SKU-100"

```mermaid
sequenceDiagram
    participant U as User (analyst)
    participant A as FastAPI /chat/stream
    participant G as Supervisor graph
    participant D as Demand
    participant I as Inventory
    participant S as Supplier
    participant L as Logistics
    participant R as RAG
    participant P as Approver
    U->>A: question + JWT
    A->>A: verify JWT (JWKS), rate limit, input guardrails
    A->>G: astream(state, thread_id)
    G->>G: classify_intent = full_recommendation, plan
    par independent
        G->>D: forecast SKU-100
        G->>R: procurement policy (doc_type=policy)
    end
    D-->>G: demand_forecast
    G->>I: reorder maths (uses forecast)
    I-->>G: inventory_data (reorder_qty, risk)
    par after inventory
        G->>S: supplier for reorder_qty
        G->>L: inbound shipments, delivery estimate
    end
    G->>G: needs_approval? (PO value > threshold)
    G-->>P: interrupt → /approvals (approve / edit / reject)
    P->>G: Command(resume=decision)
    G->>G: synthesize → validate (output guardrails)
    G-->>A: SSE events: node updates, tokens, final answer + citations
```

## 3. Data model (operational)

```mermaid
erDiagram
    products ||--o{ inventory : stocked_as
    products ||--o{ sales : sold_as
    products ||--o{ supplier_products : offered_by
    suppliers ||--o{ supplier_products : offers
    suppliers ||--o{ purchase_orders : receives
    products ||--o{ purchase_orders : for
    purchase_orders ||--o{ shipments : shipped_as
    carriers ||--o{ shipments : carries
```

Knowledge-base tables:

- `kb_sources`, the hash registry with chunk ids
- `kb_chunks`, holding the embedding, the `tsvector` and the JSONB metadata
- `kb_version`

The other tables are:

- conversation memory: `conversations` and `messages`
- `approvals`
- `audit_log`
- the LangGraph checkpointer tables

## 4. Deployment (target)

```mermaid
flowchart LR
    user --> alb[ALB Ingress] --> eks[EKS: FastAPI pods<br/>1 worker, HPA]
    eks --> redis[Redis in-cluster]
    eks --> supa[(Supabase Postgres<br/>ap-northeast-1)]
    eks --> llm[Euri / Groq / Gemini]
    eks --> cw[CloudWatch logs]
    prom[Prometheus + Grafana] --> eks
    gh[GitHub Actions OIDC] --> ecr[ECR] --> eks
    sm[Secrets Manager] --> eks
```

Local development uses `docker compose`, which runs the app and Redis and connects to Supabase. Optional
profiles add a local pgvector database and a monitoring stack.
