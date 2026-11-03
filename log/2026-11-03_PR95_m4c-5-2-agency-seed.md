# PR 95 — feat(tenancy): M4c-5-2 migrate-time seed of the one deployment agency

- **Merged:** 2026-11-03 (12:25:37 UTC) · **Merge commit:** ac2eaa83f33e92e28da30bd10b035cf819b3d246 · **Branch:** feat/m4c-5-2-agency-seed
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-95.receipt on agent-logs (log-branch commit 74a693a, receipt time 2026-11-03T12:06:55Z, before merge; reviewed head df6f107cdb3a8946ce91de9bcb00f8f6518854be, review-file hash 580d3a6bfabe07ae9ee59fce110aabe1d5ff8646, review commit 3b6cfe7)
- **Merge evidence:** `gh pr view 95` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head df6f107c
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-5 (second of three; first #94, next #96)

## What changed
- `app/tenancy/seed.py`: `seed_deployment_agency()` and `seed_after_migrate()`:
  - after every `migrate`, as `skiw_migrator`, in one transaction: lock, NO FORCE, read ids, then empty → insert, configured id present → nothing, anything else → `CommandError` naming the id and PROJECT §9;
  - FORCE back on and checked; never updates or deletes; skips when 0004 is unapplied.
- `app/tenancy/apps.py`: one `post_migrate` receiver, guard key writes first, then the seed (`keys.py` loses its own).
- Config: `config.env.deployment_agency()` / `settings.SKIW_DEPLOYMENT_AGENCY` for `SKIW_DEPLOYMENT_AGENCY_ID` (one canonical lowercase uuid) and `_NAME` (1–200 printable, no edge spaces).
- Values: a uuid per environment; names production "SK iWealth Sdn. Bhd.", staging "SK iWealth (staging)" (owner), local "Local agency", CI "CI agency".
- Wiring: host `migrate` and `x-app-env`, local `app` / `worker`, all `:?`.
- Tests: `test_agency_live.py` (+10 seed tests), `test_deployment_agency.py` (new), `test_compose_config.py`.
- Runbooks `host-rebuild.md` ("The deployment agency") and `local-dev.md`; the DECISIONS "M4c-5-2" entry.

## Why
Spec v1.21 §4.1 `agency`; plan M4c-5; owner Q2 (a); PROJECT §9 second-agency gate.

## Review rounds
- R1: Approved (head df6f107). No findings.

## Deferred conditions
- None. The reviewer's follow-up (`/readyz` binds the deployment agency) is #96 (M4c-5-3).

## Decisions worth keeping
- A `post_migrate` seed, not a data migration: it runs every deploy and can refuse a changed id; the id stays out of code.
- The name is never upserted, so a host config typo cannot rename the live agency; renames wait for M5's admin helper.
- One receiver, because Django gives no order between two.

## Follow-ups
- The owner re-confirmed the agency names in builder chat (2026-11-03), as the reviewer asked.
- #96 (M4c-5-3) retargeted to main; review it next.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-5-2" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-5-2; second of three for M4c-5)
- **Code review:** base origin/main 6af26f5 (PR 94 merged; the merge base is PR 94's head 8553746, so the diff
  is only this PR's commit) · head df6f107cdb3a8946ce91de9bcb00f8f6518854be · 19 files · head re-checked at
  end: yes (unchanged). Review worktree `.agent/worktrees/review-91`, detached at the head; the two agency
  lines from `.env.example` were added to its local `.env`; disposable DB (port 5441) removed after; worktree
  clean.
- **Spec:** v1.21, hash d95cb271 (= PROJECT.md §2). Plan M4c-5 "Seed", "Host config", "Local and CI config".
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 95`, then
M4c-5-3 (`/readyz` tenant check).

### What was checked
- **Seed order** (`tenancy/seed.py`) against plan M4c-5 steps 1–8: lock with `lock_timeout 5s` → `NO FORCE`
  → read ids (after the lift, as the plan requires; the builder's mutant that reads first fails 2 tests) →
  empty: insert / configured id present: nothing / otherwise: `SecondAgencyRefused` → `FORCE` + `pg_class`
  check. It never updates or deletes, and the name is never upserted.
- **Failure paths:** every raise is inside `transaction.atomic`, so the insert and the FORCE lift roll back
  together. Errors become `CommandError`: the config message, the second-agency message (it names the id and
  PROJECT §9) or SQLSTATE only. `migrate` exits ≠ 0. If 0004 is unapplied the seed skips, so the existing
  migrate-back test still works.
- **One receiver** (`tenancy.apps.after_migrate`): key writes first, then the seed, sender `tenancy` only.
  Django gives no order between two receivers, so one is the right choice; a failed key write stops before
  any agency write. `keys.py` loses its own receiver; no other caller (grep).
- **Config** (`env.deployment_agency`): exactly one canonical lowercase uuid (a list, braces, `urn:` or upper
  case are refused); name 1–200 printable characters with no edge spaces; lazy, so tooling imports still work.
  18 unit tests pass.
- **Wiring:** host `migrate` plus `x-app-env` (`web`, `worker`) and local `app` / `worker`, all `:?`. Each of
  ci / staging / production has its own uuid (host test). The host env files go through
  `docker compose --env-file` (`deploy.py:187`), so the unquoted names with spaces and brackets are fine.
  `.env.example` quotes the local name because `make` sources it.
- **Names:** production "SK iWealth Sdn. Bhd." and staging "SK iWealth (staging)". DECISIONS "M4c-5-2"
  records these as the owner's (2026-11-03); the reviewer cannot see that answer, so the owner should confirm
  it.
- **Runbooks:** `host-rebuild.md` "The deployment agency" (first deploy, later deploys, never change the id,
  after a restore) and `local-dev.md` (including the `make clean` path for an old local DB holding only A
  and B) are correct.
- **Local runs:** `make test-live` 268 passed (10 new in `test_agency_live.py`); `test_deployment_agency.py`
  18 passed.

### Findings
None.

### Follow-ups
- M4c-5-3: `/readyz` binds `with_agency(<deployment agency>)` and requires the row to be visible, so a key or
  id mismatch fails the deploy check (plan M4c-5 "/readyz").
