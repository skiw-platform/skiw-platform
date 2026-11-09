# PR 134 — feat(accounts): M3f-3c-2 second-factor sign-in route

- **Merged:** 2026-11-09 (01:57:44 UTC) · **Merge commit:** 735ccd4d63f458c799b78921766e52dc2b5d2c27 · **Branch:** feat/m3f-3c-2-second-factor-route (final head dfbbfe4545dc6e33ea5665bfd3fb8d8526b7ad29)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-134.receipt`, 2026-11-09T01:57:21Z, review-file hash 2de24929, review commit 70b548c) precedes the merge by 23 seconds (a thin margin, but before it).
- **Approval receipt:** `reviews/PR-134.receipt` on agent-logs (written by `approved 134` after the review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 134` state MERGED, mergedAt 2026-11-09T01:57:44Z, merge commit 735ccd4; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder (reviewed by Claude Opus 5.5, deep tier) · **Final verdict:** Approved (Round 1; the only round)
- **Spec:** v1.22 (hash 79a9a40e, unchanged), Flow 5.1 (2), (3) and "Failures"; D6, D7 · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3f · **Milestone:** M3, M3f-3c-2 (ninth and last of the M3f-3 PRs; closes M3f-3c)

## What changed
`POST /api/auth/second-factor` (`accounts.views.login_second_factor`, route `auth-second-factor`, `auth="cookie"`, JSON or form `{"code": "…"}`) calls `second_factor.attempt` and, on `Passed`, `login(request, user, factor=outcome.factor)`. Answers (AUTH-05, `no-store`): 200 `{"next": "signed_in", "csrf"}`; 400 `invalid` for a body without a text `code` (counts nothing); 401 `login-expired` for every pending-state failure (none, an enrolment's, expired, user no longer `active`); 401 `code-wrong`; 429 `limited` for the attempt budget and the factor lock alike. `PUBLIC_ROUTES["auth-second-factor"]` and a CSRF-gate fixture. Tests: 15 in `test_second_factor_route_live.py`; the enrolment route tests gain the `action-probe` check and a before-the-marker session test (PR 129 R1 P2). Runbook: the lock is checked at sign-in, and the `factor.locked` query groups by user. DECISIONS "M3f-3c-2". +324/−10 over 8 files (code about 50, tests about 250, docs about 24).

## Why
Plan M3f-3c-2: the route that makes the second factor a sign-in. Closes PR 129 R1 P2 (an enrolled session was never shown to pass `authorized_action`), takes PR 132 R1 P3 (a failed `login()` after `Passed` spends the code) and PR 133 R1 P3 #1 (per-user runbook query) and PR 133's residual (the lock tested through a route).

## Review rounds
- R1: Approved. `auth-second-factor` signed off in `PUBLIC_ROUTES` (AUTH-02, UNI-19); AUTH-01 counted as applying and met through the public pre-session pattern, as for `auth-login` and `auth-enrol-totp-confirm`. The gate from PR 132 R1 P2 (3c-1d merged first) was met. PR 129 R1 P2, PR 132 R1 P3 (the deviation of reading the `AppUser` row between `Passed` and `login()` accepted: same failure class, and `authorized_action` re-checks `status = 'active'` on every request), PR 133 R1 P3 #1 and the lock-through-a-route residual are resolved. Nothing was required before merge. Finding:
  - [P3] "the pending login is as it was" holds only if `login()` fails before `cycle_key()` deletes the old session row; after that the cookie names a deleted row, the next POST is `login-expired` and the user starts again at the password step. The code stays spent either way, so there is no security effect, but the text promises a retry that may not exist.

## Deferred conditions
- **P3 (optional) → next touch of the DECISIONS "M3f-3c-2" entry or the `login_second_factor` docstring:** say "the user can try another code, or, if the old session row was already rotated away, starts again at the password step".
- Nothing else is open from this PR. Still standing from earlier rounds: spec D20 P3 and the M3 row "AUTH-01..09" at the next spec touch; owner decision on whether M3g moves after M3i; owner Q4 (a) alert path before M17.

## Decisions worth keeping
- `unavailable` is its own 401 `login-expired`, not `code-wrong`: the page sends the user back to the password step, and a holder of a pending session learns nothing about any account. The lock and the attempt budget give the same 429 `limited` (no distinct 423).
- A recovery-code sign-in writes no revocation marker (AUTH-07; tested: a second session stays signed in).
- A failure after `Passed` (the row read or `login()`) spends the code and nothing restores it: restoring would reopen replay. Pinned by a test.
- The answer holds no recovery-code count; a later change can add one.

## Follow-ups
- M3f-3c is done. Next in the plan (docs/plans/2026-10-31-m3-auth.md §3 M3f/M3g/M3h/M3i): check which PR follows (M3g passkeys, M3h extra check and sign-out, M3i sign-in screens); the owner's decision on moving M3g after M3i is still open.
- Residual risk from the review: a user disabled between `Passed` and `login()` is logged in, but `authorized_action` refuses the first action.
- Mutants: 7 of 7 killed, including the enrolment revocation marker not written.

## Appendix — final review round

## Round 1 — 2026-11-08 · scope: slice (M3f-3c-2; last PR of M3f-3c, first public route that completes a sign-in)
- **Code review:** base (merge base) c422746434fa2ee63bd71e5e21a7818faaca5e15 · head dfbbfe4545dc6e33ea5665bfd3fb8d8526b7ad29 · head re-checked at end: yes (host head unchanged, PR open, CI finished; detached checkout `git status --untracked-files=no` clean)
- **Gate from PR 132 R1 P2:** 3c-1d (PR 133) was merged at 2026-11-08T14:04:00Z, before this round. Met.
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22 (unchanged by this PR): Flow 5.1 (2), (3) and "Failures"; D6, D7. Plan: docs/plans/2026-10-31-m3-auth.md §3 M3f. Carry-overs checked: PR 129 R1 P2; PR 132 R1 P3; PR 133 R1 P3 #1 and its residual (the lock through a route).

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. M3f-3d onward is still auth.

### PUBLIC_ROUTES sign-off (AUTH-02, UNI-19)
- **`auth-second-factor`: signed off** for head dfbbfe45.
  - It serves only a pending login session: `factors.pending` with `enrol` false.
  - Every other state gets the one 401 `login-expired` (parametrised test over none, enrolment, expired and inactive: same status, same body, and no new session cookie except where an expired state is cleared).
  - Wrong codes are counted per user, and ten in a row lock the user (PR 133). The lock and the budget give the same 429 `limited`.
  - Only `login()` turns the session into a login.
  - It is in the CSRF gate (fixture: no `code` gives 400), and the registry entry's reason matches the code.
- **AUTH-01:** I count it as applying and met through the public pre-session pattern, as for `auth-login` (PR 113/115) and `auth-enrol-totp-confirm` (PR 129). The ordered check runs inside `second_factor.attempt` (pending state → count/lock → `with_agency` → active → compare), then `login()`.

### Carry-overs (re-inspected, not taken from the PR body)
- **PR 129 R1 P2 (enrolled session through `authorized_action`): resolved.**
  - The full enrolment flow now POSTs the test-only `action-probe` (`tests/csrf_urls.py:24`, `@authorized_action`) with the new session, and gets 200.
  - `test_a_session_signed_in_before_the_enrolment_marker_is_refused` shows both sides: a session logged in before `confirm_totp` gets 401 on the probe, and the new session gets 200.
  - The sign-in tests do the same after a TOTP sign-in. A recovery-code sign-in leaves a second session signed in (no marker, AUTH-07).
  - The builder reports the mutant "enrolment marker not written" as killed (list reviewed, not re-run).
- **PR 132 R1 P3 (a code spent if `login()` fails): resolved, with one wording point (P3 #1).**
  - The cost is recorded in DECISIONS M3f-3c-2 and the view docstring.
  - `test_a_failure_in_login_after_the_attempt_spends_the_code` pins it: 9 recovery codes left, the spent one gives `code-wrong`, and the next one signs in.
  - **The deviation is accepted.** Reading the `AppUser` row between `Passed` and `login()` has the same failure class, and changing `Passed` or `login()` would change merged APIs for no gain.
  - A user disabled in that gap would still be logged in, but `authorized_action` re-checks `status = 'active'` on every request (`wrapper.py:121`), so the first action is refused.
- **PR 133 R1 P3 #1 (runbook query per user): resolved.** It groups by `encode(email_hmac, 'hex')`, with the line that the hash can't be reversed.
- **PR 133 R1 residual (the lock through a route): resolved.**
  - `test_a_locked_user_gets_the_limited_answer_even_with_the_right_code` sends ten wrong codes across two windows, alternating TOTP and the recovery-shaped `WRONGWRONGWRONG0`, with a fresh password step each window.
  - Then, in a fresh window, the right code gets 429 `limited`. The budget is still 0 and the probe gives 401, so the refusal comes from the lock, not the budget.

### Findings

### [P3] "The pending login is as it was" holds only if `login()` fails before the old session row is deleted
- Category: documentation
- Evidence:
  - DECISIONS M3f-3c-2 and the view docstring say that after a failed `login()`, "the 500 saves no session, so the stored pending login is as it was and the user can try another code".
  - That is true for the tested failure: the test monkeypatches `views.login` to raise before it does anything.
  - But `login()` → `_rotate` → `session.cycle_key()` (Django's: `create()` the new row, then `delete(old key)`) deletes the old row before `login()` returns.
  - A failure after that point (the middleware's save of the new session, for example) leaves the browser's cookie naming a deleted row. The next POST is then `login-expired`, and the user starts again at the password step.
- Failure scenario: none for security. The code stays spent either way, and that is the property that matters. The text just promises a retry that may not exist.
- Required correction: say "the user can try another code, or, if the old session row was already rotated away, starts again at the password step". Do it at the next touch of the entry or the docstring.
- Owner: builder · Status: open (optional)

No prompt-injection text found in the PR body, commit message, code, tests or docs.

**Design calls [A], reviewer answers:**
1. **`unavailable` is its own 401 `login-expired`:** confirmed. Only the holder of the session sees it, and the reason (none, enrolment, expired or inactive) is not revealed. The page needs it to go back to the password step.
2. **The lock and the budget share 429 `limited`:** confirmed (AUTH-05). No 423.
3. **A recovery-code sign-in writes no revocation marker:** confirmed (AUTH-07, plan M3f). Tested.
4. **No recovery-code count in the answer:** confirmed. Nothing requires it, and leaving it out adds nothing to the response.

**Code read (beyond the self-check):**
- `_text(code)` refuses non-strings, and `None`, `[]` and integers give 400 with nothing counted (test). The candidate's length is bounded in `second_factor`.
- `Cache-Control: no-store` comes from `_answer` on every branch.
- The 200 body is only `next` and the rotated CSRF token.
- `login()` cycles the key, so a pre-login session id doesn't survive.
- TEN-09/11: the user and agency come only from the MAC-verified pending session. The route's row read is under `with_agency(outcome.agency_id)`.
- No IP throttle on this route. That is acceptable, because each request needs a pending session, which needs the password step, and that step is throttled per account and per IP.

### Self-check audit
| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy 225 files | — |
| UNI-02 | yes | pass | pass | no new value | — |
| UNI-03 | yes (body) | pass | pass | `_body` / `_text`; parametrised invalid-body test | — |
| UNI-04 | yes | pass | pass | contracts kept; Semgrep 0 / 20 rules; rule tests 20/20 | — |
| UNI-05 | yes | pass | pass | the route is `attempt`'s caller | — |
| UNI-07 (hard) | yes | pass | pass | CI `security` green; diff has no values | — |
| UNI-09 | yes | pass | pass | no logging in the route; no account data in answers | — |
| UNI-13 | yes | pass | pass | CI green on dfbbfe45; local runs below | — |
| UNI-16 | yes (runbook) | pass | pass | "Enrol a user": route named, per-user query | — |
| UNI-17 | yes | pass | pass | `no-store` on every branch; CSRF rotated and returned | — |
| UNI-18/19 | yes | pass | pass | CSRF gate fixture; registry entry signed off above | — |
| AUTH-01 (hard) | yes | pass (pattern) | pass (pattern) | ordered check in `attempt`, then `login()` | — |
| AUTH-02 | yes | pass | pass, signed off | `PUBLIC_ROUTES["auth-second-factor"]` | — |
| AUTH-05 | yes | pass | pass | one `login-expired` over four causes; one `limited` for budget and lock | — |
| AUTH-06 | yes | pass | pass | five wrong then `limited`; lock end to end through the route | — |
| AUTH-07 | yes | pass | pass | enrolment marker refuses the older session, the new one passes; recovery use writes none | — |
| TEN-02 (hard) | yes | pass | pass | live tests as `skiw_app` | — |
| TEN-08 | n/a, no new table or path | n/a | n/a | — | — |
| TEN-09 (hard) | yes | pass | pass | row read under `with_agency(outcome.agency_id)` | — |
| TEN-10 | yes | pass | pass | `accounts` views only; Semgrep clean | — |
| TEN-11/12 | yes | pass | pass | no tenant input from the body | — |
| FE, EVT, MON, REC, FILE | n/a, no UI (M3i), job, money, record or file | n/a | n/a | — | — |

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-134-dfbbfe45` at dfbbfe45 | created, reviewed, ignored output cleaned, removed without `--force` |
| `git diff --check c422746...dfbbfe4` | clean |
| `make lint` | pass (contracts kept, Semgrep 0 findings / 20 rules, rule tests 20/20, eslint) |
| `make typecheck` | pass (mypy 225 files; tsc) |
| `make test` | 1702 passed; web 4 passed (matches PR) |
| `make test-live` (disposable Compose DB on port 5436, removed with `down -v`) | 706 passed (matches PR) |
| `pytest -m live` on the two route test files, 3 runs | 29/29 passed each run |
| PR 133 merge time (gate) | merged 2026-11-08T14:04:00Z |
| CI on head dfbbfe45 | checks, security, image, host: pass; publish/deploy-staging skipped |
| Host head SHA at end | dfbbfe4545dc6e33ea5665bfd3fb8d8526b7ad29, unchanged |
| Not run | builder's 7 mutants (list reviewed); `make e2e` (no screen until M3i), `host-test`, `secrets-test` (no host or env change; CI covers them) |

### Residual risks and test gaps
- The `authorized_action` check compares the marker's DB `now()` with the Python-side `_skiw_auth_at`. The tests pass because the DB and the app share the host clock (PR 129 R1 measured 0.18–0.38 ms). A DB on a different clock would fail closed (fresh sessions refused), not open.
- A known-password attacker still gets about 10 guesses per 45 minutes, and the lock is visible only to someone who looks, until the Q4 (a) alert path exists (unchanged since PR 131).
- No end-to-end browser test until M3i. The spec M3 row's Playwright items (TOTP sign-in, and a 6th wrong password gives `limited`) are still owed there.
- Flow 5.1 (2)'s passkey second factor and (3) `audit_event(login.success)` are still to come (plan M3g; M5).

### Required before merge
- None.

### Deferred conditions
- None. Every deferred condition carried from PR 128–133 is now resolved.

### Optional improvements
- P3 #1 (the retry wording after a failed `login()`).
