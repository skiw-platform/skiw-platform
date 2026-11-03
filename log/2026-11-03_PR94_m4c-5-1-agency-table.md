# PR 94 — feat(tenancy): M4c-5-1 agency root table, RLS and grants; private token-key cache

- **Merged:** 2026-11-03 (11:40:19 UTC) · **Merge commit:** 6af26f5d560ebe55ba00a9f7d623b1aed7636c00 · **Branch:** feat/m4c-5-1-agency-table
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-94.receipt on agent-logs (log-branch commit f92e7ec, receipt time 2026-11-03T11:31:35Z, before merge; reviewed head 8553746c4f37259d80f5ad6b8e98eae84d5dedf3, review-file hash 51d4bf7127010516f7bf032ea899ee0fd40c98b7, review commit ea5b24c)
- **Merge evidence:** `gh pr view 94` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 8553746c
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-5 (first of three stacked PRs; next #95, #96)

## What changed
- `app/tenancy/migrations/0004_agency.py` (new), with the `Agency` model:
  - `agency` (`id` uuid PK, `name`, `timezone` default `Asia/Kuala_Lumpur`, `data_region` default `MY`), owned by `skiw_migrator`;
  - ENABLE + FORCE RLS; restrictive `agency_tenant` FOR ALL TO `skiw_app` and permissive `agency_sel` FOR SELECT, both on `id = (SELECT guard.current_agency())`;
  - `GRANT SELECT` to `skiw_app` only; the reverse removes all of it.
- `app/tenancy/seed.py` (new): `_lift` (migrator-only, in a transaction, lock, NO FORCE), `_restore` (FORCE, checked), `stored_ids`, and the test-only `insert_agency`.
- PR 93 R1 P3:
  - `binding.token_keys()` → private `_token_keys()`; start-up calls `require_token_key()`, which returns nothing;
  - Semgrep `tenancy-token-key-reader` also flags `_token_keys`; new rule `tenancy-token-key-source` flags `"TENANT_TOKEN_KEY"` / `"TENANT_TOKEN_KEY_FILE"`; excludes pinned (8 rules).
- Tests: `test_agency_live.py` (10: isolation, writes denied, root template, FORCE-on-failure, refusals); `test_queue_grants.py` lists `agency` as the root table.
- The plan's Semgrep table; the DECISIONS "M4c-5-1" entry.

## Why
Spec v1.21 §4.1 `agency`, §4.2 schema check (2); plan M4c-5; PR 93 review R1 P3. Split from M4c-5 by the plan §1 rule (≈ 700 lines).

## Review rounds
- R1: Approved (head 8553746). No findings.

## Deferred conditions
- None. The reviewer's follow-ups (seed reads after `_lift`, second-agency refusal and FORCE-on-failure tests for the seed, `SKIW_DEPLOYMENT_AGENCY_*` wiring and runbook) are in #95 (M4c-5-2).
- Reviewer note, not a finding: `getattr(binding, "_token_keys")` still passes the Semgrep rule (hygiene only; the MAC is the boundary).

## Decisions worth keeping
- No policy names `skiw_migrator`; writes lift FORCE inside their own locked transaction and put it back before commit, so a failure rolls the lift back too.
- `require_token_key()` returns nothing, so only `with_agency()` holds the key.

## Follow-ups
- #95 (M4c-5-2) retargeted to main; review it next, then #96.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1. (The M2c Q1/Q2 follow-up is dropped: already in DECISIONS M3a item (2).)
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-5-1" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-5-1; first of three stacked PRs for M4c-5)
- **Code review:** base (merge base) 54d7387004975b922e65b882896a76ddcd4780fe (origin/main, PR 93 merged) ·
  head 8553746c4f37259d80f5ad6b8e98eae84d5dedf3 (one commit) · 14 files · head re-checked at end: yes
  (unchanged). Review worktree `.agent/worktrees/review-91`, detached at the head; disposable DB (port 5441)
  removed after; worktree clean.
- **Spec:** v1.21, hash d95cb271 (= PROJECT.md §2). Plan M4c-5 "Model and policy" and the `insert_agency` twin.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 94`, then
M4c-5-2 (the migrate-time seed and host config) on the deep tier.

### What was checked
- **Table and policies** (`0004_agency.py`) against spec §4.1 `agency` and plan M4c-5:
  - columns `id` uuid PK with no app default (the id comes from host config), `name`, `timezone` with DB
    default `Asia/Kuala_Lumpur`, `data_region` with DB default `MY`;
  - ENABLE + FORCE; restrictive `agency_tenant` FOR ALL TO `skiw_app`, USING and WITH CHECK
    `id = (SELECT guard.current_agency())`; permissive `agency_sel` FOR SELECT with the same predicate;
    `GRANT SELECT` to `skiw_app` only. Owner, ACL and both policies are pinned
    (`test_the_table_matches_the_root_template`). The reverse removes all of it and is exercised by the
    0004→0001 migrate-back in `test_guard_schema_live`.
- **Isolation:** with no token `skiw_app` sees nothing; under A and under B it sees only that row;
  INSERT, UPDATE and DELETE are denied even for its own row (no grant).
- **`tenancy.seed`:** `_lift` checks `session_user = current_user = skiw_migrator` and an open transaction,
  then `lock_timeout 5s`, `ACCESS EXCLUSIVE`, `NO FORCE`. `_restore` puts FORCE back and asserts
  `relforcerowsecurity`. The lock means no other session sees the lifted window, and a raise rolls the DDL
  back too: tested with a NOT NULL failure after the lift, plus non-migrator and autocommit refusals. The
  owner sees 0 rows under FORCE, which is why every read for the seed must come after the lift. That matches
  plan M4c-5 "Rules for the seed".
- **PR 93 R1 P3: resolved.** `token_keys()` is now private `_token_keys()`; start-up calls
  `require_token_key()`, which returns `None`. `tenancy-token-key-reader` also flags `$S._token_keys` and
  its imports. New `tenancy-token-key-source` flags the strings `"TENANT_TOKEN_KEY"` / `"TENANT_TOKEN_KEY_FILE"`
  outside settings, `keys.py` and the key tests. The excludes are pinned and the plan table is updated.
  (`getattr(binding, "_token_keys")` would still pass. Not worth another round: this is hygiene, and the MAC
  is the boundary.)
- **`test_queue_grants.py`:** `agency` is the one named root table until M4c-6b's schema check (plan).
- **Local runs:** `make test-live` 258 passed; `semgrep --test` 18/18; `semgrep --config semgrep/ --error app`
  exit 0.

### Findings
None.

### Follow-ups (M4c-5-2, already in the plan)
- The seed's id read must come after `_lift` (it does in `stored_ids`'s contract). Also check the
  second-agency refusal test and the FORCE-on-failure test for the seed itself, and the `SKIW_DEPLOYMENT_AGENCY_*`
  host wiring and runbook (UNI-16, which this PR marks n/a).
