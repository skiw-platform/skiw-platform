# PR 189 — feat(accounts): M4r-2a-i grant evaluation

- **Merged:** 2026-11-26 (02:26:55 UTC) · **Merge commit:** d4601da1ce247b2937ecff8674340e09b2c60726 · **Branch:** feat/m4r-2a-i-grant-evaluation
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-189.receipt, created 2026-11-26 02:26:27 UTC, before the merge; names head 5295a745469fe2a97217c98a3d9068631ee79818 and review hash 268fb262…; log-branch commit holding the review: 615b92e
- **Merge evidence:** `gh pr view 189` state MERGED, merge commit above, mergedAt 02:26:55Z; reachable from the fetched origin/main. Final head 5295a745… equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); plan and code by Opus sub-agents · **Final verdict:** Approved (round 1, GPT-6 (Codex) reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-2a-i (first part of M4r-2)

## What changed
`accounts/access/grants.py`: `Grant(scope, org_unit_id, line, stepup)` and `grants(user_id, code)`, one `user_role ⨝ role_permission` read in the caller's `with_agency()` transaction, never reading `role`, uncached, with a stored pair missing from the code catalogue dropped and logged. `tables.Line` type, 18 live tests and a DECISIONS entry (283 added lines). No migration, grant, route or wrapper change; nothing calls `grants()` yet.

## Why
Slice spec Decisions 6, 7 (ii)-(iii), 8 and 36; plan row M4r-2.

## Review rounds
- R1: Approved. One non-blocking P3 (below).

## Deferred conditions
none

## Decisions worth keeping
- Owner approvals 2026-11-26 (docs/DECISIONS.md "M4r-2"): split M4r-2 into 2a and 2b, then 2a into 2a-i and 2a-ii (M4-rest 32 PRs, roles track 22). A: a missing `line` raises TypeError. B: import contract now, the `accounts.access` re-exports and their Semgrep rule before the first route outside accounts. C: `no-role-name-branching` catches recognisable shapes only.
- The grant lookup did not wait for ACCESS EXCLUSIVE locks on `agency` and `role` (reviewer's own check), while a read of `role` timed out: the PR 183 steady-state seed-lock risk does not reach this query. Not covered: an initial seed writing `role_permission`, or future wrapper queries.
- On a long-lived local database, `test_session_route_live::test_the_token_in_the_answer_passes_the_csrf_gate` fails on every tenth run (its fixed email is locked for 30 minutes). CI uses a fresh database.

## Follow-ups
- P3 (R1): the `grants()` docstring should name `ValueError` and `TransactionManagementError` separately and say the self-service codes are held by active users with a second factor (Decision 6); at the next related edit.
- M4r-2a-ii (rule `no-role-name-branching`, held on a local branch), then M4r-2b; M4r-3 owns enforcement and the rename-invariance test.
- Test chore: make the CSRF-gate login test independent of earlier runs.
- Next spec update: Decisions 7, 26 and 11 (deviations A, B) and limit C.

## Appendix — final review round
## Round 1 — 2026-11-26 · scope: slice

- **Code review:** base and merge base `d23995d3ec4f3992ad685771c2291d587a2ffcd6` · head `5295a745469fe2a97217c98a3d9068631ee79818` · head re-checked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`) and M4-rest v2.5 (`bb262ec4`), Decisions 4, 6–8, 11, 26, 34 and 36, §7 and §9 row 2; owner-approved M4r-2 splits and spec readings. The scope is M4r-2a-i grant lookup. No separate PR plan, previous review round or UI preview applies.
- **Diff:** one commit, five files, +283/−3 lines.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for archiving. Use deep review for the follow-up authorization boundaries.

### Findings

No blocking findings.

#### [P3] The grant helper docstring blurs two parts of the API contract

- **Category:** defect.
- **Rule:** M4-rest Decisions 6 and 7; documentation accuracy.
- **Evidence:** `app/accounts/access/grants.py:44` reads as though a missing transaction raises `ValueError`; `require_open()` raises `TransactionManagementError`, as the live test at `app/accounts/tests/test_access_grants_live.py:197` asserts. The same docstring says “every user holds” the self-service codes. Decision 6 limits that rule to active users with a second factor.
- **Failure scenario:** A later wrapper caller reads the docstring and catches the wrong exception or cites an incomplete rule for self-service eligibility.
- **Impact:** Documentation only. Code and tests implement the intended grant lookup and exception types. The self-service check has no caller in this slice.
- **Required correction:** At the next related edit, name the two exceptions separately and state the self-service eligibility from Decision 6.
- **Owner:** builder.
- **Verification:** Compare the updated docstring with `require_open()`, the live test and Decision 6.
- **Status:** open, non-blocking.

### Self-check audit

| Rule or requirement | Verified result |
|---|---|
| UNI-01, UNI-03 | Strict typecheck passed in CI. The scope cast is guarded by the code catalogue and the line cast by the database CHECK. Unknown codes, including the separate self-service codes, are rejected. |
| UNI-04, UNI-05 | The helper reuses the existing transaction check. The query stays inside `accounts`, and the existing import checks pass. The appended decision records that the import-door contract and lint pieces land in their approved later slices. |
| UNI-07, UNI-09 | Added-line scan had no matches. The exact log assertion verifies the fail-closed warning contains only the catalogue code and scope. Stored scopes are constrained by the database. Full-history CI secret scan passed. |
| UNI-13 | All four required CI jobs passed on this exact head. |
| AUTH-03, AUTH-09, AUTH-12; Decisions 4, 7, 8, 26 and 34 | The query makes one fresh read for the requested user and code. The tests cover all 31 catalogue pairs on each of the three assignment lines and verify per-pair step-up from the reviewed catalogue. A stored pair missing from the code is dropped and logged. Tick, untick and unassignment take effect on the next read. The set union only collapses identical grant tuples and keeps the scope, unit, line and step-up paired. Wrapper enforcement remains M4r-3. |
| Decision 36 | Scoped EXPLAIN reads only `user_role` and `role_permission`, with a negative control detecting a `role` join. The next split adds the role-name lint rule, and M4r-3 still owns rename-invariance coverage. |
| TEN-02, TEN-05–10 | The one statement joins on agency and role and filters by user and code. Tested as `skiw_app` with FORCE RLS. Other users and agencies do not contribute grants. An unbound transaction returns none, and a call outside a transaction raises. No new connection or transaction is opened by the helper. |
| Other applicability | No schema, grants, routes, wrapper enforcement, external action or deployment change. No runtime consumer of the helper was added. Local-dev and CI runbooks remain applicable. |

### Verification performed

| Command or check | Result |
|---|---|
| `git fetch origin`, `git cat-file -e`, `git merge-base`, `gh pr view 189`, and the three-dot diff | Pinned the exact open PR head and base. Both unchanged on recheck. Detached checkout clean and removed. |
| `git diff --check`, added-line secret-pattern scan, and local Ruff lint/format | Passed. No prompt-injection text found. |
| Disposable PostgreSQL 17.11 with the pinned Compose image, `migrate`, and `check_tenancy_schema` | Passed. Used a resource-limited loopback-only container namespace, read-only source mounts and dummy settings. |
| Focused grant and seed live tests | **26 passed**, including the 18 new tests. |
| Independent seed-lock check, with fresh fixture grants and two sessions | The grant lookup returned the expected grant under a one-second statement timeout while another session held ACCESS EXCLUSIVE locks on `agency` and `role`. A direct read of `role` timed out. This addresses the PR 183 steady-state seed-lock concern for this query. |
| GitHub Actions run 45739738522 and checks job 139641500442 | Required `checks`, `security`, `host` and `image` succeeded. CI recorded 1,961 unit tests and 2,018 live tests, plus successful tenancy schema and end-to-end checks. Publish and staging deployment skipped as expected. |

### Residual risks and test gaps

- The independent lock test covers the steady-state locks on `agency` and `role`. It does not cover an initial seed writing `role_permission`, or future wrapper queries.
- Builder mutant outcomes were reviewed as reported. I independently ran the unchanged grant and seed suites and the lock test.
- M4r-2a-ii and M4r-2b still carry the approved lint, route registration and import work. M4r-3 owns enforcement. This slice approval applies to the lookup only.

### Required before merge

- Run the review archive and receipt step for the exact reviewed head.

### Deferred conditions

- None.

### Optional improvements

- Clarify the grant helper docstring.
