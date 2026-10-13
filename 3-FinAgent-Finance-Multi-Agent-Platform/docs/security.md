# Security

## Authentication

- Supabase Auth issues JWTs. The API verifies them against `SUPABASE_JWKS_URL`, accepting only
  **ES256/RS256**, checking `exp`, `aud` and issuer. JWKS is cached with refresh on unknown `kid`.
- The role comes only from `app_metadata.app_role` (users cannot edit `app_metadata`).
- OAuth-ready: Supabase supports Google/Microsoft/SAML providers without API changes.
- IAM-ready: in AWS, workloads use IRSA roles; no static AWS keys in containers.

## Multi-tenancy (ADR-026)

Each asset-management firm is a tenant. The tenant id comes only from the verified JWT
(`app_metadata.tenant_id`); users never choose it.

| Layer | Control |
|---|---|
| ORM | `do_orm_execute` hook adds `tenant_id = current` to every query on tenant tables; no tenant → `Forbidden` |
| Writes | `before_flush` stamps `tenant_id`; writing another tenant's rows → `Forbidden` |
| Tools / MCP / A2A | `tenant_id` travels in `ToolContext`, MCP `_meta` and A2A context |
| Database | RLS policy `tenant_isolation` on every tenant table; browser keys have no privileges |
| Caches | keys include the tenant |

## Roles and permissions

Roles: `admin`, `risk_manager`, `compliance_officer`, `portfolio_manager`, `analyst`,
`fraud_analyst`, `viewer`. Defaults below; overridable via the `roles` / `permissions` tables.

| Permission | admin | risk_mgr | compliance | pm | analyst | fraud | viewer |
|---|---|---|---|---|---|---|---|
| View dashboards, portfolios | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Ask assistant / run agents | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| Risk tools (VaR, stress) | ✓ | ✓ | ✓ | ✓ | ✓ | – | – |
| Fraud tools, transactions | ✓ | – | ✓ | – | – | ✓ | – |
| Customer profile (PII masked) | ✓ | – | ✓ | – | – | ✓ | – |
| Propose rebalance (draft) | ✓ | ✓ | – | ✓ | – | – | – |
| Approve / reject approvals | ✓* | – | ✓ | ✓ | – | – | – |
| Upload/delete documents | ✓ | – | ✓ | – | ✓ | – | – |
| Read audit log | ✓ | – | ✓ | – | – | – | – |
| Restricted documents | ✓ | ✓ | ✓ | ✓ | – | – | – |

\* admin approval is configurable and off by default (segregation of duties).

Enforcement points: routes (`require_role`), tools (registry: agent allow-list + minimum role),
MCP servers (same registry), A2A (agent cards list allowed tasks), RAG (mandatory classification
filter in SQL).

## Data protection

- **Secrets:** environment variables only (`SecretStr`), `.env` git-ignored, AWS Secrets Manager in
  the cloud. An architecture test scans tracked files for key patterns.
- **PII masking:** account numbers, cards (Luhn-checked), IBAN (checksum), SSN/tax IDs, email,
  phone are redacted before any LLM call, in logs, A2A records and audit entries.
- **Encryption:** TLS to Supabase, Redis TLS in AWS, encryption at rest (Supabase, S3 SSE-KMS,
  ElastiCache, OpenSearch). Customer PII columns in `customers` are stored masked in demo data.
- **Row-level security:** enabled on every table; the browser's publishable key reads nothing.

## LLM-specific controls (Stage 6)

| Layer | Checks |
|---|---|
| Input | length limit, secrets rejected, injection/jailbreak score, PII redaction, finance scope |
| Context | retrieved chunks, tool output and web results fenced as untrusted data; passages with instructions dropped |
| Output | citations valid, every number/ticker present in evidence, no guaranteed-return or personalised-advice language, secrets block, PII redacted |
| Actions | agents read-only; orders only via approval → draft |

## Audit

Every request has `request_id`, `trace_id`, `user_id`, timestamp. `audit_logs` records the request
summary, agents called, A2A messages, MCP tools called, retrieved document ids, ML model versions,
model outputs (summarised), LLM calls (model, tokens, cost), final response hash, approval status
and guardrail decisions with reasons. Never secrets, never raw sensitive financial data.
