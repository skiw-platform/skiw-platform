# PR 20 — docs(setup): reconcile PROJECT.md with spec v1.13

- **Merged:** 2026-10-10T15:09:44Z (GitHub) · **Merge commit:** `21db4511ffaa80741572d3adae35d54c3183a1f5` · **Branch:** `docs/reconcile-spec-v1.13` (final head `582d8c158863fcb66b2c582050e7330e0a5cd428`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-20.receipt` on `agent-logs` (written 2026-10-10T15:06:15Z, 3 minutes 29 seconds before the merge); names head `582d8c1…` and review-file hash `ebae671ac0e2c37acd1e7860819bce818b7e3a8b`; records CI green on that exact head (run 38043211839). The archived review `reviews/PR-20.md` has the same hash.
- **Merge evidence:** `gh pr view 20` → state MERGED, mergedAt 2026-10-10T15:09:44Z, merge commit `21db451`, final head `582d8c1` (equals the reviewed head of Round 2); `git merge-base --is-ancestor 21db451 origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder) · **Final verdict:** Approved (round 2; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.13 (`e3141585…`) · **Milestone:** setup Part B reconcile (no milestone)

## What changed
`agents/PROJECT.md` only: "Spec hash at last reconcile" set to `e314158562214a9173e7fdbd7ec6f2a8d9355dd9` (was v1.8 `67e36a52…`); the section 9 job rule now carries the v1.9 to v1.13 worker rules (`runworker` on `DjangoConnector`, per-agency fan-out with `job_fanout`, periodic system task exception, no automatic stalled re-queue, upgrade gate); the "Second agency onboarding" locked-switch row now also requires signed or provenance-checked periodic parents.

## Why
The reconcile gate (`agents/START.md` `build` step 2) blocks `build` until `PROJECT.md` carries the hash of the approved spec. Spec v1.13 was approved in spec review Round 16 and merged in PR 19.

## Review rounds
- R1 (Revision required): [P1] PR self-check omitted UNI-13 exact-head CI and the EVT/TEN/UNI alignment rows → table completed, CI run cited. [P2] second-agency locked-switch row lacked the signed periodic-parent prerequisite → added (`582d8c1`).
- R2: Approved.

## Deferred conditions
- none introduced. Standing: M4/M5 implementation proof; second-agency provenance gate; M1 production secret manager and TLS flag validation; M2 CSP nonce; Q2/Q32 remaining sub-questions.

## Decisions worth keeping
- All decisions behind this reconcile are in `docs/DECISIONS.md` (entry 2026-10-10 "M4 worker enqueue"); this PR records no new decision.

## Follow-ups
- The M4 implementation PR must fix plan `docs/plans/2026-10-05-m0-scaffold.md` line 164, the `docs/DECISIONS.md` 2026-10-09 "unresolved" wording and `app/jobs/management/commands/runworker.py`.
- Owner: `brew install gitleaks` then `make hooks`; decide the kit change for the explicit green-CI check.
- Next: M1 infrastructure plan (needs AWS account and budget answers). Parked: UI kit decision, API Anything / FAME spike, `skiw-old` look reference.

## Appendix — final review round
## Round 2 — 2026-10-10 · scope: slice (spec v1.13 reconciliation)
- **Code review:** base (merge base) `e84f929a8cac52437d63030ead02ca35b28cb63b` · head `582d8c158863fcb66b2c582050e7330e0a5cd428` · host head re-checked at end: yes, unchanged and OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.13 · hash `e314158562214a9173e7fdbd7ec6f2a8d9355dd9` · approved in spec Round 16.
- **Mode:** exact-head snapshot `.agent/worktrees/review-20-582d8c15`; tracked-file integrity verified and own snapshot removed. No source/PROJECT changes by Reviewer.

### Findings
None. Both Round 1 findings resolved; no new defect or open before-merge correction.

#
