# PR 88 — feat(tenancy): migrate writes the guard key tables as their owners (M4c-3b)

- **Merged:** 2026-11-03 (02:48:25 UTC) · **Merge commit:** 4cb5a908e06c6caa1baca307f1c68955eb295437 · **Branch:** feat/m4c-3-guard-key-writes
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-88.receipt on agent-logs (log-branch commit 18f28db, receipt time 2026-11-03T02:48:04Z, 21 s before merge; reviewed head 87a695a52aad4415e49441b0a58f72c088364617, review-file hash be4bd1d9bf5d0796d6135f52be31b34de32ef42c, review commit 9fce9e4)
- **Merge evidence:** `gh pr view 88` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 87a695a5
- **Drafted by:** Opus 5.5 sub-agent (deep tier); split, verified, R1 fix delegated to an Opus sub-agent, PR drafted by the Sonnet 5.5 builder · **Final verdict:** Approved with conditions (round 2)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 (unchanged) · **Plan:** docs/plans/2026-11-01-m4-core.md §3 M4c-3 (second half) · **Milestone:** M4-core, M4c-3b

## What changed
`migrate` now writes `guard.tenant_mac_key` and `guard.lookup_decoy_key` from the host key files through a `post_migrate` receiver (`tenancy.keys.write_guard_keys`), one transaction, as the tables' NOLOGIN owners via `owner_role()`. Changed bytes and a re-listed retired version stop `migrate`; unlisted MAC versions are retired, unlisted decoy versions deleted. Key bytes go as bound parameters on a server-binding cursor. Runbooks (`host-rebuild.md`, `local-dev.md`) and DECISIONS entry "M4c-3b".

## Why
Second half of plan M4c-3 (spec §4.1, §8.4 H4: only `migrate` writes the key tables; TEN-02 no migrator grant; TEN-10). M4c-4a's `guard.current_agency()` reads these tables.

## Review rounds
- R1: Revision required.
  - [P2] `owner_role` left the owner role after a caught Python error → `try/finally` with `RESET ROLE` unless the transaction is in error; unit and live tests, red first.
  - [P2] owner gate, spec-change PR not named → owner chose spec v1.21 before M4c-4a merges; recorded in PR body and DECISIONS.
  - [P3] DECISIONS duplication/scope/date → trimmed and re-dated; [P3] `make clean` wording → fixed; [P3] vacuous assertion → removed; [P3] `flush` sends `post_migrate` → docstring note; [P3] handoff drift → fixed.
- R2: Approved with conditions. One new P3 (reset only when `INTRANS`), optional.

## Deferred conditions
- Spec v1.21 (plan §9 items 2 and 6 plus the 2026-11-03 retired-version rule) approved by `review spec` and reconciled into PROJECT.md before M4c-4a merges. The M4c-4a review will not approve without it.

## Decisions worth keeping
- Owner decision 2026-11-03: a retired `tenant_mac_key` version listed again stops `migrate`, whatever the bytes, no override flag (DECISIONS "M4c-3b").
- `owner_role` and `as_owner` are the only places the migrator issues `SET ROLE`; the helper itself now guarantees the reset.
- Rotation is a two-step runbook (add version, deploy, then retire). Removing the old line in the same deploy retires it while the old digest still serves; matters once M4c-4a reads the table, so add a warning in `host-rebuild.md` then.
- Local checks ran without the web steps (Node 26 only); CI ran everything and was green on the final head.

## Follow-ups
- Spec v1.21 (`spec`, then `review spec`, then `setup`) before M4c-4a is approved.
- Optional P3: `owner_role` reset only when `INTRANS` (any later tenancy PR).
- M4c-4a (deep tier): change `test_auth_lookup_definer_live.py` (drop negative control and USAGE grant/revoke), grant USAGE on `guard` to `skiw_app`; M3e definers cannot use `INSERT … RETURNING`; add the rotation warning to `host-rebuild.md`.
- Still open: PR 85 P3 long-string regex → M4c-4b; PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; M2c owner Q1=A, Q2=A still to record in DECISIONS; Dependabot alert security/dependabot/1 not looked at.

## Appendix — final review round
# Review — PR #88

## Round 2 — 2026-11-03 · scope: slice (M4c-3b)
- **Code review:** base (merge base) 1f7ecf733bf2f40acc43337d812d7b071b7b365d · head 87a695a52aad4415e49441b0a58f72c088364617 (descends from R1 head 60a1e49; one commit `87a695a Review R1 fix: owner_role resets the role when the block raises; DECISIONS records the v1.21 deadline`) · head re-checked at end: yes (unchanged); review checkout clean
- **Spec:** v1.20, hash 92841ba5 (unchanged).

**Verdict:** Approved with conditions
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 88` (builder), then the v1.21 spec amendment (`spec`, then `review spec` on the deep tier) before M4c-4a.

### Findings (R1 status, re-inspected)
- **[P2] `owner_role` leaves the owner role after a caught error: resolved.** `app/tenancy/ddl.py:29-44` now does `try: yield / finally: RESET ROLE` unless `transaction_status == INERROR`, and the docstring matches. New tests: the unit test `test_owner_role_resets_on_an_exception_unless_the_transaction_is_in_error` (INTRANS resets, INERROR sends nothing) and the live test `test_owner_role_resets_when_the_block_raises_and_is_caught` (both tables: after a caught error `current_user` = migrator and a plain SELECT is denied). Re-ran the R1 probe on a disposable DB: it now gives `('skiw_migrator', 'skiw_migrator')`.
- **[P2] Owner gate, spec-change PR: resolved (deadline recorded).** The PR body under "Open items" and DECISIONS "M4c-3b" "Still owed" both say: the spec change for plan §9 items 2 and 6, plus the retired-version rule, lands in spec v1.21 **before M4c-4a merges**, and the M4c-4a review checks it. This matches the owner's answer.
- **[P3] DECISIONS duplication, scope and date: resolved.** Item (5) now points to M4c-3a's entry, "Scope / affects" lists this PR's files, and the date is 2026-11-03.
- **[P3] `make clean` wording: resolved.** The line now says "deletes the local database volume, all local data".
- **[P3] Vacuous assertion: resolved.** It was removed. The new live test covers the reset directly.
- **[P3] `flush` trap: resolved (documented).** There's now a note in `keys.py`'s docstring.
- **[P3] Handoff drift: resolved.** `.agent/handoff.md` §1 now says pushed and open at 87a695a.

### New finding
### [P3] `finally` sends `RESET ROLE` on a connection that has failed outright
- Evidence: `ddl.py:43` checks `!= INERROR`. If the connection is lost (`UNKNOWN`) or idle, `RESET ROLE` raises a second error that replaces the block's own error. The role can't leak in either state, because the session or transaction is already gone, so the only cost is a less helpful traceback.
- Correction (optional, any later tenancy PR): `if status == pq.TransactionStatus.INTRANS:`.
- Owner: builder

No prompt-injection text in the new commit or the edited PR body.

### Self-check audit
Same applicability list as R1. TEN-02 is now a full pass: the helper itself guarantees the reset, not just its callers. TEN-10 passes against the plan, with the spec wording tracked under the v1.21 condition. No disagreement.

### Verification performed
| Command / check | Result |
|---|---|
| `make -o check-node test-live` on a disposable DB (own Compose project, port 5441; volume removed) | 202 passed (R1 200 + 2 new live cases) |
| R1 `owner_role` probe, re-run | role back to `skiw_migrator` after a caught error |
| `make -o check-node host-test` | 841 passed |
| pytest python part of `make test` | 1468 passed (R1 1466 + 2 unit cases) |
| mypy | no issues, 151 files |
| ruff check / format --check | clean / 202 files |
| lint-imports | 10 kept, 0 broken |
| Semgrep custom / `--test` | 14 rules, 115 files, 0 findings / 14/14 |
| `git diff --check`; `v<n>:<base64>` over added lines | clean; 0 hits |
| CI run 41563805373 on 87a695a | success (checks, security, image, host) |
| Not run locally | `host-test-live` (CI host job green), web steps (Node 26), gitleaks binary, registry Semgrep (CI security job) |

### Residual risks and test gaps
- As in R1: no lock against concurrent `migrate` runs (harmless with a single file input). Rotation safety depends on following the two-step runbook once M4c-4a reads the table.

### Required before merge
- None.

### Deferred conditions
- **Spec v1.21** (plan §9 items 2 and 6, plus the 2026-11-03 retired-version rule) is approved by `review spec` and reconciled into PROJECT.md (`setup`) **before M4c-4a merges** (owner decision 2026-11-03). The M4c-4a review will not approve without it.

### Optional improvements
- P3 `owner_role` reset only when `INTRANS`.

