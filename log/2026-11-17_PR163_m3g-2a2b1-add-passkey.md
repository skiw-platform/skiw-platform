# PR 163 — feat(web): M3g-2a-2b-1 add a passkey from the Security page

- **Merged:** 2026-11-17T04:56:29Z · **Merge commit:** 54a122d17031b57639924831ea786a8899aa0ec6 · **Branch:** feat/m3g-2a-2b-add-passkey
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-163.receipt` (log-branch commit holding the review `14edeb96d7b147fdc4b091ce6c4979ffa960c440`; receipt time 2026-11-17T04:54:12Z, before the merge; head `d6690c194fa218a749810c4f29f4764015ea8c7a`; review hash `40bd0694c0509b0ca7c5052edc22e31b34fded7a`)
- **Merge evidence:** `gh pr view 163` state MERGED, merge commit above; commit is an ancestor of the fetched `origin/main`. Final head SHA equals the reviewed SHA.
- **Drafted by:** deep-tier sub-agent (Claude Opus), orchestrated by Claude Sonnet 5.5 · **Final verdict:** Approved with conditions (round 2, independent review GPT-6.1 Codex)
- **Spec:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 · **Plan:** M3 plan · **Milestone:** M3g-2a-2b-1

## What changed
Registration helper (manual base64url, confirm body exactly `{credential}`), a module-level operation runner (a sent confirm always finishes; ambiguous answers never claim success), the Sign out gate, and Add a passkey on the Security page with busy, status and focus behaviour. A 403 step-up shows a temporary message; the dialog follows in 2b-2. Final size 795 changed lines (owner accepted 627 for the first commit; Round 1 fixes added the rest).

## Why
Second PR of M3g-2a-2 (owner split the planned 2b, 760 lines, into 2b-1 and 2b-2 on 2026-11-16).

## Review rounds
- R1: [P1] Sign out did not cancel a pre-confirm registration and could race its confirm → the runner owns the abort controller; Sign out blocks new adds and aborts begin or prompt before logout.
- R1: [P1] the real Today link reloaded the document and destroyed the runner → plain nav clicks use `pushState`; reload and tab close limitation documented.
- R1: [P2] Add unlocked before its list read and allowed overlapping completions → Add stays busy through the read; token gate separate from the add's lifetime; focus in `useLayoutEffect`.
- R2: Approved with conditions, no new finding.

## Deferred conditions
- P2 → M3g-2a-2b-2: StepUp dialog on 403 with a second begin, modal containment, repeated `stepup-required` refusal.
- Real-browser matrix (keyboard, axe, responsive, virtual authenticator) → M3g-2b.
- An unidentified test flake (1 failure in 130 runs on the final code): capture the failing test if it recurs.

## Decisions worth keeping
- A sent confirm carries no signal and is reconciled; "added" only from the exact success shape with a UUID `factor_id`; a list difference never proves success.
- Nav clicks keep the document; a reload or tab close discards the runner (the next load reads the server).
- The full 2b (760 lines) is saved as `2b-full.patch` in the session scratchpad for 2b-2.

## Follow-ups
- Build M3g-2a-2b-2 (deep tier), then 2c remove, 2d the offer, M3g-2b browser tests.

## Appendix — final review round
## Round 2 — 2026-11-16 · scope: slice

- **Code review:** merge base `514a8ca655330d74f0df04dd051fa93799f03878`; head `d6690c194fa218a749810c4f29f4764015ea8c7a`. Host head rechecked unchanged, PR open.
- **Spec:** passkey screens v1.3, hash `cd1a0ac71877db864f19377172c95b77b71be303`, unchanged. Accepted 2b-1 scope is registration/runner/logout gate/Add with temporary step-up message; 2b-2 owns the dialog/modal.
- **Reviewer:** Codex; builder: Builder; owner: Ying. Detached checkout `.agent/worktrees/review-163-d6690c19`; main and builder files untouched.

### Findings

No new blocking findings. All three Round 1 findings are resolved in the inspected scope.

| Prior finding | Re-inspected correction and verification | Result |
|---|---|---|
| P1: sign-out races a pre-send add | Runner owns an AbortController; `leave()` sets its exclusion synchronously and aborts that controller before App awaits `trusted()` or sends logout. `addPasskey()` refuses work while leaving; `stay()` releases it in logout's finally. New held-begin/held-prompt tests prove abort before logout and no late confirm; held-logout test proves Add starts nothing and works after failed logout recovery. | Resolved |
| P1: Today replaces document and discards runner | `App.follow()` intercepts only an ordinary left click, pushes the actual href and updates page; modified/middle clicks retain default link behavior. Unit tests cover actual nav anchors, history, held confirm and a returning page. Independent Chromium replay returned `sameDocument: true`, `phaseWhileHeld: sent`, `signOutDisabledWhileHeld: true`; after releasing the confirm, logout sent `X-CSRFToken: fresh`, exactly from that confirm. Reload/tab-close limitation is now explicit in DECISIONS and runbook. | Resolved |
| P2: Add unlocks before list reconciliation | Token phase and operation busy lifetime are separate. `adding()` awaits `readPasskeys()` before the runner's finally releases busy; Security consumes that result. A page mounted during an earlier visit's operation waits before its own list GET. Held-list tests cover added/unconfirmed, no second begin, token gate already idle and logout available, then proper release. Failed-list cases assert busy cleared. | Resolved |

Focus handling now uses a layout effect to commit focus with the visible message. This addresses the identified focus-assertion race; it is not proof that the separately disclosed unidentified intermittent failure has been diagnosed.

### Applicability / self-check audit

Round 1's applicability list was retained and checked against the effective correction: UNI boundary/types/ephemeral data/gates/runbook requirements; AUTH server authority, step-up/revocation and logout lifecycle; TEN-11; FE owned components, real links, content, fetch lifetime and quality checks; A11Y focus/live feedback and the named browser deferral; PROJECT §9. The updated PR self-check now cites cancellation, document-preserving navigation and held-operation evidence for AUTH-13. The browser/server proof distinction remains: fake API tests do not establish server revocation. No new dependency, server, tenant, money, file, record, job, external-service or locked-switch scope.

### Size and scope

The effective diff is now 740 added / 55 removed = 795 changed lines. The initial 627-line size exception was accepted in the session. The growth consists of the requested lifecycle repairs and their held-operation regressions within that same accepted unit; it adds no new product path. I accept the stated coupling rationale for this repaired diff: the logout/runner/navigation corrections must ship with the Add path they protect. This is not blanket approval of larger subsequent PRs, and it does not justify cutting required test evidence.

### Verification performed

| Check | Result |
|---|---|
| Fetch/pin/diff | Fetched origin, exact detached head, merge base above; inspected full incremental diff from `16f3b88`, updated tests, decision and runbook. |
| Spec | Approved v1.3 hash unchanged. |
| Local tooling | Node 24.21.0, frozen-lockfile installation with `.review-store` inside reviewer checkout. |
| `pnpm -C web test` | 200 tests / 7 files pass locally. Read the 12 new held-operation/nav cases. Did not rerun the builder's 26 mutants or 130 repetitions. |
| Typecheck, lint, production build | All pass locally on the reviewed source. |
| Focused browser replay | Headless Chromium, local Vite, fake authenticator/API, real Today anchor and held confirm. Same document retained, sent phase/gate retained, eventual logout used confirm's exact fresh token. This is not the full real-server/WebAuthn/axe/responsive matrix. Standalone Vite lacks the Django-prerendered shell; hydration recovery warnings are not treated as a production hydration result. |
| Exact-head CI | Run 43872082742 reports this head and success; checks/security/image/host all pass. Publish/staging skipped for PR. |
| Fresh UI guidance | Re-fetched official Web Interface Guidelines and checked link semantics, focus and async states against the changes. |
| Hygiene/integrity | `git diff --check origin/main...HEAD` clean; tracked/staged checkout state clean; host head unchanged and PR open at final check. No suspicious instruction introduced in the correction. |
| Cleanup | Local Vite stopped; reviewer-created install/cache/build output and clean detached checkout removed. No tracked source modified by the reviewer. |

### Required before merge

No remaining review correction. Run `approved 163` to archive this exact-head review and create its receipt before the owner merges. Approval is limited to this slice and is not a merge instruction.

### Deferred conditions and residual risks

- **P2 deferred to M3g-2a-2b-2:** step-up dialog integration, modal containment and repeated-stepup refusal behavior, under the accepted split. Server still enforces step-up; temporary text remains disclosed.
- **P2 deferred to M3g-2b:** full real WebAuthn/virtual-authenticator, keyboard, axe, responsive and cross-browser matrix. The targeted Chromium reproduction above proves the repaired navigation case only.
- Builder disclosed one unidentified failure in 130 final-code runs. This review's local run and exact-head CI passed; no root-cause claim is made. Capture the failing test/output if it recurs, and carry the outstanding observation into the M3g-2b/M3 gate evidence.
- Explicit reload/tab close destroys in-memory work; next load reads server session/list afresh. Ordinary app navigation now retains the runner. No cross-document operation persistence or arbitrary tab-close guarantee is claimed.

**Model used:** GPT-6.1 (Codex), independent review. **Switch model next step?** No — corrections verified; keep deep reasoning for the step-up/modal follow-up.

**Verdict:** Approved with conditions

