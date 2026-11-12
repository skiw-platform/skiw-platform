# PR 149 — feat(accounts): M3i-0 session state route and /enrol page

- **Merged:** 2026-11-12 (12:26:33 UTC) · **Merge commit:** 3c97efba70905eade7470c823a7f80de62139f58 · **Branch:** feat/m3i-0-session (final head 6a79bddc1e95b62408d1ddd85f0d6b7853e59036)
- **Gate breaches:** none. The review's final round (R1) head SHA equals the PR's final head; the receipt (`reviews/PR-149.receipt`, 2026-11-12T12:08:37Z, review-file hash 8a049ca, review commit e7cdfda) precedes the merge by about 18 minutes.
- **Approval receipt:** `reviews/PR-149.receipt` on agent-logs.
- **Merge evidence:** `gh pr view 149` (skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-12T12:26:33Z, merge commit 3c97efb; reachable from fetched origin/main.
- **Built by:** Claude Opus sub-agent (deep tier) wrote the code; the Sonnet 5.5 builder re-ran the gates and wrote the PR · **Reviewed by:** Claude Opus 5.5 (deep tier), one round · **Final verdict:** Approved (round 1)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** M3 §3 M3i, amended by the owner's 2026-11-12 choice · **Milestone:** M3, package M3i (first of four PRs: M3i-0 to M3i-3)

## What changed
`GET /api/auth/session` (always 200, no-store, `{"state": signed_out|signed_in|second_factor|enrol_factor, "csrf"}`; one body for every signed-out reason; no identity in it); `signed_in(session)` shares `_tenant_step` with the wrapper's idle, active and revocation checks and writes nothing; `GET /enrol` serves the shell (the invite link `/enrol#<token>`). 17 live tests, shell and registry tests, DECISIONS "M3i-0", runbook lines. +294/-6 over 10 files.

## Why
The M3 plan missed that the static page cannot tell whether the browser is signed in or mid-login, and that the invite link's path was not routed. The owner chose on 2026-11-12 to fix both server-side first ("Add both, as a small server PR first"); M3i is split into M3i-0 server, M3i-1 login/second factor/logout, M3i-2 enrolment, M3i-3 step-up and Playwright.

## Review rounds
- R1 (head 6a79bdd): Approved, P3 only. Reviewer re-ran lint, typecheck, test (1801), test-live (922) and ran mutants S1-S8 in a scratch copy: all killed except S7 (csrf value) and S8 (equivalent).

## Deferred conditions
- None. P3s, open: (1) the returned `csrf` is not proved usable (mutant S7 survived): add a test that POSTs to a CSRF-enforcing route with the returned token, here or in M3i-1; (2) a session only polled while its user is disabled reads signed in again when the user is re-enabled, by design of a read-only route (the wrapper had the same gap): M4 "disable user" must write a user-wide marker, `mark(agency, user, None)`, worth a line in the M4 plan; (3) M3i-2: after reading `#<token>` remove the fragment with `history.replaceState`, send the token only in a POST body; the reviewer will check; (4) equivalent mutant S8, no action.

## Decisions worth keeping
- The session route is read-only: it never extends the idle clock, flushes or marks; its one write is the stale-pending clear that the other routes already do.
- Pending states do not re-check user status (a user disabled in the 5-minute window sees the code screen once; the next step answers `login-expired`).

## Follow-ups
- **M3i-1 next** (standard tier; frontend packs; first screens): api.ts reading `<meta name="csrf-token">` and the session route, login, second factor (TOTP and recovery code), logout, signed-in Today. Add the P3 #1 csrf test. Shell template and `App.tsx` output must stay byte-equal.
- M3i-2 (enrolment, P3 #3, review carefully), M3i-3 (step-up dialog, Playwright), then M3g, then the M3 gate review (deep tier).
- Add to the M4 plan: disable user writes a user-wide marker (P3 #2).
- Carried P3s: PR 148 `host-rebuild.md:326` DECISIONS date; PR 143 regenerate `hold` race test; PR 139 permission matrix (M4-rest); PR 140 P3s and apk layer removal; PR 140 review tier gap.
- Progress page not republished (M3i not complete).

## Appendix — final review round
# Review — PR #149 (M3i-0: session state route and /enrol page)

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 1 — 2026-11-12 · scope: slice (M3i-0; one public GET route, the shell at `/enrol`, a read-only extraction from the wrapper; no migration, setting or dependency)
- **Code review:** base (merge base) f319bd9ff5fb49a1349963541329ea59ef161124 (= `origin/main`, PR 148 merged) · head 6a79bddc1e95b62408d1ddd85f0d6b7853e59036 · one commit · +294/−6 over 10 files · head re-checked at end: yes (PR open, main unmoved; detached checkout `git status --untracked-files=no` clean)
- **Spec:** v1.22 (D7, AUTH-01/05/07, UNI-17/19). Plan M3 §3 M3i, amended by the owner's 2026-11-12 choice (option 1: a server PR first). DECISIONS "M3i-0".
- **CI:** green on this head: `checks`, `security`, `image`, `host` success; `publish`, `deploy-staging` skipped (PR event).

**Verdict:** Approved.
**Model used:** Claude Opus 5.5 (deep tier, as the PR asked) · **Switch model next step?** M3i-1 to M3i-3 are screens, so the standard tier is fine for building them. M3i-2 (enrolment) handles the invite token in the browser; review it carefully (see P3 #3). The M3 gate review should be deep.

### Applicability (reviewer's own list) and self-check audit
AUTH-01 (wrapper behaviour unchanged: met), AUTH-05 (one signed-out body: met), AUTH-07 (revoked or marked sessions read as signed out: met), TEN-09/11 (`with_agency(signed.agency_id)`, identity only from the signed session: met), TEN-10/12 (registered public route with a reason: met), UNI-03 (GET only, POST 405 on `/enrol`), UNI-05 (one `_tenant_step`), UNI-07, UNI-09 (nothing logged, no identity in the body), UNI-13, UNI-16 (runbook lines), UNI-17 (`/enrol` headers equal `/`). I agree with the self-check. Its UNI-07 row is a commit-range scan, but CI `security` ran gitleaks over full history green.

### What I checked
- **Wrapper refactor is behaviour-identical.** `_tenant_step` moves the idle check, then the active and revocation checks, in the same order, inside the same `with_agency`. The wrapper still marks and flushes on idle and flushes on signed-out, and its factor check and seen-at bump are untouched. Mutants S1 (idle writes no marker) and S6 (idle handled as signed-out) are both killed.
- **`signed_in` is the wrapper's gate, read-only.** It returns False on `_signed() is None` or an unknown factor, then calls `_tenant_step` with the real session key and the current time. It writes nothing. `SESSION_SAVE_EVERY_REQUEST = False` and `CSRF_USE_SESSIONS = False`, so neither the session store nor `get_token` creates or saves a row for an anonymous caller (the anonymous test proves no query and no session cookie).
- **The one write is the existing one.** `factors.pending` only `pop`s keys, and Django marks the session modified only when a key was present. So a refused signed-in session with no pending keys is not saved. A stale pending state is cleared exactly as the second-factor and enrolment routes already do.
- **No identity or reason leaks.** The body is exactly `{state, csrf}`; the test checks the key set. `_answer` sets `no-store`.
- **`/enrol`:** same view, same headers and body as `/` apart from the nonce (tested). `Referrer-Policy: same-origin`, not the `no-referrer` I suggested before the PR. It is acceptable: browsers never put the fragment in `Referer`, and only the bare path `/enrol` reaches same-origin requests.
- **Builder's question (end a refused session on this route?):** no. Keep it read-only. A GET that ends sessions would make a page load a write path. The wrapper ends the session on the next real call, and the store's absolute deadline caps it anyway.

### Findings

### [P3] #1 The `csrf` value in the answer is not proved usable
- Category: test gap
- Evidence: mutant S7 (answer `"csrf": "x"` instead of `get_token(request)`) **survived**, 99/99 passed. The test only checks that `csrf` is truthy.
- Why it matters: the CSRF cookie is `HttpOnly`, so after a reload the page can only learn the token from the shell or this answer. A wrong value would make every POST after a reload fail with 403. M3i-1's screens or M3i-3's Playwright run would catch it, but late.
- Required correction (here or in M3i-1): in the session route test, POST to a CSRF-enforcing route with the returned token and expect it to pass the CSRF gate (the PR 143 csrf fixture pattern).

### [P3] #2 A session only polled while its user is disabled revives when the user is re-enabled
- Category: forward note (M4-rest "Manage staff")
- Evidence: `test_a_user_made_active_again_is_signed_in_again` encodes this on purpose. Because the route is read-only, a disabled user's session is not flushed when it is polled. It reads `signed_out` while disabled and `signed_in` again once the user is active. The wrapper had the same gap for a session that made no request while disabled, so this PR adds no new exposure. There is no disable flow on `main` yet (`git grep`: only tests set `disabled`).
- Required correction: none here. When M4 builds "disable user", it must write a user-wide revocation marker (`mark(agency, user, None)`), so a disabled user's sessions end for good rather than pausing. Worth a line in the M4 plan now.

### [P3] #3 Forward note for M3i-2 (enrolment screen)
- After the page reads `#<token>`, it should remove the fragment from the address bar (`history.replaceState`), so the token does not stay in browser history, a bookmark or a copied URL. It should send the token only in a POST body, never in a query string. I will check this in the M3i-2 review.

### [P3] #4 Equivalent mutant (no action)
- S8 (check the pending state before `signed_in`) survived. It is equivalent: completing a login clears every pending key, so no live session is both signed in and pending.

### Verification performed
In a detached checkout at the head with its own DB (`COMPOSE_PROJECT_NAME=review-149`, port 5449): `make install lint typecheck test` (lint and Semgrep clean, mypy 242 files, 1801 passed, web 4 passed); `make test-live` (migrate and the migration lint included): 922 passed. **Mutants** (scratch copy, bytecode off, caches cleared; session route, wrapper, revoke, logout/password live files and shell tests, baseline 99 passed): S1 idle without marker, S2 `>=` to `>` on idle, S3 revocation by the wrong key, S4 idle counted as live, S5 active check dropped, S6 wrapper idle as signed-out: all **killed**; S7 fake csrf: **survived** (P3 #1); S8 order swap: survived, equivalent (P3 #4). I did not re-run the builder's 10 mutants. Not run: `host-test`, `e2e`, gitleaks locally (CI `host` and `security` are green).

### Residual risks
- Disable and re-enable without a marker (P3 #2) until M4 builds the disable flow.
- Lost-authenticator recovery is still unbuilt (owner reset, M4-rest must-have before real data).
