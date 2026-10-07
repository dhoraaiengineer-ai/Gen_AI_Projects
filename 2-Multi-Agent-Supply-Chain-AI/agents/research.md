# Research Agent

**Code:** `app/agents/research.py`

## Responsibility

Answer open questions by combining the knowledge base with web search, for example market conditions or
news about a supplier or a port disruption.

## Tools (allow-list)

| Tool | Purpose |
|---|---|
| `search_knowledge_base(query, filters?)` | The RAG retriever, without the reranker |
| `search_web(query)` | Tavily. Only registered when `TAVILY_API_KEY` is set. |

## Rules

- Web results are **untrusted data**. They are fenced, scanned for injection, and cited by URL. The response
  lists `web_sources`.
- The tool loop is bounded by `AGENT_MAX_TOOL_ITERATIONS`.
- Internal data is never sent to web search. Queries are scanned for PII before they leave the system.

## Access

- **Roles allowed:** analyst, approver and admin.
