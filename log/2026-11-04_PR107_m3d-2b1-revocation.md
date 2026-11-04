# PR 107 — feat(accounts): M3d-2b1 revocation primitives, the login() old-key marker, PR 106 R1 P3s

- **Merged:** 2026-11-04 (08:18:26 UTC) · **Merge commit:** d2656553b320e29e21379302a3f4fed3e5b4aca4 · **Branch:** feat/m3d-2b1-revocation
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-107.receipt on agent-logs (log-branch commit 4a95dce, receipt time 2026-11-04T08:17:21Z, before merge; reviewed head ed6de9d7c2fd2a49dc37fb9cffb5f3a17fa34c04, review-file hash cc4ca8a1fd4774cbbac8963d6dcb8beab0a1bf1c, review commit 815a67d)
- **Merge evidence:** `gh pr view 107` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head ed6de9d
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1); merge condition (CI `checks` pass at ed6de9d) met, run 41797192892
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3d · **Milestone:** M3, M3d-2b1 (M3d-2b split in three by the plan §1 size rule)

## What changed
- `app/accounts/auth/revoke.py` (new):
  - `mark(agency, user, session_key | None)`: one `session_revocation` marker, for one session or user-wide;
  - `revoked(user, session_key, auth_at)`: a key marker, or a user-wide marker with `revoked_at ≥ auth_at`;
  - `revoke_user(agency, user)`: the AUTH-07 primitive, a user-wide marker in its own `with_agency()`.
- `login()` over a session that already holds `_skiw_user`: in one `with_agency(<old session's agency>)` transaction, a key marker for the old cookie under the old session's user, then the flush or rotation. A failed insert deletes nothing. So `login()` must run outside any atomic block.
- Clock rule (PR 104 R1 note), in the `revoke.py` docstring and DECISIONS: `revoked_at` is the DB's statement time and `_skiw_auth_at` the web clock, both on the one host clock; a tie counts as revoked.
- PR 106 R1 P3 #1: `NoExceptionText.format()` clears `record.exc_text` (not restored); the `django` logger has no handlers of its own and propagates to root (drops `console` and the unset `mail_admins`).
- PR 106 R1 P3 #2: Semgrep `start-new-lifetime-login-only` matches the attribute, so aliases are flagged; sync and async alias fixtures.
- Tests: `test_revoke_live.py` (new, 6); `revoked_at` pinned as statement time (`pg_sleep`, `> now()`); re-login test on committed users; `conftest.committed_user(status, agency)` and `agency_b`; two stderr cases (DEBUG on; a cached traceback). DECISIONS "M3d-2b1". +286 −13. 14 mutants killed.

## Why
Spec D6 (revocation), AUTH-07, TEN-11, UNI-09; plan M3 §3 M3d carry-over (b); PR 104 review R1 note; PR 106 review R1 P3 #1, #2. M3d-2b as one PR came to ≈ 650 lines with two items unwritten, so it is 2b1 (this), 2b2 and 2b3.

## Review rounds
- R1: Approved (head ed6de9d), no findings. PR 106 R1 P3 #1 and #2 and the PR 104 R1 note closed. The reviewer re-ran `make test-live` (433 passed, schema check ok) and pytest unit (1539 passed; the web half not run, no pnpm), re-ran the PR 106 logger probe with `DJANGO_DEBUG=1` (marker 0 times, was twice) and the Semgrep alias probe (now flagged). Merge condition: CI `checks` at ed6de9d, which passed before `approved 107`.

## Deferred conditions
- None.

## Decisions worth keeping
- A login over an authenticated session retires the old key with a marker under the old session's user and agency, in the transaction that deletes the row.
- `login()` must run outside any atomic block (`with_agency()` cannot nest; `ATOMIC_REQUESTS` is not set).
- `revoked_at` is statement time; a tie with `_skiw_auth_at` counts as revoked; both clocks are the one host clock.
- `NoExceptionText` never reuses a cached traceback; `django.*` goes through the root handler.

## Follow-ups
- M3d-2b2: `authorized_action` (AUTH-01 order, idle timeout, the `status` and revocation checks in one `with_agency()`), the forged-`agency_id` tests, TEN-11 (i) through the wrapper.
- M3d-2b3: the route registry test (AUTH-02) and the logged-in CSRF fixture.
- M3e (reviewer note): the password step's `cycle_key()` rotates a pending session without a marker; a put-back pending row skips the password step until `SKIW_LOGIN_PENDING_MIN` (the second factor is still required). Mark the pending key when the second factor completes, or record the accepted risk in DECISIONS against plan §4.2 (b). Also: the password step must retire an authenticated session as `login()` does (DECISIONS M3d-2b1).
- Reviewer note: the clock rule assumes one host; revisit the tie rule (a margin) if the DB ever moves off the VPS.
- Earlier, still open: spec §4.1 / D6 gap for `session_revocation` (plan §9 item 2); `guard.auth_lookup_login` must name `public.citext` (M3e, PR 103 note); `login()` is sync only (PR 106 note); PR 88 optional P3; PR 78, 77, 81 items → M3e; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3d-2b1" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M3d-2b, part 1 of 3)
- **Code review:**
  - **Base:** merge base afebfa82974dbf4dd44e6e8b06a4bdeb47ab41d7 (origin/main, PR 106 merged).
  - **Head:** ed6de9d7c2fd2a49dc37fb9cffb5f3a17fa34c04, one commit. 13 files, +286 −13. Re-checked at
    the end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). AUTH-07, TEN-03, TEN-09, TEN-11, UNI-09; plan
  `docs/plans/2026-10-31-m3-auth.md` §3 M3d (the revocation marker, carry-over (b)).
- **CI:** security, image, host: pass. `checks` was still running at the end of the review.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Merge condition:** CI `checks` passes at ed6de9d.
- **Then:** `approved 107` (builder), then merge, then M3d-2b2.

### PR 106 R1 P3 #1 (cached traceback with DEBUG on): resolved
- `NoExceptionText.format()` clears `record.exc_text` before formatting, so its own message-free text
  is what stays cached.
- The `django` logger has no handlers of its own, so Django's `console` handler no longer prints
  tracebacks. `mail_admins` goes with it, but it was never set up (no `ADMINS`).
- **The builder's departure from my example is better:**
  - My example restored the earlier cache afterwards.
  - Leaving the message-free text cached means a later stock handler prints that text, not its own.
- **Reviewer probe:** I re-ran the PR 106 probe with `DJANGO_DEBUG=1` and a `django.template` ERROR.
  It printed one line and `KeyError`, and the marker appeared 0 times. It had appeared twice at PR
  106's head.
- Both cases have a test.
- **Status:** closed.

### PR 106 R1 P3 #2 (Semgrep alias): resolved
- The rule now matches the attribute itself.
- **Reviewer probe:** my PR 106 probe file is now flagged at
  `renew_fn = request.session.start_new_lifetime`.
- The fixture has sync and async alias cases.
- **Status:** closed.

### PR 104 R1 note (`revoked_at`): resolved
- After a `pg_sleep` in the same transaction, the test asserts `revoked_at > now()`. That pins
  statement time, and the builder's `transaction_timestamp()` mutant is killed.
- The clock rule is in the `revoke.py` docstring and in DECISIONS:
  - `revoked_at` is the database's statement time; `_skiw_auth_at` is the web clock.
  - Both read the one host clock.
  - A tie counts as revoked, which the test checks at the exact instant.

### What was checked
- **`login()` over an authenticated session:**
  - There is one `with_agency(<old session's agency>)` transaction. In it, `mark()` runs first, then
    the flush or `cycle_key`. Django's DB session store uses the default connection, so the marker,
    the new row and the old row's delete commit together.
  - If the insert fails, nothing is deleted. The test forces a real CHECK failure in the database, and
    the old row, its deadline and its data survive.
  - The marker's user and agency come from the MAC-verified session, not from the new user. The test
    pins this with a user of a second agency (TEN-11).
  - A login over a session that has no login writes no marker, as the plan says (authenticated
    rotations only).
  - `with_agency()` refuses to run inside an atomic block. `ATOMIC_REQUESTS` isn't set anywhere in
    `app/config/`, so `login()` can run from a normal view once the caller's own `with_agency()` has
    closed. The PR states this.
- **`revoked()`:**
  - The key match uses `stored_key()`, which is the `django_session` primary key and the marker's
    hash shape.
  - The user-wide match is `user_id` and `session_key_hash IS NULL` and `revoked_at ≥ auth_at`.
  - RLS limits both matches to the bound agency, which is the session's own `_skiw_agency` in 2b2.
  - The tests cover one session only, at or before the marker (including the tie), not 1 µs after,
    and not another user.
- **`revoke_user()`** is a user-wide marker in its own `with_agency()`: the AUTH-07 primitive. Its
  callers come in M3f/M3h.
- **The password-change order works:** `revoke_user()` runs, then `login()` re-issues the current
  session. The new `_skiw_auth_at` is taken after the marker commits, so it is later than `revoked_at`,
  and the re-issued session survives. `login()` also marks the old key.
- **TEN-03:** nothing updates or deletes a marker, and the grants are unchanged.

### Checks
- `make test-live` at ed6de9d on a disposable DB: 433 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- **`make test`:** pytest gave 1539 passed, which matches. The web half (`pnpm -C web test`) didn't run
  here because pnpm isn't installed. This PR has no web change, and CI runs it.
- **The two probes above:**
  - the logger probe ran from a temp dir with `python -I` and was deleted afterwards;
  - the Semgrep probe file sat in the review worktree for the run and was deleted afterwards.
- The worktree is clean.

### Findings
None.

### Notes (no action here)
- **For M3e: a pending-login row is rotated without a marker.**
  - The password step's `cycle_key()` retires an unauthenticated session, so the plan's rule writes no
    marker for it.
  - Suppose SQL-level access puts back a deleted *pending* row, one holding `_skiw_pending_user` after
    a correct password. That would skip the password step until `SKIW_LOGIN_PENDING_MIN` runs out. The
    second factor is still required.
  - M3e should either mark the pending key when the second factor completes, or accept this risk and
    record it in DECISIONS against plan §4.2 (b).
- **The clock rule assumes a single host.** If the database ever moves off the VPS, a managed database
    for example, `revoked_at` and `_skiw_auth_at` come from different clocks, and the tie rule needs a
    margin. The DECISIONS entry should be revisited at that point.

### Follow-ups
- M3d-2b2: `authorized_action` (AUTH-01 order, idle timeout, the `status` and revocation checks in one
  `with_agency()`), the forged-`agency_id` tests, and TEN-11 (i) through the wrapper.
- M3d-2b3: the route registry test (AUTH-02) and the logged-in CSRF fixture.
- M3e: the pending-row note above.
