# PR 7 — docs(plan): revise M0 plan to spec v1.8

- **Merged:** 2026-10-09T00:30:32Z (GitHub) · **Merge commit:** `7c889c502c75d75ac9cda9749bd7f4dd4999ab1e` · **Branch:** `docs/m0-plan-update` (final head `fbc1740346fd14afe553c71b11d2a548f994a757`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-7.receipt` on `agent-logs` (commit `23a2f1f`, written 2026-10-09T00:28:56Z, before the merge); names head `fbc1740…` and review-file hash `a8c88aa7e2a938bce8db3f333abb2e535d0ce430`; the archived review `reviews/PR-7.md` (log-branch commit `d4f6ed3`) has the same hash.
- **Merge evidence:** `gh pr view 7` → state MERGED, mergedAt 2026-10-09T00:30:32Z, merge commit `7c889c5`, final head `fbc1740` (equals the reviewed head of Round 2); `git merge-base --is-ancestor 7c889c5 origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder); plan text by Claude Opus 5.5 (deep tier subagent) · **Final verdict:** Approved (round 2; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8 (`67e36a52…`) · **Plan:** `docs/plans/2026-10-05-m0-scaffold.md` (blob `6c109bd91430a43047a50a3a49aadb044c7878a1`) · **Milestone:** plan update before M0c

## What changed
The M0 plan now agrees with the approved spec v1.8: M0a and M0b marked done; M0c rewritten (probe-only `enqueue_in_tx` subset, registry, Semgrep ban on direct defer, grants migration run as `skiw_migrator`, tests as `skiw_app`, worker service, exact `job_outbox` fallback criterion); M0d trimmed; settled owner answers recorded (ASK-1 a, ASK-2, ASK-5, ASK-6 b, TEN-03 option A); M4 hand-over list; DB port 5433 and role URLs stated.

## Why
Condition [P2] of spec review Round 11: revise the plan before M0c starts. Also closes PR 1 Round 1 P2.

## Review rounds
- R1 (Revision required): [P1] the plan let the builder defer `django-migration-linter` to M4 → now a required M0c gate (`django-migration-linter==6.0.0`, `lintmigrations --warnings-as-errors`, negative test; deferral only by owner-approved spec change). [P1] self-check omitted UNI-04/14/15/16 and TEN-10/11 → rows added to the PR body.
- R2: Approved.

## Deferred conditions
- none introduced. Standing: M0d scans and cache-constant name; M2 CSP nonce. ASK-3 and ASK-4 stay open (M0d items).

## Decisions worth keeping
- The migration-linter gate cannot be dropped by the builder.
- M0c tests run on an already-migrated database (no test-DB creation, no TRUNCATE) as `skiw_app`.
- The M0c plan condition from spec Round 11 is satisfied; M0c may start.

## Follow-ups
- Start M0c (deep tier) on `feat/m0c-jobs-enqueue` from `main`.
- Ask the owner about ASK-3 and ASK-4 before M0d.
- Owner UI-kit direction (shadcn/ui, SmoothUI) is recorded in the local handoff only; it needs a decisions entry and a spec D2 change before the product frontend milestone.

## Appendix — final review round
## Round 2 — 2026-10-09 · scope: plan-change slice (M0 scaffold, spec v1.8)
- **Code review:** base (merge base) `5f923b320acc744f7993b17e5290da912f4aa905` · head `fbc1740346fd14afe553c71b11d2a548f994a757` · host head re-checked at end: yes, unchanged and OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`, unchanged.
- **Plan:** `docs/plans/2026-10-05-m0-scaffold.md`, hash `6c109bd91430a43047a50a3a49aadb044c7878a1`.
- **Mode:** exact-head snapshot `.agent/worktrees/review-7-fbc17403`; tracked-file integrity verified by commit hashes, then snapshot removed. Fetch denied by read-only `.git/FETCH_HEAD`; exact head present. Host main confirmed the recorded base.

**Model used:** Codex GPT-6 · **Switch model next step?** No for review/archiving; M0c implementation retains the project's deep-tier requirement.

### Findings
No blocking findings or new defects.

#
