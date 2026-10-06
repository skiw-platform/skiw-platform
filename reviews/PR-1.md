# Review — PR #1

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 6 — 2026-10-06 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `fbde411df3be568dd8c09d5052c9633aa9e4abdf` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings
- No new findings. R5 P2 is resolved: `.github/workflows/ci.yml:17` uses the explicit `ubuntu-24.04` runner label, and `docs/DECISIONS.md:10` records the choice. GitHub reports `ci / python` success at this exact PR head (run `37445808806`).
- R1 P1 runtime-role and TLS-option corrections remain resolved. The R1 P2 M0c plan role drift and R2 P2 invalid TLS flag remain deferred to their named milestones.

### Self-check audit
- The R1 applicability list and R5 audit remain current: the only new changes are the runner label and its decision entry. The UNI-14 mismatch is corrected. The committed workflow still runs the live role checks and Compose smoke test; full UNI-13 gates remain scheduled for M0d by the approved plan.

### Verification performed
| Command / check | Result |
|---|---|
| `git fetch origin` | Denied writing `.git/FETCH_HEAD` (`Operation not permitted`). The exact head object was already local; GitHub independently reported the same head SHA and open PR state. |
| Host PR and CI check | PR open at `fbde411df3be568dd8c09d5052c9633aa9e4abdf`; `ci / python` passed at that head. |
| `git worktree add --detach` | Still denied creating `.git/worktrees`. Used a separate local clone at `.agent/worktrees/review-clone-1-fbde411d`, detached at the exact host head; no tracked or staged changes. |
| Base and patch | Merge base remains `2425983`; only `.github/workflows/ci.yml` and `docs/DECISIONS.md` changed since R5; `git diff --check` passed. |
| Workflow and decision inspection | Versioned `ubuntu-24.04` label and SHA-pinned actions present; decision entry matches. |
| `docker compose --env-file .env.example config --quiet` | Passed in the isolated clone. |
| Independent lint, typecheck and unit tests | Not repeated: R5 ran these on the same application source, and this head changes only the workflow runner label and decision text. The new exact head has a successful host CI check. |

### Residual risks and test gaps
- Local Docker/PostgreSQL remains unavailable in this sandbox; the successful CI workflow is the live role and Compose evidence. Detailed Actions step logs remained unavailable through the GitHub API.
- This is approval of M0a only. M0c must reconcile queue grants and the plan; M1 must validate the TLS flag and prove live TLS before staging deploy.

### Required before merge
- None for this M0a slice.

### Deferred conditions
- M0c: reconcile the plan with `skiw_app` queue grants (R1 P2).
- M1 before staging deploy: reject invalid TLS flag values and prove live TLS (R2 P2).

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the next step is the builder's approval archive.
**Verdict:** Approved with conditions

## Round 5 — 2026-10-06 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `28dbd6aad1e2162ea54d115781e15160515c1afa` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings

### [P2] CI uses a floating runner label despite UNI-14
- Category: guardrail mismatch
- Rule: UNI-14 ("no floating `latest` in CI or deploy")
- Evidence: `.github/workflows/ci.yml:17` sets `runs-on: ubuntu-latest`; `docs/DECISIONS.md:10` explicitly records that the runner is not pinned to an image version. The PR self-check still marks UNI-14 `pass` based on the lockfile, base images and tools; it does not cover the new runner label.
- Failure scenario: GitHub changes which Ubuntu release `ubuntu-latest` selects, changing the CI environment and possibly breaking or changing the role and Compose checks without a repository change.
- Why it matters: this directly conflicts with the project's CI pinning rule. Severity is P2 because the drift is isolated to this scaffold's CI runner; M0a has no production deployment or data path.
- Required correction: use an explicit supported Ubuntu release label (for example `ubuntu-24.04`) in the workflow, record the chosen label in `docs/DECISIONS.md`, and re-run CI on the resulting PR head.
- Owner: builder
- Verification: workflow has no floating `latest` runner label and the check passes on the new exact head.
- Disposition: before merge
- Status: open

### Prior findings rechecked
- R1 P1 runtime-role correction: CI at this head reports success for a workflow that runs `make test-live`. That target starts disposable Postgres, runs `make migrate` with `MIGRATION_DATABASE_URL`, and executes seven live tests including the real Django connection's `current_user = skiw_app`, migrator ownership, and app-role privilege checks. This supplies the independent runtime evidence requested in R4. Detailed Actions logs were unavailable through the GitHub API in this reviewer environment; the host check conclusion and checked-in workflow are the evidence.
- R1 P1 TLS option loss: prior source correction remains; the unit tests pass independently in the isolated checkout. Live TLS is still due before the M1 staging deploy.
- R1 P2 M0c plan role drift and R2 P2 invalid TLS flag remain deferred to M0c and M1 respectively.

### Self-check audit
- The R1 applicability list remains valid for M0a. New CI touches UNI-13/14, UNI-07/08, UNI-11/12/16, TEN-01/02 and TEN-10. The PR body has a self-check table. UNI-14's `pass` is contradicted by the new floating runner label (finding above). The live role check closes the earlier TEN-01/02 evidence gap. Full UNI-13 gates remain scheduled for M0d by the approved plan; this PR adds the subset needed for the role proof.

### Verification performed
| Command / check | Result |
|---|---|
| `git fetch origin`, `gh pr view 1`, `gh pr checks 1` | PR open at exact head `28dbd6a`; `ci / python` success reported by GitHub (run `37444695275`). |
| `git worktree add --detach` | Still denied creating `.git/worktrees` (`Operation not permitted`). Used a separate local clone under `.agent/worktrees/review-clone-1-28dbd6aa`, detached at the exact head; no tracked changes. |
| Ruff check and format check | Pass; 40 files already formatted. Existing pinned tools from the main checkout's `.venv` were invoked against the isolated clone's source. |
| `lint-imports` and strict mypy | Pass; 3 contracts kept, 0 broken; 13 source files typechecked. |
| pytest | Pass; 20 unit tests, 7 live tests deselected by design. |
| `docker compose --env-file .env.example config --quiet`, `git diff --check` | Pass. |
| Workflow, `Makefile`, role tests, runbook and decisions inspection | Confirmed CI step chain, runtime/migration URL separation, seven live assertions, SHA-pinned actions, and floating runner label. |
| Local Docker / PostgreSQL | Docker socket denied; local live check unavailable. GitHub check supplies the runtime evidence. |
| Actions job step logs | `gh run view` and job API intermittently failed to connect; individual step output was not inspected. |

### Residual risks and test gaps
- CI runner version needs a fixed release label and a green rerun on the new head.
- The staging TLS check and strict flag validation are deferred to M1. The M0c plan needs role/grant reconciliation in M0c.
- Detailed GitHub Actions job logs and local Docker execution were unavailable; the successful host check, workflow and local source checks form the present evidence.

### Required before merge
- Resolve the P2 UNI-14 runner finding and rerun `review 1` on the new head after CI passes.

### Deferred conditions
- M0c: reconcile the plan with `skiw_app` queue grants (R1 P2).
- M1 before staging deploy: reject invalid TLS flag values and prove live TLS (R2 P2).

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the remaining correction is narrow.
**Verdict:** Revision required

## Round 4 — 2026-10-06 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `4da0d0ce5ac7f34b0bab1564d9578efb595d7783` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings
- No new source findings. The R1 runtime-role and TLS-option code corrections pass the independent source-level checks below. The role distinction still needs a live database check under `skiw_app` and `skiw_migrator`; no disposable PostgreSQL instance could run in this sandbox.
- R1 P2 (M0c plan role drift) and R2 P2 (TLS flag accepts invalid values) remain deferred as recorded. The latter was reproduced independently: `DJANGO_REQUIRE_DB_TLS=tru` with a URL lacking `sslmode` imports settings and yields empty database `OPTIONS`.

### Self-check audit
- The Round 1 applicability list and Round 2 source audit remain current; the PR head is unchanged. This round independently confirms UNI-01, UNI-04, UNI-05, the URL-parser part of UNI-03, and the test suite. TEN-01/02 role behavior, Compose startup, and the production HTTP endpoint remain unverified at runtime.

### Verification performed
| Command / check | Result |
|---|---|
| Local clone into `.agent/worktrees/review-clone-1-4da0d0ce`, detached at the PR head | Succeeded; exact HEAD `4da0d0c`, no tracked changes. The GitHub remote clone failed on DNS, so the clone source was the already fetched local repository; the head was matched to GitHub before and after checks. |
| `make install` | Could not initialize the global uv cache: `Operation not permitted`. Existing pinned project tools in the original `.venv` were invoked against the detached clone's source; independent dependency installation remains unverified. |
| Ruff check and format check | Pass; 39 files formatted. |
| `lint-imports` | Pass; 3 contracts kept, 0 broken. |
| Strict mypy | Pass; 12 source files. |
| pytest | Pass; 20 tests, including the new TLS URL tests. |
| `docker compose --env-file .env.example config --quiet` | Pass; Compose configuration parses. |
| ASGI import and Gunicorn `--check-config` | Pass. Live bind of `127.0.0.1:4016` denied by the sandbox (`Operation not permitted`). |
| Docker/DB-role checks | Docker API socket denied; no local PostgreSQL server binaries found. `current_user`, migration, live TLS and Compose startup could not be checked independently. |
| Pinned source inspection and `git diff --check` | Role URLs, migration override and TLS `OPTIONS` correction present; diff check clean. Secret-name scan found placeholder/config references only in changed code and runbook. |
| Git host final-head and checkout status | PR open at `4da0d0c`, no status checks; detached clone clean. |

### Residual risks and test gaps
- No independent live database proof that app connections use `skiw_app` and migrations use `skiw_migrator` (TEN-01/02, the R1 hard-rule finding).
- No independent Compose/production HTTP smoke test or live TLS check. The latter is due before M1 staging deploy.
- Dependency installation used the builder-created `.venv` because sandbox access to uv's cache and the network failed; source lint/typecheck/tests were run in the detached clone.
- PR #1 has no CI checks; CI is scheduled for M0d in the approved plan.

### Required before merge
- Obtain independent live role and Compose checks in an environment with a usable disposable PostgreSQL server and Docker/socket access, or CI at this exact head. R1 P1 role verification is still open; the source correction alone is insufficient for the hard TEN-02 gate.

### Deferred conditions
- M0c: reconcile the plan with `skiw_app` queue grants (R1 P2).
- M1 before staging deploy: reject invalid TLS flag values and prove live TLS (R2 P2).

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — remaining checks need runtime access.
**Verdict:** Blocked

## Round 3 — 2026-10-06 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `4da0d0ce5ac7f34b0bab1564d9578efb595d7783` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings
- No new source findings. The R1 P1 code corrections remain present but lack independent runtime verification. The R1 P2 M0c plan drift and R2 P2 TLS flag validation remain deferred as recorded in Round 2.
- The mandatory review checkout is still inaccessible. The current workspace permits reading `.git` but denies creating `.git/worktrees/review-1-4da0d0ce`; `git worktree add --detach` returned `Operation not permitted` again.

### Self-check audit
- The Round 1 applicability list and Round 2 recheck remain current because the pinned PR head has not changed. Builder self-check claims for runtime tests remain unverified independently; GitHub reports no status checks.

### Verification performed
| Command / check | Result |
|---|---|
| `git fetch origin`; `gh pr view 1 --json ...` | Fetch succeeded. PR open; base `2425983`, head `4da0d0c`, zero status checks. |
| `git cat-file -e`, `git merge-base` | Exact head object present; merge base `2425983`. |
| `git diff --check` | Clean. |
| `git worktree add --detach .agent/worktrees/review-1-4da0d0ce <head>` | Failed again at `.git/worktrees`: `Operation not permitted`. No checkout created. |
| Independent lint/typecheck/test/Compose/DB-role checks | Not run; reviewer rules require the detached checkout. |

### Residual risks and test gaps
- The R1 P1 runtime-role and TLS-option corrections still need independent execution of their tests and DB-role checks.
- PR #1 has no CI checks because the approved M0 plan adds CI in M0d.

### Required before merge
- The review workspace must permit `git worktree add --detach` to write `.git/worktrees`, then `review 1` must be rerun with independent checks. No code change is requested by this round.

### Deferred conditions
- M0c: reconcile the queue plan with `skiw_app` grants (R1 P2).
- M1 before staging deploy: reject invalid TLS flag values and verify the live DB connection uses TLS (R2 P2).

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the blocker is workspace access.
**Verdict:** Blocked

## Round 2 — 2026-10-06 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `4da0d0ce5ac7f34b0bab1564d9578efb595d7783` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

### Findings

### [P2] TLS enforcement flag accepts invalid values as false
- Category: material risk
- Rule: UNI-03; spec D4
- Evidence: `app/config/settings.py:19` uses `env.flag("DJANGO_REQUIRE_DB_TLS")`; `app/config/env.py:26-30` returns `False` for every value outside its true set, including a typo. `.env.example:20` leaves the flag commented out. The new tests cover `"1"`, not an invalid flag value.
- Failure scenario: a non-local deployment sets `DJANGO_REQUIRE_DB_TLS=tru` and omits `sslmode` in its URL. Settings import succeeds and libpq is allowed to fall back to a plaintext connection.
- Why it matters: the guard is fail-open on configuration mistakes. The risk is confined to the later non-local deployment path; M0a has no staging or production deployment.
- Required correction: before M1 deploy, make the TLS flag parser reject invalid values and have CDK set an explicit required TLS configuration. Test an invalid flag and confirm the staging connection uses TLS.
- Owner: builder / infrastructure
- Verification: settings import fails for an invalid flag; M1 configuration carries the strict mode and staging `pg_stat_ssl` shows SSL for the app connection.
- Disposition: deferred to M1 PR, before staging deploy
- Status: open

### Prior findings rechecked
- **R1 P1 runtime role:** source correction present. `.env.example:15,17` now separates the runtime and migration URLs; `Makefile:33-34` overrides `DATABASE_URL` only for migration commands; the runbook was updated. The required `current_user` checks remain unverified independently because no detached checkout can be created. Status: source corrected, runtime verification open.
- **R1 P1 TLS option loss:** source correction present. `app/config/env.py:41-62` preserves allow-listed TLS parameters in Django `OPTIONS`; `app/tests/test_database_url.py:25-28,55-71` adds direct and settings-level assertions. The tests could not be run independently. Status: source corrected, runtime verification open.
- **R1 P2 M0c plan drift:** unchanged at `docs/plans/2026-10-05-m0-scaffold.md:149,159`; remains deferred to M0c.

### Self-check audit

The Round 1 applicability list still applies. This round rechecked the changed surfaces and compared them with the PR's self-check plus its R1 comment.

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01, UNI-04, UNI-05 | yes, typing and lint | pass | source changes small; lint/typecheck not independently run | `app/config`, `pyproject.toml` | unverified |
| UNI-03 | yes, env boundary | pass | TLS URL options preserved; invalid TLS flag silently becomes false | `app/config/env.py:26-30,41-62` | P2 deferred to M1 |
| UNI-07, UNI-08 | yes, secrets and config | pass | no new committed secret in inspected diff; independent secret scan unavailable | `.env.example`, PR patch | unverified |
| UNI-13 | staged to M0d by approved plan | n/a | host reports no checks for this head | PR metadata | milestone gap, unchanged |
| UNI-14, UNI-16 | yes, pins and runbook | pass | pins unchanged; runbook now describes separate URLs and TLS flag | `Dockerfile`, `docs/runbooks/local-dev.md:24-29` | no |
| TEN-01, TEN-02 | yes, role separation | pass | source correction present; live `current_user` not independently checked | `.env.example:15,17`, `Makefile:33-34` | verification open |
| TEN-10, UNI-19 | yes, import boundary and health endpoint | pass | unchanged source; local checks unavailable | `pyproject.toml`, `app/health` | unverified |
| Other ticked-pack rules | n/a for this M0a slice as listed in Round 1 | n/a | unchanged | M0a diff | no |

### Verification performed
| Command / check | Result |
|---|---|
| `git fetch origin`; host PR metadata | Fetch succeeded; PR #1 open, base `2425983`, exact head `4da0d0c`, zero reported status checks. |
| Exact local object and merge base | Head present locally; merge base equals `2425983`. |
| Host patch and pinned source-object review | Inspected both R1 fixes, new tests, runbook and decisions entry. |
| `git diff --check` | Clean for base-to-head diff. |
| `git worktree add --detach .agent/worktrees/review-1-4da0d0ce <head>` | Failed: `.git/worktrees/...: Operation not permitted`; no detached review checkout created. |
| Independent lint/typecheck/test/Compose/DB-role checks | Not run; reviewer rules require the detached checkout. Builder's PR comment reports 20 passing tests and DB role checks, but these are not independent verification. |

### Residual risks and test gaps
- A detached checkout and all independent runtime checks are still blocked by `.git/worktrees` write permission.
- CI is scheduled for M0d; PR #1 has no status checks and is not CI-verified.
- The live TLS connection check and the flag validation belong to M1 before staging deploy.

### Required before merge
- Provide a review environment where `git worktree add --detach` can create the checkout, then rerun `review 1` on the same or a newer head. The source fixes for the R1 P1 findings are present, but their independent runtime verification remains open.

### Deferred conditions
- Reconcile the M0c plan with `skiw_app` queue grants in the M0c PR (R1 P2).
- Reject invalid TLS flag values and prove a live TLS connection in the M1 PR before staging deploy (R2 P2).

### Optional improvements
- None.

**Model used:** Codex (GPT-6) · **Switch model next step?** No — the blocker is filesystem access, not model capability.
**Verdict:** Blocked

## Round 1 — 2026-10-05 · scope: slice (M0a)
- **Code review:** base (merge base) `2425983550118b3b03d3d7dbbec6a973dfe00776` · head `b4e8328c51f1e9e5ddda75cc9fa79a9e26ee82e0` · head re-checked at end: yes
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.7 · `git hash-object` `cf57625da85c77d9be83995721fce9ed45907a07`

**Verdict:** Blocked
**Model used:** Codex (GPT-6) · **Switch model next step?** No — the blocker is checkout access, not model capability.

### Findings

### [P1] The default local database URL gives host-run application code the migration role
- Category: guardrail mismatch
- Rule: TEN-01, TEN-02 (hard); spec D4 and D16
- Evidence: `.env.example:14-15` sets `DATABASE_URL` to `skiw_migrator`; `docs/runbooks/local-dev.md:24-27` states that all host-run commands connect as that role. `Makefile:32-34` sources the same variable for migrations. Compose overrides it for its app container, but host-run `manage.py runserver` does not.
- Failure scenario: a developer starts the Django app from the host after following the first-run instructions. Its queries run as schema owner rather than `skiw_app`, so the runtime role boundary is bypassed.
- Why it matters: TEN-02 allows only `skiw_app` for a running app; TEN-01 reserves `skiw_migrator` for migrations.
- Required correction: make the normal `DATABASE_URL` use `skiw_app`; give `make migrate` a separately named migration URL that is injected only into the migration process. Update the runbook accordingly.
- Owner: builder
- Verification: from the standard local environment, check `current_user` for a host-run app connection and a migration command; they must be `skiw_app` and `skiw_migrator` respectively.
- Status: open

### [P1] Database URL parsing discards the required TLS settings
- Category: spec/guardrail mismatch
- Rule: spec D4 (TLS required), UNI-03
- Evidence: `app/config/env.py:28-39` parses the URL but drops `parts.query` and returns no TLS `OPTIONS`; `app/config/settings.py:17` uses that result unchanged. A URL carrying `sslmode=verify-full` and `sslrootcert` therefore loses both settings.
- Failure scenario: the deployed app attempts to connect without an enforced TLS mode. PostgreSQL libpq defaults to `prefer`, which may fall back to an unencrypted connection.
- Why it matters: the approved spec requires TLS to PostgreSQL; silently discarding a security option defeats an operator's attempt to enforce it.
- Required correction: preserve and validate the supported TLS parameters, or configure and require TLS explicitly for non-local deployments. Add a settings test proving the option reaches Django and a staging connection check before M1 deploy.
- Owner: builder
- Verification: inspect the resulting `DATABASES` settings for a URL containing TLS parameters, and in staging confirm the live connection is TLS-protected.
- Status: open

### [P2] The committed M0 plan still proposes running the app as the migration role
- Category: consistency
- Rule: TEN-02; plan §7 and ASK-6
- Evidence: `docs/plans/2026-10-05-m0-scaffold.md:149,159` says the local and CI app/worker use `skiw_migrator` until M4. `docker-compose.yml:31-35` and the new decision entry instead use `skiw_app` for the app.
- Failure scenario: M0c follows the plan's risk note and silently changes the app/worker back to `skiw_migrator` to make the queue work.
- Why it matters: it would reintroduce a hard role-boundary violation.
- Required correction: before M0c starts, reconcile the plan with the runtime-role decision and specify the queue grants needed by `skiw_app`.
- Owner: builder
- Verification: M0c plan and Compose both use `skiw_app`; Procrastinate enqueue tests pass under that role.
- Disposition: deferred to M0c PR
- Status: open

### Self-check audit

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes, Python typing | pass | configured; local result unverified | `pyproject.toml:49-54` | no |
| UNI-02 | n/a, no business values | n/a | n/a | M0a diff | no |
| UNI-03 | yes, env boundary | pass | TLS URL options dropped | `app/config/env.py:28-39` | yes; P1 |
| UNI-04 | yes, package boundaries | pass | contracts present; local result unverified | `pyproject.toml:63-79` | partial |
| UNI-05 | yes, code hygiene | pass | no apparent dead code in static diff | M0a diff | no |
| UNI-06 | yes, new dependencies | pass | decision entry records choices; maintenance claims not independently tested | `docs/DECISIONS.md:5-12` | no |
| UNI-07 | yes, secrets | pass | placeholders only in inspected diff; independent secret scan unavailable | `.env.example`, `.gitignore` | partial |
| UNI-08 | yes, production secret source | pass | local env only; production integration belongs to M1 | spec D16, M0a diff | partial |
| UNI-09 | n/a, no app logging configured | n/a | n/a | M0a diff | no |
| UNI-10 | n/a, no audit log | n/a | n/a | M0a diff | no |
| UNI-11 | yes, no unauthorised external service | pass | no such call in inspected code | M0a diff | no |
| UNI-12 | yes, write scope | pass | no code writes outside project; runtime tests unavailable | M0a diff | partial |
| UNI-13 | staged to M0d by approved M0 plan | n/a | no CI checks on PR #1; not a passing gate yet | PR statusCheckRollup empty | no; milestone gap |
| UNI-14 | yes, lock/pins | pass | lockfile and digest pins present | `uv.lock`, `Dockerfile`, `docker-compose.yml` | no |
| UNI-15 | n/a, no project migrations | n/a | n/a | M0a diff | no |
| UNI-16 | yes, env/deployment runbook | pass | present, but role guidance is wrong | `docs/runbooks/local-dev.md:24-27` | yes; P1 |
| UNI-17 | deferred to M2; no HTML or HTTPS terminator | n/a | n/a for this slice | M0a diff | no |
| UNI-18 | n/a, no cookies | n/a | n/a | M0a diff | no |
| UNI-19 | yes, intended health endpoint only | pass | only `/healthz` routed; runtime result unverified | `app/config/urls.py`, `app/health/views.py` | partial |
| TEN-01 | yes, migrator owns schema and only migrates | pass | migrator is default for host-run app commands | `.env.example:15`, `Makefile:32-34` | yes; P1 |
| TEN-02 | yes, app runs only as `skiw_app` | pass | Compose app correct; host-run app uses migrator | `docker-compose.yml:31-35`, `.env.example:15` | yes; P1 |
| TEN-03..09, TEN-11..12 | n/a, no tenant or audit tables/helpers | n/a | n/a for this slice | M0a diff | no |
| TEN-10 | yes, DB-import boundary preparation | pass (prep) | contract present; local result unverified | `pyproject.toml:70-75` | partial |
| Frontend FE-01..71 | n/a, no UI | n/a | n/a | M0a diff | no |
| Money MON-01..07 | n/a, no money data/logic | n/a | n/a | M0a diff | no |
| Finalized records REC-01..12 | n/a, no final records | n/a | n/a | M0a diff | no |
| Auth AUTH-01..13 | n/a, no auth implementation | n/a | n/a | M0a diff | no |
| Files FILE-01..06 | n/a, no upload/document implementation | n/a | n/a | M0a diff | no |
| Events EVT-01..12 | n/a, no queue or jobs in M0a | n/a | n/a | M0a diff | no |
| PROJECT.md §9 | yes, architecture boundaries and no out-of-scope feature | n/a | no feature creep; role issue above | M0a diff | partial |

### Verification performed
| Command / check | Result |
|---|---|
| Git host PR metadata | PR #1 open; base `main` at `2425983`; head `b4e8328`; no status checks reported. |
| Local object and merge base | Exact head object present; merge base equals `2425983`. |
| Three-dot diff inventory | 24 paths; no feature code outside M0a. |
| `git diff --check` | Clean; read-only diff check. |
| `git worktree add --detach .agent/worktrees/review-1-b4e8328c <head>` | Failed: `could not create leading directories of .git/worktrees/...: Operation not permitted`. No review checkout created. |
| Independent lint/typecheck/test/Compose/DB-role checks | Not run; reviewer rules require running them in the detached review checkout. Builder's PR body reports local passes, which are not independent verification. |

### Residual risks and test gaps
- Mandatory detached-checkout and independent runtime checks remain unavailable because `.git/worktrees` is not writable in this environment.
- The approved M0 plan stages CI for M0d. PR #1 therefore has no CI result and must not be described as CI-verified.
- Production secret injection, TLS connection enforcement and startup migration checks remain to be exercised before staging deployment.

### Required before merge
- Correct both P1 findings and provide an environment where the reviewer can create the required detached checkout and run focused checks; then re-run `review 1` on the new head.

### Deferred conditions
- Reconcile the M0c plan and queue grants in the M0c PR (P2).

### Optional improvements
- None.
