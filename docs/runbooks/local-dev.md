# Runbook — local development

Applies from M0a. Production deployment, rollback and restore runbooks arrive with M0d and M1.

## Prerequisites
- `uv` (installs Python 3.12 from `.python-version`), Docker with Compose, GNU make.
- Node 24.21.0 and pnpm 11 for the web shell. Use `fnm` (`fnm install` then `fnm use`; it reads `.node-version`). `make` refuses other Node majors (`make check-node`).
- First end-to-end run only: `pnpm -C web exec playwright install chromium`.

## First run
1. `make install` — creates `.venv` from `uv.lock` and installs the web packages from `pnpm-lock.yaml`.
2. `make dev` — builds the web shell, copies `.env.example` to `.env` if missing, builds the image, starts Postgres 17 and the app.
3. `curl http://127.0.0.1:8000/healthz` returns `ok` (HTTP 200); `http://127.0.0.1:8000/` shows the shell.

## Everyday commands
| Command | What it does |
|---|---|
| `make lint` | ruff, import-linter contracts, eslint |
| `make typecheck` | mypy (strict, django-stubs) and `tsc` |
| `make test` | pytest (no database needed) and vitest |
| `make web-build` / `make web-dev` | production build of the shell into `web/dist` / Vite dev server with `/healthz` and `/api` proxied to `:8000` |
| `make e2e` | builds the shell, starts Compose, runs Playwright on desktop and mobile widths (axe, keyboard, overflow, no-JS, console errors) |
| `make test-live` | starts the database, migrates as `skiw_migrator`, then runs the live role checks (the app connection must report `skiw_app`) |
| `make db-up` | starts only the database and waits until healthy |
| `make migrate` | runs migrations with `MIGRATION_DATABASE_URL` (`skiw_migrator`), then `makemigrations --check` |
| `make clean` | stops the stack and deletes the local database volume |

## Environment variables
All come from `.env` (copied from `.env.example`; never committed). The app fails to start if
`DJANGO_SECRET_KEY` or `DATABASE_URL` is missing.
- `DATABASE_URL` is the runtime URL and uses `skiw_app`. The `app` container and any host-run app or test use it (TEN-02).
- `MIGRATION_DATABASE_URL` uses `skiw_migrator`. Only `make migrate` reads it, and it injects it as `DATABASE_URL` for that one process (TEN-01).
- TLS: `DATABASE_URL` may carry `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, `sslcrl`; other options are rejected. Non-local deployments set `DJANGO_REQUIRE_DB_TLS=1`, which refuses any `sslmode` other than `verify-full` or `verify-ca`. Local values are placeholders, not secrets.

## Known local conflicts
- The database is published on host port **5433** (`SKIW_DB_PORT`), because 5432 is often taken by another local Postgres.
- The app is published on `127.0.0.1:8000`.

## Rebuilding the database roles
Roles are created only on the first start of an empty volume (`docker/postgres/10-roles.sh`). After changing it, run `make clean` and `make dev`.

## CI
`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`: install, lint, typecheck, unit tests (pytest and vitest), live database role checks (`make test-live` against a disposable Postgres), and the Playwright end-to-end tests (`make e2e`). Actions are pinned by commit SHA. The M0d PR extends this workflow (secret scan, dependency audit, image scan, web build stage in the image).
