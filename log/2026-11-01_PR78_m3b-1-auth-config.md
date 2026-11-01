# PR 78 — feat(auth): M3b-1 config and key wiring

- **Merged:** 2026-11-01 (05:04 UTC) · **Merge commit:** f8f7075bfd4c98bd95636ea61b3173e3d8a6277b · **Branch:** feat/m3b-1-auth-config
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-78.receipt on agent-logs (commit fabdd40; receipt time 2026-11-01T05:03:53Z, before merge)
- **Merge evidence:** `gh pr view 78` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 026845303b3c6bc3494b1cb7868e57d9aa979711
- **Drafted by:** Claude Sonnet 5.5 (Opus sub-agent wrote the code) · **Final verdict:** Approved with conditions (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 (unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3b · **Milestone:** M3 auth, M3b-1

## What changed
Adds 12 required, bounded `SKIW_*` auth settings, wired into every context. Adds the `login_blob_key` reader with `max_version`, checked at start-up in `web` and `worker`. Sends `django.request` ERROR to stderr. Adds a shared test settings helper. No new dependency. 28 files, +454 / -74.

## Why
Plan §3 M3b. The plan's 450-line rule split M3b in two. This is the config half. The crypto half is M3b-2.

## Review rounds
- R1: no P0 or P1. Two P2 items deferred (below).

## Deferred conditions
- P2 settings bounds can go weaker than spec T5 / Flow 5.1 and the owner's 30-minute link → M3b-2.
- P2 `django.request` log line prints exception messages (a database error could carry an email) → M3d. No-token-in-path rule → M3e.

## Decisions worth keeping
- 9 of 12 settings have no reader until M3c–M3h (same pattern as M2b; noted in DECISIONS).
- `max_version=0xFFFF` on the login blob key (blob stores version in 2 bytes).
- Mutation check: 14 killed, 1 survived (`propagate: True` not observable with DEBUG off).
- Local DEBUG console no longer shows Django 404/405 warnings.
- M3b-2 patch saved locally at .agent/auto/m3b-2-crypto.patch with notes in m3b-2-notes.md (not committed).

## Follow-ups
- M3b-2 crypto PR (apply bounds P2 there; add DECISIONS dependency ladder; Docker build check; warm dummy hash duty for M3e).
- M3e: reset `unmatched_ignore_imports_alerting` to error and add a check; `host_live` same-origin POST test.
- Stakeholder progress page: update at M3 completion.

## Appendix — final review round
# Review — PR #78

## Round 1 — 2026-11-01 · scope: slice (M3b-1, first half of plan §3 M3b; plan `docs/plans/2026-10-31-m3-auth.md`)
- **Code review:** base (merge base) `77d0569a44090e59a1f1c26dc4350b3eb0a35558` · head `026845303b3c6bc3494b1cb7868e57d9aa979711` · head re-checked at end: yes (GitHub)
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash (`git hash-object`) `92841ba555e9e857ac70e86a5b043cf9729ed371` (unchanged by this PR)
- Review checkout: `.agent/worktrees/review-78-02684530` (detached worktree at the head SHA).

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier, `PROJECT.md` §6) · **Switch model next step?** No — M3b-2 (crypto) needs the deep tier.

### Findings

No P0 or P1 findings. The wiring is complete and well tested:
- Every context that imports settings carries all 12 values: `.env.example`, `TOOL_ENV`, local Compose, the CI label step, `infra/host/env/*.env`, and host `x-app-env` plus `migrate`.
- `login_blob_key` is checked at start-up in `web` and `worker`, with no key text in the error.
- The key is already minted and mounted (`secrets.py:46`, `compose.yml:57`).
- The split into M3b-1 and M3b-2 follows the plan's 450-line rule.

Two P2 items are deferred. Nothing in this PR reads the auth values, and no table holds PII yet, so merging now is safe.

### [P2] The bounds let a host config go weaker than the spec's T5 and Flow 5.1 values, and the owner's 30-minute link
- Category: security control (config bounds)
- Rule: UNI-02 (values live in config); spec T5, Flow 5.1; owner Q5 (a), Q6 (a)
- Evidence: `app/config/settings.py` (this PR), with the spec value for each:

  | Setting | Spec or owner value | Bounds in PR | Weakest allowed |
  |---|---|---|---|
  | `SKIW_ARGON2_MEMORY_KIB` | T5: 64 MiB | 19456–131072 | 19 MiB |
  | `SKIW_ARGON2_TIME_COST` | T5: t=3 | 2–10 | t=2 |
  | `SKIW_AUTH_FAILS_PER_ACCOUNT` | Flow 5.1: 5 | 3–20 | 20 |
  | `SKIW_AUTH_FAILS_PER_IP` | Flow 5.1: 20 | 5–200 | 200 |
  | `SKIW_AUTH_WINDOW_MIN` | Flow 5.1: 15 | 1–1440 | 1 min |
  | `SKIW_AUTH_LOCK_AFTER` | Flow 5.1: 10 | 3–50 | 50 |
  | `SKIW_AUTH_LOCK_MIN` | Flow 5.1: 30 | 1–1440 | 1 min |
  | `SKIW_STEPUP_MAX_AGE_MIN` | T5: "≤ 5 min" | 1–15 | 15 min |
  | `SKIW_TOTP_SKEW_STEPS` | Flow 5.1: ±1 | 0–2 | ±2 |
  | `SKIW_ENROL_LINK_MIN` | owner Q5 (a): 30 | 5–1440 | 24 h |

  T5 and Flow 5.1 state fixed values and do not call them configurable. D6 calls the session values "configurable", which is why the M2b session bounds were acceptable.
- Failure scenario: a later PR changes `infra/host/env/production.env` to `SKIW_AUTH_FAILS_PER_ACCOUNT=20` and `SKIW_AUTH_LOCK_MIN=1`, for example to stop staff complaints. Settings accept it, so the guessing rate for a password goes up about 4× per window, and the lock almost does nothing. No test fails. A reviewer must catch it by eye. The settings bound exists for this case and does not catch it.
- Why it matters: these values are the T5 account-takeover control. A bound should stop a weakening that needs an owner decision.
- Required correction: in each bound, make the spec or owner value the weakest allowed value. Stricter values stay allowed. The limits become: memory ≥ 65536 KiB; time cost ≥ 3; fails per account ≤ 5; fails per IP ≤ 20; window ≥ 15; lock after ≤ 10; lock minutes ≥ 30; step-up ≤ 5; skew ≤ 1; enrolment link ≤ 30. Keep a sensible strict end, for example memory ≤ 131072 for the 512 MiB limit. If the builder wants room to lower Argon2 memory for RAM (plan Risk 3), that is a T5 change: ask the owner and record it in DECISIONS as an exception.
- Owner: builder
- Disposition: deferred to M3b-2. That is the first PR that reads any value (Argon2). It must land before M3c reads the limits.
- Verification: `app/tests/settings_env.py` `AUTH_BOUNDS` and `test_auth_settings.py` show the new ends. A planted `SKIW_AUTH_FAILS_PER_ACCOUNT=6` fails settings import.
- Status: open

### [P2] The new `django.request` log line prints exception messages, and a database error message can carry an email
- Category: privacy (log content)
- Rule: UNI-09 ("Logs … carry no PII, tokens, passwords or secret values")
- Evidence:
  - `app/config/settings.py`: `"django.request": {"handlers": ["stderr"], "level": "ERROR", ...}`, with the default formatter. Django logs a 500 with `exc_info`, so the full traceback and the exception message reach stderr.
  - The PR's own test asserts this: `assert lines[-1] == "RuntimeError: planted failure"` in `test_a_500_logs_its_path_and_traceback_to_stderr_but_no_request_data`.
  - I checked what Postgres puts in that message, against the live test database (psycopg, a temp table with `email text unique`). A duplicate insert raised `UniqueViolation | duplicate key value violates unique constraint "t_email_key" / DETAIL:  Key (email)=(person@example.test) already exists.`
  - From M3d on, `app_user` has a global `uq(email)` (spec §4.1).
  - The log line also carries `request.path`. A token placed in a path (for example an enrolment link) would be logged on any 500.
- Failure scenario: in M3e, two enrolments for the same email race. One hits the unique constraint, and the view does not catch it. The 500 log line in the `web` container log holds the staff member's email. Container logs are not treated as PII stores.
- Why it matters: this is the line I asked for in the PR 77 review (residual risk). I did not point out then that tracebacks carry exception text. The test proves the request body, query string and cookies stay out, which is good. The exception text is the gap.
- Required correction:
  1. Format `django.request` records so the traceback keeps the exception class and the stack frames, but not the exception message. For example, add a `logging.Formatter` subclass whose `formatException` prints the frames plus `type(exc).__name__` only.
  2. Add a test: a view raises an exception whose message holds a marker such as `person@example.test`. The class name and frames reach stderr; the marker does not.
  3. In the M3e plan text or self-check, state that no token travels in a URL path. The enrolment token goes in a POST body or a URL fragment.
- Owner: builder
- Disposition: deferred to M3d (before the first table that holds PII, `app_user`). Item 3 goes to M3e.
- Verification: the new test, in the M3d review.
- Status: open

### Notes (no severity)
- **The PR 77 P3 (CI note) is closed.** DECISIONS M3a point (8) now cites CI run 41206976831.
- **The `propagate: True` survivor is acceptable.** It shows only with DEBUG on, as a duplicate line.
- **Local DEBUG console loses Django 404/405 warnings.** This is a small loss for local work. It is not a defect.
- **Owner Q6 (a).** DECISIONS records that the step-up age moves into `setting` in M5. Fine.
- **No text in the PR body is addressed to an AI agent.**

### Self-check audit

I read the diff and built this list before I read the PR body.

My applicability list:
- UNI-01, 02, 03, 05, 07, 08, 09, 13 and 16 apply: config values, key reader, log output, wiring and runbooks.
- UNI-06, 10–12, 14, 15, 17–19 are n-a: no dependency, audit, service, lockfile, migration, header or route.
- AUTH-04 is prerequisite only (Argon2 values). Other AUTH rules are n-a until a route exists.
- TEN rules are n-a: no table or grant.
- FE rules are n-a: no web change. E2E still runs.
- PROJECT §9: the key mounts.

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy: 124 files, no issues | none |
| UNI-02 | yes (12 values) | pass | pass with gap | in config, required, fail closed; but the bounds allow weaker than spec | P2 (bounds) |
| UNI-03 | yes (key lines, values) | pass | pass | `test_auth_settings.py` malformed matrix; `v65536` refused | none |
| UNI-05 | yes | pass | pass | values without readers are recorded with their reader PR, like M2b | none |
| UNI-07, 08 | yes | pass | pass | `make .env` generates `LOGIN_BLOB_KEY`; none in `.env.example`; added-line scan clean | none |
| UNI-09 | yes (`django.request`) | pass | gap | exception messages reach stderr | P2 (log) |
| UNI-13 | yes | pass | pass | CI run 41214485033 green | none |
| UNI-16 | yes | pass | pass | `local-dev.md`, `host-rebuild.md` | none |
| AUTH-04 (prereq) | yes (Argon2 values) | — | gap | same as UNI-02 bounds | P2 (bounds) |
| PROJECT §9 | yes | pass | pass | `LOGIN_BLOB_KEY_FILE` on web and worker only (`test_compose_config.py`) | none |
| Others | n-a | n/a | n/a | — | none |

### Verification performed
| Command / check | Result |
|---|---|
| `git diff --check 77d0569...0268453` | clean |
| `make lint` | ruff pass; 10 contracts kept; Semgrep 9 rules 0 findings; `--test` 9/9 |
| `make typecheck` | mypy: no issues in 124 files; `tsc` pass |
| `make test` | 1372 passed; vitest 4 passed |
| `make host-test` | 832 passed |
| `make test-live` (Docker db) | 126 passed |
| psycopg `UniqueViolation` text (live db, temp table) | message carries the duplicate email in `DETAIL` |
| `make host-test-live`, `make e2e`, registry Semgrep | not run locally; CI run 41214485033 on `02684530`: checks, host, image, security pass |
| Counts vs PR body | match (1372, 832, 126) |
| Added-line secret scan; PR body scan for agent-addressed text | clean; none |
| Clean-up: `docker compose down -v`, `rm .env`, `git clean -fdX` | done |
| End: GitHub head re-read; checkout `git status --untracked-files=no` | unchanged; clean |

### Residual risks and test gaps
- The 500 line is proven in a subprocess with the Django test client, not under uvicorn in a host container.
- The M3a P3 (`unmatched_ignore_imports_alerting`) stays open for M3e.

### Required before merge
- None.

### Deferred conditions
- P2 bounds → M3b-2.
- P2 `django.request` exception text → M3d; the no-token-in-path rule → M3e.

### Optional improvements
- None.
