# PR 197 — feat(auth): M4r-4a scope boundary (ScopedModel, scoped-only rule, coverage check)

- **Merged:** 2026-11-28T03:10:26Z · **Merge commit:** a74baf42dcdb4ae51b098fbb89fce55b1aa8230a · **Branch:** feat/m4r-4a-scope-boundary
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-197.receipt (commit 3e55afb, 2026-11-28T03:08:09Z, before the merge; head 872b17fafbdd06c014feeda6ed0b20a915c949c3, review-file hash 8c41c91bc81f0ba673f7ad3284d77788ae98aaca)
- **Merge evidence:** `gh pr view 197` state MERGED with that merge commit and date; the commit is reachable from the fetched origin/main and its second parent is the final head 872b17f, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with an Opus sub-agent · **Final verdict:** Approved (round 5)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-4 (first of three PRs) · **Milestone:** M4 (M4r-4a)

## What changed
New module `accounts.access.scope`: the abstract `ScopedModel` (only manager `_unscoped`, whose reads all raise), system checks `scope.E001` to `E005`, the Semgrep rule `scoped-only`, and a coverage check that every concrete scoped model has a scope case. Nothing is filtered yet; `scoped()` lands in M4r-4b. No migration, grant, database object or dependency; no concrete scoped model exists. 692 added lines, 6 removed (the owner allowed up to 700).

## Why
Slice spec v2.5 Decisions 9, 10, 11, 13 and 27, §7 and §9 row 4: a record filtered by owner must not be reachable except through the scope module.

## Review rounds
- R1: [P1] Hidden reverse accessors still leave ORM joins to scoped rows → every join to a scoped model refused (`scope.E003`, `E004`)
- R1: [P1] Django's lookup shortcuts select the unfiltered manager → the manager refuses at run time
- R2: [P1] A standard Django model formset still reads through the unfiltered default manager → `get_queryset()` raises, so every read through the manager does (owner: block Django forms)
- R3: [P1] Typed direct QuerySet construction passes the scope lint → `scoped-only` flags the typed, aliased and `getattr` forms
- R3: [P2] The owner-approved form block still allows scoped records to render → owner accepted display of an already fetched record; `scope.E005` added so a bound form cannot save
- R4: [P2] The startup check accepts unrelated uniqueness rules → `scope.E005` requires the unconditional `unique (agency_id, id)`
- R5: Approved, no findings

## Deferred conditions
none

## Decisions worth keeping
All are in docs/DECISIONS.md, "2026-11-27 — M4r-4a", with the questions asked. Owner, 2026-11-27: M4r-4 is three PRs; business lines are per record type; the filter will be `scoped(model, signed)` (differs from Decision 9's signature; spec wording at the next update); the filter cannot see which permission the route checked (recorded limit); Django model forms and formsets may not read or save scoped records but may display an already fetched one; add `scope.E005`; the PR may grow to 700 lines. One scoped record refers to another by a `UUIDField`, never a relation. PR CI run 46090438313 on 872b17f passed (2118 unit, 254 web, 2047 live database, 60 end-to-end).

## Follow-ups
- Next: M4r-4b (own, team and agency filter), then M4r-4c (line filter and end-to-end tests).
- Open limits, carried to 4b's review and the first real scoped model (full list in DECISIONS): `refresh_from_db()` on a hand-built instance; the `QuerySet` class kept or passed as a value; names built at run time; method overrides of `validate_constraints`, `get_constraints`, `full_clean` or a form's `_post_clean`; raw SQL, `extra(tables=...)` and database views.
- Forms were checked by probes on sqlite, not on PostgreSQL or in a browser; the reviewer did not repeat the mutation runs.
- CI on `main`: image paths still name `ghcr.io/skiw-dev1` (see the PR 193 and 194 logs); their own deploy-path PR is not made. No image can be deployed until it is.
- Post-merge run 46101568636 on a74baf4 (repository public until it finished): checks, security, image and host passed (2118 unit, 2047 live database, 60 end-to-end; 855 host tooling, 39 live host stack; secret scan clean); `publish` failed in "Push by digest" with `denied: permission_denied: The requested installation does not exist`, as on ab17074; deploy-staging skipped.

## Appendix — final review round

## Round 5 — 2026-11-28 · scope: slice

- **Code review:** base and merge base `ab170745307abdb454367094f9f3a3caab21a8ec` · head `872b17fafbdd06c014feeda6ed0b20a915c949c3` · head rechecked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`) D18, M4-rest v2.5 (`bb262ec4`), Decisions 9–11, §7 and §9 row 4, and the owner-approved form display policy and model metadata safeguard. Scope is M4r-4a.
- **Diff:** ten files, +692/−6, 698 changed lines within the approved 700-line limit. The follow-up changes three files, +29/−16.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for archiving and recording the receipt.

### Findings

No open findings. Round 4's P2 is resolved.

- `app/accounts/access/scope.py:84`–`:93` requires a field-based, unconditional, non-deferrable `UniqueConstraint` on exactly `agency_id` and `id`, with Django's stock validator. The focused tests accept the inherited constraint and either field order, and reject unrelated, wider, conditional, expression, deferrable and overridden-validator constraints.
- The independent probe confirmed the inherited declaration passes. A different model uniqueness rule plus a matching database-only index still produces `scope.E005`. Both tested forms rendered already-fetched rows and refused save attempts. The synthetic record stayed unchanged.

### Self-check audit

The revised `scope.E005` enforces the owner-approved metadata invariant. The earlier relation, shortcut, formset and typed-query changes remain in place. The decisions entry matches the tightened rule and the approved display-only policy. Exact-head CI passed lint, types, secrets and the existing TEN-08 registry checks. This review covers the boundary and its tests. The filter implementation follows in M4r-4b and M4r-4c.

### Verification performed

| Check | Result |
|---|---|
| GitHub pin, merge base, effective and follow-up diffs, end-of-round pin | Matched. Removed the detached checkout after confirming it was clean. |
| `git diff --check` and follow-up added-line secret-pattern scan | Clean. |
| Focused scope model, coverage and lint-path tests | 48 passed in an offline, resource-limited container with read-only code and dummy settings. |
| Independent model and form probes | Used dummy rows in an isolated in-memory SQLite database. Confirmed the database-only key refusal and the accepted form display and save behavior. |
| GitHub Actions run 46090438313 | All four required jobs passed on the exact head. Includes 25/25 Semgrep rule fixtures, 2,118 Python unit tests, 254 web unit tests, 2,047 live database tests, the tenancy schema check, 60 end-to-end tests and a clean full-history secret scan. |

### Residual risks and test gaps

- The independent form probe used SQLite. PostgreSQL and browser suites were verified through CI. Builder and sub-agent mutation runs were not independently repeated.

### Required before merge

- Archive this round and record the review receipt for the exact reviewed head.

### Deferred conditions

- None.
