# PR 99 — feat(tenancy): M4c-6b-1 the tenancy schema check

- **Merged:** 2026-11-03 (15:30:53 UTC) · **Merge commit:** 99c6271fc580491aef3d5b85e22fe069270a07b4 · **Branch:** feat/m4c-6b-1-schema-check
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-99.receipt on agent-logs (log-branch commit bb5187a, receipt time 2026-11-03T15:30:04Z, before merge; reviewed head bc229dcb21c957015106c84c8b3528ec1022e74d, review-file hash e34448139da5de679d9ac4a27572fb2c3b12a4df, review commit 07ee03a)
- **Merge evidence:** `gh pr view 99` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head bc229dcb
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-6b (part 1 of 2)

## What changed
- `app/tenancy/check.py` (new): `check(conn, schemas=None, extra_allowed=())` classifies every relation of kind r, p, v, m or f as a listed global (first), the `agency` root, or a tenant table of the `tenant_table()` shape, and returns sorted `Violation(table, reason)`; unlisted views and PUBLIC / `true` / `current_setting` policies always fail.
- `app/tenancy/tests/test_check_live.py` (new, 18): pass and fail fixtures in a rolled-back scratch schema `chk`.
- `app/jobs/tests/test_queue_grants.py`: PR 98 R1 P3 fix (known globals must be in the checked set).
- The DECISIONS "M4c-6b-1" entry.

## Why
Spec §4.2 "Schema check (M4)", TEN-04–07; plan M4c-6b. Split because M4c-6b came to ≈ 550 lines against the ≈ 450 rule; the migrate-step wiring follows in M4c-6b-2.

## Review rounds
- R1: Approved (head bc229dc). PR 98 R1 P3 closed. One new P3 (test gap), deferred to M4c-6b-2.

## Deferred conditions
- P3 → M4c-6b-2: pin the root branch and the global policy rules. On the real `agency` in the rolled-back transaction: drop `agency_tenant` (restrictive reason), `ADD COLUMN agency_id uuid` (agency_id reason), replace the PK with a unique constraint (PK reason); plus a listed global (`public.bridge_session`) with a `current_setting` or PUBLIC policy.

## Decisions worth keeping
- List membership before the tenant rule; an FK to a listed global is an ordinary FK.
- Predicates compared as `pg_get_expr` deparses them (A4); PUBLIC read from `pg_policy.polroles` (0).
- All relations are classified; `schemas` limits only what is reported.

## Follow-ups
- M4c-6b-2: the P3 above; `manage.py check_tenancy_schema` last in `make migrate` and the host deploy migrate step; `host-rebuild.md` text (forward fix only, never a reverse on the host); `make db-test`; PROJECT §7 line only with the owner's yes (asked at PR 99, open).
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1; M5 waffle m2m tables (owner/spec call).
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-6b-1" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-6b, part 1 of 2)
- **Code review:** base (merge base) a36f3feafcfd14e42c1c64840775ff2632a741d7 (origin/main, PR 98 merged)
  · head bc229dcb21c957015106c84c8b3528ec1022e74d (one commit) · 4 files, +466 −1 · head re-checked at end:
  yes (unchanged). Detached review worktree `.agent/worktrees/review-91`; disposable DB (port 5441),
  removed after (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). §4.2 "Schema check (M4) — what counts as compliant". Plan
  `docs/plans/2026-11-01-m4-core.md` §3 M4c-6b.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 99`
(builder), then M4c-6b-2 (deep tier), which carries the P3 below.

### PR 98 R1 P3 (vacuous classification): resolved
`test_every_existing_global_table_is_in_the_closed_list` now requires `django_migrations`,
`security_event` and `guard.tenant_mac_key` in the checked set (after the tenant exemption). The builder's
mutant (`HAS_AGENCY_ID` matching any column) now fails. **Status:** closed.

### What was checked
- **Against spec §4.2, each of the three kinds:**
  - **Global:** schema-qualified list membership, tested first, so `bridge_session` with its `agency_id`
    is global. The PR 98 note is handled, and `test_a_listed_global_with_agency_id_is_global` covers it.
    The `schema.relname` key is unambiguous: the listed names hold a single dot, so no other
    schema/table split can produce them.
  - **Root:** `id` PK; no `agency_id`; ENABLE + FORCE; a restrictive FOR ALL TO `skiw_app` policy with
    both clauses on `id`; exactly one permissive SELECT policy.
  - **Tenant:**
    - `id`, `agency_id uuid not null` and `unique(agency_id, id)`, where a PK on the pair counts and a
      unique index that isn't a constraint does not, which fails closed;
    - ENABLE and FORCE, reported separately;
    - the restrictive policy, exact;
    - permissive policies of the template shape only, so a permissive FOR ALL or another role fails;
    - the `agency_id → agency(id)` FK;
    - every FK to a tenant table composite on `agency_id`.
  - **Everything else fails:** an unlisted view or matview, or a table with no `agency_id`.
- **On every relation:** a PUBLIC policy, a `true` predicate or a `current_setting` predicate fails.
  - PUBLIC is read from `polroles` (0), which is the right source.
  - An obfuscated predicate (for example `(1 = 1)` or a wrapper function) can only be:
    - a non-template permissive policy, which is caught; or
    - an extra restrictive policy, which can only narrow access.
- **Edge cases reasoned through (fail closed in each):**
  - Partitions are `r` with their own `agency_id`, so each needs its own policies. PostgreSQL doesn't
    inherit RLS policies to partitions, so the check is right to demand them.
  - A foreign table with `agency_id` is checked as a tenant table and fails RLS.
  - An FK to a global is ordinary.
  - The whole catalog is classified, and `schemas` filters only the report.
- **Out of the check's scope, and covered elsewhere:**
  - TRUNCATE and other table privileges are covered by the grant audit in `test_queue_grants.py`
    (spec line 225, which covers any table in any non-system schema).
  - Ownership is covered by TEN-01's CI query.
- **Plan fixtures:**
  - All five spec fail cases are present: undeclared table, no unique, agency-shaped, single-column FK,
    `current_setting`.
  - So are the builder's extra cases: not forced, not enabled, `USING (true)`, PUBLIC, no restrictive
    policy, restrictive without WITH CHECK, no agency FK, nullable `agency_id`, unlisted view.
  - Pass cases: compliant parent and child, a listed global, and the real schema.
- **The real schema passes** `check()` with only the test-only probe tables allowed.
- **DECISIONS** "M4c-6b-1" is present, with the split reason and the deparse dependency on `search_path`.
  Wiring into `migrate`, the command, the runbook and `make db-test` are named for M4c-6b-2.

### Checks
- `make test-live` at bc229dc on a disposable DB: 291 passed (matches the PR body).
- Reviewer mutants on `check.py`, run against `test_check_live.py` with bytecode off and the cache
  cleared, each reverted (the worktree is clean):

  | Mutant | Result |
  |---|---|
  | `_policy_rules` skipped for listed globals | **survives** (P3) |
  | root: `id` PK check removed | **survives** (P3) |
  | root: "has `agency_id`" check removed | **survives** (P3) |
  | root: restrictive policy not checked | **survives** (P3) |
  | tenant: "no id column" check removed | survives, equivalent: `unique(agency_id, id)` cannot exist without `id`, so that reason always fires too |
  | `schemas` filter ignored | survives, equivalent in this run: no other schema has a violation |

### Findings

### [P3] The root branch and the global policy rules are not pinned by any fixture
- **Category:** test gap
- **Evidence:**
  - `test_the_real_agency_fails_without_force_or_with_another_permissive_policy` covers two of the
    root's five rules: FORCE and "exactly one permissive SELECT".
  - Removing the `id` PK rule, the no-`agency_id` rule or the restrictive-policy rule in `_root()`
    leaves all 18 tests green.
  - Likewise, no fixture puts a PUBLIC, `true` or `current_setting` policy on a *listed global*. So
    moving `_policy_rules` under the non-global branches is not caught, although the PR body says the
    rules apply "on **every** relation".
  - `test_agency_live.py::test_the_table_matches_the_root_template` pins the *real* `agency` shape. So a
    drifted `agency` is still caught today, but by that test, not by the check that M4c-6b-2 will run
    in the deploy.
- **Failure scenario:**
  - A later refactor of `_root()` loses the restrictive-policy rule, and every test stays green.
  - The migrate-step check then accepts an `agency` whose restrictive policy a migration dropped. The
    permissive SELECT still narrows reads, which is why this is P3 rather than P2. But the spec's
    "named exception" shape is no longer enforced by the gate meant to enforce it.
- **Required correction:** add three root fixtures to `test_check_live.py`, each on the real `agency`
  in the rolled-back transaction:
  - drop `agency_tenant`, giving the restrictive-policy reason;
  - `ADD COLUMN agency_id uuid`, giving the "tenant root has an agency_id column" reason;
  - replace the PK with a unique constraint, giving the "id is not the primary key" reason.

  Add one listed-global fixture with a `current_setting` (or PUBLIC) policy. `public.bridge_session` in
  the scratch transaction works, as in the existing global test.
- **Owner:** builder · **Disposition:** deferred to M4c-6b-2, the next PR, which wires this check into
  `migrate`. Or fix it here, at the builder's choice. · **Status:** open (deferred)

### Follow-ups
- M4c-6b-2:
  - the P3 above;
  - run the check after the migrations as the last step of `migrate`, on hosts too;
  - the `host-rebuild.md` text (forward fix only, never a reverse on the host);
  - `make db-test`, with the owner's yes in the PR for the PROJECT §7 line.
