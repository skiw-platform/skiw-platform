# PR 190 — feat(lint): M4r-2a-ii rule against authorization by role name

- **Merged:** 2026-11-26 (05:44:43 UTC) · **Merge commit:** 56d5301dda45ce21153c7fa7995f157ce04e0105 · **Branch:** feat/m4r-2a-ii-role-name-rule
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-190.receipt, created 2026-11-26 05:44:26 UTC, 17 seconds before the merge; names head 133179a1865bc5ff4ee57c9919bbd768f3f00b64 and review hash 03722d84…; log-branch commit holding the review: 59f2dde
- **Merge evidence:** `gh pr view 190` state MERGED, merge commit above, mergedAt 05:44:43Z; reachable from the fetched origin/main. Final head 133179a1… equals the reviewed head.
- **Drafted by:** Claude Sonnet 5.5 (builder); rule by Opus sub-agents · **Final verdict:** Approved (round 2, GPT-6 (Codex) reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-2a-ii (second part of M4r-2a)

## What changed
`semgrep/no-role-name-branching.yml` with two rules (a pattern rule and a flow-sensitive taint rule) that stop app code outside Decision 36's list from branching on a role's name or system flag, their fixture, a path-pin test and a DECISIONS entry (328 added lines). Lint only: no application, schema, grant or route change.

## Why
Slice spec Decision 36 and the §6 threat table; plan row M4r-2.

## Review rounds
- R1: [P1] Recognizable role-name reads and filters escape the lint rule → flow rule (a read before reassignment is flagged, after a non-role reassignment allowed); name lookups inside a Role queryset call (`Q`, `~Q`, `When`) and `F("name")` flagged.
- R1: [P2] The reflective name check also rejects ordinary non-role names → `getattr(…, "name")` flagged only on recognisable role receivers.
- R2: Approved; one non-blocking P3 (below).

## Deferred conditions
none

## Decisions worth keeping
- Limit C (owner-approved): the rule catches recognisable shapes only; the gaps and known false positives are listed in docs/DECISIONS.md "M4r-2a-ii". The M4r-3 rename-invariance test is the behavioural backstop.
- The flow rule treats function calls as safe, so another model fetched by a role's id stays allowed; the cost is that `qs.first().name` on a stored role queryset is not caught.
- The builder's own probe before opening the PR, and the reviewer after it, each found ordinary shapes the fixtures did not cover: for a lint rule, probe with code written apart from the fixture.
- CI run 45756554543 attempt 1 failed on `test_auth_totp::test_another_secret_is_refused` (random secrets; unrelated to this diff); attempt 2 passed.

## Follow-ups
- P3 (R2): narrow the nested-queryset name matcher (an `OrgUnit` filter nested inside a `Role` queryset call is flagged) at the next rule edit, keeping the direct `Q`, `When` and `F` fixtures.
- Test chore: give `test_another_secret_is_refused` fixed secrets so it cannot collide by chance.
- M4r-2b next (route registration, import contract, `roles-access-only`).
- Next spec update: Decisions 7, 26 and 11 (deviations A, B) and limit C.

## Appendix — final review round
## Round 2 — 2026-11-26 · scope: slice

- **Code review:** base and merge base `d4601da1ce247b2937ecff8674340e09b2c60726` · head `133179a1865bc5ff4ee57c9919bbd768f3f00b64` · head re-checked at end: yes.
- **Governing specs:** platform v1.24 and M4-rest v2.5, Decision 36, §7 and §9 row 2, and the approved recognizable-pattern limit C. M4r-2a-ii is the role-name lint slice.
- **Diff:** three commits, four files, 328 added lines.

**Verdict:** Approved  
**Model used:** GPT-6 (Codex) · **Switch model next step?** No for archiving. Use deep review for the next route-registration and import-boundary slice.

### Findings

No blocking findings. Both round 1 findings are resolved.

#### [P3] A known nested queryset case still flags a non-role name

- **Category:** defect.
- **Rule:** Decision 36, role-name lint scope.
- **Evidence:** The `pattern-inside` rule at `semgrep/no-role-name-branching.yml:78` covers descendant calls inside a `Role` queryset. A separate `OrgUnit.objects.filter(name=...)` nested as an argument was flagged in the independent probe. DECISIONS records this false positive.
- **Failure scenario:** A future query uses a named org unit to constrain a role queryset, and the lint flags the org-unit filter.
- **Impact:** Isolated to this nested expression shape. The application scan is clean and the direct non-role reads from round 1 are accepted.
- **Required correction:** At the next related rule edit, scope the nested name lookup matcher to expressions that use the role's own fields, and preserve the direct `Q`, `When` and `F` fixtures.
- **Owner:** builder.
- **Verification:** A nested org-unit filter is accepted while a role-name predicate in the outer query is flagged.
- **Status:** open, non-blocking.

### Resolved findings

| Round 1 finding | Verified change |
|---|---|
| P1, recognizable role-name reads and filters missed | The flow rule at `semgrep/no-role-name-branching.yml:103` flags the earlier read and permits a read after an unconditional non-role reassignment. The official fixture also checks a one-branch reassignment. The Role queryset rule flags the direct `Q(name=…)` probe and the supplied negated, compound, `When` and `F` cases. |
| P2, ordinary non-role `getattr` flagged | The direct rule now constrains reflective name reads to role-named receivers or explicit Role queries. The flow rule handles a query result stored in a plain variable. Independent probes confirmed the non-role read is accepted and the role result is flagged. |

### Self-check audit

| Rule or requirement | Result |
|---|---|
| UNI-01, UNI-05 | CI typecheck and lint passed. The full pinned rule suite and the focused path tests passed locally. |
| UNI-04, AUTH-03 and Decision 36 | The two lint rules enforce the reviewed recognizable cases. Both use the same Decision 36 exclusions, pinned separately by rule ID. The DECISIONS entry describes the retained limits. The M4r-3 rename-invariance check remains part of that slice. |
| UNI-07 and UNI-13 | The exact-head CI run passed on attempt 2, including the required security job. |
| Other applicability | The follow-up is lint, fixtures and decisions text. There is no application or database change. |

### Verification performed

| Command or check | Result |
|---|---|
| `git fetch origin`, `git cat-file -e`, `git merge-base`, `gh pr view 190`, effective and round-to-round diffs | Pinned the exact open PR and rechecked both SHAs. `git diff --check` passed. Detached checkout clean and removed. No prompt-injection text found. |
| Offline Semgrep 1.179.0 fixtures and application scan | **23/23** rule tests passed and the application scan was clean. |
| Focused role-name and tenancy path tests | **14 passed**. |
| Independent static probes | Confirmed the round 1 cases, the controls before and after reassignment, and the documented nested false positive. |
| GitHub Actions run 45756554543 | All four required jobs passed on attempt 2 at the recorded head. Logs show 1,962 unit tests and 2,018 live tests, plus successful schema and end-to-end checks. Attempt 1 failed in the pre-existing randomized TOTP test `test_another_secret_is_refused`, which passed on rerun. |

### Residual risks and test gaps

- The approved static-analysis limits still apply to dynamic receivers, aliases and names. The nested non-role false positive is recorded above.
- The first CI attempt's TOTP failure is outside this lint-only diff. Runtime checks were verified through CI. Builder mutant outcomes were reviewed as reported.

### Required before merge

- Run the approval archive and receipt step for the exact reviewed head.

### Deferred conditions

- None.

### Optional improvements

- Narrow the nested queryset matcher when revisiting the rule.

