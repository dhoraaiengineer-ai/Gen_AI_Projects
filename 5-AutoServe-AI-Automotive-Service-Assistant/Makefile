# AutoServe AI — developer targets. Windows without make: use ./dev.ps1 <target> (same targets).
SERVER := autoserve-server
CLIENT := autoserve-client

.PHONY: help install up down logs migrate seed ingest test test-server test-client lint eval demo check-models

help:
	@echo "install up down logs migrate seed ingest test lint eval demo check-models"

install:
	cd $(SERVER) && uv sync
	cd $(CLIENT) && npm ci

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	cd $(SERVER) && uv run alembic upgrade head

seed:
	cd $(SERVER) && uv run python -m scripts.seed

ingest:
	cd $(SERVER) && uv run python -m scripts.ingest

test: test-server test-client

test-server:
	cd $(SERVER) && uv run pytest -q --cov --cov-report=term-missing:skip-covered

test-client:
	cd $(CLIENT) && npm run test

lint:
	cd $(SERVER) && uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd $(CLIENT) && npm run lint && npm run typecheck

eval:
	@echo "eval: not implemented yet (task P1-7)"; exit 1

demo:
	@echo "demo: not implemented yet (task P5-2)"; exit 1

check-models:
	cd $(SERVER) && uv run python -m scripts.check_models
