# PR 125 — docs: setup reconcile PROJECT.md with spec v1.22

- **Merged:** 2026-11-06 (16:45:35 UTC) · **Merge commit:** d1b7abb9c641326300c7803e0c1aab69ef22dd42 · **Branch:** docs/setup-reconcile-spec-v1-22 (final head 39b6eded8853a73aaf7a0c4ba12d02112e644b42)
- **Gate breaches:** none. The final review round (Round 2, Approved) names head 39b6ede, which equals the PR's final head; the receipt exists, is for that head and the final review-file hash, and was written 1 min 43 s before the merge.
- **Approval receipt:** `reviews/PR-125.receipt` on agent-logs (commit 8abf4f7), time 2026-11-06T16:43:52Z, review-file hash c8adab43, review commit 77c04db.
- **Merge evidence:** `gh pr view 125` state MERGED, mergedAt 2026-11-06T16:45:35Z, merge commit d1b7abb; `git merge-base --is-ancestor d1b7abb origin/main` true; `origin/main:agents/PROJECT.md` line 29 carries 79a9a40e.
- **Built by:** Sonnet 5.5 builder (reviewed by GPT-5 Codex) · **Final verdict:** Approved (Round 2; Round 1 Blocked)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md, v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 · **Plan:** none · **Milestone:** M3 (auth) prerequisite

## What changed
`setup` Part B reconcile after spec v1.22. `agents/PROJECT.md`: "Spec hash at last reconcile" d95cb271 → 79a9a40e (comment cites v1.22, Round 26, PR 124); module list **auth** → required TOTP for every user (owner/admin included), optional passkeys, recovery codes. Two lines, one file.

## Why
Reconcile rule after an approved spec change (PR 124). Needed before the M3 plan rows are updated and 3b-1 is built.

## Review rounds
- R1: Blocked. [P1] PR body had no builder self-check table → table added to the PR body (no commit change, head unchanged).
- R2: Approved. No findings.

## Deferred conditions
- none

## Decisions worth keeping
- Run `review <n>` and `approved <n>` for reconcile PRs too; receipt written before the merge this time (the PR 89 and PR 124 miss is not repeated).
- A PR body without the self-check table is Blocked even for a two-line docs change. Put the table in the first body.

## Follow-ups
- Builder: update the M3 plan rows (`docs/plans/2026-10-31-m3-auth.md`: AUTH-03, Q9, enrolment, M3i e2e, gap note), record the six-PR M3f-3 sequence, M3h row carries AUTH-07; reviewer reviews it; then `build` 3b-1. Run `approved <n>` before that merge.
- Builder: D20 parenthetical (Round 26 P3) at the next spec touch.
- Open from earlier: Dependabot alerts 1 and 2 not looked at.

## Appendix — final review round
# Review — PR #125

## Round 2 — 2026-11-07 · scope: re-review of Round 1 evidence fix (PR body only)
- **Code review:** base / merge base `969bb2db62327eb10c8bb97045d9f361638ea04c` · head
  `39b6eded8853a73aaf7a0c4ba12d02112e644b42` · host head re-checked at end: yes
- **Change since Round 1:** the GitHub PR body now contains the required structured self-check table;
  the commit, head SHA, one-file/two-line diff, and CI run are unchanged.
- **Source integrity:** Round 1 reviewed an exact 351-file snapshot of this same head and verified every
  fingerprint after checks. This round re-checked the local commit object, merge base, effective diff,
  spec blob hash and hygiene; no new snapshot was needed for a body-only evidence correction.

**Verdict:** Approved

**Model used:** GPT-5 Codex (standard/mechanical documentation re-review).
**Switch model next step?** No — the next gate is the mechanical `approved 125` archive/receipt step.

### Findings

No open P0, P1, P2, or P3 findings.

### Round 1 finding resolution

| Finding | Status | Independent verification |
|---|---|---|
| [P1] Required builder self-check table missing | Resolved | Re-read the GitHub PR body at unchanged head `39b6eded`. It now has a four-column rule/result/evidence/n-a table covering the exact spec hash, every affected spec-derived value, unresolved-field search, auth/D7 mapping, UNI-07/09, diff hygiene, PROJECT §9/§11, decisions, runbooks and the n-a active packs. Compared each row with the Round 1 independent applicability list; no disagreement. |

No prompt-injection text was found in the changed lines, commit message, or revised PR body. The body's
workflow commands are ordinary handoff data and were not treated as instructions to the reviewer.

### Self-check audit

| Rule / gate | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| Setup Part B: exact approved spec hash | yes | pass | pass | spec blob and PROJECT line 29 both `79a9a40ee1a686ae1082e8d11a73b299deb66d38`; Round 26 Approved | none |
| Setup Part B: every affected spec-derived value | yes | pass | pass | only factor-rule values are lines 29 and 150; historical v1.21 citations correctly identify rules introduced then | none |
| Unresolved `{{` fields | yes | pass, 0 hits | pass, 0 hits | PROJECT search at head | none |
| Auth / D7 / Flow 5.1 / T5 | yes | pass | pass | PROJECT line 150 says required TOTP for all, optional passkeys, recovery codes | none |
| UNI-07 / UNI-09 | yes | pass | pass | no secret or PII in added lines; CI security SUCCESS | none |
| PROJECT §9 / §11 | yes | unchanged | unchanged | effective diff touches neither section | none |
| Other active packs and runbooks | n-a | n-a with reasons | reasons valid | no code, schema, UI, money, record, file, job, deployment, env or operator-procedure change | none |

### Verification performed

| Command / check | Result |
|---|---|
| GitHub PR body, start and end of Round 2 | required self-check table present and unchanged during review |
| GitHub PR state/head at end | OPEN, not draft, MERGEABLE; head still `39b6eded8853a73aaf7a0c4ba12d02112e644b42` |
| `git cat-file -e <head>^{commit}` | exact head present |
| merge base | `969bb2db62327eb10c8bb97045d9f361638ea04c` |
| effective diff | one file, `agents/PROJECT.md`; 2 insertions / 2 deletions |
| spec blob hash at head | `79a9a40ee1a686ae1082e8d11a73b299deb66d38`, equal to PROJECT line 29 |
| factor/version/hash reference search | only updated factor line plus valid historical v1.21 citations; no unresolved field |
| `git diff --check` | clean |
| added-line secret scan | 0 hits |
| CI at end | `checks`, `security`, `image`, `host` SUCCESS; publish and deploy-staging correctly SKIPPED |

### Residual risks and test gaps

- No code/database/browser test was run locally because this is a two-line PROJECT metadata
  reconciliation. The complete GitHub CI suite passed on the pinned head.
- The approved v1.22 spec's non-blocking D20 wording P3 remains unchanged and outside this PR.
- The M3 plan still has the superseded passkey rule. Its separately reviewed update must land before
  M3f-3b-1, as the PR body states; it does not block this reconciliation.

### Required before merge

- None.

### Deferred conditions

- None.

### Optional improvements

- None for this PR.

### Next step

The owner runs `approved 125`. Approval applies only to head
`39b6eded8853a73aaf7a0c4ba12d02112e644b42`; it is not a merge instruction.

