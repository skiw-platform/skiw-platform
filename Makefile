.PHONY: install lint typecheck test test-live build dev db-up migrate clean

export PYTHONPATH := app
TOOL_ENV := DJANGO_SECRET_KEY=tooling-only-not-a-secret DATABASE_URL=postgres://u:p@localhost:5432/db

install:
	uv sync --locked

lint:
	uv run ruff check .
	uv run ruff format --check .
	$(TOOL_ENV) uv run lint-imports

typecheck:
	$(TOOL_ENV) uv run mypy app

test:
	$(TOOL_ENV) uv run pytest

test-live: .env
	docker compose up -d --wait db
	$(MAKE) migrate
	set -a; . ./.env; set +a; uv run pytest -m live

build:
	docker compose build

.env:
	cp .env.example .env

dev: .env
	docker compose up --build

db-up: .env
	docker compose up -d --wait db

migrate: .env
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py migrate
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py makemigrations --check --dry-run

clean:
	docker compose down -v
