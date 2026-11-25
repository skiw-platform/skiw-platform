# PR 185 — test(accounts): M4r-1g-ii skiw_app audit tests

- **Merged:** 2026-11-25 (01:55:31 UTC) · **Merge commit:** 47977963966a1a23a3dcd990215cf4eb195afa02 · **Branch:** feat/m4r-1g-ii-skiw-app-audit-tests
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-185.receipt, created 2026-11-25 01:54:56 UTC, before the merge; names head e570f697c069bb6146c77a8474fc716f7e23fa70 and review hash 19bd6b3c…; log-branch commit 5014928
- **Merge evidence:** `gh pr view 185` state MERGED, merge commit above, mergedAt 01:55:31Z; reachable from the fetched origin/main. Final head e570f697… equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); tests by an Opus sub-agent · **Final verdict:** Approved (round 2, GPT-6 (Codex) reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1g-ii (second of three parts of M4r-1g)

## What changed
Twelve live tests as `skiw_app` in `app/accounts/tests/test_access_audit_live.py` plus a DECISIONS entry; no schema. They cover the single-statement forms on `role`, `role_permission`, `user_role` and `org_unit`: commit with exactly its events (16 steps), refusal under five bad operators (including the combined org move and rename and a root insert in a rootless agency), statements outside Decision 3, rollback with its events, and TEN-08 write isolation including `role` UPDATE(`name`).

## Why
Slice spec §7 and §9 row 1g: every granted write path must commit with its audit record, refuse bad operators and out-of-grant statements, and stay tenant-isolated.

## Review rounds
- R1 (Blocked): [P1] CI jobs did not start → repo was private; made public per the standing rule, PR closed and reopened for a fresh run (green).
- R1: [P1] invalid-operator tests omit two org write forms → combined move and rename plus rootless root INSERT added to the matrix.
- R1: [P1] self-check omits UNI-09 → row added to the PR body.
- R1: [P2] undocumented `Any` types → narrowed; `Ids` keeps `Any` with a comment.
- R1: [P3] stale handoff summary → refreshed (carried to R2, refreshed again).
- R2: Approved; only the P3 handoff note, since refreshed.

## Deferred conditions
none

## Decisions worth keeping
- `ON CONFLICT DO UPDATE` is tested as refused only on `role_permission` and `user_role`; on `role` and `org_unit` it is a granted rename or move, recorded by the audit trigger (DECISIONS M4r-1g-ii, choice 3; reviewer found it consistent with Decision 32).
- The repo must be made public before `gh pr create`; this was missed on PR 185 and cost two failed CI runs.
- Local `make test-live` has 5 failures when the cluster superuser is not `postgres` (test_live_role_set x4, test_guard_schema_live pgcrypto); CI is clean.

## Follow-ups
- M4r-1g-iii: event `at = statement_timestamp()` assertion, reverse of 0022, `tgqual IS NULL` rule, PR 183 P3s.
- M4r-1h: remaining DML forms (multi-row, INSERT … SELECT, COPY, MERGE, ON CONFLICT DO NOTHING) and two-connection races.

## Appendix — final review round
## Round 2 — 2026-11-25 · scope: slice

- **Code review:** base and merge base `5a6ec2def93031476d88b35c8e8813d13d064310` · head `e570f697c069bb6146c77a8474fc716f7e23fa70` · head re-checked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`) and M4-rest v2.5 (`bb262ec4`), Decisions 3, 28, 30, 32 and 33, §7 and §9 row 1g. Same M4r-1g-ii slice as round 1. The PR has two files and 383 added lines. The follow-up commit changes only the test module.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for the approval archive. Use the deep tier for the M4r-1h concurrency review.

### Findings

No blocking findings. All round 1 P1 and P2 findings are resolved.

#### [P3] The handoff summary is partly stale

- **Category:** defect.
- **Rule:** reviewer §2.
- **Evidence:** `.agent/handoff.md:10` and `:13` now identify PR 185 and the fix commit. The git-state summary at line 20 still reports `main`, the next step at line 30 still says to build this slice, and line 40 still names PR 184 as the latest verdict.
- **Failure scenario:** A session using the git-state or next-step section can repeat work already completed.
- **Impact:** Limited to the handoff summary. The active-target section records the correct PR.
- **Required correction:** Refresh those sections when recording the round 2 verdict.
- **Owner:** builder.
- **Verification:** Compare those sections with the current checkout, GitHub state and this review round.
- **Status:** open, carried from round 1.

### Resolved findings

| Finding | Verified resolution |
|---|---|
| P1, required CI jobs did not start | Run 45429070835 is a successful PR run on `e570f69` with all four required jobs green. The older failed run remains visible in the check history. |
| P1, invalid-operator tests omit two org write forms | `app/accounts/tests/test_access_audit_live.py:236` and `:241–261` check the combined path and root INSERT under all five invalid-operator values. The team begins under a child unit, so the combined UPDATE changes both fields. A separate rootless agency gives the root INSERT a valid fixture. Both paths assert the exact operator refusal and re-read state and events. CI ran all 12 tests in the module. |
| P1, audit data minimization missing from self-check | The PR body lists UNI-09 and cites exact `details_json` comparisons, synthetic fixture data, and the schema CHECK. The CHECK requires both HMAC fields to be null for change kinds (`app/accounts/migrations/0022_security_event_agency.py:52`). |
| P2, undocumented `Any` | `app/accounts/tests/test_access_audit_live.py:31–34`, `:109` and `:119` narrow the event data, state return and IDs. The remaining named SQL parameter mapping documents its mixed fixture values. CI typecheck passed. |

### Self-check audit

| Rule | Evidence and result |
|---|---|
| UNI-01, UNI-05 | Re-inspected the revised helpers and reused refusal queries. Ruff lint and format, project lint and strict typecheck passed. |
| UNI-07, UNI-09 | Added-line scan found tenant-token terminology only. Exact payload checks, synthetic identifiers and schema evidence support the new self-check row. CI full-history secret scan and secret-rule tests passed. |
| UNI-10, TEN-03 | The module reads events written by the audit triggers. Existing live append-only and isolation tests ran in the green suite. |
| UNI-13 | The latest PR run exercised lint, typecheck, unit, live DB and end-to-end tests, dependency and secret scans, and host and image gates. |
| TEN-02, TEN-05–09, Project §9 and M4-rest Decisions 3, 28, 30, 32 and 33 | The new refusals run as `skiw_app` in separate `with_agency()` transactions and preserve the committed state and event log. The rest of the audited query shapes, privilege checks, rollback and isolation coverage are unchanged from round 1 and passed on the final head. |
| Runtime module boundaries, migrations, deployment and request authorization | The follow-up changes test code only. Round 1's applicability and runbook conclusions still hold. |

### Verification performed

| Command or check | Result |
|---|---|
| `git fetch origin`, `git cat-file -e`, `git merge-base`, `gh pr view 185` | Pinned the open PR to the exact head and base above. Rechecked both before closing the round. |
| Three-dot diff, round-to-round diff, and `git diff --check` | Inspected the complete file inventory and the test-only fix. No whitespace errors or prompt-injection text found. |
| Ruff lint and format checks on the changed test module | Passed in the detached checkout. Verified clean tracked and untracked status and removed that checkout. |
| `gh run view 45429070835` and job log 138569016345 | All four required jobs passed. CI logged a successful tenancy schema check and 1,964 live tests passed, including all 12 in the changed module. Publish and staging deploy were skipped for this PR run. |

### Residual risks and test gaps

- Round 2 relied on the successful CI run for the full test suite, typecheck and security scans. Reviewer also ran focused Ruff checks locally.
- The event timestamp assertion and reverse-migration follow-up remain scheduled for M4r-1g-iii. The remaining DML forms, fail-closed case and two-connection races remain scheduled for M4r-1h.

### Required before merge

- Run the project approval archive and receipt step for PR 185 on the reviewed head.

### Deferred conditions

- None for this verdict.

### Optional improvements

- Refresh the remaining stale handoff sections.

