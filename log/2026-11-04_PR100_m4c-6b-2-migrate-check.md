# PR 100 — feat(tenancy): M4c-6b-2 run the tenancy schema check in the migrate step

- **Merged:** 2026-11-04 (03:25:34 UTC) · **Merge commit:** 97d59fba217fd078fad34863bc828abb58b4c9ee · **Branch:** feat/m4c-6b-2-migrate-check
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-100.receipt on agent-logs (log-branch commit 0873f85, receipt time 2026-11-04T03:23:56Z, before merge; reviewed head eef4dca9907bb2e40638a44e4a284d18b6a04148, review-file hash 8cd588e4536f203c4247745c5d201ae9588c8a41, review commit 0809561)
- **Merge evidence:** `gh pr view 100` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head eef4dca9
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-6b (part 2 of 2)

## What changed
- `manage.py check_tenancy_schema` (new): runs `check()` on the default connection, prints each violation as `<table>: <reason>` on stderr and fails with `CommandError`; passes no `extra_allowed`.
- `Makefile`: `migrate` ends with the check; new `make db-test` (migrate, live tenancy tests, the check again).
- `infra/host/skiw_host/deploy.py`: the check runs in the new image right after `migrate`, bounded by `TOOL_S`; a failure exits 1 before the switch, the old digest keeps serving, output withheld.
- Runbooks: `host-rebuild.md` "The tenancy schema check (M4c-6b)"; `deploy.md` step 4.
- Tests: `test_check_command_live.py` (new, 2); `test_deploy.py` step order and a failed-check case; `test_check_live.py` PR 99 R1 P3 fixtures (22).
- The DECISIONS "M4c-6b-2" entry.

## Why
Spec §4.2 "Schema check (M4)"; plan M4c-6b: "runs last in the migrate step, so a bad schema fails CI and stops a deploy before the switch". Second half of the M4c-6b split.

## Review rounds
- R1: Approved (head eef4dca). PR 99 R1 P3 closed. One new P3 (docs), deferred to M4c-7a. The reviewer also probed the Makefile wiring with an unlisted table: `make migrate` failed, then passed after the drop.

## Deferred conditions
- P3 → M4c-7a: `docs/runbooks/local-dev.md` — extend the `make migrate` row with "then `check_tenancy_schema`", add a `make db-test` row, and one sentence on a leftover `jobs_probe`/`files_probe` after an interrupted `make test-live` (drop it as the migrator, or `make clean`).

## Decisions worth keeping
- The check is a separate step after `migrate`, not a post-migrate signal (which would run on `migrate --plan` and on test databases).
- Bounded (read-only), unlike `migrate`.
- A rollback runs neither `migrate` nor the check (reviewer note: an older image's list could wrongly flag newer tables).

## Follow-ups
- M4c-7a: the P3 above. M4 done-when "Schema check and fixtures" is met with this merge.
- Owner ASK still open: may PROJECT.md §7's `pending M4` line name `make db-test`? (asked at PR 99 and PR 100; if yes, it lands in M4c-7a).
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1; M5 waffle m2m tables (owner/spec call).
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-6b-2" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M4c-6b, part 2 of 2)
- **Code review:** base (merge base) 99c6271fc580491aef3d5b85e22fe069270a07b4 (origin/main, PR 99 merged)
  · head eef4dca9907bb2e40638a44e4a284d18b6a04148 (one commit) · 11 files, +175 −6 · head re-checked at
  end: yes (unchanged). Detached review worktree `.agent/worktrees/review-91`; disposable DB (port 5441),
  removed after (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-6b.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 100`
(builder), after the owner answers the PROJECT §7 ASK. Then M4c-7a (deep tier), which carries the P3
below.

### PR 99 R1 P3 (root branch and global policy rules unpinned): resolved
`test_check_live.py` now has one case per root rule on the real `agency`:
- the restrictive policy dropped;
- `agency_id` added;
- the PK replaced by a unique constraint.

It also has `test_the_policy_rules_apply_to_a_listed_global`: `bridge_session` with a `current_setting`
policy and a PUBLIC `true` policy gives all three reasons. Each new case expects its exact reason, so the
four mutants that survived in PR 99 R1 are now killed (by construction of the expected lists).
**Status:** closed.

### What was checked
- **The command:**
  - It runs `check()` on Django's default connection. Under `make migrate` and on hosts, that is
    `skiw_migrator`.
  - It writes violations to stderr, one `<table>: <reason>` per line, and then raises
    `CommandError` with the count. Otherwise it prints `ok`.
  - It passes no `extra_allowed`, so a leftover probe table fails.
  - Its output names catalog objects only (UNI-09).
- **Makefile:**
  - `migrate` ends with the check, so `test-live`, `e2e`, `dev` and CI all run it.
  - `db-test` runs migrate, then the live tenancy tests, then the check again. That second check proves
    the fixtures leave nothing behind.
- **Deploy:**
  - The step is in the new image, right after `migrate`, and before the status-line removal and the
    switch.
  - It is bounded by `TOOL_S`.
  - A failure exits 1. The old digest keeps serving, the journal names the step, and the tool output is
    withheld (the test asserts that `public.loose` is not on stderr).
  - The check runs on the new image, so its `GLOBAL_TABLES` matches the migrations that were just
    applied.
  - A rollback runs neither `migrate` nor the check. That is right: the schema is unchanged, and an
    older image's list could wrongly flag tables that later migrations added.
- **Runbooks:**
  - The `host-rebuild.md` text matches the plan: the bad table stays, CI runs the check first, the fix is
    a forward migration, and there is never a reverse migration on the host.
  - `deploy.md` step 4 names the check.
  - `local-dev.md` is not updated (see the P3).
- **DECISIONS** has an "M4c-6b-2" entry. The rejected alternative, a post-migrate signal that would run
  on `migrate --plan` and on test databases, is rejected for a sound reason.

### Checks
- `make test-live` at eef4dca on a disposable DB: 297 passed. Migrate printed `tenancy schema check: ok`.
- **Makefile wiring probe**, which the builder didn't mutation-test:
  - I created an unlisted `public.zz_review_loose` table as the migrator. `make migrate` then printed
    `public.zz_review_loose: not on the global list and has no agency_id column` and
    `CommandError: tenancy schema check: 1 violations`, and stopped with `make: *** [migrate] Error 1`.
  - After I dropped the table, `make migrate` printed `ok` again.
- `make db-test`: the check said ok, then 144 passed, then the check said ok again (matches the PR body).
- `make host-test`: 846 passed (matches).
- The worktree is clean.

### Findings

### [P3] `local-dev.md` doesn't mention the check, `make db-test`, or the leftover-probe failure
- **Category:** docs (UNI-16)
- **Evidence:**
  - The `make migrate` row in `docs/runbooks/local-dev.md` (`:32`) still lists only the migrations,
    `makemigrations --check` and `lintmigrations`.
  - The make-target table has no `make db-test` row.
  - `jobs_probe` and `files_probe` are created by session fixtures and dropped at teardown. The command
    deliberately doesn't allow them.
- **Failure scenario:**
  - A developer interrupts `make test-live`, for example with Ctrl-C or a crashed run.
  - The probe table stays behind, and every later `make migrate`, `make dev` or `make test-live` stops
    with `public.jobs_probe: not on the global list …`.
  - The local runbook doesn't explain why, or that `DROP TABLE` (as the migrator) or `make clean` fixes
    it.
- **Required correction:**
  - Extend the `make migrate` row with "then `check_tenancy_schema`".
  - Add a `make db-test` row.
  - Add one sentence on the leftover-probe case and its fix.
- **Owner:** builder · **Disposition:** deferred to M4c-7a (the next PR), or fixed here at the builder's
  choice · **Status:** open (deferred)

### Owner ASK (relayed, not decided by the reviewer)
- The PR asks whether PROJECT.md §7's `pending M4` line (`agents/PROJECT.md:107`) may now name
  `make db-test`. The target exists and passes, so the reviewer sees no technical blocker. The decision
  is the owner's.
- If the answer is yes, the line changes in this PR or the next one, and that review checks it.

### Follow-ups
- M4c-7a: the P3 above. M4 done-when "Schema check and fixtures" is met once this merges.
