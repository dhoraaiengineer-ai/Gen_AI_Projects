# Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-llm-provider.md) | LLM provider strategy: OpenAI-compatible chain, single embedding provider | Accepted |
| [ADR-002](ADR-002-react-implementation.md) | ReAct agent for research mode (evidence gathering only) | Accepted |
| [ADR-003](ADR-003-reasoning-format.md) | Reasoning and output format: structured, cited, no exposed chain-of-thought | Accepted |
| [ADR-004](ADR-004-web-access-and-control.md) | Web access: clinician-only, allow-listed medical domains, untrusted | Accepted |
| [ADR-005](ADR-005-llm-failure-and-fallback.md) | LLM failure handling and fallback | Accepted |
| [ADR-006](ADR-006-llm-gateway-routing-and-tokens.md) | LLM gateway: model routing, token limits and caching | Accepted |

Format: Context, Decision, Alternatives considered, Consequences. A changed decision gets a new ADR that
supersedes the old one; docs, presentation and narrative are updated in the same change.
