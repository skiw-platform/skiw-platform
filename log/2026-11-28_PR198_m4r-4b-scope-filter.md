# PR 198 — feat(auth): M4r-4b scoped() filters records by own, team and agency

- **Merged:** 2026-11-28T09:52:41Z · **Merge commit:** c3750f91974ac4a0aff805eea386d776a763df54 · **Branch:** feat/m4r-4b-scope-filter
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-198.receipt (commit 532a14e, 2026-11-28T09:40:33Z, before the merge; head 18c38b9b445ee2535ea7f176fa614747293f2420, review-file hash f79ca10d4621745a5b2b3c13328b096dc750f17a)
- **Merge evidence:** `gh pr view 198` state MERGED with that merge commit and date; the commit is reachable from the fetched origin/main and its second parent is the final head 18c38b9, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with an Opus sub-agent · **Final verdict:** Approved (round 2)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-4 (second of three PRs) · **Milestone:** M4 (M4r-4b)

## What changed
`accounts.access.scope.scoped(model, signed)` returns the rows of a `ScopedModel` that the signed-in user's kept grants allow: always the user's agency, then all rows for an `agency` grant, otherwise own rows and the rows of users in the grant's org-unit subtree. A cycle, a subtree past 32 levels or a unit RLS cannot see raises `ScopeIntegrityError`. No migration, grant, database object, dependency or live route; no real scoped model exists, only the test-only `scope_probe`. 457 added lines, 25 removed.

## Why
Slice spec v2.5 Decisions 9, 10 and 27, flow 5.2, §7 and §9 row 4: staff see only the records their role and place in the organisation allow.

## Review rounds
- R1: [P2] Missing Signed fields raise a different error from the documented API → `TypeError` for `None`, another object or a missing field, before any read; `access` must be exactly a `frozenset`
- R1: [P2] The authorization runbook omits the new scoped query contract → `docs/runbooks/local-dev.md` entry for `scoped()`
- R2: Approved, no findings

## Deferred conditions
none

## Decisions worth keeping
All are in docs/DECISIONS.md, "2026-11-28 — M4r-4b". Owner, 2026-11-28: the filter limits reads, bulk changes and deletes but not creating or overwriting a record by ID; "Record it, decide later": the first restricted record type's spec must say how writes are checked. Depth counts from the grant's unit; a unit RLS cannot see raises instead of giving no rows; the result is typed `QuerySet[M, M]`. PR CI run 46116830936 on 18c38b9 passed (2119 unit, 254 web, 2053 live database, 60 end-to-end).

## Follow-ups
- Next: M4r-4c (line filter and end-to-end tests; `SCOPE_LINE` must be None until then).
- Carried limits (full list in DECISIONS, M4r-4a and M4r-4b): writes by key; a hand-built `QuerySet` or instance; the team owner set is fixed when `scoped()` runs; `|` with another user's result; raw SQL; the permission code is not seen; a `Signed` or `Grant` built or altered in code is trusted; a `signed` whose attribute raises its own error passes that error on.
- Spec wording at the next update: the `scoped(model, signed)` signature, per-record-type business lines and flow 5.2.
- Not checked: async paths, more than one database, performance on large trees. The reviewer relied on exact-head CI in round 2 and did not rerun tests locally.
- The web test in `App.test.tsx` ("goes to the code step after a right password...") failed once in the builder's local runs on 60a71fa and passed every later run, locally and in CI.
- CI on `main`: image paths still name `ghcr.io/skiw-dev1` (see the PR 193 and 194 logs); their own deploy-path PR is not made. No image can be deployed until it is.
- Post-merge run 46132517279 on c3750f9 (repository public until it finished): checks, security, image and host passed (2119 unit, 254 web, 2053 live database, 60 end-to-end; 855 host tooling, 39 live host stack; secret scan clean); `publish` failed in "Push by digest" with `denied: permission_denied: The requested installation does not exist`, as on a74baf4; deploy-staging skipped.

## Appendix — final review round

## Round 2 — 2026-11-28 · scope: M4r-4b slice

- **Code review** · Merge base `a74baf42dcdb4ae51b098fbb89fce55b1aa8230a` · head `18c38b9b445ee2535ea7f176fa614747293f2420` · GitHub head rechecked at end.
- **Governing specs** · Platform v1.24 (`e47de4ed`), D18, and M4-rest v2.5 (`bb262ec4`), Decisions 9, 10 and 27, Flow 5.2, §7 and §9 row 4. The scope is the owner-approved 4b split recorded in `docs/DECISIONS.md`. The effective diff has 11 files and 482 changed lines. The PR explains keeping the filter, traversal and integrity checks together.

**Verdict:** Approved  
**Model used:** Codex (GPT-6) · **Switch model next step?** No. The review is complete for this slice.

### Findings

No open findings.

- **Resolved R1 · Signed input contract.** `app/accounts/access/scope.py:152`–`:162` converts missing attributes to `TypeError` and requires an exact `frozenset` before checking the transaction. `app/accounts/tests/test_access_scope.py:297`–`:325` exercises each missing attribute, `None`, an unrelated object and a `frozenset` subclass, and separately checks that valid input outside a transaction raises `TransactionManagementError`.
- **Resolved R1 · Authorization runbook.** `docs/runbooks/local-dev.md:54` documents the tenant transaction lifetime, integrity error and log, the focused live test, and the owner-recorded limits on writes by key. The command follows the live-test setup in `Makefile`.

### Self-check audit

| Rule | Evidence |
|---|---|
| UNI-01, UNI-03–05 | Reviewed the typed input checks, test-only typing escapes, the scoped ORM boundary and reuse of the existing transaction helper. Exact-head typecheck and lint passed. |
| UNI-07, UNI-09, UNI-13 | The added-line secret-pattern scan found no matches. The integrity log includes a closed reason and structural IDs. CI passed its security, checks, image and host jobs. |
| UNI-16 | The new local-dev entry matches the transaction order and focused test. |
| TEN-04–11, AUTH-03 | The only new table is a managed-by-fixture probe built with the tenancy template and a composite owner key. The production filter takes the agency and user from the wrapper's signed context, narrows to that agency and consumes the kept grants. Reviewed the cross-binding, no-binding, mixed grant, fresh assignment, cycle, depth and missing-anchor cases. The live database role-check step passed in CI. |
| Other active rules | The diff adds no production route, permission-catalogue change, migration, database role, deployment setting, dependency, cookie, frontend or live record type. |

### Verification performed

| Check | Result |
|---|---|
| Origin fetch, GitHub base and head, merge base, effective diff and end-of-round pin | Confirmed. |
| Source checkout | The sandbox denied registration of a git worktree. Reviewed a detached `git archive` snapshot inside SKIW's review worktree directory. All 476 paths matched the commit tree and the source fingerprint matched before and after review. |
| `git diff --check`, added-line secret-pattern scan and PR text review | Clean. No instructions addressed to the reviewer were found in the changed content. |
| GitHub Actions run 46116830936 | Verified the checks, security, image and host jobs passed for the pinned PR head. The checks job includes lint, typecheck, unit tests, live database role checks and end-to-end tests. The security job includes the full-history secret scan. |

### Residual risks and test gaps

- This round used exact-head CI results for executable checks. Local test and build commands were not rerun because the session did not establish the isolated execution environment required by the security-audit skill. Round 1's local results apply to its recorded SHA.
- The owner-recorded write limit remains with the first restricted record type's spec. The line filter and end-to-end scope integration belong to 4c.

### Required before merge

- No code changes required for this review round.

### Deferred conditions

- None.
