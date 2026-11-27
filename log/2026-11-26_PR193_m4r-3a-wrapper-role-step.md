# PR 193 — feat(auth): M4r-3a wrapper role step with step-up grants failing closed

- **Merged:** 2026-11-26T23:56:54Z · **Merge commit:** d18862ff26a7d5ac9e72c700194e7a97a780431c · **Branch:** feat/m4r-3a-wrapper-role-step
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-193.receipt (commit b90ec1d, 2026-11-26T14:03:40Z, before the merge; head 4d235f8d4dd92548ea9ad7a52aa66d21677ed341, review-file hash ee6336e02ed438e2a69fabaa5bddc976bd0f46fc)
- **Merge evidence:** `gh pr view 193` state MERGED with that merge commit and date, merged by the owner; the commit is reachable from the fetched origin/main and its second parent is the final head 4d235f8, which equals the reviewed SHA
- **Drafted by:** Claude Sonnet 5.5 (orchestrator) with Opus sub-agents for the plan, the implementation and the R1 fix draft · **Final verdict:** Approved (round 2)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md v2.5 under platform spec v1.24 · **Plan:** plan row M4r-3 · **Milestone:** M4 (M4r-3a)

## What changed
Step 3 of `authorized_action` now reads the user's grants once per request for a catalogue code, keeps those whose assignment line matches the route's line, and passes them to the handler as `Signed.access`. A refusal is 403 `forbidden` or 403 `stepup-required`; every grant that needs a step-up is dropped until M4r-3b. No migration, grant or live route change. 333 added lines, 18 removed.

## Why
Slice spec v2.5 Decisions 6, 7, 8 and 26, and AUTH-01, AUTH-03 and AUTH-12: the interim "signed in with a second factor" is replaced by a check against the stored ticks.

## Review rounds
- R1: [P2] Unhashable runtime line metadata raises instead of returning 403 → `isinstance` check before the line table lookup, with list and dictionary test cases (3c790f6)
- R1: [P2] The auth runbook omits the new authorization refusals → wrapper section of local-dev updated (4d235f8)
- R2: no open findings

## Deferred conditions
none

## Decisions worth keeping
The owner split M4r-3 into 3a (this PR), 3b (the step-up check, with `stepup.PURPOSES` widened to every catalogue purpose) and 3c (extra tests only). Readings and limits are in docs/DECISIONS.md, "2026-11-26 — M4r-3a". PR CI run 45831318625 on 4d235f8 passed (2084 unit, 254 web, 2034 live database, 60 end-to-end).

## Follow-ups
- M4r-3b next, then M4r-3c.
- Once the wrapper imports `stepup`, it reaches `webauthn`; the first module outside `accounts` that imports `authorized_action` would break an import contract (DECISIONS M4r-3a).
- The reviewer did not rerun the builder's mutation runs.
- CI on `main` (found during `merged 193`): the latest successful run of the last 60 is 2026-11-13. Of the 13 failed runs from 1058766 to cee2d98, 11 failed only in `publish`, each with the GitHub billing message (the job starts after the checks, when the repository is already private again); 53c2bd7 failed in the end-to-end tests; cee2d98 failed in one web unit test (App.test.tsx, code step) and in the clamav image pull of the live host tests. The earlier failures were not opened.
- Post-merge run 45913870474 on d18862f (repository still public): checks, security, image and host passed (2084 unit, 254 web, 2034 live database, 60 end-to-end); `publish` failed in "Push by digest" with `denied: permission_denied: The requested installation does not exist`, pushing to `ghcr.io/skiw-dev1/skiw-platform` as ci.yml names it. DECISIONS 2026-11-14 records those paths as a separate deploy-path PR, not yet made.
- Local only: the dev database was initialised with another superuser name, so 5 role-set live tests fail on it.

## Appendix — final review round

## Round 2 — 2026-11-26 · scope: slice

- **Code review:** base and merge base `cee2d987f49a9980ecfa40728733dfa8ddb057bb` · head `4d235f8d4dd92548ea9ad7a52aa66d21677ed341` · head rechecked at end: yes.
- **Governing specs:** platform v1.24 (`e47de4ed`) and M4-rest v2.5 (`bb262ec4`), Decisions 6–8, 26, 29 and 36, §7 and §9 row 3. Scope is the owner-approved M4r-3a split.
- **Diff:** 12 files, +333/−18. The follow-up changes four files, +12/−8.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for the archive and receipt.

### Findings

No open findings. Both Round 1 P2s are resolved.

- **Invalid runtime line.** `app/accounts/auth/wrapper.py:132` checks the line's type before set lookup. The list and dictionary cases now return `403 forbidden` with `Cache-Control: no-store` and no handler call. `app/accounts/tests/test_wrapper_roles_live.py:212` adds both cases to the live regression test and keeps the valid-line control.
- **Auth runbook.** `docs/runbooks/local-dev.md:53` explains the per-request grant and line checks, the two 403 codes, and the temporary refusal of step-up grants until M4r-3b. Its focused live check uses the same database setup and marker as `make test-live` and selects the wrapper test file.

### Self-check audit

UNI-16 now passes. Decision 26's runtime line finding is resolved. Independent probes confirmed one grant read for the catalogue request, unchanged valid-line controls, and separate `forbidden` and `stepup-required` outcomes. The Round 1 conclusions on session order, tenant binding, next-request grant refresh, and the approved fail-closed step-up behavior hold on this head.

### Verification performed

| Check | Result |
|---|---|
| GitHub PR pin, local commit, merge base, effective and follow-up diffs, end-of-round GitHub pin | Matched. Removed the detached checkout after confirming it was clean. |
| `git diff --check` and added-line secret-pattern scan on the follow-up | Clean. No prompt-injection text found in the follow-up or updated PR body. |
| Wrapper, route-registry and CSRF tests | 303 passed in a resource-limited, offline container with read-only source and dummy settings. |
| Independent wrapper probe | Eight cases passed with stubbed session and grant reads. Invalid metadata and wrong-line grants returned `forbidden`, the two valid-line controls reached the handler, and a matching step-up grant returned `stepup-required`. |
| GitHub Actions run 45831318625 | All four required jobs passed on this exact head. Verified 2,084 Python unit tests, 254 web unit tests, 2,034 live database tests, all 16 cases in the wrapper role test file, 60 end-to-end tests, the tenancy schema check and a clean full-history secret scan. |

### Residual risks and test gaps

- The full live and end-to-end suites were verified in exact-head CI. Mutation runs were not independently repeated.
- Catalogue re-verification and rename-invariance coverage follow in 3b and 3c under the approved split.

### Required before merge

- Archive this round and record the review receipt for the exact reviewed head.

### Deferred conditions

- None.
