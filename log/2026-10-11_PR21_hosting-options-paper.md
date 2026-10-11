# PR 21 — docs(spec): hosting options decision paper (no spec change)

- **Merged:** 2026-10-11T13:52:15Z (GitHub) · **Merge commit:** `896eb4cf519a2fbdf573d349d0ce98a85b273521` · **Branch:** `docs/hosting-options` (final head `67b0b53a43ae1899a10ede86d848d1387d350ff5`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-21.receipt` on `agent-logs` (written 2026-10-11T13:51:01Z, 74 seconds before the merge); names head `67b0b53…` and review-file hash `d013aeb5078a7061a399abe4ca19c65ed277526f`; records CI green on that exact head (run 38142868064). The archived review `reviews/SPEC-2026-10-11-hosting-options.md` has the same hash. PR 21 is a decision-paper PR, so its reviewer record is the spec review file (as for PR 3 and PR 19).
- **Merge evidence:** `gh pr view 21` → state MERGED, mergedAt 2026-10-11T13:52:15Z, merge commit `896eb4c`, final head `67b0b53` (equals the reviewed head of Round 4); `git merge-base --is-ancestor 896eb4c origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder; research and text by Opus subagents, deep tier) · **Final verdict:** Approved with conditions (spec review round 4; reviewer Codex GPT-6)
- **Spec:** the paper `docs/specs/2026-10-11-hosting-options.md` v1.6 (`4c642318…`). The platform spec stays v1.13 (`e3141585…`); PROJECT.md spec hash unchanged. **Milestone:** none (input to a hosting decision and a possible spec v1.14).

## What changed
One new file, `docs/specs/2026-10-11-hosting-options.md` (v1.6, 48 fact rows). It compares AWS as specified (A), trimmed AWS in Malaysia (A2), DigitalOcean Droplets (B, B2, B3), a Malaysian VPS (B4, iCore, and an Azure Malaysia West alternative), DigitalOcean App Platform (C), Render (D, D2 lean) and Vercel (rejected), with cost ranges, PDPA exposure per option (a checklist, not legal advice), security-control impact, spec items that would change, backup design for the owner's two proposals (Google Drive export, local export with a pull) and a complete-recovery inventory and drill. It changes no spec text and chooses no platform.

## Why
Owner request 2026-10-11: AWS Step 1 (spec 8.2, about US$245 a month) costs too much; asked about a VPS (DigitalOcean) and Vercel-like platforms. Owner chose an options paper reviewed first, then a platform decision.

## Review rounds
- R1 (Revision required): [P1] DigitalOcean standby price ignored the plan change from 30 Nov 2026 → eligibility and Advanced pricing added, B/C recomputed. [P2] PDPA wording (TIA is evidence for a section 129(2) finding, not a basis; notice required) → rewritten. [P2] trimmed AWS adoption scope → section 7.1 retained/replaced/removed table.
- R2: Approved with conditions (v1.1). Deferred P2: ALB-only ingress for trimmed AWS public-subnet tasks.
- R3 (Revision required, after v1.2 to v1.5 added lean Render, lean VPS, owner HA and backup input): [P1] a database-only export is not complete recovery → recovery inventory and complete-recovery drill. [P2] decision tree excluded the in-country VPS → B4 and Azure on the in-country branch, conditional.
- R4: Approved with conditions (v1.6).

## Deferred conditions
- Hosting-adoption spec v1.14, before M1 plan/implementation, if A2 public-subnet tasks are selected: replace the deny-all-inbound wording with ALB-source service and health-check ingress only, deny direct Internet ingress, with M1 positive and negative checks (paper section 7.1).
- Open for the adopting spec: Q10 (one web instance), Q11 (export interval, who restores, key custody, Drive vs Malaysian copy), named server operator for VPS options, RTO/RPO numbers, spike S1 (backup role with BYPASSRLS on the chosen database), PDPA step for any non-Malaysian host.

## Decisions worth keeping
- No platform is chosen. The paper records owner inputs of 2026-10-11 as inputs, not decisions: HA (database standby) is not required in v1 for a team of 5; a short outage with manual recovery is bearable; backups are a scheduled export (Google Drive or the VPS's own disk). The final one-web, RTO/RPO and backup choices must be recorded in `docs/DECISIONS.md` by the adopting change.
- Builder recommendation in the paper (not a decision): trimmed AWS first; DigitalOcean App Platform without a database standby second, only if the owner accepts the Singapore PDPA step.
- A Google Drive database copy needs the PDPA process; encryption before upload reduces exposure but is not stated to make the transfer lawful.

## Follow-ups
- Owner: choose the hosting platform and answer the PDPA step; then the builder drafts hosting spec v1.14 (deep tier), the reviewer checks it, `setup` Part B reconcile, then the M1 plan.
- Owner: `brew install gitleaks` then `make hooks`; decide the kit change for the explicit green-CI check.
- Optional (noted by reviewer): the PR body's old full-service savings sentence; no effect on the merged file.
- Parked: UI kit decision, API Anything / FAME spike, `skiw-old` look reference. Local branches `docs/reconcile-spec-v1.13` and `docs/hosting-options` and the `.agent/worktrees/hosting` worktree remain; owner yes needed to delete.

## Appendix — final review round
## Round 4 — 2026-10-11 · scope: slice (hosting decision paper v1.6, recovery corrections)
- **Spec review:** `docs/specs/2026-10-11-hosting-options.md` · version 1.6 · hash `4c642318dafcd8bdbd6b93b25cfb629f8ed4d5ba`.
- **Pinned PR 21:** base `21db4511ffaa80741572d3adae35d54c3183a1f5` · head `67b0b53a43ae1899a10ede86d848d1387d350ff5` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-commit snapshot `.agent/worktrees/review-spec-hosting-67b0b53a`; all tracked file hashes match pinned commit; snapshot removed. No source/document/handoff edit by Reviewer.
- Approval applies to the comparison paper only. Platform spec v1.13 and its PROJECT reconciliation are unchanged; owner platform choice is still open.

### Findings
No new finding. Round 3's P1 and before-merge P2 are resolved. Existing Round 2 P2 remains deferred to the named adopting-spec follow-up.

#
