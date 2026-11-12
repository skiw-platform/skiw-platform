# PR 151 — feat(web): M3i-2 invitation and enrolment screens

- **Merged:** 2026-11-12 (17:33:28 UTC; the host's date) · **Merge commit:** 7a3504e3776112ea0e53e5de60cfa474594c8ef5 · **Branch:** feat/m3i-2-enrol (final head f49b178fbdce20f512bbe1f56bb409b84a4b8b27)
- **Gate breaches:** none. The final review round (R2) head SHA equals the PR's final head; the receipt (2026-11-12T16:38:20Z, review-file hash eb03fd6c) precedes the merge by about 55 minutes.
- **Approval receipt:** `reviews/PR-151.receipt` on agent-logs (log-branch commit f77000f; the review itself is at commit 7344c7f).
- **Merge evidence:** `gh pr view 151` (skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-12T17:33:28Z, merge commit 7a3504e; reachable from fetched origin/main.
- **Conditions of the approval:** CI `checks` green on the head: it was green (all four jobs) when `approved 151` ran, before the merge.
- **Built by:** the Sonnet 5.5 builder (screens, standard tier) · **Reviewed by:** Claude Opus 5.5 (deep tier), two rounds · **Final verdict:** Approved with conditions (round 2)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** M3 §3 M3i · **Milestone:** M3, package M3i (third of four PRs)

## What changed
The invitation and enrolment screens: `web/src/enrolLink.ts` (token read once from `/enrol#<token>`, removed from the address bar, kept in memory), `screens/Enrol.tsx` (password step, setup key in groups plus `otpauth://` link, code confirm, a "Show setup key" button after a reload), `screens/Recovery.tsx` (recovery codes shown once, copy button, never stored), App state (`Shown` with setup and codes), shared `testkit.ts`, copy and styles, `e2e/auth.spec.ts`, DECISIONS "M3i-2". It also carries the PR 150 review's test follow-ups and the sign-out busy state. No server change. +682/-79 over 13 files after the fix (owner answered "open it as one PR" past the 600 stop line).

## Why
Plan M3 §3 M3i: a new staff member must be able to turn an invitation into an account with a password and an authenticator, in the browser. Spec Flow 5.1 (4), AUTH-05/08/13; PR 149 review P3 #3 (token out of the address bar).

## Review rounds
- R1: [P1] the invitation token stayed in the address bar unless the visitor was signed out (AUTH-08) → the first effect takes the fragment on `/enrol` before the session request; any answer but `signed_out` discards the invitation and moves to `/`. Tests for the three session states, the pending request, a later sign-out and `/#main`; mutants killed. [P3] 429 and missing-codes tests added, testkit blank lines fixed.
- R2: approved with one condition (CI `checks` green), met before the merge. No new findings.

## Deferred conditions
none. Open P3s carried: PR 150 P3 #2 ("Use a different account" leaves the pending login; needs a server change, M3i-3 or a small server PR); R1 P3 #1 G12 (sign-out button not disabled while busy, test only) and G7 (setup-key button junk body; harmless), for M3i-3.

## Decisions worth keeping
- The token is read at page start on `/enrol`, not in render; a visitor who is not signed out never keeps or uses the invitation (DECISIONS "M3i-2").
- No QR code (needs a dependency); "Show setup key" is a click because asking replaces the unconfirmed key; the 12-character hint is a floor, the server is the authority ([A] in DECISIONS).
- The setup and recovery screens are unproven in a real browser until M3i-3 seeds an invitation.

## Follow-ups
- M3i-3: step-up dialog, seeded Playwright (real sign-in through the code step, sign-out, reload on each screen, axe on code and signed-in screens, idle sign-out). Review on the deep tier (closes M3).
- Then M3g (passkeys), then the M3 gate review.
- Owed: M4 note "disable user" writes a user-wide marker; PR 148 P3 (`host-rebuild.md:326` cites 2026-11-11, should be 2026-11-12); PR 143 and 139 and 140 P3s; owner check: `ghcr_read_token` must read `skiw-dev1` packages before any host.

## Appendix — final review round
## Round 2 — 2026-11-12 · scope: fix round (R1 P1 #1, P3 #1, P3 #2)
- **Code review:** base 348836f526adcec4857bbb0ff44cebda7d22c9bf (= `origin/main`, unchanged) · head f49b178fbdce20f512bbe1f56bb409b84a4b8b27 (one fix commit on top of R1's ef92aa04) · whole PR now +682/−79 · head re-checked at end: yes (PR open, main unmoved)
- **CI:** at the end of this review `security`, `image` and `host` had passed; **`checks` was still running** (run 43252312458).

**Verdict:** Approved with one condition: CI `checks` green on this head.
**Model used:** Claude Opus 5.5 · **Switch model next step?** M3i-3 (seeded users, Playwright end to end, step-up dialog) can be built at the standard tier. Review it on the deep tier, because it closes the M3 milestone.

### R1 findings, re-inspected
- **P1 #1 (token left in the address bar): resolved.**
  - `App`'s first effect now calls `takeToken()` on `/enrol` before it sends the session request. When the answer is anything but `signed_out`, it calls `discardInvitation()`, which forgets the token and moves the address to `/`.
  - My R1 probe (`/enrol#tok-999` with `signed_in`, `second_factor`, `enrol_factor`) now passes 3 of 3. It was re-run in a scratch copy, not added to the repo.
  - New tests cover all three states, the token gone before the answer arrives, no invitation after a signed-in person signs out, and `/#main` untouched.
  - **Mutants on the fix:** H1 no early take, H2 no discard, H4 discard keeps `/enrol`, H5 fragment taken on any path, H6 discard even when signed out: all **killed**. H3 (discard keeps the token in memory) survived and is equivalent: the address is `/` by then, and `SignedOut` checks the path before it reads the token. A full page load resets the module. Keep the line as defence in depth.
- **P3 #1 (G6, G10): resolved.** One test covers 429 at confirm ("too many tries") and a 200 without codes (generic message, no crash).
- **P3 #2 (testkit blank lines): resolved.** `git diff --check` on the whole PR is clean. The render-time `takeToken()` in `SignedOut` remains, but it now only reads the remembered value, because the effect takes the token first. That is acceptable.
- **DECISIONS "M3i-2"** gained a line describing the start-of-page behaviour. It matches the code.

### New findings
None.

### Verification performed
In a detached checkout at the head: `make install lint typecheck test`: lint, Semgrep and eslint clean; mypy 242 files and `tsc`; 1801 passed; vitest 34 passed. **`make e2e`** from a scratch copy, app on port 8052: 52 passed (desktop and mobile). Probe 3 of 3 passed; mutants as above. Not re-run: `test-live` (the fix has no server code; R1 ran 923 green), `host-test` and gitleaks (CI).

### Residual risks
- PR 150 P3 #2 ("Use a different account" leaves the pending login) is still open, because it needs a server change.
- The setup and recovery screens are unproven in a real browser until M3i-3 seeds an invitation.
- Lost-authenticator recovery is still unbuilt (owner reset, M4-rest must-have before real data).
