# PR 98 — feat(tenancy): M4c-6a-2 TenantModel and the closed global table list

- **Merged:** 2026-11-03 (14:34:55 UTC) · **Merge commit:** a36f3feafcfd14e42c1c64840775ff2632a741d7 · **Branch:** feat/m4c-6a-2-global-list
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-98.receipt on agent-logs (log-branch commit fbcf430, receipt time 2026-11-03T14:34:00Z, before merge; reviewed head ca6733ddee439d655d654d2267afe7402db4e2b6, review-file hash a7dde6bab15246fc54a79a7b8928bb744a6a1782, review commit e3bab73)
- **Merge evidence:** `gh pr view 98` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head ca6733dd
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-6a (part 2 of 2; #97 before). M4c-6a complete.

## What changed
- `app/tenancy/models.py`: abstract `TenantModel` with `agency_id uuid` and `UniqueConstraint(agency_id, id)` named `<app>_<model>_agency_id_id_uq`.
- `app/tenancy/schema.py` (new): `GLOBAL_TABLES` (spec §4.1, schema-qualified) and `ROOT_TABLE = "public.agency"`.
- `app/jobs/tests/test_queue_grants.py`: imports the list; "every existing non-tenant table is on the list" (a listed table may not exist yet); the audited grant tables are pinned to the list.
- `app/tenancy/tests/test_template.py`: the `makemigrations` drift test (single `RemoveConstraint`) and the PR 97 R1 P3 boundary pair (63 accepted, 64 refused).
- The DECISIONS "M4c-6a-2" entry.

## Why
Plan M4c-6a; spec §4 conventions and §4.1. Every composite FK from `tenant_table()` (PR 97) needs `unique (agency_id, id)` on the parent, and Django must know the constraint so `makemigrations --check` catches drift.

## Review rounds
- R1: Approved (head ca6733d). PR 97 R1 P3 closed. One new P3 (test gap), deferred to M4c-6b.

## Deferred conditions
- P3 → M4c-6b: the global-list test passes vacuously if the tenant classification flags every table (mutant `HAS_AGENCY_ID` matches any column survives). Pin the classification (`tenant == set()` until M3d, or known globals in the checked remainder); M4c-6b's `check()` keeps a fixture where a listed global must classify as global.

## Decisions worth keeping
- The global list may name tables that later milestones create; the test requires existing ⊆ list, not equality.
- Waffle names (`waffle_flag`, `waffle_switch`, `waffle_sample`) are an assumption until M5 installs waffle.
- Mutant runs use `PYTHONDONTWRITEBYTECODE=1` and a cleared `__pycache__` (a same-size mutant restored in the same second left a stale .pyc during the build).

## Follow-ups
- M4c-6b: the P3 above; `check()` must test list membership before the "has `agency_id` → tenant" rule, since `bridge_session` is a listed global with `agency_id` (M14 creates it).
- M5 (waffle install): django-waffle also creates `waffle_flag_users` and `waffle_flag_groups`; add them if spec §4.1's "waffle tables" covers them (owner or spec call).
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-6a-2" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-6a, part 2 of 2)
- **Code review:**
  - **Base:** merge base 3506a1f633a0a34aa1a372411d84ccb93486ee6c. It is the PR 97 head and tree-equal to
    origin/main 2e9f707 (`git diff 3506a1f origin/main` is empty).
  - **Head:** ca6733ddee439d655d654d2267afe7402db4e2b6, two commits: `959493c` and `ca6733d`. 5 files,
    +165 −19. Head re-checked at the end: unchanged.
  - **Setup:** detached review worktree `.agent/worktrees/review-91`; disposable DB (port 5441), removed
    afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-6a.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 98`
(builder), then M4c-6b (deep tier), which carries the P3 below.

### PR 97 R1 P3 (63-character boundary): resolved
`test_the_name_limit_is_63_at_the_longest_derived_name` checks the 63-character limit at its edge:
- a 58-character column gives `t_<col>_fk` = 63 characters, which is accepted;
- a 59-character column gives 64 characters, which is refused with the `constraint` message.

I re-ran the `MAX_NAME = 64` mutant on `test_template.py`: 1 failed, 17 passed. The boundary test now
kills it. **Status:** closed.

### What was checked
- **`TenantModel`** against plan M4c-6a:
  - It is abstract, with `agency_id = UUIDField()` and `UniqueConstraint(agency_id, id)`.
  - The constraint name is `%(app_label)s_%(class)s_agency_id_id_uq`, so it is unique per model.
  - The plan test "`makemigrations --check` catches a removed unique constraint" is met. The autodetector,
    run on states with and without the constraint, gives a single `RemoveConstraint` with that name.
  - The test also documents the known Django pitfall: a subclass `Meta` that doesn't inherit
    `TenantModel.Meta` silently has no constraint. That case can't be seen as drift, because the
    constraint was never there. The backstop is M4c-6b, whose tenant-table rule requires
    `unique(agency_id, id)` and whose fail fixtures include its absence (plan §3 M4c-6b).
- **`GLOBAL_TABLES`** against spec §4.1, every row:
  - Every row is present and schema-qualified: `role`, `currency`, `form_template`, `django_session`,
    `bridge_session`, `auth_throttle`, `security_event`, the Procrastinate tables, `django_migrations`,
    `django_content_type`, the waffle tables and `guard.{tenant_mac_key, approval_mac_key,
    lookup_decoy_key}`.
  - `ROOT_TABLE = "public.agency"`.
- **`test_queue_grants.py`:**
  - It imports the list instead of keeping its own copy, as the plan says.
  - The rule is now "every existing table, minus the test-only tables, the root and tables with
    `agency_id`, is a subset of the list", as the plan says.
  - It checks that the guard schema is in scope: `guard.tenant_mac_key ∈ existing`.
  - A new test pins the audited grant tables (`TABLES`, `AUTH_TABLES`, `DELETE_ALLOW_LIST`) to the list.
- **DECISIONS** has an "M4c-6a-2" entry. The waffle-name assumption is stated and handed to M5.

### Checks
- `make test-live` at ca6733d on a disposable DB: 273 passed (matches the PR body).
- `app/tenancy/tests` + `test_queue_grants.py` (live and unit, bytecode off, cache cleared): 193 passed.
- Reviewer mutants, each reverted (the worktree is clean):
  - The `guard.*` entries were removed from `GLOBAL_TABLES`. This was killed: 1 failed.
  - `MAX_NAME = 64`. This was killed by the new boundary test: 1 failed.
  - **`HAS_AGENCY_ID` matched any column, so every table counted as a tenant table. This survived** (see
    the P3).

### Findings

### [P3] The global-list test passes vacuously if every table is classed as tenant
- **Category:** test gap
- **Evidence:**
  - `test_every_existing_global_table_is_in_the_closed_list` exempts every table that `HAS_AGENCY_ID`
    flags, and then checks the rest against the list.
  - I mutated the predicate to "has any column", so every table counts as a tenant table. The test
    still passes, because the remainder is empty.
  - The sanity assertion `{django_migrations, tenant_mac_key, agency} <= existing` checks only the
    `existing` set, not the classification.
- **Failure scenario:**
  - A later edit breaks the tenant classification, for example a wrong column name or a join that matches
    everything.
  - The test then stops checking the global list at all, and stays green.
  - An unlisted table with no `agency_id` and no RLS could then land unnoticed until M4c-6b's check
    exists.
  - This is test-only, and M4c-6b replaces it with the schema check, hence P3.
- **Required correction:** pin the classification. Until M3d adds the first tenant table, assert that
  `tenant == set()`. Or assert that known globals are in the checked remainder, for example
  `{"public.django_migrations", "guard.tenant_mac_key"} <= existing - TEST_ONLY_TABLES - {ROOT_TABLE} -
  tenant`. The M4c-6b schema check should keep the same guard: a fixture where a listed global must be
  classified as global.
- **Owner:** builder · **Disposition:** deferred to M4c-6b (the next PR, which reworks this
  classification into `check()`) · **Status:** open (deferred)

### Notes for later PRs (no action here)
- **M4c-6b:** `bridge_session` is a listed global that has an `agency_id` column (spec §4.1). So
  `check()` must test list membership *before* the "has `agency_id`, so tenant" rule, or it will demand
  RLS on `bridge_session` when M14 creates it.
- **M5 (waffle install):** django-waffle's `Flag` model has `users` and `groups` many-to-many fields. Its
  migrations therefore also create `waffle_flag_users` and `waffle_flag_groups`. Those aren't on the list
  yet. The existing-table test will fail loudly when waffle lands. Add them then, if spec §4.1's "waffle
  tables" covers them, which is an owner or spec call.

### Follow-ups
- M4c-6b: the P3 above and the `bridge_session` ordering note.
