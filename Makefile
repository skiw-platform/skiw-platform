.PHONY: install lint typecheck test test-live build web-build web-dev e2e dev db-up migrate clean check-node

export PYTHONPATH := app
NODE_MAJOR := $(shell node -p "process.versions.node.split('.')[0]" 2>/dev/null)
TOOL_ENV := DJANGO_SECRET_KEY=tooling-only-not-a-secret DATABASE_URL=postgres://u:p@localhost:5432/db

check-node:
	@test "$(NODE_MAJOR)" = "24" || { echo "Node 24 is required (see .node-version); run: fnm use"; exit 1; }

install: check-node
	uv sync --locked
	pnpm install --frozen-lockfile

lint: check-node
	uv run ruff check .
	uv run ruff format --check .
	$(TOOL_ENV) uv run lint-imports
	pnpm -C web lint

typecheck: check-node
	$(TOOL_ENV) uv run mypy app
	pnpm -C web typecheck

test: check-node
	$(TOOL_ENV) uv run pytest
	pnpm -C web test

test-live: .env
	docker compose up -d --wait db
	$(MAKE) migrate
	set -a; . ./.env; set +a; uv run pytest -m live

web-build: check-node
	pnpm -C web build

web-dev: check-node
	pnpm -C web dev

build: web-build
	docker compose build

.env:
	cp .env.example .env

dev: .env web-build
	docker compose up --build

e2e: .env web-build
	docker compose up -d --build --wait
	pnpm -C web exec playwright test

db-up: .env
	docker compose up -d --wait db

migrate: .env
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py migrate
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py makemigrations --check --dry-run

clean:
	docker compose down -v
