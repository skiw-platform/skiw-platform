# PR 199 — feat(auth): M4r-4c scoped() filters records by business line

- **Merged:** 2026-11-28T12:36:22Z · **Merge commit:** 6ea937ce0804253b7e9e5563eb5fa9e9ac4b0544 · **Branch:** feat/m4r-4c-line-filter
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-199.receipt (commit 95ab057, 2026-11-28T12:35:23Z, before the merge; head a9697678f62907a1cf899b3a02226d454bc1098d, review-file hash 28787f6257d932ca7fb88fcdf05d21ef2ad3769a)
- **Merge evidence:** `gh pr view 199` state MERGED with that merge commit and date; the commit is reachable from the fetched origin/main and its second parent is the final head a969767, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with an Opus sub-agent · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-4 (third of three PRs) · **Milestone:** M4 (M4r-4c)

## What changed
`ScopedModel.SCOPE_LINE` accepts `insurance`, `investment` or None, and `scoped()` keeps only the grants whose line matches the model's, for every scope. `LINE_MATCHES` moved from the wrapper to `accounts.access.catalogue`. Test-only: two lined probe tables and `scope/<line>` routes behind the real wrapper. No migration, production database object, grant, dependency or live route. 351 added lines, 55 removed. This completes M4r-4.

## Why
Slice spec v2.5 Decisions 9, 26 and 36, flow 5.2, §7 and §9 row 4: staff on one business line must not see the other line's records.

## Review rounds
- R1: Approved, no findings

## Deferred conditions
none

## Decisions worth keeping
All are in docs/DECISIONS.md, "2026-11-28 — M4r-4c". Lines are per record type (owner, 2026-11-27): one probe table per line, no line column, so the spec's `line_tag` and "both row lines" wording is superseded until the next spec revision. A `both` grant sees every model line whatever the route's line (Decision 9 as written); which model a route reads is the handler's choice, reviewed per route. PR CI run 46138313974 on a969767 passed (2123 unit, 254 web, 2062 live database, 60 end-to-end). Post-merge main run 46145495995 on 6ea937c: checks, security, image and host passed (same counts; full-history secret scan clean); `publish` failed as on earlier merges (permission_denied pushing to the old image registry path).

## Follow-ups
- Next: M4r-5a.
- Carried limits (DECISIONS M4r-4a to 4c): writes by key (the first restricted record type's spec must say how writes are checked); the permission code is not seen, and the same spec binds models to codes and routes; a hand-built `QuerySet`, instance, `Signed` or `Grant`; a kept `QuerySet`; raw SQL; `SCOPE_LINE` reassigned to another valid line after declaration.
- Spec wording at the next update: the `scoped(model, signed)` signature, per-record-type lines, `line_tag`, §9 row 4 and flow 5.2.
- Before the first route outside `accounts`: re-export `scoped` and `ScopedModel`, and the import-contract changes (DECISIONS M4r-3a, 3b).
- Not checked: async paths, more than one database, performance on large trees. The reviewer ran the focused suites and relied on exact-head CI for the rest.

## Appendix — final review round

## Round 1 — 2026-11-28 · scope: slice (M4r-4c)

- **Code review** · Merge base `c3750f91974ac4a0aff805eea386d776a763df54` · head `a9697678f62907a1cf899b3a02226d454bc1098d` · GitHub head rechecked at end.
- **Governing specs** · Platform v1.24 (`e47de4ed`) D18, and M4-rest v2.5 (`bb262ec4`) Decisions 9, 10, 26, 27 and 36, Flow 5.2, §7 and §9 row 4. The owner-recorded M4r-4 split uses a line per record type. The diff adds 351 lines and removes 55 across 14 files.

**Verdict:** Approved  
**Model used:** Codex (GPT-6) · **Switch model next step?** No. This slice has source review, exact-head CI and independent focused checks.

### Findings

No open findings.

### Self-check audit

| Rule | Applicability and verification |
|---|---|
| UNI-01, UNI-03–05 | Typecheck and lint passed in CI. `ScopedModel` checks the allowed values at declaration (`app/accounts/access/scope.py:95`), and `scoped()` checks model and grant values before choosing a scope (`:172`). The shared seven-pair table has one definition (`app/accounts/access/catalogue.py:64`). The fixed-table SQL exception in `app/accounts/tests/scope_probe.py` follows its allowlist check. The import contracts and `scoped-only` gate passed in CI. |
| UNI-07, UNI-13 | The added-line secret-pattern scan yielded no matches. The CI security, checks, image and host jobs passed. The existing integrity log still reports the closed reason and structural IDs. |
| UNI-16 | `docs/runbooks/local-dev.md:54` specifies the line and scope order, transaction lifetime, integrity refusals and the focused live suites. Both test files passed on the disposable reviewer database. |
| TEN-04–11 | The changes add only fixture-owned probes with FORCE RLS through the tenancy template and a composite owner reference. Row selection still includes the signed agency and runs inside the request binding. The harness covers another agency, lost binding, invalid line and mixed grants. The full live role and schema checks passed in CI. |
| AUTH-03, AUTH-12 | The route checks the assignment line before handing kept grants to the handler (`app/accounts/auth/wrapper.py:123`). The model then filters each grant independently before the agency, own and team branches. The live route cases cover all three model lines, stable authorization under role renames, and the next-request effects of a tick, unit move, reassignment and unassignment (`app/accounts/tests/test_scope_routes_live.py:65`). |
| Other active rules | The diff adds no production route, schema migration, database role, permission-catalogue entry, credentials, dependencies, deployment changes, frontend, or live record type. |

### Verification performed

| Check | Result |
|---|---|
| Origin fetch, GitHub base and head, three-dot diff, and pinned worktree | Confirmed. Final GitHub head matched and the detached worktree was clean before removal. |
| `git diff --check`, added-line secret-pattern scan, and PR text review | Clean. No instructions addressed to the reviewer found in changed content. |
| Focused unit tests | 131 passed across `test_access_scope.py`, `test_scope_coverage.py` and `test_action_wrapper.py`. Existing local container and toolchain, read-only source, no network, dummy settings and bounded scratch. |
| Focused live tests | 15 passed across `test_access_scope_live.py` and `test_scope_routes_live.py`. PostgreSQL 17.11 with the repository's role setup, migrations as `skiw_migrator` and tests as `skiw_app`. Private Docker loopback, disposable scratch storage and dummy credentials. The database container was removed. |
| GitHub Actions run 46138313974 | Confirmed the four required jobs passed for this head, including lint, typecheck, unit, live database, end-to-end, security and image checks. |

### Residual risks and test gaps

- The owner-recorded per-record-type line decision supersedes the slice spec's test schema wording. A grant on `both` passes any model-line check after the wrapper authorizes the route. The first real handlers still own the choice of model for each permission and route.
- The write-by-key limit remains with the first restricted record type's design. Local execution was limited to the focused suites. The full suites were verified in CI, and builder mutation tests were not repeated.

### Required before merge

- No code changes required for this round.

### Deferred conditions

- None.
