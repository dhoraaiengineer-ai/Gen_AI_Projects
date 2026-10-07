# Gen AI Projects

Production-style Generative AI systems, each self-contained in its own folder with its own README,
tests, Docker setup and infrastructure code.

| # | Project | What it is | Stack |
|---|---|---|---|
| 1 | [GenAI RAG Platform](1-GenAI-RAG-Platform/) | Document Q&A with citations to the page, sheet or slide; hybrid retrieval, OCR, hallucination guard, evaluation | FastAPI · LangChain · LangGraph · Supabase pgvector · Redis · Docker · Kubernetes · Terraform |
| 2 | [Multi-Agent Supply Chain AI](2-Multi-Agent-Supply-Chain-AI/) | A LangGraph supervisor routes questions to demand, inventory, supplier, logistics and knowledge agents; real-time streaming, human-in-the-loop approvals, layered guardrails, Next.js command center | FastAPI · LangGraph · LangChain · Supabase pgvector · Redis · Next.js · Docker · Terraform |

Each project's CI runs only when files in its own folder change (`.github/workflows/p<N>-*.yml`).
