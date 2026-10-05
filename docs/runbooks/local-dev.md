# Runbook — local development

Applies from M0a. Production deployment, rollback and restore runbooks arrive with M0d and M1.

## Prerequisites
- `uv` (installs Python 3.12 from `.python-version`), Docker with Compose, GNU make.
- Web tooling (`node`, `pnpm`) arrives with M0b.

## First run
1. `make install` — creates `.venv` from `uv.lock`.
2. `make dev` — copies `.env.example` to `.env` if missing, builds the image, starts Postgres 17 and the app.
3. `curl http://127.0.0.1:8000/healthz` returns `ok` (HTTP 200).

## Everyday commands
| Command | What it does |
|---|---|
| `make lint` | ruff check and format check, import-linter contracts |
| `make typecheck` | mypy (strict, django-stubs) |
| `make test` | pytest (no database needed in M0a) |
| `make db-up` | starts only the database and waits until healthy |
| `make migrate` | runs migrations as `skiw_migrator`, then `makemigrations --check` |
| `make clean` | stops the stack and deletes the local database volume |

## Environment variables
All come from `.env` (copied from `.env.example`; never committed). The app fails to start if
`DJANGO_SECRET_KEY` or `DATABASE_URL` is missing. The `app` container connects as `skiw_app`;
host-run commands connect as `skiw_migrator`. Local values are placeholders, not secrets.

## Known local conflicts
- The database is published on host port **5433** (`SKIW_DB_PORT`), because 5432 is often taken by another local Postgres.
- The app is published on `127.0.0.1:8000`.

## Rebuilding the database roles
Roles are created only on the first start of an empty volume (`docker/postgres/10-roles.sh`). After changing it, run `make clean` and `make dev`.
