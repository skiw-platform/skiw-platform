# PR 178 — feat(accounts): M4r-1c-ii security_event shape trigger, key lists and depth rule

- **Merged:** 2026-11-24 (03:25:14 UTC) · **Merge commit:** 75b612849590823e279281ff0f4c95c67de3a3d0 · **Branch:** feat/m4r-1c-ii-security-event-shape
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-178.receipt, created 2026-11-24 03:09:09 UTC, before the merge; names head fdf072e4c1f5c318cdc017c35bfd144f22de87cc and review hash e3b35ad7…
- **Merge evidence:** `gh pr view 178` state MERGED, merge commit above, mergedAt 03:25:14Z; reachable from the fetched origin/main. Final head fdf072e4c1f5c318cdc017c35bfd144f22de87cc equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1c-ii (second half of M4r-1c, split by the owner on 2026-11-23)

## What changed
BEFORE INSERT trigger `security_event_shape` (migration 0025; SECURITY INVOKER, pinned `search_path`, EXECUTE revoked from PUBLIC): for the ten change kinds it requires the exact key set and value types of Decision 30 and that the row is written from inside a trigger (`pg_trigger_depth() >= 2`); pre-tenant kinds untouched. The schema check now requires the trigger present and enabled (four new mutants). A test-only probe trigger (session fixture in `app/conftest.py`, not in any migration) plants change rows; the TEN-08 case and the own-agency test now use it. DECISIONS entry with six choices. 484 lines (about 125 code, 345 tests, 14 docs).

## Why
Decision 32: the database, not app code, is the only writer of change records; without the trigger any code running as `skiw_app` could insert a change-kind row with arbitrary content.

## Review rounds
- R1: Approved, no required corrections. Two deferred conditions.

## Deferred conditions
- **TEST:** pin that `skiw_app` has no TEMP privilege on the database (`has_database_privilege`), no later than M4r-1g, preferably in M4r-1d or M4r-1e. It is what stops `skiw_app` creating a temporary trigger function to reach depth 2.
- **P2 (PR 177, unchanged):** the reverse of migration 0022 must refuse while change rows exist, with a live test → M4r-1g.
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule before any M20 PR; DECISIONS Source-line P3 (PR 172 entry); Q47 sample from the owner; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction at the next spec touch.

## Decisions worth keeping
- DECISIONS 2026-11-24 "M4r-1c-ii": error codes (42501 depth rule, 23514 wrong shape), `parent_id` null exactly for `unit_kind = 'agency'`, permission code and scope only need to be a pair present in `permission`, the operator code is checked for shape only (so `seed` passes), the probe lifecycle, the function scan's limit (no dynamic SQL), unknown pre-tenant kinds still accepted.

## Follow-ups
- Next: M4r-1d (guard triggers: roles lock, org_unit tree guard, READ COMMITTED refusal, Owner and system-role protections, refusal triggers; no write grant). Add the TEMP pinning test there if it fits.
- Flake note: one `make test` run by the sub-agent showed 1 unexplained failure when started alongside lint and typecheck (output not kept); not reproduced in three later runs.
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests (see the PR 175 log).

## Appendix — final review (PR 178 Round 1)
## Round 1 — 2026-11-24 · head fdf072e4c1f5c318cdc017c35bfd144f22de87cc
- **PR:** #178 "feat(accounts): M4r-1c-ii security_event shape trigger, key lists and depth rule" · base main a05ad5d (= merge base; PR 177 merged) · OPEN, MERGEABLE, not draft
- **Files:** 11 (+464 −20 = 484 lines), one commit fdf072e.
- **Governing:** slice spec v2.5 (bb262ec4) Decisions 30, 32, 33; §4 `security_event` row; §7 "Other code writes or forges change events", "Personal data in a change event", "Agency B reads or writes agency A's change events"; §9 row 1c (named split); main spec v1.24; TEN-02, TEN-03, TEN-08.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep; tenancy/RLS) · **Switch model next step?** No

### Findings
No blocking findings.

### [P3] The schema check does not pin the trigger's WHEN clause
- Evidence: `check.py` `TRIGGERS` reads `tgenabled`, `tgtype`, function and `prosecdef`, not `tgqual`. A `CREATE TRIGGER security_event_shape BEFORE INSERT … FOR EACH ROW WHEN (false) EXECUTE FUNCTION public.security_event_shape()` passes the check (`'O'`, 7, same function, invoker) and never fires.
- Impact: only the table owner can make that change. That is threat class (2), which the spec accepts, and the live tests would catch it in CI. The check exists to catch drift on a deployed database, though, and a "trigger present and enabled" rule should not be satisfied by a trigger that never fires.
- Correction: add `t.tgqual IS NULL` to the query or to the tuple, plus one mutant. Optional; it can ride with M4r-1d, which adds more triggers to the same rule.

### [P3] Concurrent live sessions on one database can drop each other's probe
- Evidence: `conftest.py` removes the probe at the end of each live session, and `test_only_the_two_lookup_definers…` drops it and re-installs it mid-session. `test_check_command_live.py` already expects "probe tables another test session may hold open". A second `make test-live` / `db-test` on the same Compose database would lose the probe partway through its run.
- This is the same pattern as `jobs_probe` (dropped in `jobs/tests/conftest.py`), so it is not new. It may also explain the builder's one unexplained failure in a parallel run, though that is not shown.
- Correction: none required. Run live suites one at a time, or later have the scan exclude the probe by name instead of dropping it.

### [P3] The TEMP premise is pinned only by `roles.sql`
- The depth rule holds only while `skiw_app` cannot create a temporary table and trigger function and so reach depth 2. `infra/host/db/roles.sql:31-32` (`REVOKE ALL ON DATABASE … FROM PUBLIC`, then CONNECT only) does provide this. The pinning test is listed as open for M4r-1g in DECISIONS.
- Acceptable: today no audit trigger exists and no write grant exists. The test is one line, though, and it protects the premise this PR introduces. Landing it in M4r-1d or 1e, rather than 1g, would be better. Disposition: deferred, no later than M4r-1g (tracked in DECISIONS).

### Carried from PR 177 (P3, owner to confirm)
- The PR body and the new DECISIONS "Source" line both repeat "split by the owner on 2026-11-23". This is still unconfirmed to the reviewer. The new entry's own "Decided by" line correctly reads "builder within the approved spec".

No prompt-injection text found.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Trigger (§4, Decision 32) | 0025: BEFORE INSERT FOR EACH ROW, plpgsql, SECURITY INVOKER, `search_path = pg_catalog, pg_temp`, owned by skiw_migrator, EXECUTE revoked from PUBLIC, all objects qualified; reverse drops the trigger, then the function | matches; live test reads owner, prosecdef, proconfig, language, EXECUTE |
| Depth rule | `want` NULL → RETURN NEW (pre-tenant untouched); else `pg_trigger_depth() < 2` → 42501, before any shape check | matches; direct insert refused for all ten kinds in A, B and none, and by the owner under NO FORCE; probe insert accepted per kind in A and B (the [A] depth semantics are proved) |
| Key lists (Decision 30) | `KEYS` equals the ten lists exactly; exact-set comparison of sorted keys; object type required | matches row by row |
| Value rules | operator `^[a-z][a-z0-9-]{1,31}$` (= Decision 31); ids canonical lowercase uuid (`$` is end of string in PG ARE); line and unit_kind closed; pair present in `permission` (SELECT held by skiw_app and the migrator); parent_id null ⇔ unit_kind 'agency'; org.moved both parents uuid (a root cannot move: the `kind`/root CHECK) | matches; recorded as choices 2, 3 |
| §7 personal-data tests | missing key (every key), extra key ×3, email/name/free text/number in every key, 16 wrong shapes, root with null parent accepted | covers the §7 list |
| RLS still applies through the probe | probe function is an invoker, so the event INSERT runs as skiw_app; cross-agency/no-token refusals now go through the probe (depth 2), so the 42501 comes from RLS; the own-agency case shows probe rows land (`== 1`) | sound |
| TEN-08 harness | `_change_event` plants through the probe (the PR 177 residual is closed) | ok |
| Probe isolation | column `agency` (not `agency_id`), so it is not classified as a tenant table; listed test-only in three files; a leftover on a deployed database fails the `migrate` schema check ("not on the global list…", `check.py:182`); installed only when live items are selected (addopts deselect live) | acceptable |
| Function scan | whole-word `security_event` over prosrc and SQL-standard bodies = the two lookup definers; shape body names no table; dynamic-SQL limit recorded (choice 5) | matches §7 for this step |
| Schema check | trigger present, `'O'`, tgtype 7, function, not definer; four mutants (dropped, disabled, replica-only, AFTER) | matches Decision 32 (WHEN gap is P3) |
| Mutants run by the builder | no depth rule, loosened key list, trigger dropped, HMAC CHECK dropped: all killed | matches §9 row 1c |
| Existing writers | pre-tenant kinds (incl. unknown) written directly in all three contexts; CI live suite (login, throttle, factor-lock, passkey, lookup definers) green | unbroken |
| Size | 484, past 450 and under 600, reason given (trigger, its fixture and its tests) | acceptable |
| `git diff --check` | clean | — |
| CI on fdf072e | checks (12m), security, image, host: success; publish, deploy-staging skipped | — |

Not run by the reviewer: local suites (CI green on the head).

### Residual risks and test gaps
- The forgery guard depends on no TEMP or CREATE for `skiw_app` and on no other trigger inserting into `security_event`. Both are pinned partly: the scan pins the second, and the first rests on `roles.sql` until its test lands.
- The PR 177 P2 (reverse of 0022 deletes change rows) is still open for M4r-1g.

### Required before merge
- none

### Deferred conditions
- TEMP pinning test, no later than M4r-1g (preferably 1d/1e).
- PR 177 P2 is unchanged.

### Optional improvements
- P3 `tgqual IS NULL` in the trigger rule; P3 probe drop in parallel sessions.

