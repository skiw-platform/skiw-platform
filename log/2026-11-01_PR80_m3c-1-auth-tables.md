# PR 80 — feat(auth): M3c-1 auth tables, grants, Semgrep rule

- **Merged:** 2026-11-01 (07:56:13 UTC) · **Merge commit:** 559a8c4bb9bf33593a1d66e7154d46cad13dbc36 · **Branch:** feat/m3c-throttle-and-security-events
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-80.receipt on agent-logs (commit 1df9a4b; receipt time 2026-11-01T07:55:54Z, before merge)
- **Merge evidence:** `gh pr view 80` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 1de1cb95f2d98602c2e7ed0b0209878da6e5c4bb
- **Drafted by:** Claude Sonnet 5.5 (Opus sub-agent wrote the code) · **Final verdict:** Approved with conditions (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 (unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3c · **Milestone:** M3 auth, M3c-1

## What changed
Migration `accounts/0002` adds `auth_throttle` and `security_event` (Django models plus a grants RunSQL). `skiw_app` gets SELECT/INSERT/UPDATE on `auth_throttle` and SELECT/INSERT only on `security_event`. CHECK `length = 32` on the three HMAC columns. Grant audit extended; new live test for CHECKs and append-only. New Semgrep rule `auth-tables-accounts-only`. Bob's two PR 79 P3 blob tests added and a docstring fixed. 10 files, +316 code/tests/config, +16 docs. No writer yet.

## Why
Plan §3 M3c first half (plan's 450-line rule split M3c in two).

## Review rounds
- R1: no P0 or P1. One P2 and one P3 deferred (below).

## Deferred conditions
- P2 Semgrep SQL check only matches a string that starts with the write verb (regex anchoring and manager names) → M3c-2.
- P3 per-rule self-check in the PR body → M3c-2.

## Decisions worth keeping
- Tables as Django models: raw RunSQL DDL failed lintmigrations.
- CHECK constraints are a builder addition [A]; a live test exists because dropping a CHECK broke no test before.
- `skiw_auth_lookup` INSERT on `security_event` is NOT here (M4-core / M3e).
- Mutation check: 13 killed, 0 survived.
- Process: sub-agent made one failed login on port 5432 (BOMY DB, placeholder user) via the Makefile TOOL_ENV default; no data read or written; stated in PR body.

## Follow-ups
- M3c-2: throttle, client_ip, record_event, lock; fix the P2 Semgrep anchoring; per-rule self-check; mutation sweep of the parked live tests (.agent/auto/m3c-2/NOTES.md); optionally point TOOL_ENV placeholder DATABASE_URL at an unused port.
- M3e: password length cap, one normalised email, warm dummy hash at start-up, reset unmatched_ignore alerting, host_live same-origin POST, no-token-in-path.
- M3d: `django.request` exception text (PII risk).

## Appendix — final review round
# Review — PR #80

## Round 1 — 2026-11-01 · scope: slice (M3c-1, first half of plan §3 M3c; plan `docs/plans/2026-10-31-m3-auth.md`)
- **Code review:** base (merge base) `d676a63347037dbd38c8fbf063e214757b16078b` · head `1de1cb95f2d98602c2e7ed0b0209878da6e5c4bb` · head re-checked at end: yes (GitHub; OPEN)
- **Spec review:** spec path `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash (`git hash-object`) `92841ba555e9e857ac70e86a5b043cf9729ed371` (unchanged by this PR)
- Review checkout: `.agent/worktrees/review-80-1de1cb95` (detached worktree at the head SHA). Semgrep probes and the fixed-rule check ran on copies in the reviewer's scratch folder, never in the checkout.

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier, `PROJECT.md` §6) · **Switch model next step?** No — M3c-2 (throttle, lock, client IP) needs the deep tier.

### Findings

No P0 or P1 findings. The schema and grants match spec §4.1 and plan M3c exactly. I checked them in the live database as `skiw_migrator`:
- `auth_throttle(key_hmac bytea, window_start timestamptz, count integer)`, primary key `(key_hmac, window_start)`. `security_event(id uuid, at timestamptz, kind varchar, email_hmac bytea null, ip_hmac bytea null, details_json jsonb)`.
- Owner `skiw_migrator` on both. ACL: `skiw_app=arw` on `auth_throttle`, `skiw_app=ar` on `security_event`. No other grantee. `skiw_backup` reads through `pg_read_all_data`, the same as the older tables.
- CHECKs: `length(key_hmac) = 32`, `length(email_hmac) = 32`, `length(ip_hmac) = 32`, `count >= 0`. NULL still passes the two nullable columns, as DECISIONS says.
- The live tests run as `skiw_app` (`DATABASE_URL` → `current_user = skiw_app`), so the InsufficientPrivilege tests prove the real role.
- The PR 79 P3 is closed: both blob tests are in `test_auth_blob.py`, and the builder's mutation run kills each.

One P2 is deferred. Nothing outside `accounts` writes these tables today, so merging now is safe.

### [P2] The Semgrep SQL check only matches a string that starts with the write verb
- Category: security control (lint boundary)
- Rule: UNI-04; spec §4.1 ("Only `accounts.auth`" for both tables); TEN-10; plan M3c (Semgrep `auth-tables-accounts-only`)
- Evidence: `semgrep/auth-tables-accounts-only.yml`, `regex: (?is)\b(insert|update|...)\b.*\b(auth_throttle|security_event|auth_stepup)\b`. Semgrep applies `metavariable-regex` from the start of the value, like Python `re.match`. In a scratch copy (a probe file in `app/billing/`), the rule did **not** flag any of these:
  - `"""` + newline + `UPDATE auth_throttle SET count = 0` (the usual style for multi-line SQL)
  - `" DELETE FROM auth_throttle"` (leading space)
  - `"WITH d AS (DELETE FROM auth_throttle RETURNING 1) SELECT count(*) FROM d"`
  - `"SELECT 1; UPDATE auth_throttle SET count = 0"`
  - `"-- reset\nUPDATE auth_throttle SET count = 0"`
  
  It also did not flag `AuthThrottle._default_manager.all().delete()` (the model patterns name only `.objects`).
  Every `ruleid` line in the fixture starts with the verb, so `--test` cannot see the gap. The DECISIONS mutation list ("No survivors") and "Not proven here" do not mention it.
- Failure scenario: a later PR in another app adds a maintenance job with `cursor.execute("""\n  UPDATE auth_throttle SET count = 0\n""")`. `skiw_app` holds UPDATE on `auth_throttle`, so the database allows it. Semgrep passes. The throttle and soft-lock reset with no review signal. For `security_event` the grants still stop UPDATE and DELETE, but an INSERT from outside `accounts.auth` (junk events) also slips past.
- Why it matters: for `auth_throttle` this rule is the only code-level guard. The grants allow writes from any code in `web`.
- Required correction:
  1. Let the regex match anywhere in the string. For example, start it with `^.*?`: `(?is)^.*?\b(insert|update|delete|truncate|copy|merge|alter|drop|grant|revoke|lock)\b.*\b(auth_throttle|security_event|auth_stepup)\b`. I tested this in scratch: all 5 cases above are flagged; the rule still gives 0 findings on `app/` at this head; `semgrep --test` still passes 10/10.
  2. Also match `_default_manager` and `_base_manager`, not only `.objects`. For example `AuthThrottle.$M` with a `metavariable-regex` on `$M`: `^(objects|_default_manager|_base_manager)$`. Do the same for the `accounts.models.` and `accounts.auth.tables.` forms.
  3. Add `ruleid` lines to `semgrep/auth-tables-accounts-only.py`: a triple-quoted SQL with a leading newline, a leading space, a CTE, a second statement, and `_default_manager`.
  4. Correct the M3c-1 mutation and "Not proven" text in the M3c-2 DECISIONS entry.
- Owner: builder
- Disposition: deferred to M3c-2 (the next PR, stacked on this one). It must land before any code outside `accounts` touches the database by raw SQL.
- Verification: the M3c-2 review re-runs the 5 probe strings and `_default_manager` against the rule.
- Status: open

### [P3] The PR self-check lists commands, not rules
- Category: process
- Rule: reviewer role §3 (self-check audit); builder self-check template
- Evidence: the PR body "Self-check" table has `make` targets and results only. It gives no pass or n/a claim per rule (UNI, TEN, AUTH). Earlier PRs (77, 78, 79) gave one.
- Failure scenario: a rule the builder skipped looks covered, and the reviewer cannot tell a skipped rule from a judged n/a.
- Required correction: in M3c-2, add the per-rule self-check table.
- Owner: builder
- Disposition: deferred to M3c-2
- Status: open

### Notes (no severity)
- **DECISIONS points to an untracked file.** It says the soft-lock proposal is in `.agent/auto/m3c-2/NOTES.md` in the main checkout. That file is not in the repo and can disappear. I did not read it. The M3c-2 DECISIONS entry must hold the decision itself. Also note for M3c-2: plan M3c says "lock = count ≥ 10 within the lock window", and spec Flow 5.1 says "10 consecutive fails". M3c-2 must pick one and say why.
- **The `skiw_auth_lookup` INSERT grant on `security_event`** is not here. Plan §0 already lists it for M4-core. Good. Keep it on the M4-core list.
- **The rule also flags reads.** It flags `AuthThrottle.objects` for any use, not only writes. That is stricter than its message says. It is fine.
- **The closed-list test** (`test_every_table_is_in_the_closed_global_list`) is a good addition. M4-core must extend it with the schema check.
- **Port 5432 on this machine is another project's database.** The PR body says one `makemigrations` run tried to log in there. `TOOL_ENV` in the `Makefile` points `DATABASE_URL` at `localhost:5432`, and the BOMY Postgres listens on that port here. Nothing was read or written. This is older than this PR. A later PR can point `TOOL_ENV` at a port nothing uses.
- **No text in the PR body is addressed to an AI agent.**

### Self-check audit

I read the diff and built this list before I read the PR body.

My applicability list:
- UNI-01, 03, 04, 05, 07, 08, 09, 10, 13 and 15 apply: new models, CHECKs on input shape, a Semgrep rule, tables with no writer yet, a migration, `__str__` with no key, append-only evidence.
- UNI-02, 06, 11, 12, 14, 16–19 are n-a: no config value, dependency, external service, lockfile, header, runbook step, web change or route.
- AUTH-06 is prerequisite only (the table). Its behaviour is M3c-2.
- TEN-01/02 (owner and grants), TEN-03 (append-only) and TEN-10 (only `accounts.auth`) apply. Other TEN rules are n-a: no tenant-owned table.
- FE rules are n-a. E2E still runs in CI.

The builder gave no per-rule claims (P3 above), so the "Builder said" column is "—".

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | — | pass | mypy: no issues in 132 files | none |
| UNI-03 | yes (HMAC columns) | — | pass | 32-byte CHECKs; live test refuses 20 and 33 bytes | none |
| UNI-04 | yes (Semgrep rule) | — | gap | the regex is start-anchored; `_default_manager` missed | P2 |
| UNI-05 | yes (no writer yet) | — | pass | writer is M3c-2, recorded; M3b-1 pattern | none |
| UNI-07, 08 | yes | — | pass | added-line secret scan clean | none |
| UNI-09 | yes (`__str__`) | — | pass | no key, window or count in reprs | none |
| UNI-10 | yes (evidence table) | — | pass | `security_event` INSERT/SELECT only | none |
| UNI-13 | yes | — | pass | CI run 41283839938: checks, host, image, security pass | none |
| UNI-15 | yes (migration) | — | pass | `lintmigrations`, `makemigrations --check` clean in `make test-live` | none |
| AUTH-06 (prereq) | yes (table) | — | pass | spec §4.1 columns | none |
| TEN-01/02 | yes | — | pass | owner `skiw_migrator`; ACL exact (live) | none |
| TEN-03 | yes | — | pass | UPDATE, DELETE, TRUNCATE refused as `skiw_app` (live) | none |
| TEN-10 | yes | — | gap | same as UNI-04 | P2 |
| Others | n-a | — | n/a | — | none |

### Verification performed
| Command / check | Result |
|---|---|
| `git diff --check d676a63...1de1cb9` | clean |
| `make lint` | ruff pass; 10 contracts kept; Semgrep 10 rules on 96 files, 0 findings; `--test` 10/10 |
| `make typecheck` | mypy: no issues in 132 files; `tsc` pass |
| `make test` | 1405 passed; vitest 4 passed |
| `make host-test` | 832 passed |
| `make test-live` (Docker db, own Compose project, port 5436) | 139 passed; migrate, `lintmigrations` clean |
| `make audit-python` | no known vulnerabilities |
| Live db as `skiw_migrator`: owner, ACL, constraints, columns | match spec §4.1 and plan M3c |
| Live db: `current_user` for `DATABASE_URL` | `skiw_app` |
| Scratch Semgrep probes (17 forms in 3 runs) | flagged: module alias, implicit concat, f-string with literal table, aliased `.objects`; missed: `_default_manager`, `apps.get_model`, f-string variable, leading-newline triple quote, leading space, CTE, second statement, leading comment |
| Scratch: fixed regex `^.*?` on the same probes, on `app/`, and `--test` | all 5 SQL cases flagged; 0 findings on `app/`; 10/10 |
| `make host-test-live`, `make e2e`, registry Semgrep | not run locally; CI run 41283839938 on `1de1cb95`: checks, host, image, security pass |
| Counts vs PR body | match (1405, 832, 139) |
| Added-line secret scan; PR body scan for agent-addressed text | clean; none |
| Clean-up: `docker compose down -v`, `rm .env`, `git clean -fdX` | done |
| End: GitHub head re-read; checkout `git status --untracked-files=no` | unchanged (OPEN); clean |

### Residual risks and test gaps
- All throttle behaviour waits for M3c-2 (plan §6: concurrency, window roll-over, lock and release, unknown email, no raw value in SQL parameters, XFF).
- SQL built at run time stays outside any lint rule. The grants are the hard limit, and they allow `auth_throttle` writes from any `web` code.
- Still open from earlier rounds: PR 78 P2 (`django.request` exception text) → M3d; PR 78 no-token-in-path rule → M3e; PR 77 P3 (`warn` switch-back) → M3e.

### Required before merge
- None.

### Deferred conditions
- P2 Semgrep regex anchoring and manager names → M3c-2.
- P3 per-rule self-check → M3c-2.

### Optional improvements
- Point `TOOL_ENV`'s placeholder `DATABASE_URL` at a port that nothing uses.
