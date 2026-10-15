# Gen AI Projects

Production-style Generative AI systems, each self-contained in its own folder with its own README,
tests, Docker setup and infrastructure code.

| # | Project | What it is | Stack |
|---|---|---|---|
| 1 | [GenAI RAG Platform](1-GenAI-RAG-Platform/) | Document Q&A with citations to the page, sheet or slide; hybrid retrieval, OCR, hallucination guard, evaluation | FastAPI · LangChain · LangGraph · Supabase pgvector · Redis · Docker · Kubernetes · Terraform |
| 2 | [Multi-Agent Supply Chain AI](2-Multi-Agent-Supply-Chain-AI/) | A LangGraph supervisor routes questions to demand, inventory, supplier, logistics and knowledge agents; real-time streaming, human-in-the-loop approvals, layered guardrails, Next.js command center | FastAPI · LangGraph · LangChain · Supabase pgvector · Redis · Next.js · Docker · Terraform |
| 3 | [FinAgent — Finance Multi-Agent Platform](3-FinAgent-Finance-Multi-Agent-Platform/) | Decision support for an asset manager: a LangGraph supervisor delegates to eight specialist agents (portfolio, market, risk, compliance, fraud, research, prediction, report) over A2A; tools served by six MCP servers; pure financial maths, MLflow fraud/risk/forecast models, cited RAG, guardrails and human approval before any order draft | FastAPI · LangGraph · MCP · A2A · LightGBM · MLflow · Supabase pgvector · Redis · Next.js · Prometheus · OpenTelemetry · Docker · Kubernetes · Terraform |
| 4 | [MedInfo — Medical Multi-Agent Assistant](4-MedInfo-Medical-Multi-Agent-Assistant/) | Safety-first medical information assistant: urgent-symptom triage first (rules + LLM), scope agent, hybrid pgvector + BM25 retrieval with re-ranking, cited answers checked by a verifier and a fail-closed faithfulness judge, ReAct research agent, LLM gateway with token budgets, PHI redaction, agent trace; release-blocking safety suite (100% live) and RAGAS + LLM-judge evaluation | FastAPI · LangGraph · LangChain · Supabase pgvector · Redis · RapidOCR · MLflow · RAGAS · Playwright · Docker · Kubernetes · Terraform |

Each project's CI runs only when files in its own folder change (`.github/workflows/p<N>-*.yml`).
