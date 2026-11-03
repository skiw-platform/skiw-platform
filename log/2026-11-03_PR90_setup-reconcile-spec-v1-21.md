# PR 90 — docs: setup reconcile PROJECT.md with spec v1.21

- **Merged:** 2026-11-03 (07:12:15 UTC) · **Merge commit:** 0344c5c0b9ae3e63c422e1ff77dc3eb2d184fdca · **Branch:** docs/setup-reconcile-spec-v1-21
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-90.receipt on agent-logs (log-branch commit fdba8bb, receipt time 2026-11-03T07:07:35Z, before merge; reviewed head 128e2d5a992197bb7ef7617c26823de781a0b012, review-file hash a747cd635126c7a547cdfb3fe363bccd743521f8, review commit 00f09e7)
- **Merge evidence:** `gh pr view 90` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 128e2d5a
- **Drafted by:** Sonnet 5.5 builder · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2 now) · **Milestone:** M4-core, closes the PR 88 R2 condition

## What changed
`agents/PROJECT.md` only, +3 −3: §2 spec hash d95cb271 with the v1.21 history comment; the role-set line adds the migrator's `INHERIT FALSE, SET TRUE` membership of the two NOLOGIN owners with no standing grant; the TEN-10 line adds the `migrate` task's key write as the table owner through `SET ROLE` (`tenancy.keys`).

## Why
Part B reconcile after spec v1.21 (PR 89). The PR 88 review required spec v1.21 approved and reconciled before M4c-4a merges.

## Review rounds
- R1: Approved. No findings.

## Deferred conditions
- none. The PR 88 R2 condition is now met (spec v1.21 merged in PR 89, reconciled here).

## Decisions worth keeping
- PROJECT.md does not restate the v1.21 verifier, encoding or TEN-09 detail; the spec is the source.

## Follow-ups
- M4c-4a review checks: `guard.current_agency()` refuses absent or retired key versions; minter and verifier pass the committed token test vector (spec §4.2 items 2–3, TEN-09).
- M4c-4a also: `test_auth_lookup_definer_live.py` change, USAGE on `guard` to `skiw_app`, rotation warning in `host-rebuild.md`.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 85 P3 → M4c-4b; PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; M2c owner Q1=A, Q2=A to record in DECISIONS; Dependabot alert security/dependabot/1.

## Appendix — final review round
# Review — PR #90

## Round 1 — 2026-11-03 · scope: docs (setup reconcile; `agents/PROJECT.md` only)
- **Code review:** base origin/main 238fc054460fb208d90059598485a1060163158d (merge of PR 89; the PR head
  descends from it) · head 128e2d5a992197bb7ef7617c26823de781a0b012 · 1 file, +3 −3 · head re-checked at
  end: yes (unchanged). Read from the PR diff and `git show`; no checkout needed for a docs-only change.
- **Spec:** v1.21, hash d95cb2717bd1cfabf62d3dbe6cd4af2f1e4c73fd (spec review Round 25 Approved). The spec
  on origin/main (`git show origin/main:<spec> | git hash-object --stdin`) gives exactly this hash.
- **CI:** checks, security, image, host: success; publish and deploy-staging: skipped (normal for a PR).

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 90`
(builder), then merge; M4c-4a can start after that.

### What was checked
- **§2 spec hash** (`PROJECT.md:29`): d95cb271 / v1.21 / Round 25 / PR 89 merged 2026-11-03 (GitHub merge
  time 06:12Z), all correct. The comment keeps the earlier reconciles (v1.20 92841ba5 and older).
- **Role-set line** (`PROJECT.md:159`): adds the migrator's membership of `skiw_tenant_guard` and
  `skiw_auth_lookup` with `INHERIT FALSE, SET TRUE` and no standing grant. This matches spec D4, TEN-02 and
  H6 (`spec:918`) word for word in substance. The closed role set is unchanged.
- **TEN-10 line** (`PROJECT.md:193`): adds "the `migrate` task's own key write as the table owner through
  `SET ROLE` (`tenancy.keys` …)". This matches the spec TEN-10 row and the code merged in PR 88
  (`app/tenancy/keys.py` exists). This was the stale line flagged in spec review Round 25.
- **Nothing else needed reconciling.** The rest of v1.21 (retired-key refusal in `current_agency()`, the
  token encoding, the TEN-09 retired-key test, the decoy and `approval_mac_key` rows) is spec detail that
  PROJECT.md doesn't restate; its existing lines (`:158`, `:191`) still hold. No `{{` placeholders remain;
  no "v1.20" or old hash left outside the history comment.
- **Owner decisions:** none changed or invented.

### Findings
None.

### Follow-ups
- This PR, once merged, closes the PR 88 R2 condition ("spec v1.21 reviewed and reconciled before M4c-4a
  merges"). The M4c-4a review should check that `guard.current_agency()` refuses absent or retired key
  versions and that the minter and verifier pass the committed token test vector (spec §4.2 items 2–3,
  TEN-09).
