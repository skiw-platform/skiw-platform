# PR 162 — feat(web): M3g-2a-2a Security page with the passkey list, and passkey focus fixes

- **Merged:** 2026-11-16T06:29:58Z · **Merge commit:** 514a8ca655330d74f0df04dd051fa93799f03878 · **Branch:** feat/m3g-2a-2a-security
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-162.receipt` (log-branch commit holding the review `ecaaceaa3df004540c9a53973803632c1266f76e`; receipt time 2026-11-16T06:28:37Z, before the merge; head `92f889292e8158aa7fc36f8f9eac93dae6156670`; review hash `7696b90e0b7ff9597d52116cdac55cad1781f663`)
- **Merge evidence:** `gh pr view 162` state MERGED, merge commit above, merged by the owner; commit is an ancestor of the fetched `origin/main`. Final head SHA equals the reviewed SHA.
- **Drafted by:** Claude Sonnet 5.5 (standard tier; PROJECT.md §6 maps auth to deep, no deep-tier sub-agent used, disclosed in the PR and DECISIONS) · **Final verdict:** Approved with conditions (round 2, independent review GPT-6.1 Codex)
- **Spec:** `docs/specs/2026-11-16-m3g-2a-2-passkey-screens-design.md` v1.3 (hash `cd1a0ac71877db864f19377172c95b77b71be303`) · **Plan:** M3 plan · **Milestone:** M3g-2a-2a

## What changed
Security page at `/#security` (second nav item, real anchors with `aria-current`, `hashchange` and `popstate`, hash cleared on sign-out), a read-only passkey list from `GET /api/auth/factors` with loading, empty, error-with-retry and 401 paths, `parseFactors` (one reader of the list) and `passkeyRows` (Malaysia time, null, " (n)" numbering). After a failed passkey, focus returns to the passkey button on the code screen and in the step-up dialog. The slice spec, its PROJECT.md §2 entry and a DECISIONS entry landed with it. 592 changed lines.

## Why
First of four PRs for M3g-2a-2 (owner chose 2a page and list, 2b add, 2c remove, 2d the offer after enrolment). It also clears PR 161's Round 9 P2 #1 focus condition.

## Review rounds
- R1: [P1] self-check omitted applicable rules (UNI-07, UNI-14, FE-23, FE-24, FE-34 and others) → PR body completed, no code change.
- R1: [P2] DECISIONS credited the deep tier while the PR said Sonnet → DECISIONS and PR Model section now name the standard tier and the independent review (`92f8892`).
- R2: Approved with conditions, no new finding.

## Deferred conditions
- P2 → M3g-2b: real-browser keyboard, axe, responsive overflow, focus and virtual-authenticator matrix for the Security and passkey screens (A11Y-06, FE-70, FE-71).
- StepUp mounting and modal containment → M3g-2a-2b.

## Decisions worth keeping
- Hash URL `/#security`; only the exact hash selects Security; Today link from Security does a full reload (no click handler, outside the spec).
- Ambiguous registration results never claim success from a list difference (spec decision 6(f), for 2b).
- Repo goes public before `gh pr create`; runs created while private fail on billing (memory note).

## Follow-ups
- Next: M3g-2a-2b add a passkey (deep tier), then 2c remove, 2d the offer, M3g-2b browser tests.
- Optional PR 161 P3 #1 (recovery codes on an exact success) still open and out of scope.

## Appendix — final review round
## Round 2 — 2026-11-16 · scope: slice

- **Code review:** merge base `af01756f454e2ae3cf4b3360accc51be82ae615c`; head `92f889292e8158aa7fc36f8f9eac93dae6156670`. Host head rechecked at end: unchanged; PR open.
- **Spec:** passkey screens v1.3, hash `cd1a0ac71877db864f19377172c95b77b71be303`, unchanged from approved spec Round 4 and PR Round 1. Scope: milestone 2a, read-only Security and carried focus fixes.
- **Checkout:** detached `.agent/worktrees/review-162-92f88929`. Only review record written; main and builder checkouts untouched.

### Findings

No new blocking findings. Both Round 1 findings are resolved.

| Finding | Re-inspected evidence | Result |
|---|---|---|
| P1: incomplete self-check | Current PR body adds UNI-07/14, FE-23/24/34, plus module-boundary, layout, rendering and dependency/registry assessments. Typed owned account code, tests, component-lifetime reads, lockfile and exact-head security CI substantiate the flagged rows. Browser claims remain qualified by the named M3g-2b deferral. | Resolved |
| P2: inaccurate implementation provenance | `docs/DECISIONS.md:1548` now identifies standard-tier Sonnet implementation without a deep-tier sub-agent and separately identifies independent GPT-6.1 review. Current PR Model section agrees. | Resolved |

### Applicability / self-check audit

Round 1's applicability list and code assessment remain applicable: UNI-01/02/03/05/06/07/09/13/14/16; AUTH-02/03/13; TEN-11; semantic/layout/component/rendering/quality FE rules; A11Y focus/live feedback and named browser deferrals; PROJECT §9. The only repository delta since that review is the one-line DECISIONS correction; no code, test, dependency, config, spec or runbook changed. The updated self-check addresses the prior audit omissions. No new scope or guardrail issue found.

### Verification performed

| Check | Result |
|---|---|
| Fetch/pin | Fetched origin, computed merge base and created detached checkout at exact host head. |
| Incremental diff | `git diff 6fe0547...HEAD`: only `docs/DECISIONS.md:1548` changed. Source/tests identical to Round 1. |
| Spec | Exact approved hash above retained. |
| PR body | Re-read self-check and Model sections against Round 1 findings and code evidence. |
| CI | Run 43815819370 reports head `92f889292e8158aa7fc36f8f9eac93dae6156670` and success; checks/security/image/host all successful. Publish/staging jobs skipped as expected for a PR. |
| Local tests | Not rerun for this documentation-only delta. Round 1 locally verified 156 tests, typecheck, lint and production build; current exact-head CI independently passed. |
| Hygiene/integrity | `git diff --check af01756...HEAD` clean; checkout tracked/staged state clean; host head unchanged and PR open at final check. No suspicious instruction or secret introduced by the one-line correction. |
| Review cleanup | Removed the clean detached checkout after checks. No install/build output created this round. |

### Required before merge

No remaining review correction. Builder must run `approved 162` to archive this exact-head review and create the approval receipt before the owner merges. This verdict is not a merge instruction.

### Deferred conditions / residual risks

- **P2 deferred to M3g-2b:** new Security/passkey real-browser keyboard, axe, responsive overflow, focus and virtual-authenticator matrix, carried from approved spec Round 4 and PR Round 1. Existing CI e2e success does not replace this specific matrix.
- StepUp mounting/modal containment remains in M3g-2a-2b; add/remove/enrolment paths remain later slices. This approves milestone 2a only, not feature completion or production readiness.
- Round 1 size acceptance stands: 592 changed lines including the approved spec's first committed copy and focused tests; no additional scope in this revision.

**Model used:** GPT-6.1 (Codex), independent review. **Switch model next step?** No — review corrections are complete; retain deep reasoning for subsequent auth slices.

**Verdict:** Approved with conditions

