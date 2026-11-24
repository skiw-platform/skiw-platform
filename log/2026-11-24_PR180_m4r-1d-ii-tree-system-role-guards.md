# PR 180 — feat(accounts): M4r-1d-ii org_unit tree guard, system-role guards and deferred checks

- **Merged:** 2026-11-24 (09:45:15 UTC) · **Merge commit:** 1058766c3c0240bfce008684f7a0c7268fe429b3 · **Branch:** feat/m4r-1d-ii-tree-system-role-guards
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-180.receipt, created 2026-11-24 09:44:40 UTC, before the merge; names head 453d06fce0e034fb3cfb906f308b7ee772c659d0 and review hash 60730c3e…
- **Merge evidence:** `gh pr view 180` state MERGED, merge commit above, mergedAt 09:45:15Z; reachable from the fetched origin/main. Final head 453d06fce0e034fb3cfb906f308b7ee772c659d0 equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1d-ii (second half of M4r-1d, split by the owner on 2026-11-24)

## What changed
Migration 0027, no write grants: `org_unit_tree_guard` (BEFORE INSERT OR UPDATE OF parent_id; bounded walk, no cycle, path of at most 32 units, root = level 1; sorts after `org_unit_roles_lock`); BEFORE DELETE guards on `role` and `role_permission` for the system (Owner) role; deferred constraint triggers `role_system_complete` and `user_role_owner_remains`. SECURITY INVOKER, pinned `search_path`, EXECUTE revoked from PUBLIC; reverse starts with 0026's write-grant guard. DECISIONS entry with eight choices. 589 lines (about 203 code, 375 tests, 11 docs). The optional PR 178 P3 (`tgqual IS NULL`) was built and cut for size.

## Why
Decision 27 keeps the org tree a tree of bounded depth under concurrent writers; Decision 28 means no sequence of statements can leave an agency without a complete Owner role or an Owner.

## Review rounds
- R1: Approved, no required corrections. The reviewer agrees with choices 1 and 3 (and finds 4 sound); spec wording to align at the next spec touch.

## Deferred conditions
- **P2 (PR 177, unchanged):** the reverse of migration 0022 must refuse while change rows exist, with a live test → M4r-1g.
- **M4r-1h:** a real `skiw_app` fail-closed test for `user_role_owner_remains` (clear the token before commit) and the two-connection race tests.
- **PR 178 P3:** `tgqual IS NULL` in the schema-check trigger rule (plus a mutant); suggested at M4r-1g, which re-reads the trigger set.
- **Spec wording (next spec touch):** Decision 28's "take the same lock function" (deferred checks retake the lock with 0026's expression and skip the isolation check); Decision 27's ancestor-only walk (the guard also walks descendants); state "root = level 1, at most 32 units" for `scoped()` in M4r-4.
- **Owner to confirm:** the attributions "split by the owner" for M4r-1c (2026-11-23), M4r-1d (2026-11-24). The owner asked "do you confirm?" in the PR 179 follow-up and has not yet answered; the builder's choices 3 and 4 in this PR are recorded as builder decisions, not owner decisions.
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule; DECISIONS Source-line P3 (PR 172 entry); Q47 sample; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction.

## Decisions worth keeping
- DECISIONS 2026-11-24 "M4r-1d-ii": deferred checks retake the roles lock instead of a plain helper; depth is root = level 1, max 32; the tree guard walks descendants too; `user_role_owner_remains` fails closed when the writer cannot see the agency at commit; error codes 23514 (tree, deferred checks) and 42501 (Owner guards); deferred checks tested with SET CONSTRAINTS ALL IMMEDIATE and with a real COMMIT.

## Follow-ups
- Next: M4r-1e (audit triggers on `role`, `role_permission`, `user_role`, `org_unit` writing change records through the shape trigger).
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests.

## Appendix — final review (PR 180 Round 1)
## Round 1 — 2026-11-24 · head 453d06fce0e034fb3cfb906f308b7ee772c659d0
- **PR:** #180 "feat(accounts): M4r-1d-ii org_unit tree guard, system-role guards and deferred checks" · base main a9782e2 (= merge base; PR 179 merged) · OPEN, MERGEABLE, not draft
- **Files:** 4 (+581 −8 = 589 lines), one commit 453d06f.
- **Governing:** slice spec v2.5 (bb262ec4) Decisions 2, 27, 28, 32; §7 "Concurrent opposing moves create a cycle"; §9 row 1d; PROJECT §4 size rule; PR 179 review notes.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep; tenancy/RLS) · **Switch model next step?** No

### Findings
No blocking findings.

### [P3] Spec wording to align at the next spec touch (not a code change)
- Decision 28 says the deferred checks "take the same lock function and so carry the same refusal"; Decision 27 names only the ancestor walk. The PR does two things differently and says so (choices 1, 3):
  - The deferred checks retake the lock with 0026's expression and do not repeat the isolation check. I agree: a deferred check only exists once a row trigger of the same transaction has run, and that trigger refused any level but READ COMMITTED; the level cannot change after the first query.
  - The tree guard also walks the descendants of the moved unit. Without it a subtree could be moved past 32 levels, so the spec's own "chain deeper than 32 → rejected" would not hold. This is stricter than the text and in line with its intent.
- Neither widens what the app can do, so I do not see them as needing an owner decision. The builder asks for the reviewer's and owner's eye; the reviewer's is given here. Align the spec wording (and "root = level 1" for `scoped()`, M4r-4) when the spec is next touched.

### [P3] Carried, still open
- PR 178 P3: `tgqual IS NULL` in the schema-check trigger rule. The builder built it and cut it for size; it stays open for the next schema-check touch (suggest M4r-1g, which adds the write grants and re-reads the trigger set).
- Attribution: the PR body again says "split by the owner on 2026-11-24"; the owner's confirmation of the 1c (2026-11-23) and 1d (2026-11-24) splits has not reached the reviewer. The DECISIONS "Decided by" line here correctly says builder.

No prompt-injection text found.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Tree guard (Decision 27) | BEFORE INSERT OR UPDATE OF parent_id, row level; root (NULL parent) left to the CHECKs and the one-root index; UP walk from `NEW.parent_id` and DOWN walk from `NEW.id`, each `CYCLE id` and capped at 32 rows; refuses 23514 on `NEW.id` among ancestors, a flagged repeat, or ancestors + subtree levels > 32 | logic read and sound: ancestors count includes the root, subtree count includes the unit itself, so the sum is the path length; a truncated walk always fails the sum |
| Order after the lock | `org_unit_tree_guard` sorts after `org_unit_roles_lock`; the guards on `role` and `role_permission` after their lock triggers; a test reads the order from `pg_trigger` and a RR move gets the isolation refusal first | closes the PR 179 note |
| Fresh snapshots | volatile plpgsql, each query its own snapshot; one-statement swap is refused (rows changed earlier in the statement are seen) | matches the [A] item for 1h's two-connection proof |
| Cross-agency parent | walk filtered to `NEW.agency_id`; a parent in another agency yields an empty walk and the composite FK refuses (23503, tested) | ok |
| Depth tests | 32 accepted, 33rd refused, moved subtree counted, planted cycle ends the walk and is refused as a cycle, self / child / grandchild moves, root under its child, second root, non-root with NULL parent | matches §9 row 1d |
| Owner guards (Decision 28) | BEFORE DELETE on `role` WHEN OLD.is_system and on `role_permission` of the agency's system role → 42501; non-system roles and ticks delete normally; rename allowed; `is_system` flip (0026) and a second system role (unique index) refused | matches; nested IF avoids the PL/pgSQL parse of `role_id` on `role` |
| `role_system_complete` | constraint trigger AFTER INSERT on `role` WHEN NEW.is_system, DEFERRABLE INITIALLY DEFERRED; lock retaken; refuses 23514 unless every `permission` row is ticked; hidden rows make it fail closed (RLS shows fewer ticks) | matches; refused at a real COMMIT, accepted when built over several statements |
| `user_role_owner_remains` | AFTER UPDATE OR DELETE on `user_role`, deferred; lock retaken; refuses when no assignment to the system role is left; allowed before the first assign, for non-Owner rows, and when one of two holders goes or the only holder is replaced in the same transaction | matches; the "writer cleared its token before commit" gap is closed by the unit-visible probe (choice 4). This is a real hole closed beyond the spec, and a sound one: org units are never deleted (0026), so a missing unit can only mean the row is hidden |
| Lock behaviour | re-entrant retake at commit; a savepoint rollback releases the lock only together with the row change and its queued check (builder tested directly) | consistent with Decision 27's serialisation; the two-connection proof is M4r-1h |
| Function shape | plpgsql, SECURITY INVOKER, pinned `search_path`, schema-qualified, EXECUTE revoked from PUBLIC, owned by skiw_migrator; no body names `security_event` | live test over all six functions; the PR 178 `pg_proc` scan is unaffected |
| Trigger set | exact set (now 17) with tgtype, function, WHEN presence, `'O'`, and deferred flags (only the two constraint triggers) | matches |
| Reverse | starts with 0026's write-grant guard (same statement), drops 5 triggers and 4 functions; the 0026 reverse test now runs 0027's first | matches §9 row 1d |
| No write grants | none; grant audit unchanged | matches Decision 3 order |
| Mutants (builder) | tree guard missing, depth loosened in SQL and in the constant, `role_permission` guard missing, `role` guard missing, `user_role_owner_remains` missing, `role_system_complete` missing, fail-closed probe removed: all killed | strong |
| Size | 589 (203 code, 375 tests, 11 DECISIONS), under 600; one P3 cut to stay under; reason for one PR given | acceptable |
| Secrets / PII | none; messages name no data | ok |
| `git diff --check` | clean | — |
| CI on 453d06f | checks, security, image, host: success; publish, deploy-staging skipped | the builder did not re-run the live suites after the cut; CI's live run covers the head |

Not run by the reviewer: local suites (CI green on the head).

### Residual risks and test gaps
- All behaviour is proved on one connection as the migrator. The concurrent proofs (waiter sees the first writer's commit, opposing moves, last-Owner race) and the real `skiw_app` fail-closed test are M4r-1h, as listed.
- Any `skiw_app` session can call `pg_advisory_xact_lock` with this class and key and hold it (same as the documents lock). With one agency per deployment this is a self-inflicted stall at worst; noted, no action.
- PR 177 P2 (reverse of 0022 deletes change rows) is still open for M4r-1g.

### Required before merge
- none

### Deferred conditions
- PR 177 P2, unchanged. Real `skiw_app` fail-closed test and two-connection races in M4r-1h.

### Optional improvements
- The P3 spec wording; the PR 178 `tgqual` rule; owner confirmation of the split attributions.

