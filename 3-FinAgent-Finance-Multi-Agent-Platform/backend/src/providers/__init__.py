"""Provider adapters (LLMs, embeddings, re-ranker, OCR, web search).

Together with ``src/container.py`` this package is the only place allowed to import provider
SDKs (ADR-022). Everything else depends on LangChain interfaces and receives adapters from the
container.
"""
