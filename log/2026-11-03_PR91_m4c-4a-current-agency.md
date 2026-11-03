# PR 91 — feat(tenancy): M4c-4a guard.current_agency() verifier and token vector

- **Merged:** 2026-11-03 (08:58:05 UTC) · **Merge commit:** ad67d11f203b8745b1f15184c90fe0c2707017ab · **Branch:** feat/m4c-4a-current-agency
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-91.receipt on agent-logs (log-branch commit 3be5552, receipt time 2026-11-03T08:57:43Z, before merge; reviewed head f46e7e1f354a10b244c4857b5621be4dcba333a8, review-file hash fefc4a705c281054e0d15ef2b6e0eccb3c8d7b0a, review commit fddcd5e)
- **Merge evidence:** `gh pr view 91` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head f46e7e1f
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 2)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-4a

## What changed
- `app/tenancy/token.py` (new): `mac_input` / `mint`, the spec v1.21 §4.2 item 2 encoding.
- `tenancy/0003_current_agency` (new): `guard.current_agency()`. It is plpgsql, STABLE and SECURITY DEFINER, with `search_path = pg_catalog, pg_temp`, and is owned by `skiw_tenant_guard`. EXECUTE is granted only to `skiw_app`. It refuses absent or retired key versions, a foreign xid and a non-canonical MAC; it compares by double HMAC and returns NULL on any failure. The migration also grants USAGE on `guard` to `skiw_app`.
- Tests:
  - the committed vector, in `test_token.py`;
  - the live verifier tests, plus two SQL-side encoding tests (R1), in `test_current_agency_live.py`;
  - guard ACL tests updated;
  - `test_auth_lookup_definer_live.py`: the negative control is dropped.
- `docs/runbooks/host-rebuild.md`: the two rotation steps must be separate deploys.
- `docs/DECISIONS.md` "M4c-4a" entry.

## Why
Spec v1.21 §4.2 items 2–3; TEN-06, TEN-09, TEN-12; plan M4c-4a; PR 88 R2 follow-up.

## Review rounds
- R1: Revision required (head f1e0b4e).
  - P2: the SQL side was never checked against the committed vector. Fixed in f46e7e1.
  - P3: Semgrep `tenancy-token-setting` choice. Deferred to M4c-4b.
- R2: Approved (head f46e7e1).

## Deferred conditions
- M4c-4b (R1 P3):
  - allow `/app/tenancy/tests/` in `tenancy-token-setting` and the plan table, and write the tests with the literal setting name;
  - flag `set_config` with a non-literal first argument outside `tenancy.binding`;
  - limit imports of `tenancy.token.mint` to the binding modules and tests.

## Decisions worth keeping
- The function lands in a new migration, 0003, because 0002 had already merged (PR 82). Recorded in DECISIONS "M4c-4a".
- No `EXCEPTION WHEN OTHERS` block: every step is written so that it cannot raise.

## Follow-ups
- M4c-4b: `with_agency()` must mint under the newest active key (the runbook's separate-deploys rule depends on it); also the deferred P3 above.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 85 P3 → M4c-4b; PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; M2c owner Q1=A, Q2=A to record in DECISIONS; Dependabot alert security/dependabot/1.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-4a" entry.

## Appendix — final review round
## Round 2 — 2026-11-03 · scope: slice (M4c-4a), R1 fix
- **Code review:** base (merge base) 0344c5c0b9ae3e63c422e1ff77dc3eb2d184fdca · head
  f46e7e1f354a10b244c4857b5621be4dcba333a8 (descends from R1 head f1e0b4e; one commit `f46e7e1 Review R1 fix:
  The SQL side is never checked against the committed vector`; 2 files, +47 −3) · head re-checked at end: yes
  (unchanged). Review worktree moved to the new head; disposable DB removed after.
- **Spec:** v1.21, hash d95cb271 (unchanged).
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 91` (builder),
then merge, then M4c-4b (deep tier), which carries the deferred P3.

### Findings (R1 status, re-inspected)
- **[P2] SQL side never checked against the committed vector: resolved.** `test_current_agency_live.py` adds
  `sql_mac_input`, which evaluates the migration's own `MAC_INPUT` constant in PostgreSQL. The database name
  is swapped for a column; `agency` and `xact` resolve to the subquery's columns, so the expression is otherwise
  byte-identical to the function body. Two new tests:
  - `test_the_sql_encoding_reproduces_the_committed_vector`: the SQL bytes equal `VECTOR_INPUT`, and
    `guard.hmac` over them under `VECTOR_KEY` equals the MAC in `VECTOR`.
  - `test_the_sql_encoding_matches_the_minter_on_a_multibyte_name_and_the_largest_xid`: `é-skiw` and
    xid 2^64−1, compared with `mac_input` and `mint`.

  The old test is renamed to "accepts the vector key", so it no longer claims to reproduce the vector.
  DECISIONS "M4c-4a" evidence is updated (226 live tests; builder mutants: domain string, LATIN1).
- **[P3] Semgrep `tenancy-token-setting`: deferred as decided.** DECISIONS "M4c-4a" now records the three
  M4c-4b items (allow `/app/tenancy/tests/` in the rule and plan table and use the literal name; flag a
  non-literal `set_config` name outside `tenancy.binding`; limit `tenancy.token.mint` imports).
  **Status:** open (deferred to M4c-4b; the M4c-4b review checks it).

### Checks
- `make test-live` at f46e7e1 on a disposable DB: 226 passed.
- Reviewer mutant `octet_length` → `length` survives. That is expected, not a gap: every field is `bytea`
  (`convert_to`, `uuid_send`, `xid8send`), and `length(bytea)` counts bytes, so the two are equivalent. The
  builder's LATIN1 mutant covers the character-vs-byte risk at the encoding step. Mutant reverted; the review
  worktree is clean.

### New findings
None.

