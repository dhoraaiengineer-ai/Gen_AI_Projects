# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

## Environment & Config

- All environment-specific values must come from environment variables or config files.
- Use a single config module/service that validates all required env vars at startup.
- Fail fast on missing or invalid configuration — do not silently use defaults for critical values.
- For shared dev/staging/production work, real, pre-filled `.env` files are distributed directly by project leads (root + `autorag-server/` + `autorag-client/`). For individual local testing, a self-serve root `.env.example` template exists (reintroduced 17-Jul-2026, commit `f3de0d9`, verified against `app/core/config.py`'s `Settings`) — keep it in sync with `Settings` when adding new required config, never with real secret values.

### Environment Parity

- dev, staging, and production must use the same config structure.
- Environment-specific behavior must be controlled by explicit flags, not implicit detection.
- Database URLs, API keys, model endpoints, and feature flags must all be configurable per environment.

### Secrets Management

- Never commit .env, credentials.json, token.json, or any file with real secrets.
- Use .gitignore to block secret files.
- In production, prefer secret managers (AWS Secrets Manager, Vercel env vars, VPS env files) over baked-in values.
- Rotate secrets on a schedule or after any exposure.

### Validation

- Validate config at application startup, not at first use.
- Type-check config values (ports as int, URLs as valid URLs, booleans as bool).
- Log which config keys are loaded (never log values) for debugging.

### Do Not

- Hardcode API keys, tokens, passwords, or URLs anywhere in source code.
- Use different config loading patterns across services in the same project.
- Commit .env files or any file listed in .gitignore.
