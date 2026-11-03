# PR 97 — feat(tenancy): M4c-6a-1 the tenant_table() template

- **Merged:** 2026-11-03 (14:11:13 UTC) · **Merge commit:** 2e9f707a4b58ec02e0e3089623d4dd9806401bb2 · **Branch:** feat/m4c-6a-1-tenant-template
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-97.receipt on agent-logs (log-branch commit 13e5c4e, receipt time 2026-11-03T14:07:39Z, before merge; reviewed head 3506a1f633a0a34aa1a372411d84ccb93486ee6c, review-file hash cb6a4e1a3f12109aa0df534c42502e2d4a66e141, review commit b4fcdb5)
- **Merge evidence:** `gh pr view 97` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 3506a1f6
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-6a (part 1 of 2; M4c-6a-2 stacked)

## What changed
- `app/tenancy/template.py` (new): `tenant_table(table, *, commands, composite_fks=())` returns one reversible `RunSQL` per spec §4.2 step — the `agency(id)` FK, composite FKs `(agency_id, col) → parent(agency_id, id)`, ENABLE + FORCE with the restrictive `<table>_tenant` policy, one permissive policy per granted command, and the matching `skiw_app` grant. `tenant_table_sql()` gives the same steps as typed tuples. Names are checked, never quoted.
- Tests: `test_template.py` (16 unit, incl. the spec-text test parsed from the spec file and the migration linter in both directions); `test_template_live.py` (2: catalog shape and exact reverse; composite FK refuses another agency's parent).
- The DECISIONS "M4c-6a-1" entry.

## Why
Plan M4c-6a; spec §4 and §4.2. M4c-6a came to ≈ 550 lines against the ≈ 450 split rule, so the template ships first and `TenantModel` + the closed global list follow in M4c-6a-2.

## Review rounds
- R1: Approved (head 3506a1f). One P3 (test gap), deferred to M4c-6a-2.

## Deferred conditions
- P3 → M4c-6a-2: pin the 63-character name limit at its boundary (a longest derived name of exactly 63 accepted, 64 refused); the mutant `MAX_NAME = 64` survives today.

## Decisions worth keeping
- `tenant_table_sql()` added beyond the plan so tests read the SQL without Django; a test pins `tenant_table()` to it.
- The ACL reverse leaves an explicit owner entry where the ACL was NULL; effective privileges are identical, so tests compare `coalesce(relacl, acldefault('r', relowner))`.
- Reviewer notes (no action): a composite FK on a nullable column is MATCH SIMPLE (NULL skips it; the `agency_id` FK still holds); self-reference works; a reserved-word name passes the regex but fails loudly at migrate.

## Follow-ups
- M4c-6a-2 (`feat/m4c-6a-2-global-list`, 959493c, pushed): add the P3 boundary test; `TenantModel` with `UniqueConstraint(agency_id, id)` and the `makemigrations --check` drift test; run host-test-live; open its PR against main.
- PR 97 body said 15 unit tests; it is 16 (count slip).
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-6a-1" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-6a, part 1 of 2)
- **Code review:** base (merge base) 91bd2266434bd282d3e613572715a7208618faa0 (origin/main, PR 96 merged)
  · head 3506a1f633a0a34aa1a372411d84ccb93486ee6c (one commit) · 4 files, +409 · head re-checked at end:
  yes (unchanged). Detached review worktree `.agent/worktrees/review-91`; disposable DB (port 5441),
  removed after (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-6a.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 97`
(builder), then M4c-6a-2 (deep tier), which carries the P3 below.

### What was checked
- **Against plan M4c-6a, `tenant_table()` items:**
  - the FK to `agency(id)`;
  - composite FKs `(agency_id, col) → parent(agency_id, id)`;
  - ENABLE + FORCE;
  - the restrictive policy;
  - one permissive policy per granted command, with none for UPDATE or DELETE on an append-only table;
  - the matching grant.

  All are present, and each step has its exact reverse. `TenantModel`, `GLOBAL_TABLES` and the
  `makemigrations --check` test are left to M4c-6a-2. That split is recorded in DECISIONS and is within
  the ≈ 450 split rule.
- **Against spec §4.2:**
  - The ENABLE, FORCE, restrictive and permissive statements are character-for-character the spec block
    once whitespace is collapsed and `(…same…)` is expanded.
  - The unit test parses the block from the spec file itself, so any spec edit to the template fails here.
  - `_sel` uses USING, `_ins` uses WITH CHECK, `_upd` uses both and `_del` uses USING.
  - The restrictive `_tenant` policy is FOR ALL with both clauses.
- **Names:**
  - Every table, column, parent and *derived* constraint or policy name is checked against
    `[a-z_][a-z0-9_]*` and a 63-character limit. Nothing is quoted or interpolated except checked names
    and fixed text.
  - `commands` is set-checked, so a bare string such as `"SELECT"` splits into letters and is refused.
  - `agency` is refused as a table or as a parent, `agency_id` is refused as a composite column, and a
    duplicate FK column is refused.
  - A reserved word such as `user` passes the regex, but then fails loudly at `migrate`. That is not an
    injection path.
- **Semantics:**
  - A composite FK on a nullable column is MATCH SIMPLE, so a NULL skips that FK. The single-column
    `agency_id` FK still holds, which is correct for an optional parent.
  - A self-reference (a table that is its own parent) works, which is useful for trees.
  - Reverse order: Django undoes the operations last-first. So the permissive policies are dropped before
    the step 3 reverse drops `_tenant` and turns off FORCE and RLS.
- **ACL reverse:**
  - The first GRANT turns a NULL ACL into an explicit owner entry, and REVOKE leaves that entry behind.
  - Comparing `coalesce(relacl, acldefault('r', relowner))` is the right way to test that.
  - The effective privileges are the same before and after.
- **Live test:**
  - It runs as the migrator in a transaction that is rolled back.
  - It checks the catalog shape: RLS flags, ACL, constraint definitions and the deparsed policies.
  - It checks that the reverse restores the catalog exactly.
  - It checks that a composite FK refuses another agency's parent and that the `agency` FK refuses an
    unknown agency.
- **Migration linter:** passes both directions. No statement contains `%` or a newline.

### Checks
- `make test-live` at 3506a1f on a disposable DB: 272 passed (matches the PR body).
- `test_template.py` + `test_template_live.py`: 18 passed. The PR body says 15 unit tests; with the 11
  refusal cases expanded there are 16. This is a count slip, not a gap.
- Reviewer mutants, each reverted (the worktree is clean):
  - The `parent == ROOT` refusal removed: killed (1 failed).
  - The `table == ROOT` refusal removed: killed (1 failed).
  - `MAX_NAME = 63` → `64`: **survives** (see the P3).

### Findings

### [P3] The 63-character name limit is not pinned at its boundary
- **Category:** test gap
- **Evidence:** `test_bad_names_and_arguments_are_refused` uses `"x" * 64` and `"x" * 56`. Both are
  refused even with `MAX_NAME = 64`, because the derived `<table>_agency_fk` is 66 or more characters. The
  mutant `MAX_NAME = 64` passes all 18 tests.
- **Failure scenario:**
  - Someone loosens the limit by one, for example while reading NAMEDATALEN as 64.
  - The template then accepts a 64-character derived name, which PostgreSQL silently truncates to 63
    (with only a NOTICE).
  - Two composite-FK constraint names that differ only in their 64th character would collide. The second
    `ADD CONSTRAINT` would then fail at `migrate`.
  - Also, the M4c-6b schema check, which compares expected names with catalog names, would see a
    truncated name.

  This breaks loudly and doesn't weaken isolation, hence P3.
- **Required correction:** add a boundary pair. A table whose longest derived name is exactly 63
  characters must be accepted, and one whose longest derived name is 64 must be refused. For example,
  test with `composite_fks` so that the `_<col>_fk` name is the longest one.
- **Owner:** builder · **Disposition:** deferred to M4c-6a-2 (stacked on this PR), or fixed here at the
  builder's choice · **Status:** open (deferred)

### Follow-ups
- M4c-6a-2: the P3 above. Also, in that PR, `TenantModel` must carry `UniqueConstraint(agency_id, id)`;
  every composite FK this template emits depends on it on the parent. Add the `makemigrations --check`
  drift test from the plan.
