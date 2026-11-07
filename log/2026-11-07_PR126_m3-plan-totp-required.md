# PR 126 — docs(plan): M3 plan follows spec v1.22 (TOTP required, passkey optional), six-PR M3f-3, D8 to M3h

- **Merged:** 2026-11-07 (12:13:04 UTC) · **Merge commit:** 1494306158e622262a55f16c1bb3daaeb630e967 · **Branch:** docs/plan-m3-totp-required (final head a7e0d8ba54889d18f602b8b0a5786dce0a60a795)
- **Gate breaches:** none. The final review round (Round 3, Approved) names head a7e0d8b, which equals the PR's final head; the receipt exists for that head and the final review-file hash, written 21 min 21 s before the merge.
- **Approval receipt:** `reviews/PR-126.receipt` on agent-logs, time 2026-11-07T11:51:43Z, review-file hash d36f4561.
- **Merge evidence:** `gh pr view 126` state MERGED, mergedAt 2026-11-07T12:13:04Z, merge commit 1494306; `git merge-base --is-ancestor 1494306 origin/main` true (origin/main tip is 1494306).
- **Built by:** Sonnet 5.5 builder (reviewed by GPT-5 Codex) · **Final verdict:** Approved (Round 3; Rounds 1 and 2 Revision required)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22 (hash 79a9a40e) · **Plan:** docs/plans/2026-10-31-m3-auth.md (amended 2026-11-07) · **Milestone:** M3 (auth), unblocks M3f-3b-1

## What changed
Plan and decisions log only. The M3 plan follows spec v1.22 and the owner's answers of 2026-11-06 ("1a 2ok 3yes 4yes"): TOTP required for every user, passkey optional for everyone; AUTH-03 row loses its passkey half (AUTH-03 itself stays deferred to M4-rest, Q9 (a)); M3f-3 recorded as six PRs (S, 3a, 3b-1, 3b-2, 3c-1, 3c-2, about 1 600 lines); fixed TOTP label `SKIW Assistant:<email>`; factor add/remove/regenerate on an active session moved to M3h behind step-up with an AUTH-07 test; M3f/M3h/M3i rows, tests, §5 auth row, Q9, §9 item 11 and the Done-when gap note updated. One `DECISIONS.md` entry "2026-11-07 — M3 plan".

## Why
The reviewer's spec Round 26 and `.agent/reviews/owner-decisions-m3f-3.md` required the plan rows to be updated and reviewed before M3f-3b-1 is built.

## Review rounds
- R1: Revision required. [P2] plan header named v1.20 as current → active spec v1.22 / 79a9a40e, v1.20 as original baseline. [P2] "nine PRs" vs the M3f split → nine work packages, Done when covers every sub-PR. [P2] Done when said Q9 pending → Q9 (a) answered, item 11 cleaned. [P3] reviewer-addressed PR-body heading → neutral wording.
- R2: Revision required. [P1] UNI-13 missing from the self-check while `image` was red → red job was base-image vulnerabilities (musl, zlib), fixed by PR 127 (merged first); main merged into this branch; UNI-13 and the full universal list added to the body. [P2] §0 still said Q9 must be answered → §0 amended.
- R3: Approved. No findings.

## Deferred conditions
- none

## Decisions worth keeping
- The plan's "nine" counts work packages; real PR counts are higher (M3d, M3e, M3f sub-PRs). The Done-when gate requires every sub-PR reviewed, receipted and logged.
- Q9 (a) stands for AUTH-03 only; the spec M3 row still says "AUTH-01..09" and should read "AUTH-01..02, 04..09" at the next spec touch (with the D20 wording P3).
- A red CI job on a docs-only PR can come from the vulnerability database, not the diff; fix it in a separate reviewed PR and merge main in (a CI re-run keeps the old merge ref).
- Write the self-check table against the whole universal list from the start.

## Follow-ups
- Builder: `build` M3f-3b-1 (`accounts.auth.factors`: TOTP enrolment, first factor makes the user active, `recovery.generate` in the same transaction, AUTH-07 marker, pending helpers and factor throttle; no route; about 380 lines). Then 3b-2, 3c-1, 3c-2.
- Spec, next touch: D20 parenthetical (Round 26 P3) and the M3 row's "AUTH-01..09".
- Owner: decide whether M3g (optional passkeys) moves after M3i (not decided here).
- Open from earlier: Dependabot PR 14 (python 3.15, uv 0.13) not taken; Dependabot alerts 1 and 2 not looked at.

## Appendix — final review round
# Review — PR #126

## Round 3 — 2026-11-07 · scope: slice
- **Code review:** base (merge base) `05f42a63b8b85fc738c6a7fcc61e6caf9816f9ef` · head `a7e0d8ba54889d18f602b8b0a5786dce0a60a795` · head re-checked at end: yes
- **Spec used:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.22 · hash (`git hash-object`) `79a9a40ee1a686ae1082e8d11a73b299deb66d38`

**Verdict:** Approved
**Model used:** GPT-5 Codex · **Switch model next step?** No — review is complete and the builder's approval-archive step is mechanical.

### Findings

No blocking findings.

Round 2 resolution:
- The UNI-13 P1 is resolved: the PR body now audits UNI-13 explicitly, PR 127's base-image remediation is in the base, and `checks`, `security`, `image`, and `host` all pass on exact head `a7e0d8ba…`; the image scan reports no blocking finding.
- The Q9 P2 is resolved: plan §0 records that the owner answered Q1–Q10 with (a), names the Q9 AUTH-03 deferral, and explicitly labels the following “No owner answer” sentence as historical 2026-10-31 text. Q9, §9 item 11, Done when, and DECISIONS agree.

Round 1's provenance, work-package/sub-PR accounting, Q9/Done-when, and reviewer-addressed wording findings remain resolved after the merge from `main`.

### Self-check audit

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-13 | yes — every PR must pass build, test, audit, secret, and image gates | pass, with exact-head CI evidence and prior image failure explained | pass | Actions run `42368553483`; all four required jobs green on `a7e0d8ba…` | No |
| Spec v1.22 D7, T5, Flow 5.1, M3 | yes — plan alignment is the purpose of the change | pass | pass | plan `:3-5,41-44,99-118,131-141,179,184,198`; spec `:5,92,575,1201` | No |
| AUTH-03 / Q9 | yes — role-matrix test deferral and milestone gate changed | pass, deferred to M4-rest | pass | plan `:10,25,141,179,184,198`; DECISIONS `:1133-1144` | No |
| AUTH-07 | yes — factor-change ownership moved | pass | pass | plan `:43,102-103,141`; active-session add/remove/regenerate waits for M3h, behind step-up, with other-session revocation tests | No |
| AUTH-09 | yes — step-up factor policy changed | pass | pass | plan `:112-113`; TOTP or enrolled passkey, never recovery code | No |
| PR sizing / milestone completion | yes — owner accepted six M3f-3 PRs and the plan must retain a testable gate | pass | pass | plan `:31,41,46,103,165,172,197` distinguishes work packages from sub-PRs and requires every listed sub-PR reviewed, receipted, logged, and merged | No |
| Decisions log / builder §7 | yes — owner choices and accepted risk must be durable | pass | pass | `docs/DECISIONS.md:1133`–`1144`; matches `.agent/reviews/owner-decisions-m3f-3.md` | No |
| UNI-07/08/09 | yes as secrets/PII hygiene for auth documentation | pass | pass | changed-line scan contains documented key names only, no value or personal data; exact-head `security` job passed | No |
| UNI-14 | unchanged but checked after merging `main` for the image remediation | pass | pass | `Dockerfile:12` remains digest-pinned; exact-head image job passed | No |
| `git diff --check` | yes | pass | pass | clean for `05f42a63…...a7e0d8ba…` | No |
| PROJECT §9 / §11 | applies as consistency constraints | pass, unchanged | pass | effective diff is plan and decisions only; locked switches and auth constraints remain intact | No |
| Runbooks / UNI-16 | n-a — no implemented auth, deployment, env, domain, or operator procedure changes | n-a | n-a accepted | future runbook work remains assigned in plan §6 | No |
| Frontend, tenancy-RLS, money, finalized-records, files, events/jobs | n-a for this documentation-only slice | n-a | n-a accepted | effective name-status lists only the plan and decisions log | No |

### Verification performed

| Command / check | Result |
|---|---|
| `git fetch origin`; GitHub PR metadata | PR open, not draft, mergeable; base `05f42a63…`, head `a7e0d8ba…` |
| Fresh detached checkout `.agent/worktrees/review-126-a7e0d8ba-r3` | exact head checked out; tracked state clean at end |
| Merge-base and three-dot stat/name-status/log | merge base equals current PR base; effective diff is only `docs/plans/2026-10-31-m3-auth.md` and `docs/DECISIONS.md` |
| Full effective diff and numbered plan review | all Round 1/2 corrections and the merge resolution inspected directly |
| Owner decision record comparison | plan/DECISIONS match `1a 2ok 3yes 4yes`, including the AUTH-07 test condition |
| `git hash-object` on spec | `79a9a40ee1a686ae1082e8d11a73b299deb66d38`, matching PROJECT §2 and plan provenance |
| Q9/owner-answer search | no active statement says Q9 is unanswered; historical wording is explicitly labelled; active gates agree |
| `git diff --check` | pass |
| Changed-line secret-pattern scan | only documented key names; no secret value or PII added |
| Injection-addressed-text scan of effective diff | no reviewer-approval, check-skipping, or gate-bypass instruction found |
| `gh pr checks 126` and run metadata | `checks`, `security`, `image`, `host` pass on exact head; publish/deploy correctly skipped for a PR |
| Final host and checkout check | head/base unchanged; PR remains open and mergeable; checkout clean |

### Residual risks and test gaps
- This approves the plan/decision slice, not the future M3f/M3h implementation. Concurrency, revocation, enrolment, step-up, and optional-passkey behavior still require proof in their named implementation PRs.
- The owner-accepted real-time TOTP phishing risk for owner/admin remains recorded in spec T5 and is not reopened.
- Spec D20's stale “passkeys, bridge pairing” wording remains the previously deferred Round 26 P3 for the next spec touch.
- No local application suite was rerun for this documentation-only effective diff; exact-head CI ran and passed all required gates.

### Required before merge
- None. Approved is not a merge instruction; run `approved 126` to archive this review before Ying merges.

### Deferred conditions
- None.

### Optional improvements
- None.

