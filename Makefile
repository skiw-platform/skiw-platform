.PHONY: install lint typecheck test build dev db-up migrate clean

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

build:
	docker compose build

.env:
	cp .env.example .env

dev: .env
	docker compose up --build

db-up: .env
	docker compose up -d --wait db

migrate: .env
	set -a; . ./.env; set +a; uv run python app/manage.py migrate
	set -a; . ./.env; set +a; uv run python app/manage.py makemigrations --check --dry-run

clean:
	docker compose down -v
