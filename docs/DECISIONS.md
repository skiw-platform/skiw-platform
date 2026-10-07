# Decisions log

<!-- Committed. Newest at the top. One entry per decision. A settled decision is reopened only by the owner. -->

## 2026-10-07 — Brand colours and the reviewer environment
- **Decision:** (1) **Brand colours (owner, 2026-10-07, option A):** navy `#001C30` and gold `#FFB300`, read from https://www.skiwealth.com/ (home page CSS), on the Fernly-style layout. Navy is the primary (sidebar, brand text); gold is the active item and the skip link, always with navy text on it. Gold is never text on white (about 1.8:1) and never a focus ring on white: the focus ring is navy, and gold inside the navy sidebar. The earlier Doc2 lime is dropped. The site font (Poppins) is not adopted; the system font stack stays until the owner decides. Spec D2 wording is in PR 3 (spec v1.8). (2) **Reviewer environment (owner, 2026-10-06, PR 1 round 2, option A):** the reviewer needs a detached checkout and a working browser/Docker. Until that is fixed the reviewer uses an isolated local clone, and CI (`make test-live`, `make e2e`) is the independent runtime proof.
- **Why:** Owner choice; contrast rules A11Y-02 and FE-13 (tokens only in `web/src/styles.css`).
- **Alternatives rejected:** Doc2 lime `#D6E24A`; Fernly green (neutral placeholder used in M0b).
- **Scope / affects:** `web/src/styles.css`; spec D2 (PR 3).
- **Exception to a rule?** no
- **Decided by:** owner

## 2026-10-06 — M0b web shell: toolchain, serving, UI direction and confirmed M0 answers
- **Decision:** (1) **Owner answers confirmed 2026-10-06:** Node 24 (LTS; `.node-version` and `engines` pin 24.21.0, `engineStrict`, `make check-node`; local switching with `fnm`, CI via `actions/setup-node` reading `.node-version`); UI language English, `<html lang="en-MY">`; ASK-1 option (a) (Procrastinate Django integration, synchronous `.defer()` on the Django connection, spec D5 revised to v1.8 and sent to spec review before M0c merges; M0c tests must prove commit and rollback include the job in the same transaction); ASK-6 option (b) (app and worker run as `skiw_app` from M0; M0c adds the queue grants; no TEN-02 exception). (2) **Web stack pins:** React 19.3.0, Vite 8.3.2, @vitejs/plugin-react 6.1.1, TypeScript 6.0.3 (not 7.x: typescript-eslint 8.71.0 peers `<6.1`), eslint 10.12.0 + typescript-eslint 8.71.0 (strictTypeChecked) + eslint-plugin-react-hooks 7.1.1, vitest 5.0.3 + jsdom 30.1.2 + @testing-library/react 16.3.3, @playwright/test 1.63.0 + @axe-core/playwright 4.13.0 (axe in the browser test is required by A11Y-06), @types/node 24.19.1 (Playwright config reads `process.env`), pnpm 11.6.0. (3) **Serving:** Django serves the Vite build same-origin (spec D2): `/` renders a template from `web/dist/.vite/manifest.json`; `/assets/<path>` uses Django's `serve` rooted at `web/dist/assets` with `Cache-Control: max-age=31536000, immutable` (hashed names; traversal is rejected with 400/404). No WhiteNoise: it is a new dependency and its middleware must be async-capable (D26); edge caching comes with M1. The production image does not yet contain `web/dist`; M0d adds the web build stage (Compose mounts `web/dist` for now). (4) **UI direction (owner, 2026-10-06):** follow the look and interaction of the Fernly dashboard demo (https://demo.codeandchill.store/fernly/#dashboard): soft grey-green page background, white large-radius cards, left sidebar with a pill-shaped active item, top bar, forest-green primary, calm spacing. That demo is a paid third-party template: it is a visual reference only; no code, CSS, icons or images are copied, and the Fernly name and logo are not used. Tokens are our own (`web/src/styles.css`). The earlier Doc2 visual language (lime brand, Fraunces) and spec D2's "tokens from the SK iWealth design system" are superseded for visuals by this direction; Doc2's information architecture is not yet adopted (M0b shell has one "Today" link). **Open for the owner:** does the SK iWealth brand colour override the Fernly green, and which Doc2 sections are in scope? Spec D2 wording needs a revision once answered.
- **Why:** Plan `docs/plans/2026-10-05-m0-scaffold.md` M0b; owner confirmations and the UI direction given on 2026-10-06.
- **Alternatives rejected:** `pnpm` `useNodeVersion`/`executionEnv` (did not switch the runtime in pnpm 11.6.0). Node 26 (Current, not LTS until 2026-10-28). WhiteNoise. Copying the Fernly template (licence).
- **Scope / affects:** `web/`, `pnpm-workspace.yaml`, `package.json`, `.node-version`, `app/shell/`, `app/config/{settings,urls}.py`, `Makefile`, `docker-compose.yml`, `.github/workflows/ci.yml` (web and end-to-end jobs pulled forward from M0d), `docs/runbooks/local-dev.md`; rules FE-01/05/06/07/13/14/32/40/50/51/60/70, A11Y-01/02/06, UNI-06/14.
- **Versions:** as listed; actions `pnpm/action-setup` v6.1.0 (`ea17c68d…`), `actions/setup-node` v7.0.0 (`82076278…`).
- **Exception to a rule?** no
- **Decided by:** owner (answers, UI direction); builder (pins, serving approach)

## 2026-10-06 — Minimal CI pulled forward into PR 1 (live role checks)
- **Decision:** PR 1 carries a minimal GitHub Actions workflow (`.github/workflows/ci.yml`): install, lint, typecheck, unit tests, `make test-live` (disposable Postgres via Compose, `make migrate` as `skiw_migrator`, then tests that the real Django app connection reports `current_user = skiw_app`, that `skiw_app` is not superuser/BYPASSRLS and cannot create objects, and that `skiw_migrator` owns the database and schema and can), and a Compose `/healthz` smoke test. Pytest marker `live` is excluded from `make test` by default. M0d extends this workflow instead of replacing it.
- **Why:** PR 1 review Rounds 2–4 stayed Blocked only because the reviewer's sandbox cannot run Docker or Postgres, so TEN-02 (hard) had no independent runtime proof. The owner chose option B (CI at the exact head) on 2026-10-06. Also records the owner decision (option A) to give the reviewer a checkout-capable environment; this CI is the independent evidence either way.
- **Alternatives rejected:** Accepting the builder's local runs as the proof (not independent). Waiting for M0d (blocks M0a).
- **Scope / affects:** `.github/workflows/ci.yml`, `Makefile` (`test-live`), `pyproject.toml` (marker), `app/tests/test_live_db_roles.py`, `docs/runbooks/local-dev.md`; rules UNI-13, UNI-14, TEN-01, TEN-02.
- **Versions:** `actions/checkout` v7.0.1 (`3d3c42e5aac5ba805825da76410c181273ba90b1`), `astral-sh/setup-uv` v10.2.0 (`c18668ad3cf93ea998bef934396af7bb5c839dc7`), uv 0.11.24; GitHub-hosted runner pinned to the explicit label `ubuntu-24.04` (changed from `ubuntu-latest` after PR 1 review Round 5, UNI-14); bump it deliberately in a reviewed change when moving to a newer Ubuntu.
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

