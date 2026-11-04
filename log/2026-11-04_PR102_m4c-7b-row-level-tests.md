# PR 102 — test(tenancy): M4c-7b row-level forged, leak and EXPLAIN tests

- **Merged:** 2026-11-04 (05:06:42 UTC) · **Merge commit:** 62e8114b6f3176217b550af752f37a47edf4ca93 · **Branch:** feat/m4c-7b-row-level-tests
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-102.receipt on agent-logs (log-branch commit 8cb6287, receipt time 2026-11-04T05:05:51Z, before merge; reviewed head 1ad6128a93ee5cb0218374ad32e019c01697b0ba, review-file hash 3f947472a33b63a484dd5d20622350d1b0af1599, review commit 3a761d8)
- **Merge evidence:** `gh pr view 102` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 1ad6128a
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-7b

## What changed
- `app/tenancy/tests/test_row_level_live.py` (new), on every registered isolation case (the fixture pair), as skiw_app through `with_agency()`:
  - forged tokens (M4c-4b's list plus a genuine B token replayed from B's transaction): no row for SELECT, UPDATE or DELETE, INSERT 42501, `current_agency()` NULL and A's own row hidden (not vacuous);
  - a plain `app.agency_id` does not switch; `COMMIT; BEGIN` drops the binding;
  - leak test: A then B on one backend, each sees only its own row, the token is empty afterwards;
  - EXPLAIN [A5]: every `guard.current_agency()` call inside an InitPlan, no seq scan, an index condition `agency_id = (InitPlan n).col1` (seq scans off).
- `app/tenancy/tests/conftest.py`: the fixture pair moved here (still module-scoped) and the session autouse `no_fixture_leftover` (PR 101 R1 P3). `test_isolation_live.py` uses it.
- `docs/runbooks/local-dev.md`: the leftover-pair sentence corrected; the `test-live` and `db-test` rows name the new module. The DECISIONS "M4c-7b" entry.

## Why
Spec §4.2 (the InitPlan note), TEN-09; plan M4c-7b, A5. Size +274 / −50, under the ≈ 450 rule.

## Review rounds
- R1: Approved (head 1ad6128). PR 101 R1 P3 closed (the reviewer repeated the leftover probe: 185 passed, schema cleared). No findings.

## Deferred conditions
- None.

## Decisions worth keeping
- TEN-09's "UPDATE/DELETE of B rows fail" means 0 rows affected and the row survives (RLS filters without raising), as in M4c-7a.
- A forged-token test must prove the forgery landed (NULL verifier and A's own row hidden); this caught M4c-4b's `b-shaped-bad-mac` being a no-op for another module's A.
- EXPLAIN with `enable_seqscan = off` proves the index is usable under the policy, not chosen at every size.
- "Pooled" in the sync path is Django's persistent connection; the real pool is M4c-8.

## Follow-ups
- M4c-8 (`async_with_agency()`, floats) re-runs the M4c-4b forged list and this row-level set on `AsyncConnectionPool`; or M3d. The owner picks the order.
- Reviewer note: the EXPLAIN pattern `(InitPlan n).col1` is PostgreSQL 17 wording (16 printed `$0`); update it with any major Postgres upgrade.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; Dependabot alert security/dependabot/1; M5 waffle m2m tables (owner/spec call).
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-7b" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M4c-7b)
- **Code review:**
  - **Base:** merge base 46c65e605a85c4380077dafc718dd457144b14f7 (origin/main, PR 101 merged).
  - **Head:** 1ad6128a93ee5cb0218374ad32e019c01697b0ba, one commit. 5 files, +274 −50. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-7b; spec
  §4.2 [A5].
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 102` (builder), then merge.
- **After that:** M4c-8 (`async_with_agency()`), which the plan lets float, or M3d. The owner picks
  the order.

### PR 101 R1 P3 (leftover fixture pair): resolved
- **The fix:**
  - The pair moved to `app/tenancy/tests/conftest.py`. It is still module-scoped and still drops
    first.
  - A new session autouse fixture, `no_fixture_leftover`, drops `tenancy_fixture` before the first
    tenancy test of any run that selects live tests.
  - Every test that runs `migrate` in a subprocess is in `app/tenancy/tests/`
    (`test_agency_live.py`, `test_guard_schema_live.py`, `test_key_writes_live.py`). So the fixture
    always runs before them.
- **Reviewer probe:** I repeated the R1 probe. I left a compliant `tenancy_fixture.parent` behind as
  the migrator, then ran `pytest -m live app/tenancy`.
  - Result: 185 passed, including the guard-schema reverse test that failed in R1.
  - Afterwards, `tenancy_fixture` was gone.
- **Docs:** the `local-dev.md` sentence now says the compliant pair passes the schema check and that
  the next live tenancy run drops it.

**Status:** closed.

### What was checked
- **Forged tokens against RLS:**
  - **The forgeries:** M4c-4b's seven, plus a genuine B token replayed from B's own committed
    transaction.
  - **What each one is checked against:** each is set inside A's transaction, against both registered
    tables:
    - SELECT, UPDATE and DELETE reach neither B's row nor A's own;
    - an INSERT naming B fails with 42501;
    - B's row survives.
  - **Not vacuous:** under each forgery, `current()` must be NULL **and** A's own row must vanish.
    So a forgery that leaves A's genuine token in place fails the test. That is how the builder found
    that M4c-4b's `b-shaped-bad-mac` was a no-op against this module's A (`…a7`). The local override
    is correct.
  - **The retired and absent versions:** these forgeries are tokens for B, minted under the vector key
    with the live xid and database name. The key version is therefore the only reason they are refused.
    That is the strong form of the spec v1.21 rule.
- **Reading of "UPDATE/DELETE of B rows fail":** "0 rows affected, and the row survives". This is
  correct. RLS filters without raising; only INSERT and WITH CHECK raise. It is consistent with the
  M4c-7a write check, and it is recorded in DECISIONS.
- **Plain `app.agency_id` set to B:** no effect. A sees only A.
- **`COMMIT; BEGIN` inside `with_agency(A)`:**
  - The new transaction has no valid token, so A's own row is hidden and an INSERT fails with 42501.
  - This is spec §4.2 item 4.
- **Leak test:**
  - A, then B, run on the same backend (`pg_backend_pid()` is checked).
  - Each sees only its own row.
  - Afterwards, `app.tenant_token` is empty and `current_agency()` is NULL.
  - The builder's session-level `set_config` mutant kills it.
  - "Pooled" here means Django's persistent connection. The real pool is `AsyncConnectionPool` in
    M4c-8, as the plan says.
- **EXPLAIN [A5]:** for SELECT, UPDATE and DELETE (where granted):
  - every `guard.current_agency()` call sits inside an InitPlan;
  - there is no seq scan;
  - an index condition reads `agency_id = (InitPlan n).col1`.

  With `enable_seqscan = off` this shows the index is *usable* under the policy, not that it is chosen
  at every size. The docstring states that honestly. The builder's no-`(SELECT …)` and `::text`
  mutants each kill it.
- **Semgrep `tenancy-token-setting`:** tokens are set by hand only in `tenancy/tests/`, where the rule
  allows it. `make lint` is clean.

### Checks
- `make test-live` at 1ad6128 on a disposable DB: 338 passed (26 new). Migrate printed
  `tenancy schema check: ok`. Both match the PR body.
- The leftover probe above: 185 passed, and the schema was cleared. The probe script ran from its own
  temp dir with `python -I` and was deleted afterwards. The worktree is clean.

### Findings
None.

### Notes (no action)
- **The EXPLAIN text pattern `(InitPlan n).col1` is PostgreSQL 17's wording.** PG 16 printed `$0`.
  Both stacks pin `postgres:17.11` by digest. A major-version upgrade will fail this test loudly, and
  the pattern should then be updated along with it.

### Follow-ups
- M4c-8 re-runs the M4c-4b forged list and this row-level set on `AsyncConnectionPool` (plan). Once
  this merges, the M4 done-when items "Forged-tenant tests" (row) and "EXPLAIN" are met.
