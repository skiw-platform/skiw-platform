# PR 195 — test(auth): M4r-3c wrapper rename invariance and order cases

- **Merged:** 2026-11-27T02:15:56Z · **Merge commit:** ab170745307abdb454367094f9f3a3caab21a8ec · **Branch:** test/m4r-3c-role-invariance
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-195.receipt (commit 38bc933, 2026-11-27T02:15:37Z, before the merge; head 7c0381fdfb3a637e72b07bfcaf30e8dc761b6949, review-file hash 6aa06bdd9feebad0dd3570f2a2804455b1d1ceb7)
- **Merge evidence:** `gh pr view 195` state MERGED with that merge commit and date, merged by the owner; the commit is reachable from the fetched origin/main and its second parent is the final head 7c0381f, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with an Opus sub-agent for the tests · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-3 · **Milestone:** M4 (M4r-3c)

## What changed
Tests and a DECISIONS entry only: the wrapper's outcomes are shown unchanged when every role is renamed or the names are swapped, the step-up read count is pinned for a mixed-line case, and a new live file pins the AUTH-01 order on a catalogue code in both transaction modes. No runtime code, migration, grant or dependency change. 258 added lines, 17 removed.

## Why
Slice spec v2.5 Decisions 7, 26 and 36, the §7 row "Authorization branches on a role name" and §9 row 3; the third of the owner's three M4r-3 PRs.

## Review rounds
- R1: Approved, no findings

## Deferred conditions
none

## Decisions worth keeping
Readings and limits are in docs/DECISIONS.md, "2026-11-27 — M4r-3c": the swapped-name round, and "a role-step 403 does not write the session row" pinned as today's behaviour (the spec says only "no logout"). PR CI run 45921752669 on 7c0381f passed (2084 unit, 254 web, 2047 live database, 60 end-to-end).

## Follow-ups
- M4r-3 (3a, 3b, 3c) is complete. M4r-4 (`scoped()`) is next; it takes the `scoped()` half of rename invariance and of the propagation tests.
- Renaming cannot show a branch on `is_system` or a role id; the existing lint and grant-query shape test cover reads of role identity.
- `test_with_own_transaction_every_outcome_and_the_order_are_the_same`: the closing `assert not SEEN` observes only the last request (noted in the PR body and by the reviewer); not changed.
- The reviewer did not repeat the mutation runs.
- CI on `main`: image paths still name `ghcr.io/skiw-dev1` (see the PR 193 and 194 logs); their own deploy-path PR is not made.
- Post-merge run 45927305003 on ab17074 (repository public until it finished): checks, security, image and host passed (2084 unit, 254 web, 2047 live database, 60 end-to-end; 855 host tooling, 39 live host stack); `publish` failed in "Push by digest" with `denied: permission_denied: The requested installation does not exist`, as on b557f7d; deploy-staging skipped.

## Appendix — final review round

## Round 1 — 2026-11-27 · scope: slice

- **Code review:** base and merge base `b557f7d6ab3dfd6c91ef3ffdbb9acc8d9f89e177` · head `7c0381fdfb3a637e72b07bfcaf30e8dc761b6949` · head rechecked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`) and M4-rest v2.5 (`bb262ec4`), Decisions 6–8, 26 and 36, §7 and §9 row 3. Scope is the owner-approved M4r-3c test-only split.
- **Diff:** four files, +258/−17, one commit. Changes are confined to tests, the test URL configuration and the decisions log.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for the archive and receipt.

### Findings

No open findings.

- **Decision 36.** `app/accounts/tests/test_wrapper_roles_live.py:377` checks exact status, refusal code and retained grants across all 24 test routes for an Owner, a user with mixed assignments and a user without a role. The test separately asserts the committed names under all three phases. Its final phase gives an ordinary role the `Owner` name and changes the system role to `staff`.
- **AUTH-01 and AUTH-09.** `app/accounts/tests/test_wrapper_roles_order_live.py:42` checks zero grant or proof queries when the session, tenant or factor check refuses the request. Lines 77 and 95 cover preserved sessions, denial before schema validation, and exact outcomes in both transaction modes. The separate-transaction test handler at `app/accounts/tests/urls.py:60` asserts that the wrapper transaction has ended and binds the session's agency for its own query.
- **Mixed business lines.** `app/accounts/tests/test_wrapper_roles_live.py:309` closes the read-count gap from PR 194. The same grants produce no proof lookup on the insurance route and one lookup on the `any` route, where both lines match.

### Self-check audit

| Rule | Applicability | Review |
|---|---|---|
| UNI-01, UNI-04, UNI-05 | Strict typing, boundaries and test reuse | CI typecheck and lint passed. Test URL registrations use the existing wrapper and the query-count helper is shared. |
| UNI-07, UNI-13 | Secret hygiene and required CI | Added-line secret-pattern scan found no matches. CI full-history secret scan was clean and all required jobs passed. |
| UNI-16 | Auth runbook | No production route, authorization behavior or operator command changes in this slice. |
| AUTH-01–03, AUTH-09 | Order, wrapper gate, scope and step-up assertions | Reviewed the assertions and independently ran both test files against fresh PostgreSQL as `skiw_app`. |
| TEN-09, TEN-11 | Tenant binding for the test handler | The `own_transaction` test handler rebinds from `signed.agency_id`. The existing production session source and tenancy controls remain in place. |

### Verification performed

| Check | Result |
|---|---|
| GitHub pin, commit and merge base, effective diff and end-of-round pin | Matched. Removed the detached checkout after confirming it was clean. |
| `git diff --check` and added-line secret-pattern scan | Clean. No prompt-injection text found in the diff or PR body. |
| Two focused wrapper live test files | 22 passed. Used PostgreSQL 17.11 on an isolated loopback namespace with dummy settings and tmpfs data. Migrated as `skiw_migrator` and ran tests as `skiw_app` with read-only source. The database was removed after the run. |
| GitHub Actions run 45921752669 | All four required jobs passed on this exact head. Includes strict typecheck, 24/24 Semgrep rule fixtures, 2,084 Python unit tests, 254 web unit tests, 2,047 live database tests, the tenancy schema check and 60 end-to-end tests. |

### Residual risks and test gaps

- The full suites were verified through exact-head CI. Builder and sub-agent mutations were not independently repeated.
- The rename test exercises names, with unchanged role IDs and system flags. The existing lint and grant-query shape tests cover reads of role identity. The companion `scoped()` rename check belongs to M4r-4.
- The `own_transaction` bad-body sequence checks the exact status on all three requests. The trailing `SEEN` assertion observes only the final request because `outcome()` resets the capture each time.

### Required before merge

- Archive this round and record the review receipt for the exact reviewed head.

### Deferred conditions

- None.
