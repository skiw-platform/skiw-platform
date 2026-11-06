# PR 124 — docs(spec): v1.22 TOTP required for all, passkey optional (ASK-1)

- **Merged:** 2026-11-06 (16:14:55 UTC, by charliekhc) · **Merge commit:** 969bb2db62327eb10c8bb97045d9f361638ea04c · **Branch:** docs/spec-totp-required (final head 7d051aa6fcf51d57542be7b3717bb8310e802b6a)
- **Gate breaches:** **GATE BREACH: final review was not confirmed before merge.** No `reviews/PR-124.receipt` and no `reviews/PR-124.md` exist: the builder did not run `approved 124` before the owner merged. This repeats the PR 89 process error, which that log told the builder to avoid ("next spec PR, run `approved <n>`"). The spec itself WAS reviewed: spec review Round 26, Approved, at hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 and commit 7d051aa, archived on agent-logs (`reviews/SPEC-2026-10-05-skiw-platform-stack-design.md`, commit d001521, blob hash 8403c024, equal to the local file). The reviewer's approval named the exact hash and commit. The PR head at merge equals the reviewed commit, and `git hash-object` of the spec on origin/main is 79a9a40e, equal to the approved hash. So the content was reviewed; only the pre-merge receipt step was skipped. No receipt is written after the fact. The merge was proven from the host (below), not inferred.
- **Approval receipt:** missing (see breach).
- **Merge evidence:** `gh pr view 124` state MERGED, mergedAt 2026-11-06T16:14:55Z, merge commit 969bb2d; `git merge-base --is-ancestor 969bb2d origin/main` true (origin/main tip is 969bb2d); `origin/main:docs/specs/2026-10-05-skiw-platform-stack-design.md` hash 79a9a40e.
- **Built by:** Sonnet 5.5 builder · **Final verdict:** Approved (spec review Round 26, GPT-5 Codex, no P0/P1/P2; one open P3)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md, now v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 (v1.21 was d95cb271) · **Plan:** docs/plans/2026-10-31-m3-auth.md (rows still to be updated) · **Milestone:** M3 (auth), unblocks M3f-3b-1

## What changed
Spec v1.21 → v1.22, text only (15 lines): version and changelog; D7 (heading, Why, Alternatives, step-up and OIDC wording); Flow 5.1 (2) and (4); T5 (accepted residual); the M3 row; the §9 cutover enrolment sentence. TOTP is required for every user, owner and admin included; a passkey is optional for everyone. No data-model change, no new open question.

## Why
The owner's answer "1a" to ASK-1 on 2026-11-06 (`.agent/reviews/owner-decisions-m3f-3.md`). The owner accepted that TOTP can be phished in real time, against the reviewer's recommendation to keep passkeys required for owner/admin.

## Review rounds
- Spec review Round 26: Approved first time. [P3] D20's cutover rationale still says "(passkeys, bridge pairing)" → not fixed on purpose (would change the approved hash); fix at the next spec touch.

## Deferred conditions
- none from the review. Owed before M3f-3b-1: `setup` must reconcile PROJECT.md §2 to v1.22 / 79a9a40e, then the M3 plan rows (AUTH-03, Q9, enrolment ~line 114, M3i e2e ~line 131, gap note ~line 195) are updated and reviewed.

## Decisions worth keeping
- Derived from the owner's decision, not stated by them, and accepted by the reviewer: step-up re-verifies whichever factor the user has (TOTP, or an enrolled passkey), and Google OIDC still needs that second factor.
- Passkey wording deliberately left as is: `user_factor` kinds, pre-tenant passkey discovery (§4.1), B.14.
- Spec PRs need `approved <n>` before merge, exactly like code PRs. Missed twice now (PR 89, PR 124).

## Follow-ups
- Owner: `setup` (reconcile PROJECT.md to v1.22, hash 79a9a40e).
- Builder: update the M3 plan rows and record the six-PR M3f-3 sequence; M3h row must carry AUTH-07; then reviewer reviews the plan change; then `build` 3b-1.
- Builder: fix D20 parenthetical (P3) at the next spec touch.
- Builder: before the next spec or plan PR is merged, run `approved <n>`.
- Open from earlier: Dependabot alerts 1 and 2 not looked at.

## Appendix — final review round
# Review — 2026-10-05-skiw-platform-stack-design

## Round 26 — 2026-11-07 · scope: spec-change slice (v1.22: ASK-1 TOTP required, passkeys optional)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · v1.22 · hash
  `79a9a40ee1a686ae1082e8d11a73b299deb66d38`, reviewed at commit
  `7d051aa6fcf51d57542be7b3717bb8310e802b6a` in the existing read-only review target
  `.agent/worktrees/spec-totp-required` (branch `docs/spec-totp-required`; commit and
  `origin/docs/spec-totp-required` re-checked equal at the end).
- **Previous approved version:** v1.21, hash `d95cb2717bd1cfabf62d3dbe6cd4af2f1e4c73fd`
  (Round 25; parent commit `6573126` carries that exact blob).
- **Source of the change:** Ying's direct 2026-11-06 answer `"1a"`, recorded by the reviewer in
  `.agent/reviews/owner-decisions-m3f-3.md`: required TOTP for every user, passkeys optional for every
  user, including owner/privileged users; the owner accepts real-time phishing risk and declined the
  reviewer's recommendation to keep passkeys mandatory for owner/privileged users.
- **Delta:** 15 lines in the spec (8 insertions, 7 deletions): version/changelog, D7, Flow 5.1(4), T5,
  M3 done-when, and the cutover enrolment sentence. No data-model, permission-matrix, external-service,
  legal/privacy, money, tenancy, deployment, or locked-switch change.
- **Mode:** read only. No source, spec, decision, plan, handoff, branch, or worktree file was changed;
  only this review round was written.

**Verdict:** Approved

**Model used:** GPT-5 Codex (deep review task; not one of the model names mapped in `PROJECT.md` §6).
**Switch model next step?** No for the mechanical `setup` reconcile; use the project-mapped deep tier for
any further auth-design change or re-review.

### Findings

No P0, P1, or P2 findings.

### [P3] D20's cutover rationale still names passkey enrolment as the universal work
- **Category:** consistency / documentation polish
- **Rule:** spec D20 versus D7, Flow 5.1, and §9 cutover step
- **Evidence:** `docs/specs/2026-10-05-skiw-platform-stack-design.md:105` says five staff make
  per-person re-enrolment “(passkeys, bridge pairing) cheap”, while D7 (`:92`), Flow 5.1 (`:507`) and
  the cutover step (`:1235`) now require TOTP and make passkeys optional.
- **Failure scenario:** a reader scanning the D20 rationale expects every staff member to enrol a
  passkey during cutover even though the normative rules no longer require it.
- **Why it matters:** the stale parenthetical slightly obscures the owner-approved enrolment path, but
  does not change a requirement, gate, data model, or implementation test.
- **Required correction:** at the next spec touch, say “TOTP, optional passkeys and bridge pairing” (or
  remove the parenthetical). Do not change this approved hash solely for this P3.
- **Owner:** builder
- **Verification:** re-read D20 against D7 and the cutover step on the next spec revision.
- **Status:** open (non-blocking)

### Self-check audit

The builder self-check table is not applicable to this text-only spec amendment. Applicability was
established before reading the amendment's own claims:

| Rule / requirement | Applies? | Reviewer result | Evidence |
|---|---|---|---|
| AUTH-03 | Yes, only to ensure the factor decision does not alter the §6 permission matrix | Pass; no permission changes, and every user is subject to required TOTP | D7 `:92`; §6 `:541-565`; M3 `:1201` |
| AUTH-04–08 | No behavioral delta | Unchanged from approved v1.21 | parent-to-head diff |
| AUTH-09 | Yes; the amendment says which enrolled factors may satisfy step-up | Pass; D7 retains the ≤5-minute purposes and the changelog limits step-up re-verification to TOTP or an enrolled passkey | changelog `:5`; D7 `:92` |
| UNI-02/03 | No new values or input boundary | n-a | 15-line diff |
| UNI-07/08/09 | Yes for secret/value leakage in the text | Pass; only factor names and policy text were added, with no credential or secret value | diff + secret-pattern scan |
| UNI-13 / milestone testability | Yes | Pass; M3 now requires first-login TOTP enrolment, TOTP login, and optional-passkey login coverage | M3 `:1201` |
| Project scope / locked switches | Yes | Pass; no scope, service, external mutation, data flow, or switch changed | `PROJECT.md` §9/§11; diff |
| T5 material security risk | Yes | Explicitly recorded, bounded, and accepted by Ying; no active guardrail requires phishing-resistant MFA | T5 `:575`; owner decision record |

### Verification performed

| Command / check | Result |
|---|---|
| `git hash-object <active-worktree spec>` | `79a9a40ee1a686ae1082e8d11a73b299deb66d38` |
| `git rev-parse HEAD origin/docs/spec-totp-required` in the active worktree | both `7d051aa6fcf51d57542be7b3717bb8310e802b6a` |
| Parent spec blob hash | `d95cb2717bd1cfabf62d3dbe6cd4af2f1e4c73fd` (approved v1.21) |
| `git diff --stat HEAD^..HEAD` | spec only; 15 lines, 8 insertions / 7 deletions |
| Consistency: changelog ↔ D7 ↔ Flow 5.1 ↔ T5 ↔ M3 ↔ cutover | normative text agrees; D20 has the P3 stale rationale only |
| Owner-decision provenance | exact `"1a"` and its meaning match `.agent/reviews/owner-decisions-m3f-3.md` |
| `git diff --check HEAD^..HEAD` | clean |
| Injection-pattern scan of the v1.22 spec | no instruction addressed to an agent/reviewer and no skip/approve directive |
| Secret-value pattern scan of the changed text | no credential or secret value |
| End-of-round active-worktree status | no tracked or staged change |
| End-of-round spec hash / target commit | unchanged; hash `79a9a40…`, target `7d051aa…` |

### Residual risks and test gaps

- TOTP remains phishable in real time. The owner accepted that owner/privileged accounts may rely on
  TOTP without a passkey; T5 records the risk and the rejected phishing-resistant alternative.
- This round approves design text, not implementation. The M3 plan still contains the superseded
  owner/admin-passkey requirement; as the changelog says, update its AUTH-03/Q9/enrolment/M3i rows in a
  separately reviewed plan change before M3f-3b-1 is reviewed.
- The main checkout still contains v1.21. Approval applies only to the v1.22 blob/hash and commit above.

### Required before merge

- None for the spec text.

### Deferred conditions

- None.

### Optional improvements

- Correct the D20 parenthetical at the next spec touch (P3).

### Next step

Merge/land the approved blob byte-identical, then run `setup` to reconcile `PROJECT.md` to v1.22 hash
`79a9a40…`. Update and review the M3 plan rows named above before building M3f-3b-1.

