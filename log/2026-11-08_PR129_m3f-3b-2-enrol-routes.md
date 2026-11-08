# PR 129 — feat(accounts): M3f-3b-2 TOTP enrolment routes

- **Merged:** 2026-11-08 (05:16:36 UTC) · **Merge commit:** 037c1800476f029554fd611ce01160b4b1756da7 · **Branch:** feat/m3f-3b-2-enrol-routes (final head c0c98c0a5980a9da6e990b71a621142d0d3a7617)
- **Gate breaches:** none. The review's head SHA equals the PR's final head; the receipt (`reviews/PR-129.receipt`, 2026-11-08T03:41:09Z, review-file hash 506fb0d9, review commit 405eec8) precedes the merge by 1 h 35 min.
- **Approval receipt:** `reviews/PR-129.receipt` on agent-logs (written by `approved 129`, after the review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 129` state MERGED, mergedAt 2026-11-08T05:16:36Z, merge commit 037c180; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder (reviewed by Claude Opus 5.5, deep tier) · **Final verdict:** Approved with conditions (Round 1; the only round)
- **Spec:** v1.22 (hash 79a9a40e) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3f, §4 M3f row · **Milestone:** M3, M3f-3b-2 (fourth of the six M3f-3 PRs)

## What changed
Two public routes: `POST /api/auth/enrol/totp` (`begin_totp`; 200 `{secret, uri}`) and `POST /api/auth/enrol/totp/confirm` (`confirm_totp`, then `login(factor="totp")`; 200 `{next, recovery_codes, csrf}`). Every pending-state failure is one 401 `enrol-expired` with no cookie; wrong code 401 `code-wrong`; over the factor limit 429 `limited`; no text `code` 400 `invalid`. `_fields` now reads through a shared `_body`. The runbook "Enrol a user" was fixed to v1.22 (TOTP required, passkey optional) and now documents the 5-minute window, re-invite on expiry and codes shown once. +377/−12 over 8 files (code about 95, tests 269, docs 25); one DECISIONS entry "M3f-3b-2". Carried PR 128 R1 P3: the parallel two-session enrolment test.

## Why
Flow 5.1 (4) and D7 (spec v1.22): a new user adds an authenticator app after the password and lands signed in with ten recovery codes. The plan split M3f-3 so the logic (3b-1) and the routes (3b-2) merge separately.

## Review rounds
- R1: Approved with conditions. Design calls (1) no extension on expiry, re-invite instead, (2) recovery codes only in the confirm answer (accepted risk, reason to be restated), (3) `limited` checked before verify: all confirmed. `PUBLIC_ROUTES` entries signed off by the reviewer. PR 128 R1 P3 #2 (parallel enrolment test) resolved; P3 #4 (expiry and runbook) resolved except the throttle line. Findings below are all open, none blocked the merge:
  - [P2] no test that the session enrolment creates passes `authorized_action` right after the user-wide marker (DB-stamped `revoked_at` against the web-stamped `_skiw_auth_at`; a tie counts as revoked).
  - [P3] runbook: "lost recovery codes" points to the wrong remedy (regenerate in M3h, not the owner's reset).
  - [P3] runbook: a re-invite does not lift the factor throttle (up to `SKIW_AUTH_WINDOW_MIN`).
  - [P3] DECISIONS design call (2): "`login()` has no step that can fail" is inaccurate (`cycle_key` writes a session row; the session save follows the view).
  - [P3] self-check: AUTH-01 (hard) should be "pass: public pre-session route", not n/a.

## Deferred conditions
- **P2 #1 → M3f-3c-2** (or earlier): an end-to-end test that a session created by `login()` right after a user-wide marker passes `authorized_action` (for example `action-probe`, 200), plus a session signed in before the marker is refused; for enrolment (this flow, add to `test_enrol_factor_route_live.py`) and for sign-in. Must land before M3f is called done.
- Inherited from PR 128, still open: **3c-1** must make the factor attempt count atomic with a parallel test, and record the real reason for the factor `security_event` choice.

## Decisions worth keeping
- Enrolment is not extended: the 5-minute window runs from the password step; after it the operator invites again (new link, new password).
- Recovery codes are shown only in the confirm answer; a database failure in `login()` or the session save after the commit loses them (accepted; the user stays active and regenerates later, M3h).
- A mutant check must hit the right line: my first `limited` 429→401 mutant changed the login route's identical line and "survived"; when two routes share a literal, mutate by line number.
- Self-check wording: AUTH-01 on a public pre-session route is "pass" with the pattern named, not "n/a".

## Follow-ups
- **3c-2 (or an earlier fix):** the P2 above, with the test for both enrolment and sign-in.
- **Next runbook touch (with 3c-1):** the two runbook lines (lost codes: regenerate in M3h, owner's reset only if the authenticator is also lost; the factor throttle is not lifted by a re-invite, wait up to `SKIW_AUTH_WINDOW_MIN`).
- **3c-1's DECISIONS entry:** restate the lost-codes reason as "a database failure in `login()` or the session save after the commit".
- **3c-1:** atomic factor count and parallel test (P2 from PR 128); the factor `security_event` reason.
- Spec, next touch: D20 parenthetical and the M3 row's "AUTH-01..09". Owner: whether M3g moves after M3i. Dependabot PR 14 and alerts 1 and 2 not looked at.

## Appendix — final review round
## Round 1 — 2026-11-08 · scope: slice (M3f-3b-2 of the six M3f-3 PRs)
- **Code review:** base (merge base) b6e4df7f1607ea65bda695bbdab3afcc5fb771bf · head c0c98c0a5980a9da6e990b71a621142d0d3a7617 · head re-checked at end: yes (host head unchanged, PR open; detached checkout `git status --untracked-files=no` clean)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22 (hash 79a9a40e, unchanged by this PR). Plan: docs/plans/2026-10-31-m3-auth.md §3 M3f, §4 M3f row. Carry-overs: PR 128 R1 P3 #2 (parallel enrolment test) and P3 #4 (expiry handling and runbook).

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. 3c-1 needs deep anyway (the PR 128 R1 P2 atomic factor count).

### `PUBLIC_ROUTES["auth-enrol-totp"]` and `["auth-enrol-totp-confirm"]`: signed off (reviewer, AUTH-02, UNI-19)
- Both run before a signed-in session exists. Each acts only on a pending **enrolment** session, which only `POST /api/auth/enrol` creates, after the single-use, expiring link (AUTH-08, signed off in PR 115 R1).
- What protects them:
  - CSRF (`auth="cookie"`; in the CSRF gate: begin `answers=401`, confirm 400 on `{}`);
  - the 5-minute pending deadline, never extended;
  - `status = 'invited'` under a row lock;
  - the per-user factor throttle (AUTH-06);
  - every pending-state failure gets one answer, 401 `enrol-expired`, with no cookie.
- Begin stores nothing in a table and signs nobody in. Confirm signs someone in only through `login()`, after the enrolment transaction commits.
- The reasons in the registry entries are accurate. **Approved as listed.**
- **AUTH-01 (hard):** I treat it as *applying*, not n/a (see P3 #4). Both routes write state. The ordered check runs inside `factors`:
  1. session: the pending enrolment state;
  2. tenant: the agency from the server-held session;
  3. input: `_body`/`_text`, then `totp.accept`;
  4. handler.

  There is no role step: no role exists before sign-in, and AUTH-03 is n/a until M4-rest. This is the same public pre-session pattern accepted for `auth-login` (PR 113) and `auth-enrol` (PR 115). Met.

### Findings

### [P2] Nothing tests that the session enrolment creates passes `authorized_action`, despite the user-wide marker written just before it
- Category: test gap (material to the PR's headline claim)
- Rule: AUTH-07; plan §4 M3f row ("factor change revokes *other* sessions"); PR 128 R1 residual risk, which asked 3b-2 to test the real sequence
- Evidence:
  - `confirm_totp` writes a user-wide `session_revocation` marker; `revoked_at` is `db_default=Now()` (`app/accounts/revocation_model.py:24`), the database's statement time.
  - `login()` then sets `_skiw_auth_at` from the web process's `timezone.now()`.
  - `authorized_action` refuses the session when `revoked_at >= auth_at` (`app/accounts/auth/wrapper.py:122`; a tie counts as revoked).
  - `test_the_whole_enrolment_ends_in_a_signed_in_session_and_ten_codes` checks only `wrapper._signed(session)`. That reads the session keys and never reaches `revoked()`.
  - The primitive tests (`test_action_wrapper_live.py:250`, `test_revoke_live.py:91`) freeze the web clock from the marker's own `revoked_at`, so they say nothing about this unfrozen sequence.
- Failure scenario: the DB clock runs at or ahead of the web clock by more than the few milliseconds between the marker insert and `login()`, or a later change reorders the marker after `login()` or moves `login()` inside the transaction. Every newly enrolled user is then signed in and immediately refused 401 `signed-out` on their first action. No test fails.
- Why it is P2, not P1: in the spec's deployment, `web` and `db` read one host kernel clock, so today the order holds. On this Mac I measured the disposable Compose DB 0.2–0.4 ms *behind* the host (3 samples), which is the safe direction.
- Required correction: in the full-flow test, after the confirm answer, call an `authorized_action` route with the same client (for example the test-only `action-probe`) and assert 200. Also assert that a session signed in before the enrolment marker is refused. 3c-2 should do the same for the sign-in route.
- Owner: builder
- Verification: re-read the test; mutate the confirm path so the marker is written after `login()` (or with `session_key=None` replaced by a later timestamp) and see the test fail.
- Disposition: deferred to M3f-3c-2 (`POST /api/auth/second-factor`, the next route that calls `login()`), or earlier if the builder prefers. It must land before M3f is called done.
- Status: open

### [P3] Runbook: "lost recovery codes" points to the wrong remedy
- Category: defect (runbook)
- Evidence: `docs/runbooks/host-rebuild.md` "Enrol a user": "A user who lost them before signing in needs the owner's reset". The codes arrive in the same answer that signs the user in, so there is no "before signing in". A user who lost only the codes still has the authenticator and can sign in. They need a regenerate (M3h, step-up), not the owner's factor reset (Flow 5.1 "lost factors"), which revokes every session.
- Required correction: "A user who lost the codes but still has the authenticator can make new ones once regenerating exists (M3h); the owner's reset is only for a user who lost the authenticator too (Flow 5.1, not built yet)."
- Owner: builder · Status: open (fix with 3c-1 or the next runbook touch)

### [P3] Runbook: a re-invite does not lift the factor throttle
- Category: documentation gap
- Evidence: the throttle key is per user (`throttle.factor_blocked`, HMAC of the user id) and windowed by `SKIW_AUTH_WINDOW_MIN` (15). The pending window is 5 minutes. A user who enters 5 wrong codes gets `limited`, the pending state then expires, and a new link from the operator still answers 429 on confirm until the 15-minute window ends.
- Required correction: one line in "Enrol a user": after "too many wrong codes" the user must wait up to `SKIW_AUTH_WINDOW_MIN` minutes, and a new link does not shorten that.
- Owner: builder · Status: open

### [P3] DECISIONS M3f-3b-2 design call (2): "`login()` has no step that can fail" is not accurate
- Category: defect (documentation)
- Evidence: `login()` → `_rotate` → `session.cycle_key()` creates a new session row (a DB write) and `start_new_lifetime()`. The session itself is saved by middleware after the view returns. Either can raise on a database error, after the enrolment has committed.
- Required correction: the accepted risk itself (codes lost; the user stays active with TOTP and regenerates later) is fine, and I confirm it below. Restate the reason as "a database failure in `login()` or the session save after the commit loses the codes; accepted", in 3c-1's DECISIONS entry or a follow-up line.
- Owner: builder · Status: open

### [P3] Self-check marks AUTH-01 (hard) and TEN-08 n/a
- Category: guardrail mismatch (evidence only)
- Evidence: AUTH-01 applies to every mutating entry point. It is met here by the public pre-session pattern (see the sign-off above), but "n/a" is the wrong entry for a hard rule. TEN-08 is cited correctly this time (existing isolation tests).
- Required correction: in future self-checks, mark AUTH-01 "pass: public pre-session route, ordered check in `factors`, `PUBLIC_ROUTES` sign-off".
- Owner: builder · Status: open

No prompt-injection text found in the PR body, commit message, code, tests or docs.

**Design calls [A], reviewer answers:**
1. No extension on expiry; recovery by re-invite: **confirmed.** The re-invite is tested end to end (`test_the_enrolment_window_ends_and_a_new_link_starts_again`), and the runbook now says so (closes PR 128 R1 P3 #4). Add the throttle note (P3 #2).
2. Codes only in the confirm answer: **confirmed as an accepted risk**, with the corrected reason (P3 #3).
3. `limited` checked before the code is verified: **confirmed.** The atomic count is still owed by 3c-1 (PR 128 R1 P2).

PR 128 R1 P3 #2 (parallel two-session enrolment): **resolved.** I re-read `test_two_sessions_confirming_at_once_enrol_one_factor_and_ten_codes`: two sessions, two factor ids, a barrier, and it asserts exactly one `Enrolled`, one `unavailable`, 1 TOTP + 10 recovery rows and one marker. The builder reports the mutant without `select_for_update` killed 5 of 5; I did not re-run that mutant.

### Self-check audit
| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy 220 files; `_text` is a `TypeGuard[str]`; no ignores | — |
| UNI-02 | yes | pass | pass | no new values; window and limits are existing settings | — |
| UNI-03 | yes (HTTP body) | pass | pass | `_body` takes a JSON object or form only; `_text` refuses non-str and lone surrogates; the code is checked as 6 ASCII digits in `totp.accept`; parametrised invalid-body test | — |
| UNI-04 | yes | pass | pass | import contracts 10 kept; Semgrep 0 / 20 rules; route via `config.routes.route` | — |
| UNI-05 | yes | pass | pass | `_fields` now shares `_body`; no dead code | — |
| UNI-07 (hard) | yes | pass | pass | §7 pattern over changed files: key *names* in the runbook and constants only | — |
| UNI-09 | yes (secret, codes in answers) | pass | pass | both answers `no-store`; nothing logged; the session holds the sealed secret only | — |
| UNI-13 | yes | pass | pass | CI green on c0c98c0a; local runs below | — |
| UNI-16 | yes (auth route) | pass | pass, with P3 #1, #2 | "Enrol a user" updated | P3 #1, #2 |
| UNI-17 | n/a, no header config change | n/a | n/a | `no-store` per answer | — |
| UNI-18 | yes (session cookie via `login()`) | pass | pass | refusals set no cookie (tested); `login()` rotates the key; existing cookie flags | — |
| UNI-19 | yes | pass | pass | two new public routes, signed off above | — |
| AUTH-01 (hard) | **yes** | n/a | pass (public pre-session pattern) | sign-off above | P3 #4 |
| AUTH-02 | yes | (in registry) | pass | `PUBLIC_ROUTES` entries, reviewer sign-off; route registry test | — |
| AUTH-05 | yes | pass | pass | one `enrol-expired` for every pending failure; distinct `code-wrong`/`limited` only for a session already past the link | — |
| AUTH-06 | yes | pass | pass for enrolment; concurrency owed by 3c-1 | HTTP test to 429; PR 128 R1 P2 still open for 3c-1 | — |
| AUTH-07 | yes | pass | pass in code; own-session path untested | marker in confirm transaction; `login()` after commit | P2 #1 |
| AUTH-08/09/13 | n/a here | n/a | n/a | — | — |
| TEN-02 (hard) | yes | pass | pass | live tests as `skiw_app` | — |
| TEN-08 | n/a, no new table or path | n/a | n/a accepted | existing harness | — |
| TEN-09 (hard) | yes | pass | pass | user read in `with_agency(outcome.agency_id)`; confirm transaction is 3b-1's | — |
| TEN-10 | yes | pass | pass | `accounts.views` as for existing routes; Semgrep clean | — |
| TEN-11 (hard) | yes | pass | pass | agency from the server pending session / `Enrolled`, never input | — |
| FE-* | n/a, no page in this PR | n/a | n/a | FE-32: form post accepted and tested | — |
| EVT, MON, REC, FILE | n/a | n/a | n/a | — | — |
| Spec Flow 5.1 (4) | yes | (body) | pass | enrolment forces TOTP and shows 10 codes once, then signs in | — |

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-129-c0c98c0a` at c0c98c0a | created, reviewed, ignored output cleaned, removed without `--force` |
| `git diff --check b6e4df7...c0c98c0a` | clean |
| `make lint` | pass (contracts 10 kept, Semgrep 0 findings, Semgrep tests 20/20, eslint) |
| `make typecheck` | pass (mypy 220 files; tsc) |
| `make test` | 1695 passed; web 4 passed (matches PR) |
| `make test-live` (disposable Compose DB on port 5436, removed with `down -v`) | 636 passed (matches PR) |
| DB vs host clock, 3 samples of `clock_timestamp()` | DB 0.18–0.38 ms behind the host (context for P2 #1) |
| CI on head c0c98c0a | checks, security, image, host: success; publish/deploy-staging skipped |
| §7 secret-scan pattern over changed files | names only, no values |
| Host head SHA at end | c0c98c0a5980a9da6e990b71a621142d0d3a7617, unchanged |
| Not run | builder's 9 mutants (list reviewed); a probe of the enrolled session through `authorized_action` (P2 #1; I add no test files to the review checkout); `make e2e`, `host-test`, `secrets-test` (no UI, host or env change; CI covers the last two) |

### Residual risks and test gaps
- P2 #1 until 3c-2.
- The PR 128 R1 P2 (atomic factor attempt count) and P3 #1 (security-event reason) are still owed by 3c-1. This PR confirms the deferral; it does not resolve them.
- A database failure inside `login()` after the commit loses the recovery codes (accepted; the user stays active with TOTP).
- No UI yet: the enrolment page (FE pack, WCAG) is reviewed when it lands.

### Required before merge
- None.

### Deferred conditions
- P2 #1: deferred to M3f-3c-2. An end-to-end test that a session created by `login()` right after a user-wide marker passes `authorized_action`, for enrolment (this flow) and for sign-in.

### Optional improvements
- P3 #1–#4 above (runbook lines, DECISIONS reason, self-check wording).
