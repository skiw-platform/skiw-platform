.PHONY: install lint typecheck test test-live host-test host-test-live secrets-test build web-build web-dev e2e dev db-up migrate clean check-node audit secrets audit-python audit-web image-scan hooks

export PYTHONPATH := app:infra/host
NODE_MAJOR := $(shell node -p "process.versions.node.split('.')[0]" 2>/dev/null)
SEMGREP_VERSION := 1.179.0
PIP_AUDIT_VERSION := 2.10.1
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
	uvx semgrep==$(SEMGREP_VERSION) --config semgrep/ --metrics=off --error app
	uvx semgrep==$(SEMGREP_VERSION) --test --metrics=off semgrep/
	pnpm -C web lint

typecheck: check-node
	$(TOOL_ENV) uv run --locked mypy app infra/host
	pnpm -C web typecheck

test: check-node
	$(TOOL_ENV) uv run pytest
	pnpm -C web test

test-live: .env
	docker compose up -d --wait db
	$(MAKE) migrate
	set -a; . ./.env; set +a; uv run pytest -m live

# Host tooling unit tests (spec section 8.4); no Docker daemon needed. M1b adds the Compose config tests.
host-test:
	$(TOOL_ENV) uv run --locked pytest infra/host/tests

# Live host stack tests run here once they exist; until then this target only says so.
host-test-live:
	@echo "host-test-live: stub; no live host stack tests exist yet (M1b/M1c add them), nothing was run"

# Proves .gitleaks.toml flags each secret key name (generated values, temp dir). Needs gitleaks;
# skips locally without it, fails in CI (CI=true). CI runs it in the `security` job.
secrets-test:
	$(TOOL_ENV) uv run --locked pytest -m secrets infra/host/tests/test_gitleaks_config.py

# Security gates (UNI-13). CI runs the same targets in the `security` job; docs/runbooks/ci.md.
audit: secrets audit-python audit-web

# Needs gitleaks on PATH (CI pins v8.30.1): brew install gitleaks. Scans committed history only.
secrets:
	@command -v gitleaks >/dev/null || { echo "gitleaks is required: brew install gitleaks"; exit 1; }
	gitleaks git --config .gitleaks.toml --redact --no-banner .

audit-python:
	uv export --frozen --all-groups --no-hashes --quiet --output-file .audit-requirements.txt
	uvx pip-audit==$(PIP_AUDIT_VERSION) --strict --no-deps --disable-pip -r .audit-requirements.txt; status=$$?; rm -f .audit-requirements.txt; exit $$status

audit-web: check-node
	pnpm audit --audit-level high

# Needs trivy on PATH (CI pins v0.75.0): brew install trivy. Builds the image, no push.
image-scan:
	@command -v trivy >/dev/null || { echo "trivy is required: brew install trivy"; exit 1; }
	docker build -t skiw-platform:scan .
	trivy image --severity HIGH,CRITICAL --exit-code 1 skiw-platform:scan

# Points git at .githooks (pre-push secret scan); one-time per clone. Needs gitleaks installed.
hooks:
	git config core.hooksPath .githooks

web-build: check-node
	pnpm -C web build

web-dev: check-node
	pnpm -C web dev

build: web-build
	docker compose build

.env:
	cp .env.example .env

dev: .env web-build
	docker compose up -d --wait db
	$(MAKE) migrate
	docker compose up --build

e2e: .env web-build
	docker compose up -d --wait db
	$(MAKE) migrate
	docker compose up -d --build --wait app
	pnpm -C web exec playwright test

db-up: .env
	docker compose up -d --wait db

migrate: .env
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py migrate
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py makemigrations --check --dry-run
	set -a; . ./.env; set +a; DATABASE_URL="$${MIGRATION_DATABASE_URL:?set MIGRATION_DATABASE_URL in .env}" uv run python app/manage.py lintmigrations --settings config.settings_migration_lint --warnings-as-errors --exclude-apps procrastinate --no-cache --quiet ignore

clean:
	docker compose down -v
