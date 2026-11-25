# PR 186 — test(accounts): M4r-1g-iii deferred items

- **Merged:** 2026-11-25 (08:25:50 UTC) · **Merge commit:** d17c47a7a52965ca0b640c276ed6b1174dadb1f9 · **Branch:** feat/m4r-1g-iii-deferred-items
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-186.receipt, created 2026-11-25 08:12:14 UTC, before the merge; names head 9364b088fe5dc0ac2c92485be71980d87b405411 and review hash 913b8ecf…; log-branch commit 5bd9543
- **Merge evidence:** `gh pr view 186` state MERGED, merge commit above, mergedAt 08:25:50Z; reachable from the fetched origin/main. Final head 9364b088… equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by Opus sub-agents · **Final verdict:** Approved (round 3, GPT-6 (Codex) reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1g-iii (third of three parts of M4r-1g)

## What changed
The five deferred small items of M4r-1g: schema reversal now refuses (55000, fixed message) while change-kind `security_event` rows exist, with the guard in the reverses of 0025 and 0024 (0022 kept as defence in depth); each event's `at` is asserted equal to the change statement's `statement_timestamp()`; the schema check pins `tgqual IS NULL` for `security_event_shape`; `seed.py` uses a line-level `nosemgrep` in place of a whole-file Semgrep exclusion; the seed test asserts a non-zero `lock_timeout`. `rollback.md` documents the refusal and recovery.

## Why
Deferred conditions from the PR 177 (P2), 178 (P3) and 183 (P3) reviews and the `at` check of slice spec §7 / §9 row 1g; the reverse guard had to land before any production deploy.

## Review rounds
- R1 (Revision required): [P1] refused rollback leaves audit records unprotected → guard moved to the reverses of 0025 and 0024 (FORCE lifted inside the reverse's own transaction), walk test, static test, throwaway-DB end-to-end run.
- R1: [P1] self-check and runbook omit the isolation boundary → TEN-05..08, UNI-09, UNI-16 rows; rollback.md rewritten.
- R1: [P2] undocumented `Any` cursor → Django `CursorWrapper` type.
- R1: [P3] stale handoff → refreshed.
- R2 (Revision required): [P1] runbook allowed replacing audit history with an older dump → roll-forward is the recovery; restore only as an owner-decided, accounted exception.
- R2: [P3] contradictory TEN-08 row → fixed. [P3] handoff SHA → refreshed.
- R3: Approved.

## Deferred conditions
none (one P3 carried below)

## Decisions worth keeping
- Already-merged migrations 0022, 0024 and 0025 were edited, reverse SQL only (DECISIONS M4r-1g-iii choices 1, 2, 4); 0024 got the guard beyond the review's ask.
- Django commits each reverse on its own, so a refusing reverse must come before the first one that drops a protection.
- A schema reversal that refuses leaves 0030 to 0026 reversed (roles writes fail) until rolled forward.
- Tests that commit a migrate-back must clear change rows first (`clear_change_events` helper).
- Remember: make the repo public before `gh pr create` (done this time).

## Follow-ups
- Runbook P3 (R3): at the next rollback.md edit, say the loss inventory comes before the restore and any authorised replay of business changes follows the restore through the normal audit path.
- M4r-1h: remaining DML forms and two-connection races.

## Appendix — final review round
## Round 3 — 2026-11-25 · scope: slice

- **Code review:** base and merge base `47977963966a1a23a3dcd990215cf4eb195afa02` · head `9364b088fe5dc0ac2c92485be71980d87b405411` · head re-checked at end: yes.
- **Governing specs:** platform v1.24 and M4-rest v2.5, Decisions 30, 32 and 33 and §9 row 1g. The final follow-up changes only the rollback runbook.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for the approval archive. Use the deep tier for the M4r-1h concurrency review.

### Findings

No blocking findings. The round 2 recovery blocker is resolved.

#### [P3] Clarify when to reapply changes after an exceptional restore

- **Category:** defect.
- **Rule:** UNI-16.
- **Evidence:** `docs/runbooks/rollback.md:46` puts “re-enters them” in the clause preceding the restore procedure.
- **Failure scenario:** An operator following the sequence literally might re-enter a business change before restoring the snapshot, which would then overwrite it.
- **Impact:** Limited to the exceptional, owner-authorized path. The normal roll-forward procedure is clear and preserves the records. The runbook requires a written loss inventory before incident closure.
- **Required correction:** During the next runbook edit, clarify that the loss inventory precedes the restore and any authorized replay of business changes follows the restore through the normal audited workflow.
- **Owner:** builder.
- **Verification:** Read the revised sequence against a change and event recorded after the selected snapshot.
- **Status:** open, non-blocking.

### Resolved findings

| Round 2 finding | Verified change |
|---|---|
| P1, restore alternative could discard protected audit records | `docs/runbooks/rollback.md:40` identifies roll-forward as the recovery. Line 43 limits restore to the case where roll-forward is impossible, calls out the data and audit loss, and requires the owner's decision, an exact dump and a documented account of subsequent changes and events. For a dump older than a known change, the normal recovery preserves it and the exceptional path makes the loss explicit before restoration. |
| P3, contradictory TEN-08 self-check | The current PR body contains one applicable TEN-08 result with evidence. The N/A row now lists TEN-09 and AUTH. |
| P3, handoff listed the earlier SHA | The active target and current-PR entries now identify `9364b08`. |

### Self-check audit

| Rule | Result |
|---|---|
| UNI-10, UNI-16, TEN-03 and M4-rest Decision 30 | The updated runbook distinguishes the preserving recovery from an owner-authorized restore that loses post-snapshot changes. It retains the audit isolation verification before serving. |
| TEN-05–08 and M4-rest Decisions 32 and 33 | The exact diff from round 2 changes no migrations, runtime code, or tests. The previous disposable-database evidence carries forward for the same code, and the final-head live CI suite passed. |
| UNI-07 and UNI-13 | New material is runbook text with no credential or fixture data. All four required CI jobs passed on the final head. No other rule applicability changed in the runbook-only fix. |

### Verification performed

| Command or check | Result |
|---|---|
| `git fetch origin`, `git cat-file -e`, `git merge-base`, and `gh pr view 186` | Pinned the open PR and confirmed the same head and base after CI. |
| Effective and round-to-round diffs, `git diff --check`, review checkout status | Inspected the full inventory and the runbook-only delta. No whitespace errors or prompt-injection text found. Checkout clean and removed. |
| Recovery walk-through against `rollback.md`, `restore.md` and the deploy implementation | Confirmed normal recovery re-applies forward migrations and checks the schema. The exceptional restore explicitly accounts for newer changes and their events. No host was accessed. |
| `gh run view 45568894347` and checks job 139050384095 | All four required jobs green on the recorded SHA. The checks log shows 1,961 unit tests and 1,965 live tests passed, and the end-to-end step passed. Publish and staging deploy skipped as expected for this PR run. |

### Residual risks and test gaps

- Round 3 did not replay a local restore. The final change was documentation only. The independently reproduced rollback and roll-forward from round 2 still cover the same code.
- M4r-1h concurrency and fail-closed cases remain in the planned slice.

### Required before merge

- Run the approval archive and receipt step for this exact head.

### Deferred conditions

- None.

### Optional improvements

- Clarify the replay order in the exceptional restore instructions.

