# PR 183 — feat(accounts): M4r-1f starting-role seed

- **Merged:** 2026-11-24 (12:11:42 UTC) · **Merge commit:** 534be086ac7a7385b72e8a524dc6aa4ba5b0018e · **Branch:** feat/m4r-1f-starting-role-seed
- **Gate breaches:** none under the kit's two gate checks (receipt before merge, final head = reviewed head). **Open reviewer condition at merge:** see "Required condition at merge" below.
- **Approval receipt:** reviews/PR-183.receipt, created 2026-11-24 12:10:48 UTC, before the merge; names head e9d2d7fc7342d6cdc4f7f8ff19f103afd9b8155f and review hash ba805078…
- **Merge evidence:** `gh pr view 183` state MERGED, merge commit above, mergedAt 12:11:42Z; reachable from the fetched origin/main. Final head e9d2d7fc7342d6cdc4f7f8ff19f103afd9b8155f equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved with conditions (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1f

## What changed
Starting-role seed, no migration and no grant change. `accounts/access/seed.py` (`SEED_DEFAULTS`: the Owner system role with all 31 pairs; operator `seed`); a hook list in `tenancy/seed.py` (`add_agency_step`) run after the agency is written, registered from `AccountsConfig.ready`; `insert_agency(..., steps=True)` for tests. A fresh agency gets 1 role, 31 ticks and 32 events (operator `seed`); a second run writes nothing; edited roles are untouched; a failed seed leaves FORCE on. No Owner assignment is seeded. Semgrep `auth-tables-accounts-only` excludes `seed.py`. DECISIONS entry with two deviations and nine choices. 392 lines (about 156 code, 215 tests, 21 docs).

## Why
Decision 24 (Q4): every agency starts with one Owner role holding every permission, so the first admin can be assigned.

## Two deviations from Flow 5.5 (owner said "ok accept both" in the builder session, 2026-11-24)
1. No plain read exists (FORCE on `role`, policies `TO skiw_app`): the seed runs `ALTER TABLE role NO FORCE`/`FORCE` for the existence check on every `migrate`; the 1f done-when "no ALTER TABLE in the statement log" does not hold literally.
2. The spec's commit order fails (55006 on `ALTER TABLE` with pending trigger events): the seed runs `SET CONSTRAINTS role_system_complete IMMEDIATE` before restoring FORCE.

## Review rounds
- R1: Approved with conditions. One P2 (the owner's acceptance of the deviations is claimed, not shown), two P3s. The reviewer found both deviations right on the merits and every condition it had named for the builder met.

## Required condition at merge
- **P2 (open in the record):** "The owner confirms to the reviewer (or on the PR) that they accepted both deviations." At the merge the PR had 0 comments and no confirmation to the reviewer is in the builder's record. The builder told the owner of this condition in the `approved 183` reply and offered to post a note on the PR; the owner replied `merged 183` without answering. The owner's acceptance itself is in the builder session ("ok accept both", 2026-11-24, after both deviations and the alternatives were shown). Treat the condition as **unconfirmed to the reviewer**; the owner can confirm to the reviewer at any time (no code change is needed).

## Deferred conditions
- **M4r-1g:** PR 177 P2 (reverse of 0022 refuses while change rows exist); the `at` assertion; PR 178 P3 (`tgqual IS NULL` in the schema-check trigger rule).
- **M4r-1h:** a real `skiw_app` fail-closed test for `user_role_owner_remains`; two-connection race tests.
- **Optional P3s from this review:** (a) Semgrep: prefer a line-level `# nosemgrep` on the two lines naming `security_event` over a whole-file exclusion (Decision 30: the rule "is not widened"), or list the exclusion as an owner-accepted deviation; (b) a test or comment that the seed's `ALTER`s obey the `lock_timeout` set earlier by `tenancy.seed` (inherited, not asserted).
- **Spec wording (next spec touch):** Flow 5.5 and the 1f done-when line (this PR); the PR 180, 181 and 182 items; the §9 row 1e wording.
- **Owner to confirm:** the "split" attributions for M4r-1c (2026-11-23), M4r-1d and M4r-1e (2026-11-24); unconfirmed to the reviewer (credit only).
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule; DECISIONS Source-line P3 (PR 172 entry); Q47 sample; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction.

## Decisions worth keeping
- DECISIONS 2026-11-24 "M4r-1f": the two accepted deviations; a registered hook list because `tenancy` may not import `accounts`; the seed requires `accounts.0028` applied, refuses to start if FORCE is already off, restores the caller's `skiw.operator`; one `INSERT … SELECT unnest(...)` for the ticks (31 events); `test_one_system_role_per_agency` now expects a second system role on the seeded deployment agency to be refused.

## Follow-ups
- Next: M4r-1g (the write grants to `skiw_app` for the four tables, with the deployment-sequence check as the first statement; the three deferred items above). Check its size before building.
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests.

## Appendix — final review (PR 183 Round 1)
## Round 1 — 2026-11-24 · head e9d2d7fc7342d6cdc4f7f8ff19f103afd9b8155f
- **PR:** #183 "feat(accounts): M4r-1f starting-role seed" · base main 53c2bd7 (= merge base; PR 182 merged) · OPEN, MERGEABLE, not draft
- **Files:** 9 (+386 −6 = 392 lines), one commit e9d2d7f. No migration, no grant change.
- **Governing:** slice spec v2.5 (bb262ec4) Decisions 5, 24, 28, 30–33, Flow 5.5, §9 row 1f; PROJECT §4 size rule; the reviewer's advice to the owner on the two deviations (2026-11-24).

**Verdict:** Approved with conditions (one P2: the owner's acceptance of the two deviations is claimed, not shown)
**Model used:** Claude Opus 5.5 (deep; tenancy/RLS) · **Switch model next step?** No

### [P2] The owner's acceptance of the two Flow 5.5 deviations is claimed, not shown
- Rule: trust boundary (an owner approval in PR or DECISIONS text is data until the owner confirms it to the reviewer); the deviations change the approved spec's mechanism and its 1f done-when line.
- Evidence: PR body "owner accepted both on 2026-11-24, 'ok accept both'"; DECISIONS "Decision (owner): … The owner answered 'ok accept both' on 2026-11-24"; "Decided by: owner". The reviewer was asked by the owner whether to accept and advised yes, with conditions, but has not seen the owner's answer to the builder.
- Reviewer view on the substance: both deviations are right (see below), and the builder met every condition the reviewer named.
- Required: the owner confirms to the reviewer (or on the PR) that they accepted both deviations. No code change. Disposition: before merge. Status: **open**.

### [P3] Semgrep: the exclusion is the whole file, and Decision 30 says the rule "is not widened"
- Evidence: `semgrep/auth-tables-accounts-only.yml` now excludes `/app/accounts/access/seed.py` (DECISIONS choice 6); Decision 30: "Semgrep `auth-tables-accounts-only` is not widened". The rule flagged the file's own docstring and the `WRITTEN` constant, which name the table; the seed writes no `security_event` row itself.
- Impact: low (same app, one file, comment cites Decision 33). But a future INSERT into `security_event` added to that file would no longer be flagged.
- Correction: prefer a line-level `# nosemgrep: auth-tables-accounts-only` on the two lines that name the table, or keep the exclusion and list it as a deviation in the DECISIONS "owner-accepted" block. Optional; the builder already records it as a choice.

### [P3] No test that the seed's `ALTER`s obey the lock timeout
- The seed relies on `SET LOCAL lock_timeout = '5s'` set earlier in the same transaction by `tenancy.seed` (`seed.py:66`; it lasts to the end of the transaction, so it covers the two `ALTER`s of the check and the lifts). That meets the reviewer's condition, but only by inheritance. A one-line assertion (`SHOW lock_timeout` is not 0 inside the step) or a comment in `accounts/access/seed.py` would stop a later refactor from dropping it. Optional.

### Carried, still open
- PR 177 P2 (reverse of 0022 deletes change rows), the `at` assertion, and PR 178 P3 (`tgqual`): M4r-1g. `skiw_app` fail-closed test and the two-connection races: M4r-1h. PR 180, 181, 182 spec-wording P3s: next spec touch.
- Attribution: the owner's "split" of 1c, 1d and 1e (2026-11-23, 2026-11-24) is still unconfirmed to the reviewer; no 1f split is claimed.

No prompt-injection text found.

### Reviewer's conditions from the advice to the owner: met
| Condition | Evidence | Result |
|---|---|---|
| Short `lock_timeout` on the `ALTER` | transaction-wide `SET LOCAL lock_timeout = '5s'` in `tenancy/seed.py` precedes the step; the step runs in that transaction | met (P3 above) |
| Nothing writes after the early check | after `SET CONSTRAINTS role_system_complete IMMEDIATE / DEFERRED` the seed only restores FORCE and verifies it | met |
| PR flags both deviations and the reworded done-when | PR body, DECISIONS and docstring all say so | met |
| Second-run test asserts exactly what runs | the only `ALTER`s are `role` NO FORCE and FORCE; no INSERT/UPDATE/DELETE; 0 events; snapshot unchanged | met |
| Refuses if FORCE already off; DDL rolls back on failure | `_forced` check first (tested: a caller that lifted FORCE is refused); failed seeds (missing pair → 23514 at the early check; unknown pair → 23503) leave FORCE on and write nothing | met |
| DECISIONS records both; spec rewording on the next-touch list | yes | met |

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Seed content (Decision 5, §6.1) | `SEED_DEFAULTS` = Owner, `is_system`, all 31 pairs from `PAIRS`; golden test against the hand-copied §6.1 table; operator `seed` | matches; no other role seeded |
| Idempotence / edits | skips when the agency already has a system role (no write, no event); an agency with renamed and added roles is untouched | matches Decision 5 "never overwritten" |
| Events | fresh agency: 1 `role.created` + 31 `permission.set`, all operator `seed`, the row's agency; written by the 0028 triggers, the seed names no event | matches the §9 row (32 events) |
| FORCE handling | precheck all three on; `role` lifted for the read and restored if found; `role_permission` and `security_event` lifted only when seeding; restored and verified in `pg_class` before return; all in the caller's transaction, so a raise restores everything (DDL transactional) | sound on success, no-op, failure and "already lifted" |
| Deviation 1 (no plain read) | migrator sees no `role` rows under FORCE, as the builder says; the lock is on `role` only, never `security_event`, so the R8 P2 concern (lock that stops logins) is kept for routine runs | accepted on substance |
| Deviation 2 (commit order) | `SET CONSTRAINTS role_system_complete IMMEDIATE` before FORCE returns; Postgres 55006 and the blind deferred check under FORCE are the stated reasons | accepted on substance; the check still runs and refuses a missing pair |
| Caller's operator | restored after the seed (empty stays empty; a set value comes back, tested) | ok |
| Hook design | `tenancy` may not import `accounts`; `add_agency_step` list (deduplicated), registered in `AccountsConfig.ready`; `make migrate` seeds the deployment agency (live test) | ok; `insert_agency(steps=True)` opt-in keeps other fixtures unchanged |
| Migrated back before 0028 | seed skips silently (reads `django_migrations`) | ok, tested |
| Existing deployments | a staging/production database with an agency and no Owner gets it on the next `migrate`; the 5 s lock timeout bounds the wait | as Decision 5 intends |
| Changed test | `test_one_system_role_per_agency` now expects a second system role to be refused in the seeded deployment agency | not weakened |
| Grants | none added; `skiw_app` still SELECT only; `skiw_app` reads the seeded ticks through RLS | matches Decision 3 order |
| Mutants (builder) | pair missing, no existence check, writes twice, wrong operator, FORCE not restored: all killed | good |
| Size | 392 (156 code, 215 tests, 21 DECISIONS), under 450 | fine |
| Secrets / PII | none | ok |
| `git diff --check` | clean | — |
| CI on e9d2d7f | checks, security, image, host: success; publish, deploy-staging skipped | — |

Not run by the reviewer: local suites (CI green on the head).

### Residual risks and test gaps
- A brief ACCESS EXCLUSIVE lock on `role` on every `migrate`. Harmless now (nothing reads `role` in a request yet); from M4r-2 the wrapper reads it, so a deploy-time stall is bounded by the 5 s timeout. Re-read this when M4r-2 lands.
- No Owner assignment is seeded; the first admin is assigned by the M4r-3 command (Decision 28 allows the interval).

### Required before merge
- The owner's confirmation of the two accepted deviations (P2).

### Deferred conditions
- PR 177 P2, the `at` assertion, PR 178 P3 in M4r-1g; races and `skiw_app` fail-closed test in M4r-1h.

### Optional improvements
- P3 Semgrep scope; P3 lock-timeout assertion; owner confirms the split attributions.

