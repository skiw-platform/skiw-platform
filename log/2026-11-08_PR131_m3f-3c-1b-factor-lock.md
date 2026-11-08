# PR 131 — feat(accounts): M3f-3c-1b second-factor soft-lock and owner alert

- **Merged:** 2026-11-08 (07:17:34 UTC) · **Merge commit:** 2ac4943f4e4aff8e65becdd4e7cbd544b5fdfc1c · **Branch:** feat/m3f-3c-1b-factor-lock (final head 913fd25565f968689243cbaa33fe14567205365d)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-131.receipt`, 2026-11-08T07:17:19Z, review-file hash 4890f211, review commit 3da5729) precedes the merge by 15 seconds (a thin margin, but before it).
- **Approval receipt:** `reviews/PR-131.receipt` on agent-logs (commit acb0845; written by `approved 131` after the review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 131` state MERGED, mergedAt 2026-11-08T07:17:34Z, merge commit 2ac4943; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder (reviewed by Claude Opus 5.5, deep tier) · **Final verdict:** Approved with conditions (Round 1; the only round)
- **Spec:** v1.22 (hash 79a9a40e, unchanged), Flow 5.1 "Failures" · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3f · **Milestone:** M3, M3f-3c-1b (sixth of the now eight M3f-3 PRs)

## What changed
`throttle.factor_failed(user, email, ip)` counts a user's consecutive wrong second-factor codes in one never-windowed row; each `SKIW_AUTH_LOCK_AFTER`-th (10) writes a lock marker row, a `factor.locked` event in `security_event` (HMACs of email and IP, and the count) and a `second factor soft-locked` warning. `factor_reserve` returns None (changes nothing) while a marker is newer than `SKIW_AUTH_LOCK_MIN` (30), so enrolment refuses a locked user too. `factor_reset` ends the run on a verified code. `events.KINDS` gains `factor.locked` (no migration). Runbook "Enrol a user" gains the lock; DECISIONS "M3f-3c-1b" records the split, the reading of Flow 5.1 and the correction to the 3c-1a "one extra guess in flight" cost. +232/−6 over 5 files (code about 49, tests 164, docs about 25). No caller yet.

## Why
PR 130 R1 P2: the count alone lets a holder of the password guess codes all day (5 per 15 minutes) with no soft-lock or alert, and the password counter is cleared at every verified password. Lock plus the sign-in attempt plus tests measured +650, past the plan's ≈ 450, so the lock went first and `second_factor.attempt` follows as 3c-1c.

## Review rounds
- R1: Approved with conditions. All five design calls confirmed (Flow 5.1 "Failures" covers the second factor, Ying may still overrule; a separate per-user run; the lock does not block the password step; the alert is a `security_event` row plus a warning as the M3 mechanism under Q4 (a); enrolment's wrong codes do not feed the run but a locked user is refused there). The extra split accepted. PR 130 R1 P3 #2 resolved. Findings, none blocked the merge:
  - [P2] the lock is on no sign-in path yet (`factor_failed` and `factor_reset` have callers in tests only), so every test here would still pass if 3c-1c forgot or mis-wired them.
  - [P3] `factor_failed` and `factor_reset` do not refuse an open transaction, as `factor_reserve` does; inside `with_agency()` a rollback would take the run increment and the event with it.
  - [P3] "that is the owner alert" says more than the warning does (Q4 (a): the real alert path comes with a spec change before M17); the runbook remedy has no command behind it (the only management command is `accounts_invite`; no password change exists).

## Deferred conditions
- **P2 #1 → M3f-3c-1c:** wiring tests through `second_factor.attempt`: 10 consecutive wrong codes across windows, mixing TOTP and recovery codes, give `limited` for both kinds including a right code until `SKIW_AUTH_LOCK_MIN`; exactly one `factor.locked` event; a right code before the 10th resets the run; enrolment's wrong codes do not feed the run. Verification: those tests plus a mutant that drops the `factor_failed` call.
- **P3 #1 → 3c-1c (or earlier):** add the `connection.in_atomic_block` guard to `factor_failed` and `factor_reset`, with a test.
- **P3 #2 → next docs touch (3c-1c DECISIONS or the runbook):** call it the M3 stand-in under Q4 (a) (an event and a warning nobody receives until the alert path exists); give a real check (`docker compose logs web | grep 'soft-locked'` or the `security_event` query); say plainly there is no password change until the owner's reset is built and the step until then is to tell Ying.
- Inherited, still open: PR 130 R1 P3 #1 (release only before the comparison; already implemented in the 3c-1c code) and PR 128 R1 P3 #1 (real reason for no per-attempt factor event) → 3c-1c; PR 129 R1 P2 (`authorized_action` end to end) → 3c-2.

## Decisions worth keeping
- Wrong second-factor codes feed their own per-user run, not the password lock (`reset_on_success` would keep that at zero). The lock is read before the count, not with it; attempts in flight when it is set are bounded by the count.
- Effect, stated plainly: about 10 guesses per 45 minutes for a known-password attacker with the lock. It is mainly the alert, and until the Q4 (a) alert path exists "alert" means "in the log".
- Anyone who knows the password can keep the real user's second factor locked; inherent in a soft-lock.
- A `tenant_source_key` rotation resets these locks (same accepted property as the password lock). Lock marker and run rows are never pruned (as for the password lock).
- Size rule applied again: a change measured at +650 was split before review.

## Follow-ups
- **3c-1c** (`second_factor.attempt`, written on local branch feat/m3f-3c-1c-second-factor @f5ee6d3, which also holds these 3c-1b parts): new branch from main with only `second_factor.py` and its tests; must carry the three deferred conditions above plus PR 130 R1 P3 #1 and PR 128 R1 P3 #1 and the AUTH-01 self-check wording. Drop the two tests that duplicate `test_factor_count_live.py` to save lines.
- **3c-2:** route `POST /api/auth/second-factor` → `login()`, with the PR 129 R1 P2 test for enrolment and sign-in.
- Owner Q4 (a): the alert path before M17; a password change/owner's reset (Flow 5.1) for the runbook remedy.
- Spec, next touch: D20 parenthetical and the M3 row's "AUTH-01..09". Owner: whether M3g moves after M3i. Dependabot PR 14 and alerts 1 and 2 not looked at.

## Appendix — final review round
## Round 1 — 2026-11-08 · scope: slice (M3f-3c-1b; primitives only, no caller)
- **Code review:** base (merge base) 6ff15e6cba8f66e85af2c0aaae945bbdb8704d81 · head 913fd25565f968689243cbaa33fe14567205365d · head re-checked at end: yes (host head unchanged, PR open, CI finished; detached checkout `git status --untracked-files=no` clean)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22 (unchanged by this PR), Flow 5.1 "Failures". Plan: docs/plans/2026-10-31-m3-auth.md §3 M3f. Carry-overs checked: PR 130 R1 P2, P3 #1, P3 #2; PR 128 R1 P3 #1; PR 129 R1 P2.

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. 3c-1c wires these primitives into sign-in and owes the wiring test, so it stays deep.

### Carry-overs (re-inspected, not taken from the PR body)
- **PR 130 R1 P2 (no soft-lock or alert for second-factor guessing): partly resolved, still open.** See P2 #1 below.
  - The primitives exist and are tested: `factor_failed`, `factor_reset`, and the lock check in `factor_reserve`.
  - The wiring into sign-in is in 3c-1c.
  - I accept the extra split. The condition was that the lock exists and is wired in before any route can sign in, and this order keeps it.
- **PR 130 R1 P3 #2 (wording): resolved.**
  - The runbook line now says "(sign-in from M3f-3c)".
  - DECISIONS M3f-3c-1b corrects the "one extra guess in flight" cost.
- **PR 130 R1 P3 #1 (release only before the comparison):** carried to 3c-1c (DECISIONS "Split"). Still open.
- **PR 128 R1 P3 #1 (reason there is no per-attempt factor event):** carried to 3c-1c. Still open.
- **PR 129 R1 P2 (enrolled session through `authorized_action`):** still due with 3c-2.

### Findings

### [P2] The lock is not yet on any sign-in path (PR 130 R1 P2, carried)
- Category: material risk (forward)
- Rule: AUTH-06; spec Flow 5.1 "Failures"
- Evidence:
  - `factor_failed` and `factor_reset` have no caller in `app/` outside the tests.
  - `factor_reserve` does check the lock, so enrolment already refuses a locked user. But nothing yet feeds the run.
- Failure scenario: 3c-1c could call `factor_reserve` but forget `factor_failed` on a wrong code, call it for a recovery code but not for TOTP, or never call `factor_reset`. The lock would then never trip, or never clear. Every test in this PR would still pass, because they call the primitives directly.
- Required correction (3c-1c): wiring tests through `second_factor.attempt` that show:
  - 10 consecutive wrong codes across windows, mixing TOTP and recovery codes, give `limited` for both kinds of code, including a right code, until `SKIW_AUTH_LOCK_MIN`;
  - one `factor.locked` event is written;
  - a right code before the 10th resets the run;
  - enrolment's wrong codes do not feed the run.
- Owner: builder (3c-1c)
- Verification: 3c-1c review, those tests, plus a mutant that drops the `factor_failed` call.
- Disposition: deferred to M3f-3c-1c.
- Status: open

### [P3] `factor_failed` and `factor_reset` don't refuse an open transaction, as `factor_reserve` does
- Category: material risk (guidance for 3c-1c)
- Evidence:
  - `factor_reserve` raises `TransactionManagementError` inside an atomic block (3c-1a design call 3: a rolled-back count hides a guess).
  - `factor_failed` instead opens its own `transaction.atomic()`, which becomes a savepoint inside a caller's transaction. Its docstring only asks callers to "call it in autocommit".
- Failure scenario: 3c-1c records the wrong code inside `with_agency()` (for example, in a `_confirm`-like helper after the comparison). Anything that later rolls that transaction back, or a fault raised after it, also rolls back the run increment and the `factor.locked` event. Wrong codes then never reach 10.
- Required correction: add the same `connection.in_atomic_block` guard to `factor_failed` (and to `factor_reset` for symmetry), with a test, in 3c-1c or earlier.
- Owner: builder · Status: open (3c-1c)

### [P3] "That is the owner alert" says more than the warning does; the runbook remedy can't be carried out yet
- Category: documentation
- Rule: UNI-16; reviewer §7 runbooks
- Evidence:
  - DECISIONS M3f-3c-1b and the runbook ("Ten wrong codes in a row") call the `security_event` row plus the stderr warning "the owner alert".
  - Owner Q4 (a) (DECISIONS 2026-10-31) and the M3c entry ((4) "The owner alert and the new-device mail stay with the spec change Q4 (a) names") say the actual alert path comes with a spec change before M17. Today nobody is told unless they read the web log or query `security_event`.
  - The runbook's remedy for repeated locks, "change it (the owner's reset, Flow 5.1, is not built yet)", has no command behind it. The only management command is `accounts_invite`.
- Failure scenario: an operator relies on being alerted and never looks. Or they see repeated locks and find no way to change the password.
- Required correction (wording):
  - Call it the M3 stand-in under Q4 (a) (an event and a warning, which nobody receives until the alert path exists).
  - Give the operator a real check, for example the `docker compose logs web | grep 'soft-locked'` form or the `security_event` query used for `account.locked`, if one exists.
  - Say plainly that there is no password change until the owner's reset is built, and that until then the step is to tell Ying.
- Owner: builder · Status: open (optional; next docs touch)

No prompt-injection text found in the PR body, commit message, code, tests or docs.

**Design calls [A], reviewer answers:**
1. **Flow 5.1 "Failures" covers the second factor:** confirmed. "10 consecutive fails → account soft-lock" is about the account, and the second step is part of the account's sign-in. Ying may still overrule.
2. **A separate per-user run:** confirmed. `reset_on_success` clears the password run at every verified password (`throttle.py`), so feeding that run would do nothing. The test proves the factor run survives `reset_on_success`.
3. **The lock does not block the password step:** confirmed. A factor attacker guesses nothing at the password step, and every code is refused while the lock holds, including the right one (`factor_reserve` returns None before the count).
4. **The alert is a `security_event` row plus a warning:** confirmed as the M3 mechanism under Q4 (a). The wording is P3 #2.
5. **Enrolment's wrong codes don't feed the run, but a locked user is refused there too:** confirmed.

**Code read (beyond the self-check):**
- `factor_failed` mirrors `record_failure` line for line:
  - run upsert at RUN, then the marker upsert at `now`, then the event, all in one transaction;
  - the warning only after the commit;
  - the warning carries no HMAC, email or IP.
- The lock check and the run share one HMAC label, `skiw-throttle-factor-lock-v1`. RUN (1970) is never newer than `now − LOCK_MIN`, so the run row cannot read as a marker. That label is not a prefix of any other label, and no other label is a prefix of it.
- A `tenant_source_key` rotation resets these locks too. That is the same accepted property as for the password lock (DECISIONS M3c (1)).
- No migration is needed: `security_event.kind` has no CHECK in `accounts.0002`.

### Self-check audit
| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy 222 files | — |
| UNI-02 | yes (lock values) | pass | pass | existing `SKIW_AUTH_LOCK_AFTER` / `SKIW_AUTH_LOCK_MIN`, no new value | — |
| UNI-03 | n/a, no boundary input | n/a | n/a accepted | callers pass validated values (3c-1c) | — |
| UNI-04 | yes | pass | pass | contracts kept; Semgrep 0 / 20 rules; 20/20 rule tests | — |
| UNI-05 | yes | pass | pass, caller pending | primitives with tests; caller in 3c-1c (P2 #1) | — |
| UNI-07 (hard) | yes | pass | pass | CI `security` green; diff has no values | — |
| UNI-09 | yes | pass | pass | key is an HMAC of the user id; event holds HMACs and an int; test checks the log and the event | — |
| UNI-10 | n/a, `security_event` is the existing pre-tenant table; `audit_event` is M5 | n/a | n/a accepted | — | — |
| UNI-13 | yes | pass | pass | CI green on 913fd255; local runs below | — |
| UNI-15 | n/a, no migration | n/a | n/a accepted | no CHECK on `kind` (0002) | — |
| UNI-16 | yes (auth behaviour, runbook) | pass | pass, wording P3 #2 | "Enrol a user" updated | P3 #2 |
| AUTH-01/02/05 | n/a, no entry point or response | n/a | n/a | library functions | — |
| AUTH-06 | yes | pass | pass for the primitives; wiring owed | 6 live tests, parallel test, 5 clean repeat runs | P2 #1 (3c-1c) |
| AUTH-07 | n/a, marker unchanged | n/a | n/a | — | — |
| TEN-02 (hard) | yes | pass | pass | live tests as `skiw_app` | — |
| TEN-08 | n/a, global tables (spec §4.1) | n/a | n/a | — | — |
| TEN-09 (hard) | yes | pass | pass | no tenant transaction touched | P3 #1 (guard) |
| TEN-10 | yes | pass | pass | writes stay in `accounts.auth.throttle` / `events`; Semgrep clean | — |
| TEN-11/12 | n/a, no tenant input | n/a | n/a | — | — |
| EVT, MON, REC, FILE, FE | n/a | n/a | n/a | the alert path is owner Q4 (a) | — |

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-131-913fd255` at 913fd255 | created, reviewed, ignored output cleaned, removed without `--force` |
| `git diff --check 6ff15e6...913fd25` | clean |
| `make lint` | pass (contracts kept, Semgrep 0 findings / 20 rules, rule tests 20/20, eslint) |
| `make typecheck` | pass (mypy 222 files; tsc) |
| `make test` | 1695 passed; web 4 passed (matches PR) |
| `make test-live` (disposable Compose DB on port 5436, removed with `down -v`) | 649 passed (matches PR: 643 + 6) |
| `pytest -m live` on the lock, count and factors test files, 5 runs | 24/24 passed each run |
| grep for callers of `factor_failed` / `factor_reset` in `app/` | tests only |
| grep `app/accounts/management/commands/` | `accounts_invite` only, so no password-change command exists (P3 #2) |
| CI on head 913fd255 | checks, security, image, host: pass; publish/deploy-staging skipped |
| Host head SHA at end | 913fd25565f968689243cbaa33fe14567205365d, unchanged |
| Not run | builder's 11 mutants (list reviewed); `make e2e`, `host-test`, `secrets-test` (no UI, host or env change; CI covers the last two) |

### Residual risks and test gaps
- A known-password attacker still gets about 10 guesses per 45 minutes. The lock mainly makes guessing visible, and visible means "in the log" until the Q4 (a) alert path exists. Someone has to look.
- Anyone who knows the password can keep the real user's second factor locked. That is inherent in any soft-lock, and the runbook names the cause, but there is no fix until a password change exists.
- Lock marker and run rows are never pruned. That is the same as the password lock and is small.
- Still owed elsewhere: PR 130 R1 P3 #1 and PR 128 R1 P3 #1 (3c-1c); PR 129 R1 P2 (3c-2).

### Required before merge
- None.

### Deferred conditions
- P2 #1 (PR 130 R1 P2): deferred to M3f-3c-1c. The wiring tests through `second_factor.attempt`.

### Optional improvements
- P3 #1 (the transaction guard), for 3c-1c.
- P3 #2 (alert wording and runbook remedy).
