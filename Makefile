.PHONY: install lint typecheck test test-live host-test host-test-live secrets-test build web-build web-dev e2e dev db-up migrate clean check-node audit secrets audit-python audit-web image-scan hooks

export PYTHONPATH := app:infra/host
NODE_MAJOR := $(shell node -p "process.versions.node.split('.')[0]" 2>/dev/null)
SEMGREP_VERSION := 1.179.0
PIP_AUDIT_VERSION := 2.10.1
TOOL_ENV := DJANGO_SECRET_KEY=tooling-only-not-a-secret DATABASE_URL=postgres://u:p@localhost:5432/db \
	SKIW_SESSION_ABSOLUTE_H=12 SKIW_SESSION_IDLE_MIN=30 \
	SKIW_ARGON2_MEMORY_KIB=65536 SKIW_ARGON2_TIME_COST=3 SKIW_ARGON2_PARALLELISM=1 \
	SKIW_AUTH_FAILS_PER_ACCOUNT=5 SKIW_AUTH_FAILS_PER_IP=20 SKIW_AUTH_WINDOW_MIN=15 \
	SKIW_AUTH_LOCK_AFTER=10 SKIW_AUTH_LOCK_MIN=30 SKIW_STEPUP_MAX_AGE_MIN=5 \
	SKIW_TOTP_SKEW_STEPS=1 SKIW_LOGIN_PENDING_MIN=5 SKIW_ENROL_LINK_MIN=30

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
	$(TOOL_ENV) uv run --locked mypy app infra/host scripts/deploy-prod
	pnpm -C web typecheck

test: check-node
	$(TOOL_ENV) uv run pytest
	pnpm -C web test

test-live: .env
	docker compose up -d --wait db
	$(MAKE) migrate
	set -a; . ./.env; set +a; uv run pytest -m live

# Host tooling tests (spec section 8.4) and the infra/host/compose.yml config tests. No Docker daemon
# needed; the Compose tests need the docker compose CLI (skip locally without it, fail when CI=true).
host-test:
	$(TOOL_ENV) uv run --locked pytest infra/host/tests

# Live host stack tests (needs a Docker daemon; skips locally without one, fails when CI=true):
# the edge through Caddy (M1c), the db role set and per-role network rules (M1e), EICAR through
# the pinned clamav image (M1i). Builds the app image; a throwaway Compose project per run.
host-test-live:
	$(TOOL_ENV) uv run --locked pytest -m host_live infra/host/tests app/documents/tests

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

# The local tenant_source_key and login_blob_key are generated, never committed (UNI-07; the
# gitleaks rule flags any literal value for them); an older .env without them:
# docs/runbooks/local-dev.md.
.env:
	cp .env.example .env
	printf 'TENANT_SOURCE_KEY=v1:%s\n' "$$(openssl rand -base64 32)" >> .env
	printf 'LOGIN_BLOB_KEY=v1:%s\n' "$$(openssl rand -base64 32)" >> .env

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
