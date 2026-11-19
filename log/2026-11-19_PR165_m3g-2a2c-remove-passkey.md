# PR 165 — feat(web): M3g-2a-2c remove a passkey with inline confirmation

- **Merged:** 2026-11-19T08:07:33Z · **Merge commit:** 3e50b9ae2aef897f48d6abd523ec7b50fb25ccaa · **Branch:** feat/m3g-2a-2c-remove
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-165.receipt` (log-branch commit holding the review `908bfca5570cc0e61581c8e4bede90025cd4a8d6`; receipt time 2026-11-17T17:34:10Z by the machine clock, before the merge; head `0717cb3ea142a08893ebe18ec9320da702385a97`; review hash `355c3adc345908f6f1bc3dde3a4e9875ca70d523`)
- **Merge evidence:** `gh pr view 165` state MERGED, merge commit above, an ancestor of the fetched `origin/main`. Final head SHA equals the reviewed SHA.
- **Drafted by:** Claude Sonnet 5.5 · **Final verdict:** Approved with conditions (round 3, independent reviewer Codex)
- **Spec:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 · **Milestone:** M3g-2a-2c

## What changed
Adds Remove for a passkey with inline confirmation and a shared Add/Remove lifecycle on the Security page. Final size 479 changed lines (440 additions, 39 deletions); the review accepted the coupling rationale for staying one PR.

## Why
Slice spec M3g-2a-2 (passkey screens) PR 2c: remove a passkey, after Add (PRs 163, 164).

## Review rounds
- R1: [P1] a cancelled Remove recovery read could overwrite the token installed by logout → fixed (abort ignored, logout's token kept on the next POST).
- R2: [P1] the required exact-head CI job failed its live password-throttle test → rerun of the unchanged head passed (run 44085549833 attempt 2: 1123 live, 58 e2e).
- R3: Approved with conditions; one P2 deferred.

## Deferred conditions
- [P2] password-limit live test assumes one throttle window without the frozen `clock` fixture → freeze the clock, keep the rollover test, capture boundary evidence; due in M3g-2b, before the M3 gate review.

## Decisions worth keeping
- Decisions are in docs/DECISIONS.md "M3g-2a-2c" (merged with the PR).

## Follow-ups
- The deferred P2 above.

## Appendix — final review round
## Round 3 — 2026-11-18 · scope: slice

- **Code review:** merge base `015624d27d922e76bb8c3f401373e1627d415239`; head `0717cb3ea142a08893ebe18ec9320da702385a97`, unchanged since Round 2. Host head rechecked at end; PR open.
- **Spec:** passkey screens v1.3, hash `cd1a0ac71877db864f19377172c95b77b71be303`, unchanged. Scope: Remove and shared Add/Remove lifecycle.
- **Reviewer:** Codex; builder: Builder; owner: Ying. Detached `.agent/worktrees/review-165-0717cb3e`; no implementation files changed. This round rechecks CI/evidence, not a new source revision.

### Findings

No open P0/P1 and no P2 required before merge. The exact-head CI gate from Round 2 is now resolved. One bounded test-resilience follow-up is deferred below; the original failed run remains part of the evidence.

### [P2] The sixth-attempt test assumes a single throttle window without freezing its clock

- Category: resilience / test determinism
- Rule: UNI-13; test's same-window rate-limit assertion
- Evidence: `app/accounts/tests/test_password_step_live.py:89-106` makes several real password attempts and expects the next to be limited, but requests only `spied`, not the existing `clock` fixture. Throttling uses real time and fixed windows (`app/accounts/auth/throttle.py:91-110`). `app/accounts/tests/test_auth_throttle_live.py:95-115` explicitly freezes time, places failures just before a boundary, and verifies that the account limit clears in the next window. The original CI failure happened while the password test file ran across 12:45 UTC, a default 15-minute boundary. Rerun passed unchanged code.
- Failure scenario: the test's counted failures and final assertion fall in different buckets. The assertion can then fail although fixed-window rollover is intended. This makes CI dependent on wall-clock scheduling.
- Why it matters: intermittent red security tests obscure real regressions. This is a bounded test reliability issue in unchanged backend code; it is not proof of a production throttle bypass or a continuing failed CI gate. The exact historical failure's root cause remains inferred, not experimentally established.
- Required correction: make the same-window password assertion use the existing frozen clock, preserve the separate rollover test, and capture deterministic boundary evidence when diagnosing the historical failure. Record whether that explains it rather than calling every future failure a flake.
- Owner: builder
- Verification: run the password-limit test with a frozen same-window clock and controlled boundary cases; retain all expected limit assertions; complete full CI on that follow-up.
- Disposition (P2 only): deferred to M3g-2b, before the M3 gate review
- Status: open (deferred test-resilience work; no production risk acceptance inferred)

### Prior-finding resolution

| Finding | Evidence and disposition |
|---|---|
| Round 1 token overwrite | Remains resolved at this identical head. Round 2 independently verified 238 local tests and Add/Remove Chromium replays with abort ignored, retaining logout's token on the next POST. No source change since then. |
| Round 2 required CI failure | Run 44085549833 **attempt 2** reports this exact head and success. `checks`, `security`, `image`, `host` all successful; checks includes completed live DB and e2e stages. Logs show the previously failing password test file passing, **1123 live tests passed**, and **58 e2e tests passed**. The failed delivery gate is closed; test fragility is explicitly retained as the P2 above, not silently dismissed. |

### Applicability / self-check audit

Round 2's complete applicability and source assessment remain applicable: UNI boundary/token/gates/runbook, AUTH own-factor/step-up/logout lifecycle, TEN-11, typed owned components/fetch lifetime, accessible names/focus/status and named browser deferrals, PROJECT §9. No source or scope change. Current PR body now discloses the failed first attempt, successful rerun and unresolved diagnosis; handoff records both known test observations. UNI-13's current exact-head gate now passes. The conservative GET epoch behavior, 479-line coupling rationale and spec-based Remove reconciliation assessment are unchanged.

### Verification performed

| Check | Result |
|---|---|
| Fetch/pin | Fetched origin; detached checkout at the same reviewed head; merge base unchanged. |
| CI host metadata | Run 44085549833 attempt 2: completed/success at this SHA; checks/security/image/host pass. Publish/staging skipped for PR. |
| CI log | Re-read rerun checks log: password-step live test file passes, 1123 live tests pass and 58 e2e tests pass. |
| Failure investigation | Inspected unchanged failing-test clock usage and the existing controlled-clock rollover test. This substantiates the determinism gap, but does not constitute local reproduction of the historical failure. |
| Prior local validation | Reused Round 2's 238-test/typecheck/lint/build and Chromium token-order evidence because source is byte-identical; did not reinstall dependencies or repeat those checks. |
| Integrity/hygiene | Approved spec hash unchanged; `git diff --check origin/main...HEAD` clean; tracked/staged checkout clean; final host SHA unchanged and PR open. No suspicious instruction introduced in updated disclosure. |
| Cleanup | Clean detached checkout removed; no dependency/test/build outputs created this round. |

### Required before merge

No remaining review correction. Run `approved 165` to archive this exact-head review and create its receipt before the owner merges. Approval does not itself authorize a merge.

### Deferred conditions / residual risks

- P2 test-clock determinism follow-up above → **M3g-2b, before M3 gate review**. Carry it into the next handoff/PR evidence; the historical failed attempt is not erased by the rerun.
- P2 complete real WebAuthn/virtual-authenticator, keyboard/axe, responsive and cross-browser matrix → **M3g-2b**, retained from prior rounds.
- The earlier unidentified frontend intermittent failure remains a separate observation; this named Python failure must not be conflated with it.
- This approves the Remove slice only; enrolment offer and M3 feature/production approval remain separate.

**Model used:** GPT-6.1 (Codex), independent review. **Switch model next step?** No — CI evidence checked; retain deep reasoning for subsequent auth changes and the M3 gate.

**Verdict:** Approved with conditions

