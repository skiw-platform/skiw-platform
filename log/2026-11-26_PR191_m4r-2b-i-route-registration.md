# PR 191 — feat(accounts): M4r-2b-i route registration, route registry and accounts.auth import contract

- **Merged:** 2026-11-26 (09:59:47 UTC) · **Merge commit:** 8edc7208b97430eeb36eb70263c948c47189581c · **Branch:** feat/m4r-2b-route-registration
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-191.receipt, created 2026-11-26 09:51:36 UTC, before the merge; names head 2ac4cc5f7f0dfb332882d2f9edb7fcc2651bfae1 and review hash 806e580b…; log-branch commit holding the review: 0b79d90
- **Merge evidence:** `gh pr view 191` state MERGED, merge commit above, mergedAt 09:59:47Z; reachable from the fetched origin/main. Final head 2ac4cc5f… equals the reviewed head.
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus sub-agent · **Final verdict:** Approved (round 2, GPT-6 (Codex) reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-2b-i (first part of M4r-2b)

## What changed
Every wrapped action registers a permission (catalogue or self-service code) and a keyword-only business line with no default; the route registry pins both for every live route and refuses `staff.manage`; a `protected` import contract lets only `accounts` import `accounts.auth` (334 added, 45 removed lines, 14 files). No migration or grant change; the wrapper's request-time role step is unchanged.

## Why
Slice spec Decisions 6, 7, 11, 26, 29; plan row M4r-2.

## Review rounds
- R1: [P2] New test typing exceptions lack source-level explanations → `added()` takes `Callable[..., HttpResponse]`; each deliberate `type: ignore` has a source comment (2ac4cc5).
- R2: Approved; no open findings.

## Deferred conditions
none

## Decisions worth keeping
- Owner chose to split M4r-2b (599 added lines) into 2b-i and 2b-ii: M4-rest 33 PRs, roles track 23.
- Deviations A (missing `line` → TypeError) and B (contract only; re-exports and import-door rule before the first route outside `accounts`) are in force; see docs/DECISIONS.md "M4r-2" and "M4r-2b-i".
- In test code, every `type: ignore` needs a source comment saying why (reviewer, UNI-01).
- Until 2b-ii merges, no lint rule stops code outside the access package reading or writing the role tables.

## Follow-ups
- M4r-2b-ii next: `semgrep/roles-access-only` (held on a local branch) with the listed cheap gap fixes.
- Next spec update: Decisions 7, 26 and 11 (deviations A, B), limit C, and that routes may register self-service codes.

## Appendix — final review round
## Round 2 — 2026-11-26 · scope: slice

- **Code review:** base and merge base `56d5301dda45ce21153c7fa7995f157ce04e0105` · head `2ac4cc5f7f0dfb332882d2f9edb7fcc2651bfae1` · head re-checked at end: yes.
- **Governing specs:** platform v1.24 and M4-rest v2.5, Decisions 6, 7, 11, 26 and 29, §7 and §9 row 2. M4r-2b-i, with approved deviations A and B.
- **Diff:** 14 files, +334/−45 across two commits. The follow-up changes two unit-test files only.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for archiving. Retain deep review for the remaining role-table boundary.

### Findings

No open findings. Round 1's UNI-01 P2 is resolved.

- `app/tests/test_route_registry.py:139` types the new route fixture helper's view as `Callable[..., HttpResponse]`.
- `app/accounts/tests/test_action_wrapper.py:75`, `:98`, and `:108` document the deliberate type escapes for wrong input types and omitted `line`. The tests still exercise the runtime error outcomes.

### Self-check audit

The typing evidence now appears beside the test code. The round-to-round diff leaves all route declarations, wrapper behavior, the protected import contract and runbooks unchanged. The base-to-head self-check conclusions from Round 1 still hold, with UNI-01 satisfied. The direct role-table lint check remains in the approved M4r-2b-ii split.

### Verification performed

| Command or check | Result |
|---|---|
| `git fetch origin`, `git cat-file -e`, `git merge-base`, `gh pr view 191`, and effective and round-to-round diffs | Verified both exact SHAs and rechecked the open PR. Clean detached checkout removed. |
| `git diff --check` and focused Ruff lint/format | Passed. No prompt-injection text found in the follow-up. |
| Focused wrapper, registry and CSRF test run | **302 passed** in an offline, resource-limited Docker container with dummy settings and read-only source. |
| GitHub Actions run 45794156586 and checks job 139820388712 | All four required jobs passed on this exact head. Includes strict typecheck, the `accounts.auth` import contract, 2,082 unit tests, 2,018 live tests, 60 end-to-end tests and tenancy schema checks. Publish and staging deployment skipped as expected. |

### Residual risks and test gaps

- The review reran the focused unit tests locally and relied on final-head CI for the full live and end-to-end suites.
- This approval covers route registration and the import boundary. M4r-2b-ii adds direct role-table lint enforcement, and M4r-3 applies grant checks at request time.

### Required before merge

- Run the review archive and receipt step for the exact reviewed head.

### Deferred conditions

- None.

