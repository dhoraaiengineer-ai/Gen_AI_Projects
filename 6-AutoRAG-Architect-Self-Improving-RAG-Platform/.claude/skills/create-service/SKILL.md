# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: create-service
description: Scaffold a new backend microservice module with routes, services, repositories, and schemas

---

# Create Service Skill

## Goal

Scaffold a new service module following the platform's layered architecture.

## Steps

1. Ask for: service name, domain responsibility, key entities, and initial endpoints needed.
2. Create the module directory structure:
   - `services/{name}/routes.py` — thin route handlers
   - `services/{name}/service.py` — business logic
   - `services/{name}/repository.py` — data access layer
   - `services/{name}/schemas.py` — Pydantic request/response models
   - `services/{name}/models.py` — SQLAlchemy ORM models
   - `services/{name}/exceptions.py` — domain-specific exceptions
   - `services/{name}/constants.py` — enums, status codes, config keys
3. Create SQLAlchemy models with UUID v7 primary keys (Rule 30 -- never serial integers) and timestamps.
4. Create an Alembic migration for the new tables.
5. Wire the router into the main FastAPI app.
6. Add initial unit and API tests.
7. Summarize the scaffolded structure.

## Quality rules

- Follow single-responsibility: one service, one domain.
- Use dependency injection via `Depends()`.
- Use type hints on all function signatures.
- Add structured JSON logging for key operations.
- Add indexes on columns used in common queries.
- Use soft deletes for customer-facing data.
- Do not skip the migration step.
