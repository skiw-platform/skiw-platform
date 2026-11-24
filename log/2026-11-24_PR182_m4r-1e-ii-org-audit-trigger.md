# PR 182 — feat(accounts): M4r-1e-ii org_unit audit trigger

- **Merged:** 2026-11-24 (11:16:45 UTC) · **Merge commit:** 53c2bd7993a25729629b1fa5e64c276e079d7d3a · **Branch:** feat/m4r-1e-ii-org-audit-trigger
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-182.receipt, created 2026-11-24 11:15:38 UTC, before the merge; names head 687760dfdcf7bf3e2e48c6a5fda0351fe5915bcd and review hash c7429807…
- **Merge evidence:** `gh pr view 182` state MERGED, merge commit above, mergedAt 11:16:45Z; reachable from the fetched origin/main. Final head 687760dfdcf7bf3e2e48c6a5fda0351fe5915bcd equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1e-ii (second half of M4r-1e, split by the owner on 2026-11-24)

## What changed
Migration 0029, no write grants: `org_unit_audit` (AFTER INSERT OR UPDATE FOR EACH ROW) writes `org.added` on INSERT; on UPDATE it refuses a changed `id`, `agency_id`, `kind` or `created_at`, writes `org.moved` when `parent_id` changed and `org.renamed` when `name` changed (two events for both, none for neither). Operator check reused from 0028; SECURITY INVOKER, pinned `search_path`, EXECUTE revoked from PUBLIC; reverse starts with 0026's write-grant guard. The function scan now expects the six functions of the spec. All ten change kinds are now written by the database. DECISIONS entry with eight choices and a correction of the PR 181 seed note. 389 lines (about 92 code, 257 tests, 23 docs).

## Why
Decision 32: no org unit can be added, moved or renamed without its change record, and the change and its events commit or roll back together.

## Review rounds
- R1: Approved, no required corrections. The reviewer confirmed the builder's choice 6 (no org deferred check exists; the statement-level equivalent, a tree-guard refusal writing no event, meets the intent). The PR 181 P3 about the seed note is fixed in this PR.

## Deferred conditions
- **P2 (PR 177, unchanged):** the reverse of migration 0022 must refuse while change rows exist, with a live test → M4r-1g.
- **M4r-1g:** the `at` assertion (event `at` equals the statement time); PR 178 P3 (`tgqual IS NULL` in the schema-check trigger rule).
- **M4r-1h:** real `skiw_app` fail-closed test for `user_role_owner_remains` and the two-connection races.
- **Spec wording (next spec touch):** the §9 row 1e "a deferred-check failure leaves no event" (role and user_role by deferred check; org_unit by the tree guard); the PR 180 and 181 items (deferred-check lock wording, descendant walk, "root = level 1" for `scoped()`, a no-op `role` UPDATE without an operator is refused, Decision 32's "with every trigger on" omits the NO FORCE on `security_event`).
- **Owner to confirm:** the attributions "split by the owner" for M4r-1c (2026-11-23), M4r-1d and M4r-1e (2026-11-24); unconfirmed to the reviewer (credit only; a split past 450 needs no owner approval).
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule; DECISIONS Source-line P3 (PR 172 entry); Q47 sample; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction.

## Decisions worth keeping
- DECISIONS 2026-11-24 "M4r-1e-ii": operator check, then the immutable-column refusal, then the events; the refusal reuses 0026's code and message (42501); the check compares values, not the SET list; `org.moved` before `org.renamed`, same timestamp; no org deferred check exists; FK, CHECK and unique errors precede the immutable-column refusal; test helpers set the operator and lift FORCE, the event sort ignores key order inside details.

## Follow-ups
- Next: M4r-1f (starting-role seed: `accounts.access.seed` with `SEED_DEFAULTS`, the post-migrate seed step in the agency seed transaction, reserved operator code `seed`). Cite Decision 33: the seed writes under transaction-local `NO FORCE` on `role`, `role_permission` and `security_event`.
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests.

## Appendix — final review (PR 182 Round 1)
## Round 1 — 2026-11-24 · head 687760dfdcf7bf3e2e48c6a5fda0351fe5915bcd
- **PR:** #182 "feat(accounts): M4r-1e-ii org_unit audit trigger" · base main e5ef0cf (= merge base; PR 181 merged) · OPEN, MERGEABLE, not draft
- **Files:** 7 (+366 −23 = 389 lines), one commit 687760d.
- **Governing:** slice spec v2.5 (bb262ec4) Decisions 30, 31, 32; §7 "Personal data in a change event", "Other code writes or forges change events"; §9 row 1e; PR 181 review.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep; tenancy/RLS) · **Switch model next step?** No

### Findings
No blocking findings.

### Builder question: choice 6 — confirmed
- No org deferred check exists (0027's two are on `role` and `user_role`), so the §9 row 1e wording "a deferred-check failure leaves no event" applies to `role` and `user_role` (tested in PR 181) and, for `org_unit`, to the statement-level equivalent tested here: a tree-guard refusal (cycle, depth 33) writes no event and changes nothing. I agree this meets the intent. Note the same wording at the next spec touch.

### [P3] Carried, still open
- PR 177 P2 (reverse of 0022 deletes change rows) and the `at` assertion: M4r-1g.
- PR 178 P3 (`tgqual IS NULL` in the schema-check trigger rule); PR 180 P3 (spec wording on the lock function and the descendant walk); PR 181 P3 (no-op role UPDATE without an operator is refused; spec wording).
- Attribution: PR body and DECISIONS (M4r-1e-i entry, referenced here) say the owner chose "split" on 2026-11-24. Not confirmed to the reviewer for 1c, 1d or 1e. A split past 450 needs no owner approval; this is only about credit. The 1e-ii "Decided by" line is correctly "builder".
- The PR 181 P3 about the seed note is **fixed** in this PR (DECISIONS now cites Decision 33).

No prompt-injection text found.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Trigger | `org_unit_audit` AFTER INSERT OR UPDATE (any column) FOR EACH ROW, one function | matches Decision 32 |
| Events and keys | INSERT → `org.added` (`org_unit_id`, `parent_id` = id or JSON null for the root, `unit_kind`); `parent_id IS DISTINCT` → `org.moved` (`old_parent_id` from OLD, `new_parent_id`); `name IS DISTINCT` → `org.renamed` (`org_unit_id` only); both → two events; neither → none | matches Decision 30 lists exactly (also checked by `security_event_shape` at depth 2); no names in any event, not even the new name |
| Immutable columns | row-value compare of `(id, agency_id, kind, created_at)` OLD vs NEW → 42501 with 0026's fixed message, naming no data; values compared, so `SET kind = kind` is accepted with no event (choice 4) | matches "refused if … changed"; each column and kind+name tested, nothing written; FK/CHECK errors come first (choice 7) |
| Operator check | 0028's `OPERATOR_CHECK` reused unchanged and inline, run first on every row; four org statements added to the nine bad-operator cases | matches Decision 31; nothing changed, no event |
| Atomicity | AFTER row; change and events roll back together; a tree-guard refusal writes none | matches |
| Per-row and per-field count | multi-row UPDATE: one `org.moved` per moved row and one `org.renamed` per renamed row | matches the event-count rule |
| RLS / agency | SECURITY INVOKER; event carries the row's agency; A sees it, B does not | matches Decision 33 |
| Function shape | plpgsql, SECURITY INVOKER, pinned `search_path`, schema-qualified, EXECUTE revoked from PUBLIC, owned by skiw_migrator; checked live | matches |
| Migration reuse | imports 0026 / 0028 constants instead of editing merged migrations | right call (choice 1) |
| Trigger set / scan | exact set now includes `org_unit_audit`; `pg_proc` scan = the six functions of the spec (two lookup definers + four audit) | §9 row 1e done-when met |
| Reverse | 0026's write-grant guard first, then drops trigger and function; earlier reverse tests run 0029's first | matches |
| No write grants | none; grant audit unchanged | matches Decision 3 order |
| Helper changes | `_audited` also wraps the `org_unit` harness case; event sort now ignores key order inside each details object (a real jsonb vs Python difference the first live run exposed); the first assertion now also expects the two `org.added` events (stricter) | no assertion weakened |
| Mutants (builder) | trigger missing, operator check removed, moved/renamed swapped, key dropped, immutable refusal removed, no-op writes an event: all killed | good |
| Size | 389, under 450 | fine |
| Secrets / PII | none | ok |
| `git diff --check` | clean | — |
| CI on 687760d | checks, security, image, host: success; publish, deploy-staging skipped | — |

Not run by the reviewer: local suites (CI green on the head).

### Residual risks and test gaps
- The immutable-column refusal is in an AFTER trigger, so it fires after the BEFORE guards and after the row is written; it still aborts the statement. M4r-1g should also grant UPDATE on `org_unit` by column (`parent_id`, `name`) as defence in depth; the trigger is the guarantee either way.
- The real `skiw_app` write path and the seed are M4r-1g and M4r-1f. All ten change kinds are now database-written.

### Required before merge
- none

### Deferred conditions
- PR 177 P2 and the `at` assertion in M4r-1g.

### Optional improvements
- The carried P3s; owner confirms the split attributions.

