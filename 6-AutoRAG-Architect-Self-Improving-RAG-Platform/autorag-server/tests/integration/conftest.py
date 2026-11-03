"""Integration test configuration — sets env vars before test module imports.

Settings (app.core.config) validates DATABASE_URL and JWT_SECRET_KEY at startup.
These stubs prevent ValidationError during test collection for tests that don't
need a real database (e.g. service-layer unit tests mocking LLMService).

Tests that DO need a real database must have these env vars set in their .env
or via the CI environment — the stubs here are overridden by real values if present.
"""
import os

os.environ.setdefault(
    "DATABASE_URL",
    # Must match docker-compose.yml's local Postgres provisioning
    # (POSTGRES_USER=postgres / POSTGRES_PASSWORD=postgres) -- that container
    # never creates a "test" role, so a mismatched fallback here fails auth.
    # Matches the same fix already applied in tests/conftest.py (13-Jul-2026).
    "postgresql+asyncpg://postgres:postgres@localhost:5432/autorag_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-key-minimum-32-characters-for-testing-only",
)
