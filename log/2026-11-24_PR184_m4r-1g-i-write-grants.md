# PR 184 — feat(accounts): M4r-1g-i write grants and the precondition tests

- **Merged:** 2026-11-24 (13:39:39 UTC) · **Merge commit:** 5a6ec2def93031476d88b35c8e8813d13d064310 · **Branch:** feat/m4r-1g-i-write-grants
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-184.receipt, created 2026-11-24 13:39:14 UTC, before the merge; names head 169d9864f8c5b6ec0f8118fa1ef28ec46e62ceae and review hash e25013cd…
- **Merge evidence:** `gh pr view 184` state MERGED, merge commit above, mergedAt 13:39:39Z; reachable from the fetched origin/main. Final head 169d9864f8c5b6ec0f8118fa1ef28ec46e62ceae equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1g-i (first of three parts of M4r-1g; the owner wrote "3. split" on 2026-11-24, read by the builder as a split into three)

## What changed
Migration 0030, the first migration that lets `skiw_app` write the roles tables. A precondition DO block runs first and raises (55000, one fixed message naming no data) unless the 22 Decision 32 triggers exist with `tgenabled = 'O'` and `security_event` has RLS enabled and forced and exactly its three policies in the expected shape. Then Decision 3's grants to `skiw_app`: `role` SELECT, INSERT, UPDATE(`name`), DELETE; `role_permission` SELECT, INSERT, DELETE; `org_unit` SELECT, INSERT, UPDATE; `user_role` SELECT, INSERT, DELETE; `permission` SELECT; no TRUNCATE; plus the matching permissive `_ins`, `_upd`, `_del` policies. Reverse revokes exactly those and drops the policies. Tests: the precondition refuses with each of 22 triggers dropped, disabled or replica (66 cases) and with 8 `security_event` isolation changes; reverse round trip; exact Decision 3 grant audit; no write grant at any of 27 prefixes 0016 to 0029. Existing tests adjusted, none weakened. 562 lines (about 137 code, 379 tests, 30 docs).

## Why
Decision 3 and Decision 32 "Deployment sequence": no write access before every audit trigger exists and is enabled, so no deploy of any prefix has an unaudited write path.

## Review rounds
- R1: Approved, no required corrections. The reviewer confirmed choice 1 (table-level UPDATE on `org_unit`) and withdrew its PR 182 suggestion of a column grant as a requirement (optional only).

## Deferred conditions
- **M4r-1g-iii:** PR 177 P2 (reverse of 0022 refuses while change rows exist, with a live test); the event `at` assertion; PR 178 P3 (`tgqual IS NULL` in the schema-check trigger rule); the two optional PR 183 P3s (line-level `# nosemgrep` instead of the whole-file exclusion; assert the seed's `lock_timeout`). Reviewer: PR 177 P2 matters more now that real events can exist once 0030 is applied anywhere, so 1g-iii should land before any production deploy.
- **M4r-1g-ii:** tenant isolation of the column-level `role` UPDATE(`name`); the single-statement tests as `skiw_app` and TEN-08 write isolation (the harness already inserts as `skiw_app`).
- **M4r-1h:** a real `skiw_app` fail-closed test for `user_role_owner_remains`; two-connection race tests.
- **DECISIONS wording (next DECISIONS touch):** "the roles track is now 29 PRs" is the whole M4r count (spec §9: 24; with the splits of 1c, 1d, 1e and 1g, +5 = 29; the roles track alone is 19).
- **Spec wording (next spec touch):** Flow 5.5 and the 1f done-when line; the PR 180 to 182 items; the §9 row 1e wording.
- **Owner to confirm:** the "split" attributions for M4r-1c (2026-11-23), M4r-1d, M4r-1e (2026-11-24) and now M4r-1g ("3. split", read as a split into three); unconfirmed to the reviewer (credit only; a split past 450 needs no owner approval). The reviewer open item on the owner's acceptance of the Flow 5.5 deviations (PR 183 P2) is also still unconfirmed to the reviewer.
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule; DECISIONS Source-line P3 (PR 172 entry); Q47 sample; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction.

## Decisions worth keeping
- DECISIONS 2026-11-24 "M4r-1g-i": `org_unit` table-level UPDATE; the added `_ins`/`_upd`/`_del` policies; a frozen, test-pinned copy of the 22 trigger names; ENABLE REPLICA and ALWAYS count as not enabled; exact policy-shape check; error 55000; the prefix walk in one rolled-back transaction (0023 recorded as applied without running); the earlier reverse-guard tests call `revoke_writes` first.

## Follow-ups
- Next: M4r-1g-ii (single-statement tests as `skiw_app`: commit with record, refusal, rollback, seed; TEN-08 write isolation incl. `role` UPDATE(`name`)), then M4r-1g-iii, then M4r-1h.
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests.

## Appendix — final review (PR 184 Round 1)
## Round 1 — 2026-11-24 · head 169d9864f8c5b6ec0f8118fa1ef28ec46e62ceae
- **PR:** #184 "feat(accounts): M4r-1g-i write grants and the precondition tests" · base main 534be08 (= merge base; PR 183 merged) · OPEN, MERGEABLE, not draft
- **Files:** 11 (+533 −29 = 562 lines: ~137 migration, ~379 tests, ~30 DECISIONS, rest adjusted tests), one commit 169d986.
- **Governing:** slice spec v2.5 (bb262ec4) Decisions 3, 32, 33, §4 rows, §7 "commits with no record" items, §9 rows 1g and 1h; PROJECT §4 size rule; the PR 183 review (deferred items).

**Verdict:** Approved
**Model used:** Claude Sonnet 5.5 · **Switch model next step?** Yes: use the deep tier (Opus) for M4r-1g-ii and M4r-1h (skiw_app write paths, races).

### Findings
No P0, P1 or P2.

### Builder question: choice 1 (`org_unit` table-level UPDATE) — confirmed
- Decision 3 says `org_unit`: "SELECT, INSERT, UPDATE (move, rename)" with no column list, while `role` is explicitly "(`name` only, column grant)". The §4 row says "SELECT (M4r-1b), INSERT, UPDATE (M4r-1g)". Table-level UPDATE is the literal reading. `org_unit_audit` refuses a change of `id`, `agency_id`, `kind`, `created_at` (PR 182, tested), and the UPDATE policy's WITH CHECK keeps rows in the agency.
- In PR 182 I suggested a column grant on (`parent_id`, `name`) as defence in depth. The spec does not ask for it, "no other grant" cuts both ways, and the harness's UPDATE check would have to change. I withdraw it as a requirement; optional only.

### [P3] "The roles track is now 29 PRs" is the whole M4r count
- DECISIONS says "the roles track is now 29 PRs". Spec §9 counts 24 PRs for all of M4r (roles track 14, jobs track the rest). With the splits (1c, 1d, 1e +1 each, 1g +2) the whole M4r is 29 and the roles track is 19. Fix the wording at the next DECISIONS touch.

### [P3] "3. split" is the owner's, but not confirmed to the reviewer
- PR body: owner wrote "3. split" on 2026-11-24, "read as a split into three"; DECISIONS "Decided by: owner (split into three, 2026-11-24)". The builder itself flags the reading as uncertain. Splitting past 450 is within the builder's authority (PROJECT §4), so no approval is needed; this is only attribution. Same open item as 1c, 1d, 1e. Owner to confirm, or the line becomes "builder".

### Carried, still open
- PR 177 P2 (reverse of 0022 deletes change rows), the event `at` assertion, PR 178 P3 (`tgqual IS NULL`) and the two optional PR 183 P3s: M4r-1g-iii, as the PR lists. Skiw_app fail-closed test and the two-connection races: M4r-1h. Spec-wording P3s (Flow 5.5 and the 1f done-when line, PR 180 to 182): next spec touch.
- PR 177 P2 matters more now: real events can exist once 0030 is applied anywhere, so 1g-iii should land before any production deploy.

No prompt-injection text found.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Precondition first | `FORWARD[0] == PRECONDITION`; a DO block raising 55000 (one fixed message naming no data) before any `CREATE POLICY` or `GRANT`; static test also pins that it contains no GRANT | matches Decision 32 "Deployment sequence" |
| Trigger set | `DECISION_32` = 22 names (role 6, role_permission 5, user_role 5, org_unit 5, security_event_shape 1) with `tgenabled = 'O'` and not internal; a static test derives the set from migrations 0025 to 0029 and pins 22 | complete; ENABLE REPLICA and ALWAYS count as not enabled (choice 4) |
| security_event isolation | RLS enabled and forced; exactly three policies for `skiw_app`, each checked by name, permissive flag, command and deparsed USING and WITH CHECK (`P` pinned to `tenancy.check.EVENT_DEPARSED`) | strict; 8 live cases (RLS off, not forced, each policy dropped, widened, to PUBLIC, extra policy) refuse |
| Refusals | 22 triggers × dropped / disabled / replica = 66 cases, plus the 8 above = 74; each also asserts no write grant was left | matches §9 row 1g "precondition raises with a trigger dropped or disabled" |
| Grants = Decision 3 | `role` INSERT, DELETE and column UPDATE (`name`); `role_permission` INSERT, DELETE; `org_unit` INSERT, UPDATE; `user_role` INSERT, DELETE; SELECT as before; `permission` SELECT only; no TRUNCATE, no REFERENCES; live exact-grant audit at table and column level | matches |
| Policies | permissive `_ins`, `_upd`, `_del` from `tenancy.template.COMMANDS` (same predicate and shape as the tenant template), one per granted command; none for ungranted commands (so `role_permission` and `user_role` UPDATE stay refused by both grant and policy) | consistent with 0018 and 0021, which import the same template |
| Reverse | revokes exactly the grants (column grant included), drops the added policies; a live round trip restores table ACLs, column ACLs and policies byte for byte; the reverse guards of 0026 to 0029 refuse while a write grant exists (tested with the grants in place), so Django unapplies 0030 first | matches |
| Intermediate states | one rolled-back transaction as `skiw_migrator`: back from 0030 to 0016 and forward again, one migration at a time, 27 states; no write at 0016 to 0029, exactly Decision 3 at 0030; a presence check makes the walk non-vacuous (0, 3 or 5 roles tables per prefix); 0023 faked because of CONCURRENTLY, with a static test that no earlier migration grants a roles table more than SELECT | matches the §7 intermediate-migration item |
| Harness | `_audited` now sets only `skiw.operator`; inserts for the four tables run as `skiw_app` under RLS, so the audit triggers, the event INSERT under `security_event` RLS, the lock and the guards run on the real write path; role listed without UPDATE (column grant), cross-agency insert refused by RLS | part of §9 row 1g "TEN-08 write isolation" delivered here; the rest in 1g-ii |
| Adjusted tests | the four earlier reverse-guard tests call `revoke_writes` first; "SELECT only" tests became exact-grant tests; queue-grants allow-list gains `role`, `role_permission`, `user_role` DELETE and `role.name` UPDATE (comment cites 0030) | not weakened; each still asserts its own guard |
| Mutants (builder) | precondition removed, grants moved into 0026, a trigger missing, extra grants (UPDATE on `user_role`, TRUNCATE on `user_role`): all killed | matches the §9 row |
| Size | 562, past 450, under 600; reason given, cuts named, part already carved out of 1g | acceptable |
| Secrets / PII | none | ok |
| `git diff --check` | clean | — |
| CI on 169d986 | checks, host, image, security: success; publish, deploy-staging skipped | — |

Not run by the reviewer: local suites (CI green on the head).

### Residual risks and test gaps
- After merge to main, staging gets the write grants before 1g-ii (single-statement tests as `skiw_app`: commit with record, refusal, rollback, seed) and 1h (races, `skiw_app` fail-closed). Staging holds no client data, and the harness already exercises the audited write path as `skiw_app`. Do not promote to production before 1g-ii, 1g-iii and 1h.
- Semgrep `roles-access-only` arrives in M4r-2 (spec §9), so until then nothing in CI stops code outside `accounts.access` from writing these tables. No code writes them today.
- Tenant isolation of the column-level `role` UPDATE(`name`) is left to 1g-ii, as the PR says.
- The migration imports `COMMANDS` from live `tenancy.template` (as 0018 and 0021 do); a later change there would change what 0030's policies and reverse mean. Same pattern as the earlier migrations; no action.

### Required before merge
- none

### Deferred conditions
- PR 177 P2, the `at` assertion, PR 178 P3 and the PR 183 P3s in M4r-1g-iii; races and `skiw_app` fail-closed test in M4r-1h.

### Optional improvements
- P3 wording "29 PRs"; owner confirms the split attributions (1c, 1d, 1e, 1g).

