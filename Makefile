.PHONY: install dev dev-backend dev-frontend test lint typecheck migrate gen-types up down

install:
	uv sync
	cd frontend && pnpm install

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	uv run uvicorn goalpost.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend

dev-frontend:
	cd frontend && pnpm dev

test:
	uv run pytest backend
	cd frontend && pnpm test

lint:
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && pnpm lint

typecheck:
	uv run pyright
	cd frontend && pnpm typecheck

migrate:
	uv run python -c "from goalpost.migrate import run_migrations; run_migrations()"

gen-types:
	uv run python -m goalpost.export_openapi frontend/lib/api/openapi.json
	cd frontend && pnpm gen-types

up:
	docker compose up --build -d

down:
	docker compose down
