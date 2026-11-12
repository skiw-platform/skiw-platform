# PR 150 — feat(web): M3i-1 sign-in, code entry and sign-out screens

- **Merged:** 2026-11-12 (15:29:43 UTC) · **Merge commit:** 348836f526adcec4857bbb0ff44cebda7d22c9bf · **Branch:** feat/m3i-1-login-screens (final head c9d385dbe3859436d4503655884935be67d5ae10)
- **Gate breaches:** none. The review's final round (R1) head SHA equals the PR's final head; the receipt (`reviews/PR-150.receipt`, 2026-11-12T15:27:58Z, review-file hash c5c2d32, review commit 624856f) precedes the merge by about 2 minutes.
- **Approval receipt:** `reviews/PR-150.receipt` on agent-logs.
- **Merge evidence:** `gh pr view 150` (skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-12T15:29:43Z, merge commit 348836f; reachable from fetched origin/main.
- **Conditions of the approval:** (1) CI `checks` green on the head: it was green (all four jobs) when `approved 150` ran, before the merge; (2) the owner accepts the FE-32 exception: accepted by merging with DECISIONS "M3i-1" as written.
- **Built by:** the Sonnet 5.5 builder (screens, standard tier) · **Reviewed by:** Claude Opus 5.5 (deep tier), one round · **Final verdict:** Approved with conditions (round 1)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** M3 §3 M3i as split 2026-11-12 · **Milestone:** M3, package M3i (second of four PRs)

## What changed
`web/src/api.ts` (CSRF token from the meta tag, replaced from each answer), App state machine (loading, sign-in, code entry, unfinished-enrolment notice, Today with sign-out), `screens/SignIn.tsx`, `screens/SecondFactor.tsx`, `forms.tsx`, copy in `content.ts`, styles on tokens; `shell.html` static markup is now the loading screen, compared with `renderToStaticMarkup` in vitest; live test that the session route's `csrf` passes the CSRF gate (PR 149 P3 #1); `e2e/auth.spec.ts` and three updated shell e2e assertions; DECISIONS "M3i-1". +747/-73 over 14 files (owner answered "open it as one PR" past the 600 stop line).

## Why
First screens of M3i, on the session route and `/enrol` from M3i-0.

## Review rounds
- R1 (head c9d385d): Approved with conditions. Reviewer re-ran lint, typecheck, test (1801), test-live (923), vitest (16) and `make e2e` (50 passed, desktop and mobile); 12 vitest mutants: 7 killed, 5 survived (P3 #1).

## Deferred conditions
- P2 #1 FE-32 (sign-in needs JavaScript): accepted by the owner by merging.
- P2 #2 FE-70: the code-entry and signed-in screens have no browser test yet: **deferred to M3i-3**, which must include a real sign-in through the code step, sign-out, a reload on each screen, axe on the code and signed-in screens, and the sign-out-when-idle path.
- P3s, open: (1) vitest cases for survived mutants F9 (logout 401 handled as signed out), F3 (unknown `state` read as signed out), F4 (non-200 session answer read as signed out); also F10 (no focus move on first load) and F12 (a 200 without `next: signed_in` is not a sign-in); (2) "Use a different account" and "Back to sign in" leave the server's pending login for up to `SKIW_LOGIN_PENDING_MIN`, so a reload shows the code screen again: optional server fix (cancel pending, or logout clears a pending session) in its own small PR or in M3i-3; (3) `content.signOutBusy` unused and sign-out has no busy state (double click sends two logouts; the second gets 401, handled).

## Decisions worth keeping
- The page asks `GET /api/auth/session` on load; `api.ts` is the only server caller; no router; no new dependency.
- First render is the loading state, byte-compared with the template.
- FE-32 deviation: signing in needs JavaScript.

## Follow-ups
- **M3i-2 next** (standard tier to build, **deep tier to review**: invite token in the browser): enrolment from `/enrol#token`, `history.replaceState` to drop the fragment, token only in a POST body, TOTP secret and otpauth link, recovery codes shown once. Add the P3 #1 vitest cases there or in M3i-3.
- M3i-3: seeded Playwright (see P2 #2), step-up dialog; M3g; M3 gate review (deep).
- Carried: PR 149 P3 #2 (M4 plan: disable user writes a user-wide marker); PR 148 P3 (`host-rebuild.md:326` DECISIONS date); PR 143 regenerate `hold` race test; PR 139 permission matrix (M4-rest); PR 140 P3s and apk layers; PR 140 review tier gap.
- Progress page: not republished (M3i incomplete).

## Appendix — final review round
# Review — PR #150 (M3i-1: sign-in, code entry and sign-out screens)

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 1 — 2026-11-12 · scope: slice (M3i-1; first screens: `api.ts`, App state machine, sign-in, code entry, sign-out, loading shell; one server test; no server logic, migration, setting or dependency)
- **Code review:** base (merge base) 3c97efba70905eade7470c823a7f80de62139f58 (= `origin/main`, PR 149 merged) · head c9d385dbe3859436d4503655884935be67d5ae10 · one commit · +747/−73 over 14 files · head re-checked at end: yes (PR open, main unmoved; detached checkout clean)
- **Spec:** v1.22 D2 (React SPA for every screen), D7, Flow 5.1, AUTH-05/13; guardrails `frontend.md` (FE-*, A11Y-*). Plan M3 §3 M3i as split on 2026-11-12. DECISIONS "M3i-0", "M3i-1"; "M3e-2b" (the login route takes JSON or a form post, FE-32). Carry-over: PR 149 R1 P3 #1.
- **CI:** at the end of this review `security`, `image` and `host` had passed; **`checks` was still running** (run 43239435597). See the conditions.
- **Size:** +747, over the 600 stop line. The builder asked the owner first, and the owner answered "open it as one PR" (2026-11-12); the reason is in the PR body. I agree: about 425 lines are app code and styles; the rest is tests and docs. Not a finding.

**Verdict:** Approved with conditions: (1) CI `checks` green on this head; (2) the owner accepts the FE-32 exception (P2 #1). Merging with the DECISIONS entry as written is that acceptance.
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** Standard tier is fine for building M3i-2 and M3i-3. Review M3i-2 (invite token in the browser) on the deep tier.

### Carry-over
- **PR 149 P3 #1 (csrf proved usable): resolved.** `test_the_token_in_the_answer_passes_the_csrf_gate` posts to `/api/auth/login` with the returned token through a CSRF-enforcing client and gets past the gate (401, no `X-Skiw-Csrf`). A wrong token gets 403 `rejected`. The builder reports the `"csrf": "x"` mutant killed; the test's shape kills it.

### Applicability (reviewer's own list) and self-check audit
AUTH-05 (one wrong-sign-in message: met), AUTH-13 client half (token replaced from every answer; the server rotates on login, second factor and logout: met), UNI-07, UNI-09 (password cleared after failure, nothing stored: met), UNI-13, UNI-17/19 (no inline script or style, `X-CSRFToken` on every POST: met), FE-01..07, FE-10..14, FE-20..23, FE-40, FE-50, FE-60/61, FE-71, A11Y-01..06 (met), **FE-32 (not met: P2 #1)**, **FE-70 (partial: P2 #2)**. The self-check marks both honestly. I agree with the rest of it.

### What I checked in the code
- **Storage and tokens:** the CSRF token lives in one module variable in `api.ts`. Nothing is written to `localStorage`, `sessionStorage` or cookies by script. It starts from the shell's `<meta>`, then `/api/auth/session`, login, second factor and logout each return a fresh `csrf` that replaces it. `fetch` uses `credentials: "same-origin"` and `cache: "no-store"`.
- **Messages:** sign-in maps every 401 to one message, 429 to `limited`, 0 to network, anything else to generic. The code step separates `login-expired` (back to sign-in with a notice) from other 401s (wrong code, field cleared). Errors sit in a polite live region tied to the field by `aria-describedby`. The failed field is focused, and the password is cleared.
- **Sign-out:** 200 or 401 returns to sign-in (401 means already ended, for example idle), and the logout answer's rotated token is kept. Anything else stays and says so.
- **Hydration:** the shell's static markup is now the loading screen; a vitest test compares it to the first render.
- **No secret or identity on screen:** the code screen does not name the account.

### Findings

### [P2] #1 FE-32: signing in does not work without JavaScript
- Category: guardrail (accepted-exception candidate)
- Rule: FE-32 ("Forms … work without JS succeeding")
- Evidence: without JS the page stays on "Loading / Checking your session". The server already takes a form post on `/api/auth/login` (DECISIONS M3e-2b cites FE-32), but it answers JSON, so a no-JS submit would land on raw JSON. DECISIONS "M3i-1" records this as an accepted deviation, decided by the builder.
- Why P2, not P1: spec D2 (approved) makes every screen a React SPA over a JSON API, and FE-32 cannot hold for sign-in under that design without a second, server-rendered flow. The users are about 5 agency staff on managed browsers, so the impact is isolated. A failed rule is P1 by default; this is the written reason for P2.
- **Disposition: before merge, owner action.** Accept the exception. Merging with the entry as written does that. If you would rather have it explicit, the builder can change the entry's "Decided by" to name you.

### [P2] #2 FE-70: the code-entry and signed-in screens have no browser test yet
- Category: test coverage
- Rule: FE-70
- Evidence: Chromium covers the sign-in screen, its error state, `/enrol`, the session route, axe, keyboard, overflow and CSP at both widths (I ran it: 50 passed). The code step, the signed-in screen and sign-out are covered only by vitest with a mocked `fetch`, because a browser test needs a seeded user.
- **Disposition: deferred to M3i-3** (the planned Playwright PR with a seeded user). M3i-3 must include: a real sign-in through the code step, sign-out, a reload on each screen, axe on the code and signed-in screens, and P3 #1's sign-out-when-idle path.

### [P3] #1 Test gaps found by mutants (vitest)
- Survived:
  - **F9:** logout 401 treated as an error. This is the common path for a person who went idle and then clicks Sign out: they would see "Something went wrong" while already signed out. The code is right today.
  - **F3:** an unknown `state` accepted; `Screen` would then render an empty `main`.
  - **F4:** a non-200 session answer read as its state.
  - **F10:** focus moved to `main` on first load. The existing e2e "keyboard focus survives a slow client start" may cover it; I did not rebuild the image per mutant.
  - **F12:** a 200 from the code step without `next: signed_in` accepted.
- Required correction (M3i-3 is fine): vitest cases for F9, F3 and F4 at least.

### [P3] #2 "Use a different account" leaves the server's pending login in place
- Evidence: the button only switches the screen. The pending state stays in the session for up to `SKIW_LOGIN_PENDING_MIN` (5 minutes). A reload in that window shows the code screen again for the previous person's sign-in, and "Back to sign in" on the enrolment notice behaves the same. A new sign-in replaces it. The next person would need the first person's code, so the risk is small. It is a confusing screen on a shared desk.
- Correction (optional, later): have the button end the pending state on the server (a small public "cancel pending" route, or let logout clear a pending session). This is a server change, so it would be its own small PR or part of M3i-3.

### [P3] #3 Nits
- `content.signOutBusy` ("Signing out") is defined but never used, and sign-out has no busy state, so a double click sends two logouts. The second gets 401, which is handled. Either use it or drop it.

### Verification performed
In a detached checkout at the head with its own DB (`review-150`, port 5450): `make install lint typecheck test`: ruff, contracts, Semgrep and eslint clean; mypy 242 files and `tsc`; 1801 passed; vitest 16 passed. `make test-live`: 923 passed. **`make e2e`** from a scratch copy with the app on port 8050 (port 8000 was held by the builder's own container, which I did not touch): 50 passed (desktop and mobile). **Mutants** (12, vitest, scratch copy): killed F1 token never replaced, F2 no CSRF header, F5 password kept, F6 429 as login failed, F7 login-expired as wrong code, F8 wrong code kept, F11 network as generic; survived F3, F4, F9, F10, F12 (P3 #1). Not run: `host-test`, gitleaks locally (CI `host` and `security` passed).

### Residual risks
- The code step and the signed-in screen are unproven in a real browser until M3i-3.
- Lost-authenticator recovery is still unbuilt (owner reset, M4-rest must-have before real data).
