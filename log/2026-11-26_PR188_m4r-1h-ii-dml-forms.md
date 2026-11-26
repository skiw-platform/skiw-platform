# PR 188 — test(accounts): M4r-1h-ii remaining DML forms and COPY on the roles tables

- **Merged:** 2026-11-26 (00:42:24 UTC) · **Merge commit:** d23995d3ec4f3992ad685771c2291d587a2ffcd6 · **Branch:** test/m4r-1h-ii-dml-forms
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-188.receipt, created 2026-11-26 00:41:52 UTC, before the merge; names head 30202e892f4d2029783b386c829aea5068e6cb55 and review hash 750e5599…; log-branch commit cb24753
- **Merge evidence:** `gh pr view 188` state MERGED, merge commit above, mergedAt 00:42:24Z; reachable from the fetched origin/main. Final head 30202e89… equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); tests by an Opus sub-agent · **Final verdict:** Approved (round 2, GPT-6 (Codex) reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1h-ii (second part of M4r-1h; the M4r-1 sequence is complete)

## What changed
10 live tests in `app/accounts/tests/test_roles_dml_forms_live.py` plus a DECISIONS entry (508 added lines); no migration, grant or app code. As `skiw_app`: multi-row, INSERT … SELECT, MERGE INSERT/DELETE, ON CONFLICT DO NOTHING and multi-row UPDATE/DELETE on the four roles tables with exact events, affected-row counts and rows; bad-operator refusals; MERGE DELETE on org_unit and MERGE UPDATE on tick and assignment refused 42501; COPY FROM refused 0A000, and one event per row for the table owner in a rolled-back fixture; a scan of every security_event row for per-run email, role-name and unit-name sentinels, with a rolled-back positive control.

## Why
Slice spec §7 and §9 row 1h; Decisions 3, 28, 30–33.

## Review rounds
- R1 (Revision required): [P1] §7 audit privacy scan missing → sentinel scan of every event row with a positive control.
- R1: [P2] no-change snapshot missed value updates → whole rows by id.
- R1: [P2] row-count assertion accepted its own result → explicit count per step.
- R1: [P3] DECISIONS overstated mixed-source MERGE coverage → exact source shapes.
- R2: Approved.

## Deferred conditions
none (one non-blocking P3 below)

## Correction to the PR record (R2 P3)
The PR body's self-check says security_event is only read and that COPY is the sole owner write. Accurate wording: runtime writes use `skiw_app`; there are two owner fixtures, both rolled back: the COPY fixture, and the privacy scan's positive control, which inserts one synthetic pre-tenant security_event row as the owner and rolls it back.

## Decisions worth keeping
- Owner approval 2026-11-25 on the reviewer's recommendation, COPY (option A): PostgreSQL refuses COPY FROM on a table with row-level security; test the 0A000 refusal as skiw_app and one event per row as the table owner in a disposable transaction.
- Owner approval 2026-11-25 on the reviewer's recommendation, statements that write no row (option A): they succeed without a valid skiw.operator, with no change and no event (per-row triggers); every statement that writes a row is still refused. No migration.
- The privacy scan runs after the 1h-ii commit sequence only; the reviewer accepted it for M4r-1g too (same row audit functions).
- A full-row snapshot, not ids and counts, is what catches a same-id change in refusal tests.

## Follow-ups
- Next spec update: slice spec §7 and §9 row 1h (COPY), §7 "Refused paths" (no-row statements).
- Next: M4r-2 (reviewer: use the deep tier for grant evaluation).

## Appendix — final review round
## Round 2 — 2026-11-26 · scope: slice

- **Code review:** base and merge base `c3613cc2ecc3315e232ecb511afc84b5053a207e` · head `30202e892f4d2029783b386c829aea5068e6cb55` · head re-checked at end: yes.
- **Governing specs:** platform v1.24 and M4-rest v2.5, Decisions 3, 28, 30–33, §7 and §9 row 1h. M4r-1h-ii remains the DML test slice.
- **Diff:** two commits, two files, 508 added lines. The PR body explains the increase past the split guideline by tying the privacy scan, affected-row counts and snapshot assertions to the same committed test matrix. That is a coherent reason to keep the slice together.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for archiving. Use the deep tier for M4r-2 grant evaluation.

### Findings

No blocking findings. All round 1 findings are resolved.

#### [P3] The self-check omits the rolled-back audit positive control

- **Category:** defect.
- **Rule:** Reviewer §3, evidence accuracy for UNI-10 and TEN-02/03.
- **Evidence:** The PR body says that `security_event` is only read and that COPY is the sole owner write. The privacy scan plants a synthetic pre-tenant audit row as the owner at `app/accounts/tests/test_roles_dml_forms_live.py:489`. The owner transaction rolls back, and the following scan confirms the row is gone.
- **Failure scenario:** A reader relying on the self-check misses the positive control's privileged fixture insert.
- **Impact:** The self-check wording is imprecise. The insert stays confined to the disposable test transaction.
- **Required correction:** At the next update to the PR record, say that runtime writes use `skiw_app` and name both rolled-back owner fixtures.
- **Owner:** builder.
- **Verification:** Compare the self-check with the COPY fixture and privacy positive control.
- **Status:** open, non-blocking.

### Resolved findings

| Round 1 finding | Verified change |
|---|---|
| P1, missing live audit privacy scan | `app/accounts/tests/test_roles_dml_forms_live.py:453` scans the entire event table for distinct synthetic email, role-name and org-unit-name sentinels. The commit sequence emits all ten kinds, and the test verifies the sentinels were stored. A rolled-back unscoped event with an uppercased sentinel is detected, and the final scan verifies the full event inventory for the fixture and no matches anywhere. |
| P2, no-change snapshot misses value changes | `app/accounts/tests/test_roles_dml_forms_live.py:132` and `:306` now collect whole rows by ID in one scoped read. The malformed-operator, denied MERGE and runtime COPY refusal cases use the full comparison. |
| P2, affected-row assertion used its own result | Every step supplies an independent count, checked against the returned rows at line 319. The mixed rename expects three affected rows and exactly two rename events. The standalone unchanged UPDATE and zero-row cases retain separate expected counts. |
| P3, decisions entry overstated mixed-source MERGE | DECISIONS distinguishes the single-source root MERGE, the matched/missed role deletion, and the single matching source keys used for permission and assignment deletion. It also separates the reviewer recommendations from the recorded owner approvals. |

### Self-check audit

| Rule or requirement | Result |
|---|---|
| UNI-01, UNI-05, UNI-07 | Typed shared helpers retained. Local Ruff lint and formatting and the CI typecheck and full-history secret scan passed. |
| UNI-09, Decision 30 and §7 privacy scan | The fixture writes synthetic sentinels, checks all ten event kinds and scans events from every agency and pre-tenant events. I accepted this as evidence for the privacy requirement. The multi-form suite exercises the same row audit functions as M4r-1g and the existing M4r-1g exact payload assertions still run. A separate all-row scan after the older sequence was not added. |
| UNI-10, TEN-02/03 and TEN-05–09 | Runtime grants and scoped transactions are unchanged. Whole-row snapshots verify refusals and zero-row outcomes. The owner COPY fixture and privacy positive control are rolled back. The self-check wording note is recorded above. |
| UNI-13 | All four required CI jobs passed on the exact head. |
| Recorded deviations | The approved COPY split, zero-row behavior and `org_unit` MERGE DELETE refusal still match the tests. The planned spec wording updates have no runtime change. |
| Other applicability | No touched runtime entry point, schema, deployment, auth procedure or UI. No affected runbook. |

### Verification performed

| Command or check | Result |
|---|---|
| `git fetch origin`, `git cat-file -e`, `git merge-base`, `gh pr view 188`, effective and round-to-round diffs | Pinned and rechecked both exact SHAs. Checkout clean after checks and removed. |
| `git diff --check`, added-line secret pattern, local Ruff lint/format | Passed. No prompt-injection text found. |
| Disposable PostgreSQL 17.11, `migrate`, and `check_tenancy_schema` | Passed in an isolated loopback-only container namespace with dummy settings and read-only source. |
| Focused live DML, access audit, event RLS and event shape tests | **390 passed**, including all ten DML tests and the unscoped positive control. |
| GitHub Actions run 45641714352 and checks job 139301833295 | All required jobs green. CI recorded 1,961 unit tests and 2,000 live tests, plus successful schema and end-to-end checks. Publish and staging deploy skipped as expected. |

### Residual risks and test gaps

- Builder mutant results were reviewed as recorded. I independently verified the unchanged suite and its built-in positive control.
- COPY and zero-row specification wording stays scheduled for the next spec update, as recorded.

### Required before merge

- Run the approval archive and receipt step for the exact reviewed head.

### Deferred conditions

- None.

### Optional improvements

- Describe the rolled-back audit positive control in the self-check.

