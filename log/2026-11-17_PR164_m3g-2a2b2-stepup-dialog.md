# PR 164 — feat(web): M3g-2a-2b-2 step-up dialog for adding a passkey

- **Merged:** 2026-11-17T10:22:25Z · **Merge commit:** 015624d27d922e76bb8c3f401373e1627d415239 · **Branch:** feat/m3g-2a-2b-2-stepup
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-164.receipt` (log-branch commit holding the review `993a3c5ccad1e2938bb02c05fda15fff1b4cfebd`; receipt time 2026-11-17T10:21:52Z, before the merge; head `acce28177e3ffa777c3effdeb7f084deb4b1cbec`; review hash `8b72e66f500a4274901df0d62a07fbf42b1b53e8`)
- **Merge evidence:** `gh pr view 164` state MERGED, merge commit above, an ancestor of the fetched `origin/main`. Final head SHA equals the reviewed SHA.
- **Drafted by:** deep-tier sub-agent (Claude Opus), orchestrated by Claude Sonnet 5.5 · **Final verdict:** Approved with conditions (round 2, independent review GPT-6.1 Codex)
- **Spec:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 · **Milestone:** M3g-2a-2b-2

## What changed
A 403 `stepup-required` from Add's begin opens the existing StepUp dialog (`factor.change`); once verified, begin runs once more; a second `stepup-required` is the generic error (no loop). While open, the skip link, header, nav, heading and list are `inert`, Tab wraps inside, Cancel/Escape close it and return focus to Add. Replaces PR 163's temporary message. Final size 229 changed lines.

## Why
PR 163's review deferred the dialog, modal containment and repeated-stepup refusal to this slice.

## Review rounds
- R1: [P1] a cancelled code verification could restart Add after the dialog closed → the code request has its own AbortController (the dialog's cancellation identity); Cancel, Escape and unmount abort it and late answers are ignored; each open mounts a fresh StepUp; Security's shared-controller check removed as dead code.
- R2: Approved with conditions, no new finding.

## Deferred conditions
- Real WebAuthn/virtual-authenticator, keyboard, axe, responsive and cross-browser matrix → M3g-2b (jsdom cannot move focus on Tab; Tab wrap is tested by the prevented default).
- Unidentified earlier test flake: did not recur in 23+ runs; capture the failing test if it recurs; keep the observation for M3 gate evidence.

## Decisions worth keeping
- "Sign out closes the dialog" is met by unmount: Sign out sits in the inert header while the dialog is open.
- The step-up endpoint does not rotate the CSRF token, so aborting its request is safe.
- `onModal` runs in a layout effect so the page is inert on the dialog's first paint.

## Follow-ups
- 2c remove with inline confirmation, 2d the offer after enrolment, M3g-2b browser tests, M3 gate review.

## Appendix — final review round
## Round 2 — 2026-11-17 · scope: slice

- **Code review:** merge base `54a122d17031b57639924831ea786a8899aa0ec6`; head `acce28177e3ffa777c3effdeb7f084deb4b1cbec`. Host head rechecked unchanged, PR open.
- **Spec:** passkey screens v1.3, hash `cd1a0ac71877db864f19377172c95b77b71be303`, unchanged. Scope: M3g-2a-2b-2, StepUp integration, one verified retry and modal containment.
- **Reviewer:** Codex; builder: Builder; owner: Ying. Exact detached checkout `.agent/worktrees/review-164-acce2817`; main/builder files untouched.

### Findings

No new blocking findings. Round 1's P1 is resolved.

| Prior finding | Re-inspected correction and proof | Result |
|---|---|---|
| Cancelled code verification can restart Add | `StepUp.submit()` creates and stores its own AbortController, passes its signal to the POST and checks that same signal before any callback, state change or focus work. Cancel/Escape and unmount abort it. Each reopened StepUp mounts fresh state, so the old closure cannot advance the new dialog. Security's old shared-Add-controller check is removed. Seven regression cases cover Cancel/Escape with late verified/signed-out/refused responses and reopening before the old verified response. | Resolved |

The cancellation guard does not rely solely on fetch rejecting: the fake server ignores abort, and the tests still require every late response to be ignored. The code endpoint keeps the session key/CSRF token (`app/accounts/views.py:279-287`), so this request does not require factor-mutation token reconciliation after cancellation.

Independent Chromium replays for both **Cancel** and **Escape** held the code request, closed the dialog, then attempted to deliver verified. Each observed one initial begin only, zero `credentials.create()` calls, no confirm, and Add still enabled and focused. Unit coverage separately proves the abort-ignoring late-answer and reopened-dialog cases. Normal verified retry and second-stepup refusal tests still pass.

### Applicability / self-check audit

Round 1's applicability audit remains valid: UNI typing/boundaries/ephemeral data/gates/runbook; AUTH server authority, step-up and response ownership; TEN-11; FE owned typed components/content/reuse; A11Y focus/modal/async state and named browser verification; PROJECT §9. Incremental changes are the local code-request cancellation identity, removal of the obsolete parent guard, regression tests and the corrected durable decision. No dependency/server/tenant/external-service scope added. The self-check and decision now describe cancellation correctly. Full browser checks are deferred to M3g-2b, not substantively inapplicable despite the PR table's “n-a here” label.

### Verification performed

| Check | Result |
|---|---|
| Pin/diff | Fetched origin; exact detached head and merge base; read incremental changes from `799d431`, seven new cases and updated DECISIONS. |
| Spec | Approved hash unchanged. |
| Local tooling | Node 24.21.0; frozen-lockfile install in reviewer checkout with local `.review-store`. |
| `pnpm -C web test` | 213 tests / 7 files pass. Builder's 16 mutants and repeated-run counts were not independently rerun. |
| Typecheck / lint / production build | All pass locally. |
| Focused browser replay | Headless Chromium, fake API/authenticator, held code request; Cancel and Escape each prevent registration continuation and retain enabled Add focus. Standalone Vite has no Django-prerendered shell and emits hydration recovery warnings; no production hydration or full accessibility claim is made. |
| Endpoint contract | Inspected code-stepup route: session key and CSRF token stay unchanged. |
| Exact-head CI | Waited for run 44062952477 to finish: checks/security/image/host all successful at this head. Publish/staging skipped for PR. |
| Fresh UI guidance | Re-fetched official Web Interface Guidelines; checked cancellation/focus/async semantics against the small correction. |
| Integrity/hygiene | `git diff --check origin/main...HEAD` clean; detached tracked/staged state clean; final host head unchanged and PR open. No suspicious instruction introduced. |
| Cleanup | Local Vite stopped; reviewer-created dependency/cache/build outputs and clean detached checkout removed. |

### Required before merge

No remaining review correction. Run `approved 164` to archive this exact-head review and create the receipt before the owner merges. This is slice approval, not an instruction to merge.

### Deferred conditions and residual risks

- PR 163's P2 assigned to **M3g-2a-2b-2** (mounting StepUp, one retry, second refusal and modal containment) is now closed at implementation/slice-review level.
- **P2 deferred to M3g-2b:** complete real WebAuthn/virtual-authenticator, keyboard/axe, responsive and cross-browser matrix. The focused checks in these rounds do not replace that suite.
- Earlier unidentified intermittent failure did not reproduce in this review's local run; preserve the observation in M3 gate evidence and capture the failing test if it recurs.
- No M3 feature-complete or production approval is implied. Remove and the enrolment offer remain later slices.

**Model used:** GPT-6.1 (Codex), independent review. **Switch model next step?** No — correction verified; keep deep reasoning for subsequent auth changes.

**Verdict:** Approved with conditions

