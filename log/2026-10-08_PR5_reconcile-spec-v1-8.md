# PR 5 — chore(setup): reconcile PROJECT.md with spec v1.8

- **Merged:** 2026-10-08T15:31:24Z (GitHub) · **Merge commit:** `5f923b320acc744f7993b17e5290da912f4aa905` · **Branch:** `chore/reconcile-spec-v1.8` (final head `1612629f5fe1f2e40fad8a342e268b24dc157f5a`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-5.receipt` on `agent-logs` (commit `9ce3701`, written 2026-10-08T15:26:37Z, before the merge); names head `1612629…` and review-file hash `6a24868ed5edd0daf55fb79dc0472d47984db89a`; the archived review `reviews/PR-5.md` (log-branch commit `d81919d`) has the same hash.
- **Merge evidence:** `gh pr view 5` → state MERGED, mergedAt 2026-10-08T15:31:24Z, merge commit `5f923b3`, final head `1612629` (equals the reviewed head of Round 2); `git merge-base --is-ancestor 5f923b3 origin/main` succeeded.
- **Drafted by:** Claude Sonnet 5.5 (builder; `setup` asks for the deep tier, noted in the PR) · **Final verdict:** Approved (round 2; reviewer Codex GPT-6)
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8 (`67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`) · **Plan:** none · **Milestone:** setup reconcile (between M0b and M0c)

## What changed
Three values in `agents/PROJECT.md`: "Spec hash at last reconcile" set to the v1.8 hash; the extra-frontend-standard comment restates approved D2 (Fernly layout as visual reference, navy and gold, tokens in `web/src/styles.css`); the scaffold milestone line says `jobs.enqueue_in_tx` is the M0c subset tested as `skiw_app`, with the tenant guard and `args_mac` in M4.

## Why
The reconcile gate blocks builder commands while `PROJECT.md` holds an older spec hash. Spec v1.8 (PR 3) was approved with conditions and merged.

## Review rounds
- R1 (Blocked): [P1] no rule/result/evidence self-check table → PR body rewritten with the table (same head, no code change).
- R2: Approved.

## Deferred conditions
- none introduced. Standing: spec Round 11 P2 (revise `docs/plans/2026-10-05-m0-scaffold.md` before M0c starts); M0d scans and cache-constant naming; M2 CSP nonce.

## Decisions worth keeping
- Reconcile gate is clear: `PROJECT.md` spec hash = `67e36a52…`.
- Kit version still 1.7.1; the 1.7.3 upgrade (README, START, reviewer role changed in the working tree) waits for the owner's `go` and must not ride on a reviewed PR.

## Follow-ups
- Optional (reviewer): the PR body cites `PROJECT.md` line 35 for the extra-frontend-standard row; it is line 34. Cosmetic.
- M0 plan update PR, then M0c.

## Appendix — final review round
## Round 2 — 2026-10-08 · scope: slice (spec v1.8 reconciliation)
- **Code review:** base (merge base) `76d473df659df313a8ab2b44442b22bd6556f97c` · head `1612629f5fe1f2e40fad8a342e268b24dc157f5a` · head re-checked at end: yes; unchanged, OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`, approved with conditions in spec Round 11.
- **Mode:** exact-head snapshot `.agent/worktrees/review-5-1612629f-r2`, removed after verification. Fetch denied by read-only `.git/FETCH_HEAD`; local exact head present. GitHub main ref confirmed the recorded base.

**Model used:** Codex GPT-6 · **Switch model next step?** No — reconciliation is verified; M0c implementation retains its existing deep-tier requirement.

### Findings
No blocking findings or new content defects.

**Round 1 P1 resolved:** re-read the PR body. It now contains the required Rule / Result / Evidence table with START setup Part B, FE-13/D2, TEN-02/EVT-01/D5/M0-M4, UNI-07, UNI-12, UNI-13 and justified n/a scope. CI is identified by exact head/run; project scans remain explicitly deferred to M0d. Runtime job verification is correctly assigned to M0c, rather than claimed by this docs-only PR.

### Self-check audit
Same applicability as Round 1: reconciliation accuracy; secret/write/delivery rules; documentation alignment with D2 design tokens and D5/M0/M4 runtime-role/transaction requirements. No new executable UI, tenancy, jobs, money, auth, finalized-record or file behavior. PROJECT §9 mappings and locked switches unchanged.

| Rule | Applies? | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| START setup Part B | Yes, reconcile gate | pass | Recorded hash equals reviewed v1.8 blob; no unresolved fields; changes supported | PROJECT:29; spec blob; Round 11 | No |
| FE-13 / D2 | Documentation alignment | pass, documentation only | Visual-only Fernly reference, navy/gold and token source match approved D2 | PROJECT extra-frontend-standard row (line 34); spec D2; decisions 2026-10-07 | No substantive disagreement; body and Round 1 cite line 35, an off-by-one citation |
| TEN-02 / EVT-01 / D5 / M0-M4 | Documentation alignment | pass, documentation only | M0c subset as skiw_app and full tenant guard/MAC in M4 match approved staging | PROJECT:76; spec D5 and M0/M4 | No |
| UNI-07/12 | Secrets and write scope | pass | Zero secret-pattern hits in diff; one project file changed; review writes confined to allowed locations | effective diff; snapshot checks | No |
| UNI-13 | Delivery status | slice pass; project partial | Exact-head CI success independently confirmed; prior M0d scans explicitly retained | run 37755873908; unchanged CI workflow; Round 1 audit | No |
| Other UNI / active packs / PROJECT §9 | No changed runtime contracts | n/a with scope reasons | Appropriate for this three-line documentation change; existing mappings unaffected | effective diff | No |

### Verification performed
| Command / check | Result |
|---|---|
| `gh pr view 5 --json body,headRefOid,baseRefName,state,statusCheckRollup` | Corrected self-check present; same reviewed head, main base, OPEN, successful checks. |
| `git archive <head>` snapshot; merge-base calculation | Safe resolved paths; exact-head snapshot; merge base 76d473d. |
| `git diff --name-only` and `git diff --check <base>...<head>` | Only agents/PROJECT.md; whitespace clean; effective diff unchanged from Round 1. |
| Spec hash and unresolved PROJECT field check | Exact approved hash 67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3; no unresolved fields. |
| Re-inspected changed values against spec D2/M0/M4, decisions and prior review | All three values match; no code/grant/kit changes introduced. |
| Secret-pattern scan of effective diff | Zero hits; not a full repository scan. |
| `gh run view 37755873908 --json headSha,conclusion,status` | Completed SUCCESS at exact head 1612629f. |
| Final host head and main-ref reads | Head unchanged and OPEN; host main remains 76d473d. |
| Snapshot file hashes compared with `git ls-tree -r <head>` | Every tracked file unchanged; snapshot removed. |

### Residual risks and test gaps
- No local runtime tests needed or run for this unchanged docs-only slice. Existing exact-head CI is the runtime evidence; this is not a milestone or production approval.
- Prior spec Round 11 condition still requires the M0c plan-update PR before M0c implementation. Existing M0d scan and M2 CSP work remains pending in its original scope.
- Git fetch cannot write in this sandbox; exact host base/head independently confirmed.
- No prompt-injection attempt found in corrected PR body or changed document.

### Required before merge
- No content or self-check correction required. Builder runs `approved 5` to archive this round and create the receipt before Ying merges.

### Deferred conditions
- None introduced by PR 5; prior named follow-ups unchanged.

### Optional improvements
- When next editing the PR body, change its extra-frontend-standard line citation from 35 to 34; Round 1 inherited the same off-by-one citation. The named field and evidence are unambiguous.

**Verdict:** Approved
