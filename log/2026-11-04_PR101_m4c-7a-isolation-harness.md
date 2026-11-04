# PR 101 — test(tenancy): M4c-7a the TEN-08 isolation harness

- **Merged:** 2026-11-04 (04:34:04 UTC) · **Merge commit:** 46c65e605a85c4380077dafc718dd457144b14f7 · **Branch:** feat/m4c-7a-isolation-harness
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-101.receipt on agent-logs (log-branch commit 1ad28e6, receipt time 2026-11-04T04:33:34Z, before merge; reviewed head d19299133f3c8b07c6ac24c78e4a89032d704b41, review-file hash ca927ccd249aaa77eecbc2fbb69bd02a2afaf665, review commit 6e40fa5)
- **Merge evidence:** `gh pr view 101` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head d1929913
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-7a

## What changed
- `app/tenancy/tests/isolation.py` (new): `IsolationCase`, the per-app registry (`<app>/tests/isolation_cases.py`), and the checks read, write, cross_insert, cross_update, no_token, append_only and cross_fk, run as skiw_app through `with_agency()` on committed rows.
- `app/tenancy/tests/test_isolation_live.py` (new): generated tests per case; coverage through the new `tenancy.check.tenant_tables()`; composite-FK cross-check against `pg_constraint`; the fixture pair `tenancy_fixture.parent`/`.child` from `tenant_table()` SQL; the `USING (true)` proof.
- `app/tenancy/tests/test_isolation.py` (new, no DB), `isolation_cases.py` (the fixture pair).
- `agents/PROJECT.md` §7: `pending M4` → `make db-test`.
- `docs/runbooks/local-dev.md`: PR 100 R1 P3 fix. The DECISIONS "M4c-7a" entry.

## Why
Spec §4.2, TEN-08; plan M4c-7a. Size +469 / −9, past the ≈ 450 rule; the reviewer accepted not splitting (the proof is what makes the harness trustworthy).

## Review rounds
- R1: Approved (head d192991). PR 100 R1 P3 closed. One new P3 (test robustness and docs), deferred to M4c-7b. Merge condition: the owner confirms the two answers quoted in the PR.

## Deferred conditions
- P3 → M4c-7b: a leftover compliant fixture pair (after an interrupted local run) passes the schema check and breaks `test_guard_schema_live`'s reverse migration (its policies depend on `guard.current_agency()`). Drop `tenancy_fixture` at session start (a session autouse fixture that runs before `test_guard_schema_live`), or make the reverse test drop it first; then correct the `local-dev.md` sentence (the schema check catches `leaky`, not the pair). CI unaffected (fresh DB).

## Decisions worth keeping
- The leaky proof table is committed and dropped, not rolled back (skiw_app sees only committed rows; `with_agency()` refuses an open atomic block; the migrator has no `skiw_app` membership).
- The fixture pair is module-scoped; FK tests come from declared `parents`, cross-checked against the catalog.
- 23503 proves the composite FK because RI checks bypass RLS.

## Follow-ups
- M4c-7b: the P3 above; row-level forged-tenant, pooled-leak and EXPLAIN tests on the fixture pair.
- Owner answers (scope deviations; PROJECT §7): reached the builder as the reviewer's drafted text. The reviewer made the owner's confirmation the merge condition. The owner merged after `approved 101` without a separate written confirmation; the merge is recorded here as the owner's acceptance. Not a gate breach under START.md `merged` step 5.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1; M5 waffle m2m tables (owner/spec call).
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-7a" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M4c-7a)
- **Code review:** base (merge base) 97d59fba217fd078fad34863bc828abb58b4c9ee (origin/main, PR 100 merged)
  · head d19299133f3c8b07c6ac24c78e4a89032d704b41 (one commit) · 8 files, +469 −9 · head re-checked at
  end: yes (unchanged). Detached review worktree `.agent/worktrees/review-91`; disposable DB (port 5441),
  removed after (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-7a.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Merge condition:** the owner confirms the two answers the PR quotes (see "Owner answers").
- **Then:** `approved 101` (builder), then M4c-7b (deep tier), which carries the P3 below.

### PR 100 R1 P3 (`local-dev.md`): resolved
- The `make migrate` row names `check_tenancy_schema`.
- There is a new `make db-test` row.
- The `make test-live` row describes the harness and how to clear a leftover table.

The leftover text is accurate for `files_probe`, `jobs_probe` and `tenancy_fixture.leaky`. It isn't
accurate for the fixture pair; that is part of the P3 below. **Status:** closed.

### The three conditions from the scope answer
1. **Leftovers dropped before they are created, as well as after:** partly met.
   - At the start of the module, `fixture_pair` runs `DROP SCHEMA IF EXISTS tenancy_fixture CASCADE`.
     The proof runs `DROP TABLE IF EXISTS` before and after.
   - But the reason given for the condition, reverse-migration tests hitting a leftover pair, isn't
     covered. That test runs *earlier* in the session than this module (see the P3).
2. **The proof names the failure:**
   - It runs `CHECKS["read"]` as `skiw_app` through `with_agency()`.
   - It expects exactly `tenancy_fixture.leaky: under A, 1 of B's rows visible`.
   - It also asserts that the coverage test names the unregistered table.
   - The leaky table's *restrictive* policy is replaced with `true` too. Without that, the permissive
     `true` policy would be ANDed away, and the table wouldn't actually leak.
3. **Recorded:** both changes are in DECISIONS "M4c-7a" and in the PR body. The `local-dev.md` sentence
   covers the leaky table.

### PROJECT §7 line (owner answer 2)
- `agents/PROJECT.md:107` now reads `make db-test # db up, migrate (ends with check_tenancy_schema),
  pytest -m live app/tenancy, then the check again; CI covers it through make test-live`.
- That description matches the Makefile target from PR 100.
- The generated isolation tests live in `app/tenancy/tests/test_isolation_live.py`, so `db-test` runs
  them, even though each app keeps its own `isolation_cases.py`.

### What was checked
- **Each check against TEN-08 and §4.2:**

  | Check | What it does | What it proves |
  |---|---|---|
  | read | Looks for B's row under A, and under B as the control | the B control stops it passing on an empty table |
  | write | Runs UPDATE and DELETE under A on B's row, then re-reads under B | the writes affect 0 rows |
  | cross_insert | Inserts a row naming B, with B's own parents, under A | it fails with 42501, because WITH CHECK runs before the FK triggers |
  | cross_update | Moves A's row to B | it fails with 42501 (WITH CHECK) |
  | no_token | Reads and inserts in a plain `atomic()`, with no token set | reads return 0 rows and the insert fails with 42501 |
  | append_only | Runs the ungranted UPDATE or DELETE | it fails with 42501 |
  | cross_fk | Inserts an A child pointing at B's parent | it fails with 23503. RI checks bypass RLS, so only the composite FK can refuse it, and the builder's single-column-FK mutant confirms this |
- **`refused()`:** it checks the SQLSTATE of `__cause__` and fails both on success and on any other
  SQLSTATE. Unit-tested.
- **Registry:** it reads only apps under the project path. A missing `tests` package or
  `isolation_cases` module is skipped, but a broken import inside a module still raises. A table
  registered twice is an error.
- **Coverage:** it uses the schema check's own classification (`tenant_tables()`, refactored out of
  `check()` without changing behaviour). It asserts that the classification includes the fixture pair,
  so it can't pass on an empty set.
- **FK cross-check:** the composite FKs between tenant tables in `pg_constraint` must equal the declared
  `parents`. A single-column FK between tenant tables is the schema check's job, and the check fails it.
- **A and B** are committed with `insert_agency` (`ON CONFLICT DO NOTHING`), which is the M4c-5
  precedent. The seed's one-agency check still passes, because the configured id is present (documented
  in `local-dev.md`).
- **TEN-09:** binding is only ever through `with_agency()`.
- **TEN-01/02:** the schema `USAGE` grant is test-only and goes when the schema is dropped.
- **Size:** +469 is past the ≈ 450 split rule. I accept not splitting: the proof is what makes the
  harness trustworthy, and ≈ 24 of the lines are docs.

### Checks
- `make test-live` at d192991 on a disposable DB: 312 passed. Migrate printed `tenancy schema check: ok`.
  Both match the PR body.
- **Leftover probe** (reviewer):
  - I created a compliant `tenancy_fixture.parent` from `tenant_table_sql()` as the migrator, standing
    in for a crashed earlier run.
  - `make migrate` then printed `tenancy schema check: ok`, so the leftover is **not** caught.
  - `test_guard_schema_live.py::test_the_unlinted_key_table_migration_reverses_and_reapplies_exactly`
    then failed with `DependentObjectsStillExist: cannot drop function guard.current_agency() because
    other objects depend on it … policy parent_tenant on table tenancy_fixture.parent`.
  - After `DROP SCHEMA tenancy_fixture CASCADE`, the file passed again (29 passed).
  - Probe files removed; the worktree is clean.

### Findings

### [P3] A leftover fixture pair passes the schema check and breaks the earlier reverse-migration test
- **Category:** test robustness, plus docs accuracy (UNI-16)
- **Evidence:**
  - The pair is dropped at the start and end of `test_isolation_live.py`. But
    `test_guard_schema_live.py` (collected earlier, because `g` sorts before `i`) migrates tenancy back
    to 0001.
  - Its reverse of 0003 can't drop `guard.current_agency()` while a leftover pair's policies depend on
    it (probe above).
  - The pair is compliant, so `check_tenancy_schema` doesn't flag it.
  - So the `local-dev.md` sentence "the next `make migrate` then fails the schema check naming it"
    holds for `leaky` but not for `parent` and `child`.
- **Failure scenario:**
  - A developer interrupts `make test-live` while the harness module is running. The pair stays.
  - Every later `make test-live` fails in the guard-schema test with a dependency error naming
    `tenancy_fixture`, until someone drops the schema by hand.
  - CI is not affected, because its database is fresh each run. That is why this is P3.
- **Required correction:**
  - Drop `tenancy_fixture` at the **start of the session**, before any tenancy test runs. A session-scoped
    autouse fixture in `app/tenancy/tests/conftest.py` would do it, or the root conftest, so that it
    precedes `test_guard_schema_live.py`.
  - Alternatively, make the reverse test drop it first.
  - Then correct the `local-dev.md` sentence, so it no longer claims the schema check catches the
    fixture pair.
- **Owner:** builder · **Disposition:** deferred to M4c-7b (the next PR, on the same fixture pair) ·
  **Status:** open (deferred)

### Owner answers (for the owner to confirm; the reviewer doesn't decide them)
The PR says both answers reached the builder as the reviewer's drafted recommendation, sent through the
owner's answer box, and asks the owner to confirm before merge:
1. The scope deviations: the leaky table is committed and then dropped, and the fixture pair is
   module-scoped.
2. PROJECT §7 names `make db-test`.

The code matches both answers. A word from the owner closes this.

### Follow-ups
- M4c-7b:
  - the P3 above;
  - the row-level forged-tenant, pooled-leak and EXPLAIN tests on the same fixture pair (plan).
