# GenAI RAG Platform overview

The platform answers questions over an internal document collection. Documents are split into
overlapping chunks of up to 1,000 characters (150 characters of overlap), embedded with
text-embedding-3-small, and stored in Postgres using the pgvector extension.

At query time the platform retrieves the four most similar chunks and sends them to the chat model
together with the question. Answers cite their sources with bracketed indices such as [1].

For multi-part questions, the /api/v1/agent endpoint lets the model run several searches against
the knowledge base before answering. It is built as a LangGraph tool-calling loop and stops after
six search rounds at most.

Operational metrics are exported in Prometheus format at /metrics and visualised in Grafana.
Kubernetes uses /health/live for liveness and /health/ready, which checks the database, for readiness.
