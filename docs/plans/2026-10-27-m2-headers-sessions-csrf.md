# Plan — M2 security headers, sessions and CSRF

- Spec section: §9 M2 (also D6, D26 (1), §4.1 `django_session` row, §4.2 TEN-10 and TEN-11 rows, §4.2 "Tenant binding" item 1, T6, §8.1 `session.*` row, §8.4 H1 `caddy` row, H4 inventory, H14 UNI-17 row, Flow 5.1 step 3, Appendix A.19) · spec v1.20, hash `92841ba5` (`92841ba555e9e857ac70e86a5b043cf9729ed371`, review Round 23 Approved, PR 66 merged 2026-10-25; equals **Spec hash at last reconcile** in `agents/PROJECT.md` §2) · Milestone: M2 · Target LOC: ≤ 400 per PR (generated files excluded)
- Author: Builder (deep tier), 2026-10-27. Django facts read from the installed Django **5.2.17** source in `.venv/lib/python3.12/site-packages/django/` on 2026-10-27 (marked [V]). Anything not read is marked [A].
- **Status (2026-10-27):** nothing of M2 is built. `MIDDLEWARE` is empty (`app/config/settings.py`). No `accounts` app exists. No app code reads `tenant_source_key` yet; `infra/host/compose.yml` already mounts it into `web` and `worker` (`x-app-secrets`), and `bootstrap-secrets` already mints it (`infra/host/skiw_host/secrets.py:45`). M1a–M1j are merged. M1k waits for the bought VPSs.

## Steps

### Gate before any code (builder §8)

M2 is the first PR of a new milestone and adds a new module (`accounts`). The owner's yes is needed before M2a starts. The owner said "m2" on 2026-10-27; this plan is what that yes covers. The four owner questions are under Risks → "Owner questions". Only Q1 blocks M2a. Q2 (answered) is built in M2b; Q4 blocks M2d. Q3 blocks only the "done" claim of M2.

### Does M2 depend on M1k (a real host)?

No, if the owner accepts Q3 (a). All M2 code is built and tested in CI.

The done-when item "session survives a redeploy and a restart of the one `web` container" (§9 M2) is proved in CI by `make host-test-live`. That target already builds the app image and runs `infra/host/compose.yml` with `env/ci.env` behind Caddy, with secrets generated per run (DECISIONS 2026-10-14 M1c). M2d adds a restart case and a redeploy case there (see M2d below).

What the CI proof does not cover: the real host disk, and the real `skiw-deploy` switch with its state file. M1g's switch is "`SKIW_IMAGE` in the state file, `docker compose up -d`" (M1 plan §3 M1g step 6), which is the same Compose action the CI test runs. So M2 adds one line to the M1k evidence list: repeat the restart and redeploy cases on staging.

### PR split (four PRs; spec §9 allows "1–4 PRs" per milestone)

| PR | Branch | Needs | Scope | Acceptance test (spec quote) | LOC est. |
|---|---|---|---|---|---|
| M2a | `feat/m2a-security-headers` | CI, Q1 | `SecurityMiddleware`, own CSP nonce middleware, nonce on the shell `<script>`, `frame-ancestors 'none'`, `X-Frame-Options`, HSTS equal to Caddy's, `no-store` shell, async-capable middleware test, `check --deploy` test, edge test re-run | "Header assertion tests (UNI-17/18) pass" (UNI-17 half) | ≈ 280 |
| M2b | `feat/m2b-hashed-session-store` | CI | `accounts` app, own session model on table `django_session`, grant migration, `accounts.session.SessionStore` with the hashed key (sync and async) and a fixed absolute expiry, lifetime settings and their wiring, `SessionMiddleware`, `__Host-skiw_session` cookie, import-linter contract | "the stored session key ≠ cookie value"; UNI-18 for the session cookie; D6 absolute lifetime does not slide | ≈ 420 (a justified small overage; 400 is an approximate target in PROJECT §4, and the four-PR maximum in spec §9 wins; there is no fifth PR) |
| M2c | `feat/m2c-session-hmac` | CI | key-bound HMAC under `tenant_source_key` in `session_data`, versioned key reader, `TENANT_SOURCE_KEY_FILE` wiring, web start-up check, runbook | "a row with edited data, or data copied from another row, is rejected (logged out)" | ≈ 330 |
| M2d | `feat/m2d-csrf-and-redeploy-proof` | CI, Q4 (Q3 for "done") | `CsrfViewMiddleware`, `__Host-` CSRF cookie, token in the shell, `route()` registration, fixtures and behaviour gate, no-`csrf_exempt` rule, live restart and redeploy proof | "session survives a redeploy and a restart of the one `web` container"; T6 "Django CSRF on all mutating routes (no `CSRF_ENFORCE` switch)" | ≈ 380 |

Order and dependencies:
- M2a goes first. M2b does not need its code, but both edit `MIDDLEWARE`, and the async-capable test (M2a) should exist before more middleware arrives.
- M2c needs M2b (it changes the M2b store).
- M2d needs M2a (it adds the CSRF token to the nonce shell and removes the M2a `security.W003` exception) and M2c (the live proof runs the final store).
- Between M2b and M2c merging, sessions carry no MAC. No production code writes a session in that window (no login until M3), so no real session exists. M2c must merge before M3 starts.

### M2a — `feat/m2a-security-headers` (CI)

Files:
- `app/shell/csp.py` (new, ≈ 50 lines). One middleware, sync and async capable. Per response it makes a fresh nonce (`secrets.token_urlsafe(16)`, 128 bits). It sets on **every** Django response exactly the T6 policy: `default-src 'self'; script-src 'nonce-<n>' 'strict-dynamic'; object-src 'none'; frame-ancestors 'none'`. It exposes `nonce(request) -> str` for the shell view. It lives in `shell` because the shell is the only HTML producer; `config` references it only by string in `MIDDLEWARE` (the import-linter contract "Apps do not reach into config internals" stays as it is).
- `app/config/settings.py`: `MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "shell.csp.ContentSecurityPolicyMiddleware"]`. `SECURE_HSTS_SECONDS = 31_536_000` with the include-subdomains and preload flags set per Q1. `SECURE_SSL_REDIRECT` stays `False` (Caddy owns the redirect; the internal `/readyz` probes use plain HTTP). `X_FRAME_OPTIONS = "DENY"` is the Django default [V `conf/global_settings.py:447`]; it is kept for older browsers and does not replace `frame-ancestors`.
- `app/shell/views.py` + `app/shell/templates/shell/shell.html`: `nonce="{{ nonce }}"` on the module `<script>`. The shell response gets `Cache-Control: no-store`, so a cached page never reuses a nonce. The `<link rel="icon" href="data:,">` is replaced (see Risk 3).
- `app/tests/test_middleware_async.py` (new): every `settings.MIDDLEWARE` entry has `async_capable = True` (spec D26 (1): "CI test asserts `async_capable=True` for each"). M2 is the first PR that fills `MIDDLEWARE`, so the test starts here.
- `app/tests/test_deploy_checks.py` (new): runs `manage.py check --deploy --fail-level WARNING` with production-like env. Allowed IDs, each with its reason in the test: `security.W008` (no SSL redirect in Django; Caddy redirects) [V `core/checks/security/base.py:81`]; `security.W005` and `security.W021` (no includeSubDomains / preload) only if Q1 = (a); `security.W003` (no CSRF middleware) **until M2d**, which removes it.
- `app/shell/tests/test_security_headers.py` (new): the header tests listed under Tests.
- `web/e2e/shell.spec.ts`: listen for `securitypolicyviolation` in the page and fail on any. The existing "no console errors or page errors" test stays.
- `infra/host/tests/test_edge_live.py`: extend `test_app_page_carries_hsts_once` so the app page through Caddy also carries exactly one CSP header and one HSTS header, both with the expected values.
- `docs/DECISIONS.md`: M2a entry. It updates the M1c "where each header is applied" record (UNI-17): CSP, `frame-ancestors`, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, COOP — Django; HSTS — Caddy and Django, same value, one header on the wire. No new dependency: Django 5.2 has no CSP middleware [V: `django/middleware/` holds `cache, clickjacking, common, csrf, gzip, http, locale, security` only], and an own middleware of ≈ 50 lines beats `django-csp` on the UNI-06 ladder.

### M2b — `feat/m2b-hashed-session-store` (CI)

Facts this PR rests on [V, Django 5.2.17 source]:
- `contrib/sessions/base_session.py:28`: `session_key = models.CharField(max_length=40, primary_key=True)`. A SHA-256 hex digest is 64 characters, so it does not fit Django's model.
- `contrib/sessions/middleware.py` `process_request`: `SessionStore(request.COOKIES.get(SESSION_COOKIE_NAME))` — the raw cookie goes into the store. `process_response` sets the cookie to `request.session.session_key`. So the store keeps the raw value in memory and must hash it at every database touch.
- `contrib/sessions/backends/db.py`: the model is touched by `_get_session_from_db`, `_aget_session_from_db`, `exists`, `aexists`, `create_model_instance`, `acreate_model_instance`, `save`/`asave` (through the instance's primary key), `delete`, `adelete`, `clear_expired`, `aclear_expired`.
- `contrib/sessions/backends/base.py`: `cycle_key`/`acycle_key` call `create()` and then `delete(<old raw key>)`; `_get_new_session_key` calls `exists(<raw key>)`; new keys are 32 characters from `VALID_KEY_CHARS` (lower-case letters and digits, ≈ 165 bits), so an unsalted SHA-256 of the cookie is not guessable.
- `contrib/sessions/base_session.py` `BaseSessionManager.save()` writes a raw key and bypasses the store. It must never be used.

Files:
- `app/accounts/__init__.py`, `apps.py`, `models.py` (imports the model below so Django finds it), `session_model.py`: model `Session(AbstractBaseSession)` with `session_key = CharField(max_length=64, primary_key=True)` and `Meta.db_table = "django_session"` (the name in the closed global-table list, spec §4.1). `get_session_store_class()` returns `accounts.session.SessionStore`.
- `app/accounts/migrations/0001_session.py`: `CreateModel`, then `RunSQL` that grants `SELECT, INSERT, UPDATE, DELETE ON django_session TO skiw_app` and nothing else. There are no default privileges (`infra/host/db/roles.sql` grants only `CONNECT`), so the grant must be explicit. DELETE is needed: D6 "Revocation is a row delete"; `flush` and `cycle_key` delete. No TRUNCATE. Reverse: revoke and drop. `django.contrib.sessions` is **not** added to `INSTALLED_APPS`: its `0001_initial` would create a clashing `django_session` table.
- **Absolute lifetime that cannot slide (spec D6, owner Q2).** Facts [V, Django 5.2.17 `backends/base.py`]: with no fixed datetime set, `get_expiry_date()` returns `now + SESSION_COOKIE_AGE`, so every save moves the deadline; an integer given to `set_expiry()` is an inactivity duration. So the store does not use Django's expiry settings for the deadline. It keeps one private attribute `_absolute_expiry` (UTC datetime). **Call order [V]:** `SessionMiddleware.process_response()` calls `get_expiry_age()` for a modified non-empty session **before** it calls `save()`, so on a first response no row exists yet. The store therefore has one idempotent private method `_ensure_deadline()` (sync, with an async twin only if it does I/O; it does none). It sets `_absolute_expiry = now + SKIW_SESSION_ABSOLUTE_H` hours if the attribute is unset, and otherwise returns the existing value. `get_expiry_date()`, `get_expiry_age()` and `create_model_instance()` / `acreate_model_instance()` all call it, so the cookie deadline and the row's `expire_date` are the same value, made once. `load` sets `_absolute_expiry` from the row's `expire_date` (so a loaded store never makes a new one). Every later `save` writes the same value; it never recomputes it. `get_expiry_date()` and `get_expiry_age()` return values from `_absolute_expiry`, so the cookie `Expires`/`Max-Age` that `SessionMiddleware` sets is the original deadline too. `set_expiry()` raises (no caller may move the deadline), and `SESSION_SAVE_EVERY_REQUEST` stays `False`. A row whose `expire_date` is already past is treated as absent in `load`, and the middleware deletes the cookie. **Two different events, two rules [V: Django's `cycle_key`/`acycle_key` keep the same store object and its data, then call `create()`, so a custom attribute survives].** (a) *Key rotation* (`cycle_key`/`acycle_key`, including a later rotation after a privilege change, D6) **preserves** `_absolute_expiry`: the new row gets the old deadline, so rotating again and again cannot renew the session. (b) *A new authentication* resets it: the store has an explicit `start_new_lifetime()` (sync and async twins; it clears `_absolute_expiry` so `_ensure_deadline()` makes a fresh `now + SKIW_SESSION_ABSOLUTE_H`). Only M3's successful-login code calls it, immediately before `login()`'s `cycle_key()`; no other code path may call it (a Semgrep rule restricts the call to `accounts` login code from M3). `flush` deletes the row. M3's idle timeout composes with this: the session is valid only while `now < _absolute_expiry` **and** `now - last_activity < idle`; the idle rule can only shorten a session, never extend it past the absolute deadline.
- `app/config/settings.py` also: `SKIW_SESSION_ABSOLUTE_H` and `SKIW_SESSION_IDLE_MIN` read through one validator in `app/config/env.py`, required, integers, 1 ≤ absolute ≤ 72 and 1 ≤ idle ≤ 1440 (the bounds are builder values [A]), else `ImproperlyConfigured` naming the variable and never echoing the input (UNI-03, UNI-16). The spec values are 12 and 30 (§8.1 `session.absolute_h`, `session.idle_min`). M5 moves both into `setting` by a reviewed PR.
- **Wiring of the two required variables into every context that imports settings** (a missing value is a startup failure, so each of these must carry it): `infra/host/env/{staging,production,ci}.env`; `.env.example`; `Makefile` `TOOL_ENV` (lint, typecheck, unit and host tests import settings under it); `docker-compose.yml` `app` and `worker` `environment:` (and any other service that imports Django settings); `.github/workflows/ci.yml` `env:` of the "Label image" step (the `migration_labels` container, which runs with `-e` only for named variables, so the two names are added to its `-e` list); `infra/host/compose.yml`: the two names go in `x-app-env` for `web` and `worker`, and are added **separately** to `migrate.environment` (`migrate` imports settings too). `migrate` must not take `x-app-env`, because that anchor carries the `skiw_app` `DATABASE_URL` and `DATABASE_PASSWORD_FILE`; `migrate` keeps its own `skiw_migrator` URL and password file (TEN-01, TEN-02, PROJECT §9). An alternative is a credential-free common anchor; either way no role mapping changes; the `test_edge_live.py` generated override if it does not read `ci.env`. `docs/runbooks/local-dev.md` and `docs/runbooks/host-rebuild.md` name both variables (UNI-16).
- `app/accounts/session.py`: `SessionStore(db.SessionStore)`. One private function `stored_key(raw) = sha256(raw).hexdigest()`. It overrides every method in the list above, sync and async, so the database only ever sees `stored_key(raw)`. It validates the raw key at the boundary (exactly 32 characters from `VALID_KEY_CHARS`; anything else is treated as no session, UNI-03). `get_model_class()` returns `accounts.session_model.Session`.
- `app/config/settings.py`: `INSTALLED_APPS += ["accounts"]`; `SessionMiddleware` after `SecurityMiddleware`; `SESSION_ENGINE = "accounts.session"`; `SESSION_COOKIE_NAME = "__Host-skiw_session"`; `SESSION_COOKIE_SECURE = True`; `SESSION_COOKIE_HTTPONLY = True`; `SESSION_COOKIE_SAMESITE = "Strict"`; `SESSION_COOKIE_PATH = "/"`; `SESSION_COOKIE_DOMAIN = None` (the `__Host-` prefix needs Secure, `Path=/` and no `Domain`) (spec D6).
- `pyproject.toml` import-linter: add `accounts` to the root packages and to the layers and independence contracts; a forbidden contract so that no package other than `accounts` imports `accounts.session` or `accounts.session_model` (TEN-10 allow-list: "Only `accounts.session` touches it", §4.1). `accounts.models` is left open on purpose: M3 puts the user models there, and other apps must import them.
- `semgrep/sessions-store-only.yml` + fixture: rejects `Session.objects` use and raw SQL strings naming `django_session` outside `app/accounts/session.py`, `app/accounts/session_model.py`, the `accounts` migrations and `app/accounts/tests/` (the live tests change rows by SQL on purpose).
- Tests: see Tests.
- `docs/DECISIONS.md`: M2b entry (own session model and why; hash format `sha256(cookie).hexdigest()`, which `auth_stepup.session_key_hash` and `outbox_approval.session_key_hash` reuse later; grants).

### M2c — `feat/m2c-session-hmac` (CI)

Design (spec §4.1 `django_session` row: "`session_data` carries an HMAC under `tenant_source_key` bound to that stored key"):
- `session_data` = `v<n>:<mac>:<django-signed blob>`. `mac = HMAC-SHA-256(tenant_source_key v<n>, "skiw-session-v1" ‖ len-prefixed(stored_key) ‖ len-prefixed(expire_date as UTC ISO-8601 to the microsecond) ‖ len-prefixed(blob))`, base64url. The fixed label separates this use of the key from its other uses (`bridge_session.row_mac`, job `args_mac`) [A — label value is a builder choice].
- The newest key version signs; every listed version verifies (spec §8.4 H4: "the newest mints or encrypts, every listed one verifies or decrypts").
- `expire_date` is part of the MAC (Risk 7). `load()` reads the row's `expire_date` and verifies with it; a row whose `expire_date` was edited fails. `save()` computes the MAC with the `expire_date` it writes. A test edits `expire_date` by SQL and expects logged out.
- Verify with `hmac.compare_digest`. On failure, or an unknown version, or a malformed prefix, `load()` returns `{}` and clears `_session_key`, the same as Django's not-found path in `_get_session_from_db` [V `backends/db.py`]. So a new key is minted on the next save, and the tampered row is never updated in place. The response then deletes the cookie (`middleware.py` deletes it when the session is empty) — this is "rejected (logged out)".
- One log line at warning level on `django.security.SuspiciousSession`, with no key, cookie, MAC or session content (UNI-09). The `security_event` table is M3.

Files:
- `app/config/env.py`: a `versioned_keys(name) -> list[tuple[int, bytes]]` reader that shares the line parser with `key_versions` (which today drops the version numbers). `TENANT_SOURCE_KEY_FILE` on hosts; `TENANT_SOURCE_KEY` (same `v<n>:<base64>` lines) for local and CI; both set → fail; fewer than 32 bytes → fail (the existing `MIN_KEY_BYTES`).
- `app/accounts/session.py`: encode and verify as above. The key is read lazily on first use, not at settings import, because the `migrate` service does not mount `tenant_source_key` (spec §8.4 H4 inventory: `web`, `worker` only; `infra/host/compose.yml` `migrate.secrets`).
- `app/config/asgi.py`: at start-up, before `require_migrated()`, call `accounts.session.require_key()`, which loads the key once and refuse to serve if it is missing or malformed (fail closed). `migrate` never runs `asgi.py`.
- `infra/host/compose.yml` `x-app-env`: `TENANT_SOURCE_KEY_FILE: /run/secrets/tenant_source_key`. `infra/host/tests/test_compose_config.py`: the variable is set for `web` and `worker` only, and is a `*_FILE` path.
- `docker-compose.yml` (local `app`, `worker`), `.env.example` (placeholder line, not a secret), `Makefile` `TOOL_ENV`, `.github/workflows/ci.yml` env: the local and CI value.
- `infra/host/tests/test_edge_live.py` generated override: no change needed. `write_secrets` already writes `v1:` + base64 of 32 random bytes for every secret whose name does not end in `_password` [V `test_edge_live.py:121-124`], so `tenant_source_key` passes the new reader.
- `docs/runbooks/host-rebuild.md` (rotation section) and `docs/runbooks/local-dev.md`: rotating `tenant_source_key` logs every user out unless the old version stays listed until sessions expire (UNI-16).
- `docs/DECISIONS.md`: M2c entry.

### M2d — `feat/m2d-csrf-and-redeploy-proof` (CI; Q4)

Files:
- `app/config/settings.py`: `CsrfViewMiddleware` after `SessionMiddleware`. CSRF cookie per Q4 (a): `CSRF_COOKIE_NAME = "__Host-csrftoken"`, Secure, HttpOnly, SameSite=Strict, `Path=/`, no `Domain` (T6 "cookies `__Host-`, Secure, HttpOnly, SameSite=Strict"). `CSRF_USE_SESSIONS = False`. `CSRF_FAILURE_VIEW = "config.csrf.failure"` (returns 403 with the header `X-Skiw-Csrf: rejected`; the gate relies on it). `CSRF_COOKIE_AGE = None` (browser-session cookie) [A — builder value; spec gives none; A.19 names a "CSRF cookie lifetime incident"]. No `CSRF_TRUSTED_ORIGINS` (same origin, D2).
- `app/shell/views.py` + template: `<meta name="csrf-token" content="{{ csrf_token }}">` in the `no-store` shell. The SPA sends it as `X-CSRFToken` from M3 on.
- **CSRF route registration and gate.** The gate is a behaviour test with a mechanically complete inventory, not a `csrf_exempt` scan. Django 5.2.17 keeps no accepted-method list per URL pattern (`URLPattern` has no method metadata; `require_http_methods()` does not record its list) [V], so the project records it in production code:
  - `app/config/routes.py` (new, ≈ 40 lines): `route(path, view, *, name, methods, auth)` is the only way a plain Django view is added to a URLconf (a semgrep rule rejects `path(` / `re_path(` outside it). It wraps the view in `require_http_methods(methods)` and sets `view.skiw_methods` and `view.skiw_auth` (`"cookie"` or `"token"`). Dispatch and the test read the same attribute, so the test is not the source of the method list. A URL pattern whose callable has no `skiw_methods` is a failure unless it is a django-ninja operation.
  - **django-ninja routes:** discovered from the router objects (path operations carry `methods`, path and auth classes).
  - `app/tests/csrf_fixtures.py`: only request *fixtures* per route name (`path_kwargs`, minimal `body`, an authenticated session). It holds no method or auth data.
  - **Completeness check:** walk the URL conf and the ninja routers. The set of (name, method) pairs, from `skiw_methods` and the ninja operations, is partitioned into safe (GET, HEAD, OPTIONS) and mutating. CI fails on: a callable without `skiw_methods`, an unresolved path parameter, a duplicate (name, method), a missing fixture, a mutating pair that is not a cookie-auth case and not in the reviewed `TOKEN_AUTH_ROUTES` list, and a `TOKEN_AUTH_ROUTES` entry that answers 2xx to a request with only a session cookie.
  - **Cases:** *Cookie-auth mutating pair:* valid session and valid token (`X-CSRFToken` with the matching cookie) → the handler's own outcome (success, or the expected 400/422); no token, wrong token, and valid token with a cross-site `Origin` → refused **by CSRF specifically**. To tell a CSRF refusal from any other 403, `CSRF_FAILURE_VIEW` is a project view that returns 403 with the header `X-Skiw-Csrf: rejected` and the Django reason code; the test requires that header. *Safe plain route:* for each unsafe verb not in `skiw_methods`, send a valid token and a fully authenticated fixture and require **405** (a verb the view does not accept is shown to be refused by the view, not by CSRF).
  - `TOKEN_AUTH_ROUTES` (bearer or API token, no cookie) starts empty; each entry needs the route, the reason and a reviewer sign-off in the PR.
  - **Planted-regression proof (in the M2d PR body):** (1) change an existing safe plain route so it also accepts a parameterised `PATCH`, without touching the fixtures: show `(route, PATCH)` now appears in the discovered set and that its valid, missing, wrong and cross-origin cases all ran (with the case count) and pass, because CSRF protection is intact; (2) deliberately bypass CSRF on that discovered `PATCH` (and, separately, add a new parameterised cookie-auth `PATCH` route that bypasses it): the CSRF-marker case fails; restore and show all cases pass.
  - `semgrep/no-csrf-exempt.yml` + fixture still rejects `csrf_exempt` anywhere in `app/` (T6, A.19: no `CSRF_ENFORCE` switch).
- **Before M2d starts (step 0):** read django-ninja's CSRF handling in its source and docs (the version D2 pins; if it is not installed yet, the version the lockfile will take). Record what was read in the M2d DECISIONS entry: whether its `csrf` option or its auth classes skip `CsrfViewMiddleware` or `csrf_exempt` a route, and which auth classes enforce CSRF by themselves. The behaviour test above is the proof; the reading only sets the expected result for each auth class.
- `app/tests/test_deploy_checks.py`: remove the `security.W003` exception.
- `infra/host/tests/edge/edge_probe/urls.py` + a probe view (test only, mounted only by `make host-test-live`, never in the image, like the M1c probe): `GET /probe/session/set` writes a random value into the session; `GET /probe/session/get` returns it. `edge_probe/settings.py` already imports the production settings, so the probe runs the real middleware and store.
- `infra/host/tests/test_session_live.py` (new, marker `host_live`): the restart and redeploy cases under Tests.
- `docs/runbooks/local-dev.md`, `docs/runbooks/deploy.md` (sessions survive deploys; the M1k repeat), `docs/DECISIONS.md` M2d entry.

## Tests

All unit tests run in `make test`. Tests marked `live` run in `make test-live` as `skiw_app` after `make migrate` as `skiw_migrator` (no exception to TEN-02). Tests marked `host_live` run in `make host-test-live` in the CI `host` job.

M2a — headers (UNI-17; spec §9 M2 "Header assertion tests (UNI-17/18) pass"):
- `app/shell/tests/test_security_headers.py`: for `/`, `/healthz`, `/assets/<file>`, a 404 and a 405, the response has exactly one `Content-Security-Policy` equal to the T6 string with a nonce. Two responses have different nonces. On `/`, the `<script>` nonce equals the header nonce. `X-Frame-Options: DENY`. `X-Content-Type-Options: nosniff`. On a secure request (`Client().get(..., secure=True)`), HSTS equals the Q1 value. On a plain request, there is no HSTS: `SecurityMiddleware` sets it only when `request.is_secure()` [V `middleware/security.py:36`]. `/` has `Cache-Control: no-store`.
- `app/tests/test_middleware_async.py`: every `MIDDLEWARE` entry is async-capable (D26 (1)).
- `app/tests/test_deploy_checks.py`: `check --deploy` clean except the named IDs.
- `web/e2e/shell.spec.ts`: zero `securitypolicyviolation` events and zero console errors, desktop and mobile (FE-70).
- `infra/host/tests/test_edge_live.py`: through Caddy, the app page has one HSTS and one CSP header.

M2b — lifetime settings (D6, UNI-02, UNI-16):
- `app/accounts/tests/test_session_lifetime_live.py` (`live`, frozen clock): an HTTP-level case first: a test-only view writes the session on a new client; the first response's `Set-Cookie` `Expires` equals the new row's `expire_date` (T0 + 12 h), through the middleware's real call order, sync and async; then create a session at T0; advance to T0 + 11 h 59 min; modify and save it; the row's `expire_date` and the cookie `Expires` are still T0 + 12 h. Advance past T0 + 12 h: the session loads empty and the cookie is deleted. `cycle_key` and `acycle_key` at T0 + 11 h give a new row whose deadline is still T0 + 12 h (preserved), and ten repeated rotations leave it unchanged. `start_new_lifetime()` followed by `cycle_key` at T0 + 11 h gives a row with deadline T0 + 23 h (sync and async). M3 adds the login test: a login on an existing anonymous session at a later time gets a fresh 12-hour deadline, and a privilege-change rotation inside that login does not extend it. Frequent saves (every 10 min) never move the deadline. `set_expiry()` raises.
- `app/tests/test_session_settings.py`: valid values pass; missing, empty, non-integer, zero, negative and out-of-bound values each raise `ImproperlyConfigured` naming the variable and not the value.
- `infra/host/tests/test_compose_config.py` and `app/tests/test_env_wiring.py`: the two variables are present with valid values in `staging.env`, `production.env`, `ci.env`, `.env.example`, the Makefile `TOOL_ENV`, local Compose `app` and `worker`, the CI label step, and rendered Compose config for `web`, `worker` and `migrate`: all three get both variables; `migrate` still has the `skiw_migrator` URL and password file; `web` and `worker` still have `skiw_app`. Host, local, tooling and image-label contexts all start; the matrix of bad values fails closed.

M2b — hashed key (spec §9 M2 "the stored session key ≠ cookie value"; UNI-18):
- `app/accounts/tests/test_session_store_live.py` (`live`):
  - After a save, the row's primary key equals `sha256(cookie).hexdigest()` and differs from the cookie. No row's key equals any issued cookie.
  - With `CaptureQueriesContext`, the raw cookie never appears in any SQL text or parameter across create, load, save, `cycle_key`, `delete`, `flush`, and their async twins.
  - A dump does not give a usable cookie: a request whose cookie is a stored key gets an empty session.
  - `cycle_key` leaves only the new hashed row; `flush` leaves none.
  - A malformed cookie (wrong length or characters) loads nothing and runs no query.
  - Grant audit (same method as the M0c audit, `aclexplode` over `pg_class.relacl`): `skiw_app` holds exactly SELECT, INSERT, UPDATE, DELETE on `django_session`; no TRUNCATE; no column grants. The existing M0c "no TRUNCATE for any non-owner role" check still passes.
- `app/accounts/tests/test_session_store_surface.py` (unit, Django-upgrade guard): the set of methods defined on `django.contrib.sessions.backends.db.SessionStore` equals a pinned list, and every one that touches the model is overridden in `accounts.session.SessionStore`. A new Django method fails the test until it is reviewed.
- `app/accounts/tests/test_session_cookie_live.py` (`live`, because writing the session saves a `django_session` row; a test-only URLconf view writes the session): `Set-Cookie` is `__Host-skiw_session=…; Path=/; Secure; HttpOnly; SameSite=Strict` with no `Domain` (UNI-18, D6).
- `make lint`: import-linter contract and `semgrep --test` for the store-only rule.

M2c — key-bound HMAC (spec §9 M2 "a row with edited data, or data copied from another row, is rejected (logged out)"; TEN-11 row tests):
- `app/accounts/tests/test_session_hmac_live.py` (`live`, rows changed by SQL as `skiw_app`):
  - Edited data: the test re-signs a changed dict with the Django `SECRET_KEY` (so Django's own signature is valid) and writes it into the row. The next request gets an empty session, the response deletes the cookie, and no row is updated in place.
  - Copied data: row B's `session_data` is copied into row A. Request A is rejected the same way.
  - Key rotation: a session signed with v1 verifies when the key file lists v2 and v1. It is rejected when the file lists v2 only.
  - Unknown version prefix and malformed `session_data` are rejected.
  - The warning log line has no cookie, stored key, MAC or session value (UNI-09, `caplog`).
- `app/tests/test_secret_files.py`: the versioned reader — both forms set, short key, repeated version, bad base64 all fail closed with no key text in the error.
- `app/tests/test_startup_key.py` (unit, no database): the key check is a function `accounts.session.require_key()`, which `asgi.py` calls **before** `require_migrated()`; the test calls it directly and shows it refuses a missing or malformed key. A second case shows the settings module imports with no key set (what `migrate` needs).
- `infra/host/tests/test_compose_config.py`: `TENANT_SOURCE_KEY_FILE` only on `web` and `worker`.
- The TEN-11 variant "a `django_session` row whose agency/user was edited" needs user and agency keys, which arrive in M3 and M4. M2 proves the mechanism with any data key; M3 and M4 re-run the test with the real keys.

M2d — CSRF and the restart and redeploy proof:
- `app/tests/test_csrf_gate.py`, `app/tests/csrf_fixtures.py`, `app/config/routes.py`: the completeness check and the cases above (a test-only POST route registered through `route()` returns a CSRF-marked 403 without a token, the same with a cross-site `Origin`, and 200 with the token from the shell meta plus the matching cookie; a safe route returns 405 for an unsafe verb with a valid token). Semgrep fixture for the `path(` rule. The CSRF cookie is `__Host-csrftoken`, Secure, HttpOnly, SameSite=Strict, `Path=/`, no `Domain`.
- `infra/host/tests/test_session_live.py` (`host_live`, through Caddy over HTTPS):
  1. **Restart:** `GET /probe/session/set`; keep the cookie. `compose restart web`; wait for `/readyz` 200. `GET /probe/session/get` returns the same value. The row count is unchanged.
  2. **Redeploy:** build a second image from the same tree with an extra label, so it has a new local image ID. Run the `migrate` service with it (the harness already runs `run --rm migrate` at start-up [V `test_edge_live.py:163`]). Recreate `web` with the new `SKIW_IMAGE` (`up -d --no-deps web`). Assert the container ID and image ID changed, then `GET /probe/session/get` returns the same value.
  3. **Negative control:** replace the `tenant_source_key` file with one new version only and recreate `web`. The same cookie now gets an empty session and a cookie delete. This shows the test would catch a key that does not survive.
  4. `/readyz` 200 throughout; `docker compose down -v` runs even on failure (the M1c pattern).
- M1k evidence list (not M2 code): repeat cases 1 and 2 on staging through `skiw-deploy` once staging exists.

Commands every PR runs before push: `make lint typecheck test test-live host-test`; M2a and M2d also `make e2e host-test-live`.

## Guardrail packs touched

- **universal:** UNI-01; UNI-02 (session lifetime values from config, Q2, built in M2b; the absolute deadline is fixed at row creation); UNI-03 (cookie key validated at the boundary); UNI-04 (import-linter contract for `accounts.session`; Semgrep rules); UNI-05 (the M2a `W003` exception removed in M2d); UNI-06 (no new dependency; own CSP middleware); UNI-07 (hard) and UNI-08 (`tenant_source_key` only from the host secret store; placeholders only in `.env.example`); UNI-09 (session-reject log line); UNI-13 (new tests run in existing CI jobs); UNI-15 (`accounts.0001` is additive, reversible, run as `skiw_migrator`); UNI-16 (runbooks in M2c and M2d); UNI-17; UNI-18; UNI-19 (the probe views exist only in the test-mounted `edge_probe`).
- **auth:** AUTH-07 prerequisite only (revocation is a row delete, D6); AUTH-11 (session middleware does no unsafe DB work; it loads lazily); AUTH-13 server half (an empty session deletes the cookie). AUTH-01..06, 08..10, 12 are n/a until M3 (no login, no wrapper, no mutating route).
- **tenancy-rls:** TEN-02 (hard; grants for `skiw_app` only, no BYPASSRLS); TEN-10 (`accounts.session` is the only module touching `django_session`, lint-enforced); TEN-11 (hard; the `django_session` half: MAC-verified server-side row). TEN-04..09 and 12 are n/a: `django_session` is a listed global table (§4.1).
- **frontend:** FE-50 (build passes), FE-61 (shell markup unchanged apart from the nonce, meta and icon), FE-70 (e2e console-clean on desktop and mobile).
- **Not relevant:** money, finalized-records, files-templates, events-jobs (expired-session cleanup is deferred to M4, Risk 6). public-links and payments are not ticked.
- **PROJECT.md §9:** TEN-10 allow-list (`accounts.session`); D26 middleware rule (async-capable test starts in M2a); out-of-scope list (no login, no feature code).

## Risks / things the reviewer should look at first

1. **Every Django database path hashes the key.** The override list in M2b must be complete, sync and async. The surface test pins Django's method list. A missed async method would write a raw key.
2. **HMAC failure must not keep `_session_key`.** Otherwise the next `save()` updates the tampered row in place with new data and a fresh MAC.
3. **The shell icon breaks the CSP.** `<link rel="icon" href="data:,">` is blocked by `default-src 'self'` and logs a console error, which fails the existing e2e test. M2a removes it or serves a same-origin icon from the web build [A — pick at M2a; no `img-src data:` is added, because that would change the T6 policy].
4. **`__Host-` cookies on plain HTTP.** Local `make e2e` and `make dev` use `http://127.0.0.1:8000`. Whether Chromium keeps a Secure cookie there is [A — verify in M2b/M2d e2e]. M2 has no e2e flow that needs a session; M3's login e2e may need Caddy's `tls internal` in front of the app.
5. **One HSTS header on the wire.** Caddy sets HSTS deferred (`header >…`), so the Django value is replaced (DECISIONS 2026-10-14 M1c). The M2a edge test proves it. Both values must stay equal (Q1).
6. **Expired rows pile up.** `clearsessions` comes with `django.contrib.sessions`, which is not installed. A periodic cleanup task cannot be registered before M4: until then only `jobs.noop` may be registered (D5 "Staging"). With about five accounts the table stays tiny. M4 plan: a periodic system task, or an ops command [A].
7. **`expire_date` is bound into the HMAC (owner decision 2026-10-27).** The spec binds the HMAC to the stored key and `session_data` only. SQL as `skiw_app` could extend `expire_date` of a stolen or old row. M2c binds it too (see M2c design). The reviewer checks that the MAC input has a fixed, unambiguous layout, and that every save recomputes the MAC from the new `expire_date`. The spec wording is fixed at the next spec change.
8. **CSRF failure page.** Django's default 403 page may carry inline style that the CSP blocks. It is cosmetic. M3 may add a plain failure view [A].
9. **`migrate` start-up.** Settings must not read `tenant_source_key`, because `migrate` does not mount it. M2c reads it lazily and checks it in `asgi.py` only.
10. **Later Django or django-ninja upgrades.** Django 6.0 adds its own CSP support [A — not checked]; moving to it is a later decision. django-ninja (D2) has its own CSRF handling; it must not bypass `CsrfViewMiddleware` for cookie-auth routes. Its source is read before M2d (M2d step 0), and the M2d behaviour test proves it.

### Owner questions — answered 2026-10-27: Q1 (a), Q2 (a), Q3 (a), Q4 (a)

The owner typed "1a 2a 3a 4a". Record the answers in `docs/DECISIONS.md` with the M2 plan PR.

| # | Question | Blocks | Options (at most 2) | Builder pick |
|---|---|---|---|---|
| Q1 | **HSTS value.** T6 says "HSTS 1 year + preload". The H1 `caddy` row and DECISIONS 2026-10-14 M1c say one year only, and Caddy and Django must send the same value. Preload covers every subdomain of the registrable domain and is hard to undo. Hostnames (G9) are not named yet. | M2a | (a) one year only (`max-age=31536000`), the same as Caddy today; T6's "+ preload" is fixed at the next spec change; (b) add `includeSubDomains; preload` on Caddy and Django and submit to the preload list after G9 | (a) |
| Q2 | **Session lifetime before M5.** D6 and §8.1 give idle 30 min and absolute 12 h, stored per agency in `setting`, which arrives in M5. The session is read before the agency is known. | M2b | (a) an interim deployment-wide value from host config (`SKIW_SESSION_ABSOLUTE_H=12`, `SKIW_SESSION_IDLE_MIN=30`, required, fail closed); absolute from M2, idle enforced in M3; moved into `setting` in M5; (b) no lifetime policy in M2; all of it in M3 or M5 (Django's default of two weeks would apply until then) | (a) |
| Q3 | **Redeploy proof without a VPS.** Accept the CI Compose proof (restart, recreate on a new image ID, through Caddy, with a negative control) as meeting "session survives a redeploy and a restart of the one `web` container", with a repeat on staging added to M1k. | M2 "done" only | (a) yes; (b) no, M2 stays open until a real `skiw-deploy` redeploy on staging (waits for G3 and M1k) | (a) |
| Q4 | **CSRF token delivery to the SPA.** | M2d | (a) an HttpOnly `__Host-csrftoken` cookie, with the token rendered into the `no-store` shell and sent as `X-CSRFToken` (matches T6's cookie flags); (b) `CSRF_USE_SESSIONS = True` — the token lives in the DB session, so every anonymous shell load writes a `django_session` row | (a) |

### Notes for M3

- **Login rotates the CSRF token.** Django's `login()` calls `rotate_token()`, so the token in the shell page (`<meta name="csrf-token">`) is stale after login. The login response must return the new token in its body, and the SPA must replace its stored token with it. M3 adds a test: log in, then send a mutating request with the old token (403) and with the new one (success). Same for logout.

### Assumptions [A]

- **A1 — Django 5.2 session-store internals verified against its source [A — verify at M2]** (spec §9 M2). Read in the installed Django (`.venv/lib/python3.12/site-packages/django/`, version 5.2.17 from `uv.lock`), and record what was read in the M2b DECISIONS entry:
  - `contrib/sessions/backends/db.py` — every method that uses `session_key` against the model (`_get_session_from_db`, `_aget_session_from_db`, `load`, `aload`, `exists`, `aexists`, `create`, `acreate`, `create_model_instance`, `acreate_model_instance`, `save`, `asave`, `delete`, `adelete`, `clear_expired`, `aclear_expired`), and how `save` writes by primary key with `force_insert` / `force_update`.
  - `contrib/sessions/backends/base.py` — `encode`/`decode` (signed with `SECRET_KEY` and `key_salt`; `decode` returns `{}` on a bad signature), `_get_new_session_key`, `VALID_KEY_CHARS`, `_validate_session_key` (only ≥ 8 characters), the `session_key` / `_session_key` properties, `cycle_key`/`acycle_key`, `flush`/`aflush`, `get_expiry_age`/`get_expiry_date`, `is_empty`.
  - `contrib/sessions/base_session.py` — `AbstractBaseSession` field sizes and `BaseSessionManager.save`/`encode`.
  - `contrib/sessions/models.py` and `contrib/sessions/migrations/0001_initial.py` — the table shape being replaced.
  - `contrib/sessions/middleware.py` — raw cookie in, `session_key` out, cookie delete on an empty session, no save on 5xx, `SessionInterrupted` on `UpdateError`.
  - `contrib/auth/__init__.py` `login`/`alogin`/`logout` — they call `cycle_key`, `flush` and set `HASH_SESSION_KEY`; M3 depends on these working with the hashed store.
  - `middleware/csrf.py` — `get_token`, `rotate_token`, the Origin and Referer checks on HTTPS, `CSRF_COOKIE_HTTPONLY`, `CSRF_USE_SESSIONS`.
  - `middleware/security.py` and `middleware/clickjacking.py` — HSTS only on secure requests; the `X-Frame-Options` value.
  - `core/checks/security/{base,csrf,sessions}.py` — the deploy-check IDs the tests allow.
  - Already read on 2026-10-27 [V]: `session_key` `max_length=40`; `VALID_KEY_CHARS` and length 32; the middleware cookie flow; `cycle_key` deletes by the old raw key; no CSP middleware in 5.2.17; HSTS only when secure; check IDs `security.W003`, `W005`, `W008`, `W021`.
- **A2** — Nothing in Django 5.2 that M2 uses needs `django.contrib.sessions` in `INSTALLED_APPS`. Seen so far [V]: the session deploy checks also fire when `SessionMiddleware` is in `MIDDLEWARE` (`core/checks/security/sessions.py:95`). To verify at M2b: `django.contrib.auth` (M3) works with an own session model.
- **A3** — Browsers accept a nonce made by `secrets.token_urlsafe` (base64url characters) in `nonce-…` [A — CSP nonce grammar allows `-` and `_`; the e2e test proves it].
- **A4** — `'strict-dynamic'` with a nonce on the entry module lets the browser load the module's static and dynamic imports. Vite's dynamic `modulepreload` links are not needed by today's shell [A — e2e proves the current build].
- **A5** — React `style` props do not trigger `style-src` (they go through the CSSOM). The built CSS loads through `<link>` from the same origin.
- **A6** — Recreating `web` with Compose on a new image ID matches the host switch in `skiw-deploy` step 6 (M1 plan §3 M1g). The host state file is not exercised in CI.
- **A7** — The HMAC label `skiw-session-v1` and the `v<n>:<mac>:<blob>` layout are builder choices; the spec names only the key and the binding.
- **A8** — `CSRF_COOKIE_AGE = None` (browser-session cookie) is a builder value.
- **A9** — The session lifetime values in Q2 (a) are the spec's §8.1 values; their interim home is an owner decision (Q2).
- **A10** — The shell icon: M2a removes `data:,` or serves a same-origin icon; which one is picked at M2a (Risk 3).
- **A11** — Chromium keeps `__Host-` Secure cookies on `http://127.0.0.1` for local e2e (Risk 4).
- **A12** — Expired-session cleanup moves to M4 as a periodic system task or an ops command (Risk 6).
- **A13** — Django's default CSRF failure page may be blocked cosmetically by the CSP (Risk 8).
- **A14** — Django 6.0 has its own CSP support (not checked); django-ninja's CSRF option does not bypass `CsrfViewMiddleware` (verify when django-ninja is added) (Risk 10).
- **A15** — The redeploy case uses `test_edge_live.py`'s existing `migrate` run and secret generator [V lines 121-124, 163]; only the second image build and the `web` recreate are new.

## Done when

- M2a–M2d are merged, each with an Approved review on its head SHA, archived before merge, and logged on `agent-logs`.
- Spec §9 M2 done-when, item by item:
  - "Header assertion tests (UNI-17/18) pass" — M2a header tests, M2b and M2d cookie-attribute tests, and the M2a edge test through Caddy are green in CI.
  - "session survives a redeploy and a restart of the one `web` container" — M2d `test_session_live.py` cases 1 and 2 green in the CI `host` job, with the negative control (case 3) green; per Q3 (a), the staging repeat is listed in M1k's evidence.
  - "the stored session key ≠ cookie value" — M2b live tests green, including the no-raw-key-in-SQL test.
  - "a row with edited data, or data copied from another row, is rejected (logged out)" — M2c live tests green.
  - "Django 5.2 session-store internals verified against its source" — A1 recorded in the M2b DECISIONS entry, and the store-surface test is in CI.
- `make lint typecheck test test-live host-test host-test-live e2e` green on `main`.
- `check --deploy` clean except `security.W008` (and `W005`/`W021` if Q1 = (a)), each with its reason.
- DECISIONS entries for M2a–M2d, including the updated UNI-17 header placement record. Runbooks updated (UNI-16).
- Owner answers to Q1–Q4 recorded in the handoff and in `docs/DECISIONS.md`.
