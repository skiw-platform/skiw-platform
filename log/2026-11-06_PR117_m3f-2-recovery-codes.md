# PR 117 — feat(accounts): M3f-2 recovery codes (accounts.auth.recovery)

- **Merged:** 2026-11-06T03:20:29Z · **Merge commit:** 64687fe6ead851fe6a6101f4bfca0d309df88eff · **Branch:** feat/m3f-2-recovery-codes
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-117.receipt, commit ee4a027 (2026-11-06T03:19:36Z, 53 s before the merge; head 480b673 and review hash 1d34dfd1 match)
- **Merge evidence:** `gh pr view 117` (state MERGED, mergedAt 2026-11-06T03:20:29Z, mergeCommit 64687fe, headRefOid 480b673cdb89dac897021887ea499e849cec808b = the reviewed head); `git merge-base --is-ancestor 64687fe origin/main` succeeded after a fresh fetch
- **Drafted by:** Claude Opus 5.5 sub-agent (deep tier: design and code) with a Claude Sonnet 5.5 builder session (files, runs, mutation tests) · **Final verdict:** Approved with conditions (round 3)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md (v1.21, d95cb271) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3f · **Milestone:** M3 (M3f, part 2 of 3)

## What changed
`accounts.auth.recovery`: 10 single-use recovery codes per user (16 Crockford base32 symbols, 80 bits, shown once as four groups of four). Each is one `user_factor` row (kind `recovery`) with `secret_ct` = HMAC-SHA-256 under `tenant_source_key` (label `skiw-recovery-v1`) over the length-prefixed user id and normalised code; the newest key version signs and every listed version matches. A use is one `DELETE … RETURNING`; regenerating locks the `app_user` row, deletes the user's recovery rows and inserts ten. Both functions run in the caller's `with_agency()` transaction. `source_key._field` became the public `field`. No route yet. Runbook note on `tenant_source_key` rotation; DECISIONS "M3f-2"; 19 of 19 mutants killed.

## Why
Flow 5.1 (2) recovery factor, spec D7 (10 codes), §4.1 `user_factor` (C3); plan M3f line 100. Split from M3f-1 (TOTP primitives) and before M3f-3 (enrolment and the second-factor endpoint).

## Review rounds
- R1: Revision required for the red CI `security` gate only ([P1], UNI-13: gitleaks `generic-api-key` false positives on `agent-logs`) → fixed in a separate PR 118 (label allowlist, merged c0cd78b); owner chose the fix. [P2] recovery-code version not stored → deferred. The PR's own code needed no change.
- R2: Revision required: [P1] R1 P1 still open (a re-run reuses the original merge commit, so it still had the old config; R1's note that a re-run would pick up main's config was wrong); [P1] the PR conflicted with `main` in `docs/DECISIONS.md` (PR 117 and 118 both appended at the end) → merged `main` into the branch (480b673), both entries kept byte-identical, PR 118's first.
- R3: Approved with conditions. CI run 42151633050 green with every `security` step run; the diff to R1's code is identical except `docs/DECISIONS.md`.

## Deferred conditions
- [P2] (R1) the signing key version is not stored in `secret_ct`, so the runbook's "keep the old version until every user has regenerated" step cannot be checked, and an emergency rotation silently voids every code → **M3f-3**, before any route can generate codes: either a 1-byte version prefix (33 bytes) with a live test and a runbook count query, or reword the runbook's emergency path.
- PR 118 R1 [P2] (narrow the gitleaks label regex to `^skiw(?:-[a-z]{2,12}){1,4}-v[0-9]{1,6}$` and add tests) → M3f-3, or a standalone follow-up if sooner.

## Decisions worth keeping
- Both functions run in the caller's transaction and raise outside an atomic block; `consume` must commit before `login()`, so M3f-3 calls it in its own `with_agency()` block, and writes the AUTH-07 marker in the transaction that regenerates.
- No constant-time compare (Postgres equality on a keyed MAC; reviewer accepted).
- A GitHub re-run reuses the event's original merge commit, and a PR that conflicts with `main` gets no merge ref and no CI run; close/reopen does not help. To pick up a changed `main` config, push a new head (here a merge of `main`).
- Two open PRs that both append to the end of `docs/DECISIONS.md` conflict; the second to merge needs a merge of `main`.
- The lasting decisions are in the merged DECISIONS ("2026-11-06 — M3f-2"); nothing missing.

## Follow-ups
- M3f-3: TOTP enrolment, the second-factor endpoint, the conditional step update (`sign_count < step`, two concurrent uses → one), pending-state checks (`_skiw_pending_until`, `_skiw_pending_enrol`), AUTH-07 on factor add/remove/regenerate, the `otpauth://` link and its issuer label, throttling of failed recovery uses (AUTH-06), the per-kind `secret_ct` length CHECK (`isolation_cases.py` inserts a 32-byte `totp` row and changes with it), plus the two P2s above.
- The owner's confirmation of "12, build" (PR 115 R1) is still open.

## Appendix — final review round
## Round 3 — 2026-11-06 · scope: slice (M3f, part 2 of 3)
- **Code review:** base `main` c0cd78b714ecd4d391eadc7cb3d22fdb37867663 (merge base = main) · head
  480b673cdb89dac897021887ea499e849cec808b ("Merge main into feat/m3f-2-recovery-codes", parents
  c07aec53 + c0cd78b) · head re-checked at end: yes, unchanged.
  - **Where:** detached worktree `.agent/worktrees/review-117-480b673c`, disposable DB on :5442; both
    removed afterwards.
- **Spec:** v1.21, hash d95cb271 (unchanged).
- **CI (run 42151633050, head 480b673c):** checks, security, image, host: pass. publish, deploy-staging:
  skipped. **Every `security` step ran and passed**:
  - full-history scan: 540 commits, "no leaks found";
  - Secret rule test: 5 passed;
  - Python and Web dependency audits: pass;
  - Semgrep registry rulesets: pass.

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 117` (builder), then Ying merges. Then M3f-3.

### R1/R2 findings
- **R1 P1 / R2 P1 (CI `security` red): resolved.** All its steps ran and passed on this head (above).
- **R2 P1 (DECISIONS conflict): resolved.**
  - `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`.
  - `git diff c0cd78b 480b673c` is **byte-identical** to R1's effective diff (`59af95b c07aec53`) for every
    file except `docs/DECISIONS.md`.
  - In DECISIONS:
    - the 16 added lines are identical to R1's M3f-2 entry;
    - no line is removed, so the PR 118 entry is untouched;
    - order is PR 118's "Secret scan" entry (line 1072), then "M3f-2" (line 1080).
  - `git diff --check`: clean.
- **R1 P2 (runbook check can't be run; no version stored): still open, deferred to M3f-3.** It must land
  before any route can generate codes.

### Findings
- [P2] R1 P2 above, deferred to M3f-3. No new findings. No P0/P1. No injection attempts.

### Verification performed
| Command / check | Result |
|---|---|
| Effective-diff comparison, R1 head vs R3 head (all but DECISIONS) | identical |
| DECISIONS added and removed lines vs R1 | 16 added, identical; 0 removed |
| `make -o check-node test-live` at 480b673c (disposable DB) | 592 passed |
| `make -o check-node test` at 480b673c | pytest 1676 passed (no pnpm here; CI ran web) |
| CI run 42151633050 | all jobs green; all security steps ran |
| Head re-read; `git status --untracked-files=no` | unchanged; clean |

Not re-run: lint, mypy and local Semgrep. The code is identical to R1, where they passed, and CI ran them
green at this head.

### Deferred conditions
- R1 P2 → M3f-3.
- PR 118 R1 P2 (narrow the label regex) → M3f-3, or a standalone follow-up if that comes sooner.

### Carried
- The owner's confirmation of "12, build" (PR 115 R1) is still open.
