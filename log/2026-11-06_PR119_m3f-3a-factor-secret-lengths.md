# PR 119 — feat(accounts): M3f-3a recovery-code key version in secret_ct, per-kind secret_ct lengths

- **Merged:** 2026-11-06T05:23:08Z · **Merge commit:** ad1daeccfaecd2534cccec7bd84603b1cdcb8b54 · **Branch:** feat/m3f-3a-factor-secret-lengths
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-119.receipt, commit 02ce8f2 (2026-11-06T05:05:11Z, 17 min 57 s before the merge; head 13a6463 and review hash 1449b79e match)
- **Merge evidence:** `gh pr view 119` (state MERGED, mergedAt 2026-11-06T05:23:08Z, mergeCommit ad1daec, headRefOid 13a6463c520580178f5be91a8885c0eb2edf830f = the reviewed head); `git merge-base --is-ancestor ad1daec origin/main` succeeded after a fresh fetch
- **Drafted by:** Claude Opus 5.5 sub-agent (deep tier: design and diffs) with a Claude Sonnet 5.5 builder session (files, runs, mutation tests) · **Final verdict:** Approved (round 2)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md (v1.21, d95cb271) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3f · **Milestone:** M3 (M3f-3, part a)

## What changed
Recovery rows now store the signing `tenant_source_key` version: `secret_ct` = 4-byte big-endian version, then the 32-byte HMAC-SHA-256 (36 bytes). `accounts.0010_factor_secret_lengths` adds per-kind CHECKs: a `totp` row's `secret_ct` is exactly 48 bytes and a `recovery` row's exactly 36, neither NULL. The runbook "Rotating `tenant_source_key`" gains a break-glass report (a `PGPASSFILE`-wrapped SELECT run as `postgres`) that counts users per signing version, a second SELECT that lists one version's users, a planned-rotation rule and an emergency path. `isolation_cases.py` and the factor fixtures changed with the CHECKs. DECISIONS "M3f-3a"; 18 of 18 mutants killed, plus 6 of 6 for the R1 fix.

## Why
PR 117 R1 P2 (the operator could not tell which users a key version still signs) and PR 116 R1's optional per-kind length CHECK; both had to land before any route can generate recovery codes or store TOTP secrets (M3f-3b onward). Spec §4.1 `user_factor` (C3), D7, UNI-15, UNI-16.

## Review rounds
- R1: Revision required: [P2] the runbook report ran `psql -U postgres` with no password and fails against the host's scram `pg_hba` → the report runs behind the `restore.md` `PGPASSFILE` wrapper (0600 file from `/run/secrets/postgres_password`, removed on exit); SQL unchanged; the pin test also checks the wrapper. [P3] no way to find the users → a second SELECT listing emails per version, run by a live test. [P3] name the operator read → the runbook calls it a break-glass read.
- R2: Approved. Fix commit touched only the runbook, two test files and DECISIONS; the reviewer ran both runbook blocks against `postgres:17.11` with the host hba rules and a password containing `:` and `\`. The owner's "12" (PR 115 R1) was confirmed directly to the reviewer and closed.

## Deferred conditions
none

## Decisions worth keeping
- Recovery `secret_ct` = 4-byte big-endian key version || MAC; the version is in clear and outside the MAC (a row whose version was edited matches no candidate). `RECOVERY_VERSION_BYTES` = 4 because `tenant_source_key` versions run to 999999.
- `CHECK (NOT (kind = k) OR (length(secret_ct) = n AND secret_ct IS NOT NULL))`: the explicit `IS NOT NULL` is needed because a CHECK passes on NULL. Passkey rows are unchecked (M3g).
- A host `psql` as `postgres` needs a `PGPASSFILE`: `pg_hba` is scram on the socket, the dev DB is trust, so a local run hides the failure. Test any such runbook command against a container with the host hba lines.
- Model-only edits are not mutants for a CHECK: the DB keeps the migration's constraints. Mutate the migration, migrate back to the previous number and forward again.
- The lasting decisions are in the merged DECISIONS ("2026-11-06 — M3f-3a"); nothing missing.

## Follow-ups
- PR "S" (`fix/gitleaks-label-regex`): narrow `.gitleaks.toml` to `^skiw(?:-[a-z]{2,12}){1,4}-v[0-9]{1,6}$` with tests (PR 118 R1 P2).
- Owner decisions still open: confirm the six-PR M3f-3 plan; confirm D8 (factor add/remove/regenerate on an active session) moves to M3h, which must carry AUTH-07; and the TOTP-or-email question below.
- ASK-1 was answered "Totp is required, passkey as optional" and ASK-2 "SKIW Assistant {email}" (issuer `SKIW Assistant`, account the user's email). ASK-1 departs from spec D7 (mandatory passkeys; owner/admin passkey): raise it in 3b-1's PR and ask for a spec amendment. After those answers the owner asked whether the second factor should be an emailed code (for an automation that reads the mailbox) instead of TOTP; undecided. Options given: keep TOTP and let the automation compute codes from the secret; email codes for the automation account only; email codes for everyone (spec change; rework 3b-1 to 3c-2). 3b-1 waits on this.

## Appendix — final review round
## Round 2 — 2026-11-06 · scope: slice (M3f-3, part a)
- **Code review:** base `main` 64687fe6ead851fe6a6101f4bfca0d309df88eff (merge base unchanged) · head
  13a6463c520580178f5be91a8885c0eb2edf830f (R1 head 3d314659 + one commit "Review R1 fix: runbook version
  report can't run on a host") · head re-checked at end: yes, unchanged.
  - **Where:** detached worktree `.agent/worktrees/review-119-13a6463c`, disposable DB on :5442; a
    throwaway `postgres:17.11` container with the host `pg_hba` rules. All removed.
- **Spec:** v1.21, hash d95cb271 (unchanged).
- **CI (run 42161591537, head 13a6463c):** checks, security, image, host: pass. publish, deploy-staging:
  skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 119` (builder), then Ying merges.

### R1 findings
- **P2 (report can't run on a host): resolved.** I re-inspected and ran it.
  - The fix commit touches only the runbook, two test files and DECISIONS. Code and migration are
    unchanged from R1.
  - The runbook now defines `compose()` and a `pg=` wrapper: a `umask 077` temp `PGPASSFILE` built from
    `/run/secrets/postgres_password` with `:` and `\` escaped, a `trap` that removes it, and the
    password never in argv or env. This is the same pattern as `restore.md`. Both SELECTs are fed to
    `sh -c "$pg"`.
  - **Run verbatim:** I extracted the `pg` literal and both SQL blocks from the runbook at 13a6463c and
    ran them through `docker exec -i … sh -c "$pg"` against `postgres:17.11` with the host hba lines.
    The password contained `:` and `\`. The seeded data was user a (10 codes, v1), users b and c (10
    each, v999999), and a TOTP row with a `00000001` lookalike prefix.
    - Count report: `1|1`, `999999|2`, exit 0.
    - User list for v1: `a@x` only (the TOTP row is ignored by the kind filter), exit 0.
    - `/tmp` is empty afterwards: the password file was removed.
  - The pinning test now also requires the `PGPASSFILE` wrapper and the secret path. The builder reports
    6 extra mutants, 6 killed.
- **P3 (no way to find the users): resolved.** There's a second SELECT listing emails per version. It is
  tested live (users per version match), pinned to the runbook and run by me above. The emails go to the
  operator's terminal in a break-glass read, which is acceptable for contacting the users (no log or
  file).
- **P3 (name it in the ops-access list): resolved.** The runbook and DECISIONS call it "a break-glass
  read (one SELECT, no writes) as `postgres` over the `db` socket".

### Owner item closed
- **PR 115 R1 "12, build":** Ying confirmed directly in this session on 2026-11-06: "Confirm 12 min
  char". `SKIW_PW_MIN_LENGTH` = 12. Closed.

### Findings
None open. No injection attempts.

### Verification performed
| Command / check | Result |
|---|---|
| `git diff 3d31465 13a6463` | runbook, 2 test files, DECISIONS only |
| Runbook blocks run verbatim vs `postgres:17.11` + host hba | both exit 0, correct output, no temp file left |
| `make -o check-node test-live` at 13a6463c | 602 passed; `tenancy schema check: ok` |
| `make -o check-node test` | pytest 1679 passed (+1: the pin test is now parametrised); no pnpm here |
| `make -o check-node lint` | ruff, format clean; Semgrep 0 findings |
| `git diff --check 64687fe...13a6463` | clean |
| Head re-read; `git status --untracked-files=no` | unchanged; clean |

### Still open elsewhere (not this PR)
- PR 118 R1 P2 (narrow the label regex): PR "S" in the M3f-3 sequence.
- Owner decisions from R1: the six-PR M3f-3 plan; D8 (factor changes on an active session → M3h, which
  must carry AUTH-07); ASK-1 and ASK-2 before 3b-1.
