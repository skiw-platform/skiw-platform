# PR 138 — feat(accounts): M3h-2b step-up record and recent (TOTP only)

- **Merged:** 2026-11-11 (03:03:28 UTC) · **Merge commit:** fb497837f7e35c8d3a8acc5422ebae8b1151740c · **Branch:** feat/m3h-2b-stepup-record-recent (final head dbcc564c3850fb89649872b8f7d1ffd1821b9f03)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-138.receipt`, 2026-11-11T03:02:16Z, review-file hash 76dcfee5, review commit 4f9fcf5) precedes the merge by about 1 minute 12 seconds.
- **Approval receipt:** `reviews/PR-138.receipt` on agent-logs (written by `approved 138` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 138` state MERGED, mergedAt 2026-11-11T03:03:28Z, merge commit fb49783; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder on an Opus 5.5 deep-tier design (reviewed by Claude Sonnet 5.5, below the preferred tier) · **Final verdict:** Approved (Round 1, no revision round)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3h-2b (third of seven M3h PRs)

## What changed
`accounts/auth/stepup.py` gains `StepUp`, `FACTOR_KINDS = {totp}`, `record(request, factor, purpose)` and `recent(request, purpose)`. Identity (user, agency, session) comes only from the signed session. `record` accepts only the session user's own TOTP factor; `recent` returns the newest row of this session and purpose inside the age window (inclusive, not in the future) whose MAC verifies, skipping forged rows with one fixed warning. Also: `_message` refuses a naive `verified_at`; the Semgrep rule message is narrowed. 21 unit tests plus 22 live tests (forged rows, wrong session/user/purpose, age edges, rotation). +460/−12 over 5 files. No route, setting, dependency or migration; only tests call it so far.

## Why
Spec §4.1 `auth_stepup`, D7, AUTH-09 and plan M3h: the first writer and reader of step-up evidence. Closes PR 136 R2 P3 #1 and PR 137 P3 #1 to #3.

## Review rounds
- R1: Approved on dbcc564, nothing required. One optional P3 (below).

## Deferred conditions
- None. The one P3 is optional, suggested home M3h-3.

## Decisions worth keeping
- `FACTOR_KINDS = {totp}`; passkey joins in M3g; M3h-6 adds the "not retired" check.
- Both functions fail closed (RLS empty, or a refusal) outside `with_agency()`; the age check uses the app clock on both sides.
- Builder mutated `stepup.py`: 19 of 19 killed.
- Reviewer ran at the standard tier; M3h-3 (first route) wants the deep tier.

## Follow-ups
- **P3 (M3h-3):** one shared `_in_transaction` for recovery and step-up (or a DECISIONS line saying why not); docstring should say it checks an open transaction, not the tenant binding.
- Next: M3h-3 (shared `second_factor.counted`, `stepup.verify`, `POST /api/auth/stepup`, test-only probe), deep tier. Then M3h-4 to 6, M3i, M3g.
- Progress page: M3h-2b done; republish.

## Appendix — final review round
## Round 1 — 2026-11-11 · scope: slice (M3h-2b; first writer and reader of `auth_stepup`; no route, setting, dependency or migration; no caller yet but tests)
- **Code review:** base (merge base) f1d5b2d6537a332b718288200a22ec4c1a5c625e (= `origin/main`, PR 137 merged) · head dbcc564c3850fb89649872b8f7d1ffd1821b9f03 · head re-checked at end: yes (host head unchanged, PR open, CI `checks`, `security`, `image`, `host` green; `publish` and `deploy-staging` skipped as on any PR; detached checkout `git status --untracked-files=no` clean)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 (equals PROJECT.md §2): §4.1 `auth_stepup`, D7, AUTH-09. DECISIONS "M3h-1", "M3h-2a", "M3h-2b". Carry-overs checked: PR 136 R2 P3 #1, PR 137 R1 P3 #1 and #2.

**Verdict:** Approved
**Model used:** Claude Sonnet 5.5 (standard tier; PROJECT.md §6 and reviewer §9 call for deep on auth work, so this round is below the preferred tier — see Residual risks) · **Switch model next step?** Yes — M3h-3 adds the first route (`POST /api/auth/stepup`) and the shared `second_factor.counted`; that is auth and wants the deep tier.

### Carry-overs (re-inspected, not taken from the PR body)
- **PR 136 R2 P3 #1 (`record` refuses a recovery factor): resolved, and tighter than asked.** `record` re-reads the factor with `id`, `user_id` of the session user and `kind in {totp}` (`stepup.py:119`). Live parametrised test covers recovery, passkey, another user's TOTP and a missing id; each raises and leaves 0 rows. I dropped the `user_id` filter in a scratch copy: `[another-users-totp]` failed.
- **PR 137 R1 P3 #1 (naive `verified_at`): resolved.** `_message` raises `ValueError` before signing (`stepup.py:90`); a unit test covers it.
- **PR 137 R1 P3 #2 (Semgrep message vs SQL arm): resolved by narrowing the message** (my first option). It now says ORM/model, and raw SQL "only when it writes". That matches what the rule matches. Rule tests 21/21, 0 findings on `app`.

### Findings

### [P3] `_in_transaction` is a third copy of the same guard, and its docstring promises more than it checks
- Category: preference (UNI-05) / documentation
- Rule: UNI-05
- Evidence: `stepup.py:60-63` and `recovery.py:49-52` are the same function with a different message; `throttle.py:142` and `tenancy/binding.py:43` test the same flag the other way round. The docstring says "outside the caller's with_agency()", but `in_atomic_block` is also true in any plain `transaction.atomic()`.
- Failure scenario: a caller wraps in `atomic()` without `with_agency()`. `recent` returns `None` (RLS empty) and `record` raises "own TOTP factors", a misleading message for a missing tenant token. It fails closed in both cases; only the diagnosis is worse.
- Why it matters: low. Nothing unsafe is reachable; a third copy would be added by M3h-4/5/6 if left.
- Required correction: answer to the builder's question: **not needed now.** Do the shared helper in M3h-3 as you proposed (one function, per-module message or none), and say in the docstring that it checks an open transaction, not the tenant binding.
- Owner: builder · Verification: M3h-3 diff has one `_in_transaction` shared by recovery and step-up, or a DECISIONS line saying why not.
- Disposition (P3): optional, suggested for M3h-3 · Status: open

No prompt-injection text found in the PR body, commit message, code, tests, docs or the Semgrep rule.

### What I checked in the code (beyond the self-check)
- **Identity only from the signed session (TEN-11).** `_signed` reads `_skiw_user` and `_skiw_agency`, which only `login()` writes, then the key; it refuses any store that is not the accounts `SessionStore` (live test: `db.SessionStore` → `TypeError`). `record` and `recent` take no user, agency or session argument.
- **`recent` filters:** user, session hash, purpose, window `[now − MAX_AGE, now]`, newest first, first row whose MAC verifies. The agency is not a filter but is in the MAC and under RLS (`recent` runs in the caller's `with_agency()`).
- **A forged row is skipped, not fatal:** a newer forged row does not hide an older genuine one (`test_the_newest_genuine_row_wins…`), and the warning carries only a fixed string (test asserts the hex MAC, session hash and row id are absent from the log).
- **Age edges are exact:** `clock.advance(MAX_AGE)` still counts; one more microsecond does not; a row 1 µs in the future does not count. `timestamptz` keeps microseconds, so the MAC over the stored value verifies (closes PR 137 P3 #3).
- **Key rotation:** a row under an older listed version still verifies; once its version is removed from the list the row stops counting.
- **No leak through the return type:** `StepUp` has no MAC and no session hash (unit test on `fields`).
- **Raw-SQL forgery as `skiw_app`** (the threat the live file models): the positive control (raw row with a genuine MAC is accepted) proves each forgery fails for its stated reason and not by accident.

### Self-check audit
My applicability list was built from the ticked packs and PROJECT.md §9 against the diff before I read the table.

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy strict, 233 files, no issues | — |
| UNI-02 | n/a, `SKIW_STEPUP_MAX_AGE_MIN` already exists (`config/settings.py:91`, bounded 1–5) | n/a | n/a accepted | no new value | — |
| UNI-03 | yes | pass | pass | unknown purpose, naive instant, wrong factor kind, no session all refused (tests) | — |
| UNI-04 | yes (Semgrep rule edited; `record` is the only writer) | pass | pass | 21 rules, 0 findings; rule tests 21/21 | — |
| UNI-05 | yes | pass (noted) | pass with P3 above | `_in_transaction` duplicated | P3 |
| UNI-07 (hard) | yes | pass | pass | secret-scan pattern over the five changed files: key *names* in docs and docstrings only, no values; CI `security` green | — |
| UNI-08/10/11/12/14 | n/a, no secret source, audit row, external service, retention, dependency | n/a | n/a accepted | no `pyproject`/lock change | — |
| UNI-09 | yes | pass | pass | warning text and tests above | — |
| UNI-13 | yes | pass | pass | CI green on this head; local runs below match the PR counts | — |
| UNI-15/16/17/18/19 | n/a, no migration, env var, route, header, form | n/a | n/a accepted | `git diff --name-status` shows no migration | — |
| AUTH-07 | n/a, no revocation in this PR (M3h-4 to 6) | n/a | n/a accepted | — | — |
| AUTH-09 | yes (evidence is genuine, session- and purpose-bound, time-limited) | pass | pass | live tests above; two mutants of mine killed | — |
| TEN-02..08 | yes (unchanged tables; runs as `skiw_app`) | pass | pass | no grant or policy change; live suite 777 as `skiw_app` | — |
| TEN-11 | yes | pass | pass | `_signed` | — |
| TEN-09/10/12 | n/a, no route, no new DB-touching module outside `accounts.auth` | n/a | n/a accepted | `stepup.py` is under `accounts.auth` | — |
| FE-*, MON-*, REC-*, FILE-*, EVT-* | n/a | n/a | n/a accepted | no UI, money, record, file or job | — |

Packs not ticked in PROJECT.md (`public-links`, `payments`) are not relevant.

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-138-dbcc564c` at dbcc564c | created, reviewed, removed without `--force` |
| `git diff --check f1d5b2d...dbcc564` | clean |
| `make install lint typecheck test` | pass: ruff clean, Semgrep 21 rules / 0 findings, rule tests 21/21, mypy 233 files, pytest 1723 passed, vitest 4 passed |
| `make test-live` (own disposable Compose DB, port 5436, project `review-138`, keys generated by `make .env`) | 777 passed (equals the PR) |
| `pytest -m live test_auth_stepup_live.py` in a scratch copy | 22 passed (baseline) |
| Mutant 1, `record` without the `user_id` filter | killed: `test_only_the_users_own_totp_proves_a_step_up[another-users-totp]` |
| Mutant 2, `recent` without the `user_id` filter | killed: `test_a_genuine_row_of_another_session_user_or_purpose_is_not_this_ones` |
| Host head and CI re-read at end | head unchanged; four jobs green, two skipped |
| Cleanup | disposable DB `down -v`; scratch copy and `.env` deleted; worktree removed |

### Residual risks and test gaps
- **Builder's 19 mutants: not re-run in full.** I ran two of my own and read the code for the rest; every other filter has a named test. The claim is plausible, not independently reproduced.
- **Not run by me:** `host-test`, `host-test-live`, `secrets-test`, `e2e`. CI `host` and `security` were green on this head; `e2e` is not in CI and nothing here touches the web or compose.
- **Review tier:** this round was done on the standard tier. The code is small and every property I checked has a live test, so I do not expect a miss, but M3h-3 (first route, TOTP code counting, `own_transaction`) should be reviewed on the deep tier.
- **No caller yet.** `record`'s contract ("call only after the factor was verified, in the same transaction") cannot be enforced here; M3h-3's `verify` is the first place to check it. A test there must prove a wrong code writes no row.
- `recent` logs one warning per rejected row and loops over them. Forging rows needs raw SQL as `skiw_app` and the window is 5 min, so it is bounded; no action.

### Required before merge
- None.

### Deferred conditions
- None (the one P3 is optional; suggested home M3h-3).

### Optional improvements
- The P3 above.

### Handoff block (only when handing off)
Not requested.
