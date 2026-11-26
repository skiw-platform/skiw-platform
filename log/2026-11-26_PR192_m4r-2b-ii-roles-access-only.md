# PR 192 — feat(lint): M4r-2b-ii roles-access-only rule for the role and team tables

- **Merged:** 2026-11-26T12:34:12Z · **Merge commit:** cee2d987f49a9980ecfa40728733dfa8ddb057bb · **Branch:** feat/m4r-2b-ii-roles-access-only
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-192.receipt (commit e75fa7f258f847edec64d75fd69d7ee43afc5769, 2026-11-26T12:23:56Z, before the merge; head e13d2c6ae895ad5918d5852d6d869d70ccfca5bc, review-file hash ab5f421235f57015f9c8f01eff7796526e18fb41)
- **Merge evidence:** `gh pr view 192` state MERGED with that merge commit and date; the commit is reachable from the fetched origin/main and its second parent is the final head e13d2c6, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with an Opus sub-agent; the R1 fix by Claude Sonnet 5.5 alone · **Final verdict:** Approved (round 2)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-2 · **Milestone:** M4 (M4r-2b-ii)

## What changed
The Semgrep rule `roles-access-only` flags use of the five role and team models and of SQL naming their tables outside `accounts/access/`, the accounts migrations and four test folders. It comes with rule fixtures, a test that pins the excluded paths, a runbook line and a DECISIONS entry. No runtime, migration or grant change. 585 added lines, 1 removed.

## Why
Slice spec v2.5 Decisions 3, 7, 29 and AUTH-12: only `accounts.access` reads or writes the role and team tables. It is a source-level check, not a boundary.

## Review rounds
- R1: [P1] Literal Django model access can pass the new check → flags manager `getattr` on a protected model imported under an alias, and `get_model` with only a qualified `app_label` (e13d2c6)
- R1: [P1] Direct literal SQL reads can pass the new check → literals in database calls are SQL in any case; comments or a quote may stand before the table name (e13d2c6)
- R2: no open findings

## Deferred conditions
none

## Decisions worth keeping
The rule matches recognisable ORM and SQL shapes. Its limits and known false positives are in docs/DECISIONS.md, "2026-11-26 — M4r-2b-ii". CI run 45816574328 on e13d2c6 passed (2083 unit, 254 web, 2018 live database, 60 end-to-end).

## Follow-ups
- M4r-2 is complete with this PR. Next is M4r-3 (the wrapper's role step, slice spec Decision 7; deep tier).
- The DECISIONS "Mutants" line gives 18 and 24 for the two earlier mutant sets and 22 for the R1 fix; the reviewer did not rerun them.

## Appendix — final review round

## Round 2 — 2026-11-26 · scope: slice

- **Code review:** base and merge base `8edc7208b97430eeb36eb70263c948c47189581c` · head `e13d2c6ae895ad5918d5852d6d869d70ccfca5bc` · head rechecked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`) and M4-rest v2.5 (`bb262ec4`), Decisions 3, 7 and 29, §9 row 2. Scope is M4r-2b-ii.
- **Diff:** five files, +585/−1. The follow-up changes three files, +125/−11, covering the rule, its fixtures and the decisions entry. The PR body explains keeping these in one PR.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for the archive and receipt.

### Findings

No open findings. Both Round 1 P1s are resolved.

- **Literal Django model access.** `semgrep/roles-access-only.yml:41` and `:42` resolve the protected model in a literal manager lookup through an import alias. Line 122 covers the qualified `app_label` keyword. Both original probe lines flag on this head. The unrelated registry lookup and the aliased unrelated model stay quiet.
- **Literal SQL.** `semgrep/roles-access-only.yml:128`–`:177` recognizes SQL comments before a table name and treats literals passed to database calls as SQL regardless of case. Both original SQL lines flag. Independent line-comment, nested-comment, quoted-name and SQL-expression cases flag as well. The unrelated SQL and prose controls stay quiet.

### Self-check audit

UNI-04 now passes for the recognizable direct-access cases in Round 1. The fixtures support the updated limits documented in the decisions entry. UNI-01 and UNI-05 pass in exact-head CI. UNI-07 is supported by the clean added-line scan and CI's full-history secret scan. UNI-13 and UNI-16 pass with green required CI and the local-dev rule entry. The AUTH-12 findings for this lint slice are closed. The wrapper's per-request role step remains in M4r-3.

### Verification performed

| Check | Result |
|---|---|
| GitHub PR pin, local commit, merge base and end-of-round pin | Matched. Removed the detached checkout after checking it was clean. |
| Three-dot and Round 1-to-Round 2 diffs, `git diff --check` and added-line secret-pattern scan | Clean. No prompt-injection text found in the PR body or follow-up diff. |
| Independent probe with Semgrep 1.179.0 on both versions of the rule | All four original misses flag on the revised rule. Six negative controls stayed quiet on both versions. All other positive controls flagged on the revised rule. |
| Pinned Semgrep fixture suite and tracked application scan | 24/24 rule fixtures passed. Zero findings across 261 app files. |
| Local focused Semgrep path tests | 14 passed with third-party pytest plugins and project conftest disabled. |
| GitHub Actions run 45816574328 | All four required jobs passed on this exact head, including strict typecheck, 2,083 Python unit tests, 254 web unit tests, 2,018 live database tests, 60 end-to-end tests and the tenancy schema check. |

### Residual risks and test gaps

- The rule matches recognizable ORM and SQL syntax. Dynamic forms and remaining pattern limits are documented in the decisions entry.
- The full live and end-to-end suites were verified through exact-head CI. The builder's mutation runs were not independently repeated.

### Required before merge

- Archive this round and record the review receipt for the exact reviewed head.

### Deferred conditions

- None.
