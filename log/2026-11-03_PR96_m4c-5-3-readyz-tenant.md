# PR 96 — feat(jobs): M4c-5-3 /readyz checks that the deployment agency binds

- **Merged:** 2026-11-03 (13:11:08 UTC) · **Merge commit:** 91bd2266434bd282d3e613572715a7208618faa0 · **Branch:** feat/m4c-5-3-readyz-tenant
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-96.receipt on agent-logs (log-branch commit 637bfe4, receipt time 2026-11-03T13:09:44Z, before merge; reviewed head cd99cbd2da3fd560fca6d29d136b793240de6d6d, review-file hash 2f5e4ff97281ae75954066b5e99689b8f0f47d61, review commit e47131b)
- **Merge evidence:** `gh pr view 96` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head cd99cbd2
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-5 (last of three; #94, #95 before). M4c-5 complete.

## What changed
- `app/jobs/startup.py`: `tenant_bound()` runs `SELECT guard.current_agency(), (SELECT count(*) FROM agency WHERE id = %s)` inside `with_agency(<deployment agency>)` and is ready only for `(agency_id, 1)`; `database_ready()` requires it and also maps `RuntimeError` (config key errors) to not ready.
- Tests: `test_readyz.py` (readiness table gains `bound`; bind errors give `False`); `test_agency_live.py` (503 for an unseeded id and for a different token key).
- Runbooks `host-rebuild.md` (`/readyz` bullet) and `local-dev.md`; comments in settings and compose; the DECISIONS "M4c-5-3" entry.

## Why
Plan M4c-5 ("`/readyz` binds to the deployment agency"); spec §8.3. A mismatched `tenant_token_key` or a missing seed now fails the deploy health check instead of every tenant read quietly returning no rows.

## Review rounds
- R1: Approved (head cd99cbd). No findings.

## Deferred conditions
- None.

## Decisions worth keeping
- Readiness checks the binding on every probe, not only at start-up, because `/readyz` is what the deploy switch reads.
- Reviewer note (no action): each probe opens a write transaction (`pg_current_xact_id()` assigns an xid); negligible at probe frequency.

## Follow-ups
- Plan M4c-5 complete. Next per plan: M4c-6.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-5-3" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-5-3, last part of plan M4c-5)
- **Code review:** base (merge base) df6f107cdb3a8946ce91de9bcb00f8f6518854be (tree-equal to origin/main
  ac2eaa8, the PR 95 merge; `git diff df6f107 origin/main` is empty) · head
  cd99cbd2da3fd560fca6d29d136b793240de6d6d (one commit) · 9 files, +89 −14 · head re-checked at end: yes
  (unchanged). Detached review worktree `.agent/worktrees/review-91`; disposable DB (port 5441), removed
  after (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-5.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 96`
(builder), then merge. That closes plan M4c-5.

### What was checked
- **`tenant_bound()`** (`app/jobs/startup.py`) against plan M4c-5 and spec §8.3:
  - It binds through `with_agency()` only (TEN-09). It mints no token itself and doesn't touch the key.
  - `SKIW_DEPLOYMENT_AGENCY()` returns a `uuid.UUID`, and psycopg returns `uuid` columns as `uuid.UUID`,
    so `row == (agency_id, 1)` compares like types. The live 200 test proves that equality holds on a
    seeded DB.
  - `count(*) … WHERE id = %s` runs under the `agency` RLS predicate `id = current_agency()`. A count of 1
    therefore already implies the verifier gave this agency back. The `current_agency()` column is a
    redundant second check, and that redundancy is harmless.
- **`database_ready()` error handling:**
  - `with_agency()` refusing inside an open atomic block raises `TransactionManagementError`. That class is
    a `ProgrammingError`, so `DatabaseError` catches it.
  - A non-UUID can't occur, because `deployment_agency()` returns a `uuid.UUID`.
  - `config.env`'s `MissingSettingError` and `InvalidSettingError` are `RuntimeError`s, so the new catch is
    the right width.
  - Every failure gives 503 with the body `not ready`, and nothing is logged (UNI-09).
- **`pending_migrations()`** closes the connection in `finally`. `tenant_bound()` then opens a fresh
  connection in autocommit, so it isn't inside an atomic block.
- **Sync view under ASGI:** Django runs `readyz` in a thread. That's the same as before this PR.
- **Tests:**
  - The unit table gains `bound`.
  - ImproperlyConfigured, RuntimeError and OperationalError from the bind each give `False`.
  - Two live 503 tests: an unseeded configured id, and a different token key.
  - The live positive control `test_readyz_is_200_when_fully_migrated` now runs through
    `tenant_bound()`. So the 503 tests can't pass vacuously, for example from a fixture that always
    fails.
- **Runbooks** (UNI-16): the `host-rebuild.md` `/readyz` bullet and the `local-dev.md` sentence are correct.
  The stale "from M4c-5-3" line is gone.
- **DECISIONS** "M4c-5-3" is present, and its alternative (a check at start-up only) is rejected for a
  sound reason.
- Import direction `jobs` → `tenancy` is downward; the contracts are kept.

### Checks
- `make test-live` at cd99cbd on a disposable DB: 270 passed (matches the PR body).
- `test_readyz.py` (unit): 12 passed. Semgrep: 18 rules, 0 findings.
- Reviewer mutants, each reverted (the worktree is clean):
  - The return checks only `current_agency()` and ignores the count. This is killed by
    `test_readyz_is_503_when_the_agency_row_is_missing`.
  - `with_agency()` is dropped, so a plain cursor runs and the verifier gives NULL. This is killed by
    `test_readyz_is_200_when_fully_migrated`.
  - The builder's mutant, `database_ready()` without `tenant_bound()`, gives 6 failures (PR body).
  - A mutant that checks only the count, not the verifier column, is equivalent under RLS (see above), so
    it isn't a gap.

### Findings
None.

### Notes (no action)
- Each probe now opens a write transaction: `with_agency()` reads `pg_current_xact_id()`, which assigns an
  xid. Every tenant request does the same, and the probe runs every few seconds, so the effect on xid use
  is negligible.

### Follow-ups
- None from this PR. Plan M4c-5 is complete once this merges.
