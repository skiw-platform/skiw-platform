# Decisions log

<!-- Committed. Newest at the top. One entry per decision. A settled decision is reopened only by the owner. -->

## 2026-10-06 — Minimal CI pulled forward into PR 1 (live role checks)
- **Decision:** PR 1 carries a minimal GitHub Actions workflow (`.github/workflows/ci.yml`): install, lint, typecheck, unit tests, `make test-live` (disposable Postgres via Compose, `make migrate` as `skiw_migrator`, then tests that the real Django app connection reports `current_user = skiw_app`, that `skiw_app` is not superuser/BYPASSRLS and cannot create objects, and that `skiw_migrator` owns the database and schema and can), and a Compose `/healthz` smoke test. Pytest marker `live` is excluded from `make test` by default. M0d extends this workflow instead of replacing it.
- **Why:** PR 1 review Rounds 2–4 stayed Blocked only because the reviewer's sandbox cannot run Docker or Postgres, so TEN-02 (hard) had no independent runtime proof. The owner chose option B (CI at the exact head) on 2026-10-06. Also records the owner decision (option A) to give the reviewer a checkout-capable environment; this CI is the independent evidence either way.
- **Alternatives rejected:** Accepting the builder's local runs as the proof (not independent). Waiting for M0d (blocks M0a).
- **Scope / affects:** `.github/workflows/ci.yml`, `Makefile` (`test-live`), `pyproject.toml` (marker), `app/tests/test_live_db_roles.py`, `docs/runbooks/local-dev.md`; rules UNI-13, UNI-14, TEN-01, TEN-02.
- **Versions:** `actions/checkout` v7.0.1 (`3d3c42e5aac5ba805825da76410c181273ba90b1`), `astral-sh/setup-uv` v10.2.0 (`c18668ad3cf93ea998bef934396af7bb5c839dc7`), uv 0.11.24; GitHub-hosted `ubuntu-latest` runner (not pinned to an image version).
- **Exception to a rule?** no
- **Decided by:** owner (option B)

## 2026-10-06 — Runtime vs migration database URLs and TLS options (PR 1 review R1)
- **Decision:** `DATABASE_URL` is always the runtime URL (`skiw_app`); migrations use a separate `MIGRATION_DATABASE_URL` (`skiw_migrator`) that `make migrate` injects as `DATABASE_URL` for that one process only. The URL parser keeps the libpq TLS options `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, `sslcrl` in Django `OPTIONS`, rejects any other option, repeated options and invalid `sslmode` values, and with `DJANGO_REQUIRE_DB_TLS=1` accepts only `sslmode=verify-full` or `verify-ca`. Non-local deployments must set that flag.
- **Why:** PR 1 review Round 1 findings P1-1 (TEN-01/02: a host-run app must not run as the schema owner) and P1-2 (spec D4: TLS options were silently dropped).
- **Alternatives rejected:** Keeping one `DATABASE_URL` and documenting the role (still lets a host-run app use the migrator). Passing the whole query string to libpq (would allow arbitrary connection options).
- **Scope / affects:** `.env.example`, `Makefile`, `docs/runbooks/local-dev.md`, `app/config/env.py`, `app/config/settings.py`, `app/tests/test_database_url.py`; rules TEN-01, TEN-02, UNI-03, spec D4. Still open: a staging connection check that proves the live connection is TLS-protected, due before the M1 deploy.
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** builder, following reviewer findings

## 2026-10-05 — M0a Python toolchain, pins and local database roles
- **Decision:** Python 3.12 (local 3.12.13; image `python:3.12.15-slim`), Django 5.2.17 (LTS, ASGI only, no `wsgi.py`), psycopg 3.3.6, gunicorn 26.2.0 + uvicorn 0.54.0 + uvicorn-worker 0.4.0. Dev tools: mypy 1.19.1 + django-stubs/-ext 5.2.9 (mypy stays below 1.20 because django-stubs 5.2.9 requires it; mypy 2.x not used), ruff 0.16.10, import-linter 2.15, pytest 9.1.1, pytest-django 4.14.0; `aws-cdk-lib` 2.272.0 in the `infra` group (used from M0d). uv 0.11.24. Base images pinned by digest: `python:3.12.15-slim@sha256:02108f5d…`, `ghcr.io/astral-sh/uv:0.11.24@sha256:99ea34ac…`, `postgres:17.11@sha256:d74eeac9…`. Settings read the environment through one helper (`config/env.py`, no `django-environ`) and fail closed when `DJANGO_SECRET_KEY` or `DATABASE_URL` is missing. Local Postgres creates the roles `skiw_migrator` (schema owner) and `skiw_app` (NOSUPERUSER, NOBYPASSRLS); grants and RLS arrive with M4. The `app` container connects as `skiw_app`; `make migrate` runs as `skiw_migrator`. The local database is published on host port 5433 (5432 is used by another local project).
- **Why:** Spec D1/D4/D16 and plan `docs/plans/2026-10-05-m0-scaffold.md`. A small env helper avoids a dependency (UNI-06). Versions were checked against PyPI and the tags/digests against the registries on 2026-10-05.
- **Alternatives rejected:** `django-environ` (new dependency for ~40 lines). mypy 2.x (incompatible with django-stubs 5.2.9). Unpinned image tags (T17).
- **Scope / affects:** `pyproject.toml`, `uv.lock`, `Dockerfile`, `docker-compose.yml`, `docker/postgres/10-roles.sh`, `app/`; rules UNI-06, UNI-07, TEN-01/02, TEN-10.
- **Versions:** as listed above.
- **Exception to a rule?** no (the app role is non-superuser and non-bypass from M0a; there are no tables yet, so no grants are needed)
- **Decided by:** builder, within the owner-approved M0 plan

## 2026-10-05 — New platform repo created: charliekhc/skiw-platform (private)
- **Decision:** The new platform repo is `https://github.com/charliekhc/skiw-platform`, private, created under the owner's personal GitHub account `charliekhc` (the `apiskiw` account was not used because the builder cannot create repos there). Local repo initialised on `main` with `origin` set. Nothing pushed yet.
- **Why:** Owner chose option A (create now, personal account first). The old repo stays reference only.
- **Alternatives rejected:** Creating under `apiskiw` (no access to create there). Building inside the old repo.
- **Scope / affects:** `agents/PROJECT.md` §4 Remote; log branch `agent-logs` is created on this remote by the first `merged <number>`. Moving the repo to an org later is the owner's call.
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** owner

## 2026-10-05 — Setup field values and REC-12 ruling for form PDFs
- **Decision:** (1) Owner name is Ying. (2) Durable notes path = `none`. (3) Admin transaction helper is named `with_admin_operation`; action wrapper is named `authorized_action`; both are implemented in M3/M4. (4) Agent tool folders never committed = `none` beyond `.agent/`; exclude specific local state or secrets under `.claude/` or `.codex/` individually if they appear. (5) Commit trailer = `none`. (6) REC-12 ruling: saved form data may persist; a draft PDF preview is watermarked and temporary; the final PDF is stored when issued or signed. This replaces "decide per PR".
- **Why:** The spec names no concrete helper or wrapper; naming them now fixes the contract for M3/M4. A fixed Sonnet trailer is wrong when other models commit. A standing REC-12 rule avoids deciding it again in every PR.
- **Alternatives rejected:** Blanket ban on `.claude/` and `.codex/` (could hide useful project config). A fixed Sonnet commit trailer. Per-PR REC-11/12 decisions.
- **Scope / affects:** `agents/PROJECT.md` §2, §4, §8, §9, §10; spec §4.1 `form_instance`, M16 form filling (draft preview vs stored final PDF; M16's byte-compare test must use the final PDF, not a watermarked preview).
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** owner

## 2026-10-05 — New platform gets a new repo; old repo is reference only
- **Decision:** The new platform is built in a new repository. `https://github.com/apiskiw/skiw-assistant` (private, default branch `main`) is the old app. It is read-only reference. Do not clone it. Do not copy code from it unless the owner asks. Read single files with `gh api` only when a spec or review needs a fact.
- **Why:** The old app is live and used daily. A new repo avoids a deploy accident and gives a clean start.
- **Alternatives rejected:** Build inside the old repo.
- **Scope / affects:** `agents/PROJECT.md` §4 Remote stays `pending remote` until the owner creates the new repo.
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** owner

