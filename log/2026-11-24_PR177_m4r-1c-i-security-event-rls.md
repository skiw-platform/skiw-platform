# PR 177 — feat(accounts): M4r-1c-i security_event agency column, CHECKs, RLS and schema-check rule

- **Merged:** 2026-11-24 (01:21:48 UTC) · **Merge commit:** a05ad5d6a569142d34cae7a49252559f2ccd3493 · **Branch:** feat/m4r-1c-i-security-event-rls
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-177.receipt, created 2026-11-24 01:21:32 UTC, before the merge; names head e61a0b913974209eb27e01b740bd9d10a46aae7b and review hash 8a68a183…
- **Merge evidence:** `gh pr view 177` state MERGED, merge commit above, mergedAt 01:21:48Z; reachable from the fetched origin/main. Final head e61a0b913974209eb27e01b740bd9d10a46aae7b equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1c-i (first half of M4r-1c, split by the owner on 2026-11-23)

## What changed
`security_event` gets a nullable `agency_id` (FK to `agency`) and two CHECKs (the ten change kinds exactly when `agency_id` is set; change kinds carry no `email_hmac` or `ip_hmac`), ENABLE + FORCE RLS and the three Decision 33 policies for `skiw_app`, a new index `security_event_agency_id`, a named schema-check rule (12 mutants flagged), a hand-registered TEN-08 case, and the migrator test helper moved to NO FORCE. Migrations 0022 to 0024. DECISIONS entry with seven choices. 544 lines (about 232 code, 297 tests, 15 docs).

## Why
Owner decision Q6 (2026-11-21, kept as a safety net under one agency per deployment): change records must never cross agencies, while existing login, throttle, factor-lock and passkey events (no agency) keep working.

## Review rounds
- R1: Approved, no required corrections. One deferred P2.

## Deferred conditions
- **P2:** the reverse of migration 0022 must refuse while change rows exist, with a live test → M4r-1g (it deletes change-kind rows today, which is safe only while no such row can exist outside tests).
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule before any M20 PR; DECISIONS Source-line P3 (PR 172 entry); Q47 sample from the owner; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction at the next spec touch.

## Decisions worth keeping
- DECISIONS 2026-11-23 "M4r-1c-i": the split (owner), the new index, the delete-on-reverse choice with its M4r-1g condition, CHECKs in the model, the three copies of the kind list, the global-list test tweak, the FORCE assertion in the owner helper, and change rows planted by direct INSERT until M4r-1c-ii adds the probe trigger.

## Follow-ups
- Next: M4r-1c-ii (`security_event_shape` trigger, closed key lists, the `pg_trigger_depth` rule, the probe-trigger fixture); it must switch the harness case and the own-agency test to the probe trigger.
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests (see the PR 175 log).

## Appendix — final review (PR 177 Round 1)
## Round 1 — 2026-11-24 · head e61a0b913974209eb27e01b740bd9d10a46aae7b
- **PR:** #177 "feat(accounts): M4r-1c-i security_event agency column, CHECKs, RLS and schema-check rule" · base main 4f3093d (= merge base; PR 176 merged) · OPEN, MERGEABLE, not draft
- **Files:** 10 (+533 −11 = 544 lines), one commit e61a0b9.
- **Governing:** slice spec v2.5 (bb262ec4) Decisions 30, 33, §7 "Agency B reads or writes agency A's change events", §9 row 1c with its named split; main spec v1.24; TEN-02..08.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep; tenancy/RLS) · **Switch model next step?** No

### [P2] Reverse of 0022 deletes change-kind evidence rows
- Evidence: 0022 first op `RunSQL(noop, reverse="DELETE FROM security_event WHERE kind IN (…ten kinds…)")`; DECISIONS choice 2 "Revisit before M4r-1g". The builder asks for a judgement.
- Judgement: acceptable now, not later. Today no change row can exist outside tests, and the TEN-08 harness case commits `role.created` rows under agencies A and B in the test database, so a refusing reverse would break any migrate-down run on a test database. Once M4r-1e (audit triggers) and M4r-1g (write grants) land, these rows are the append-only record of role changes (TEN-03) and a migrate-down must not silently delete them.
- Required: in M4r-1g (or the first PR that lets a real change row be written), make the reverse of 0022 raise while any change-kind row exists, with a live test (plant one row, reverse → refused, row still there). Test-database rows can be cleared by the test, not by the migration.
- Disposition: deferred to M4r-1g (tracked here and in DECISIONS choice 2). Status: open.

### [P3] "The owner chose split" — please confirm
- Evidence: DECISIONS "Decision (owner): … The owner chose "split" on 2026-11-23 when asked"; "Decided by: owner (split …)". The reviewer saw the owner ask which to pick and recommended "split"; the owner's answer to the builder is not visible here.
- The split is the one the spec names, so it needs no owner authority. If the owner did not say "split", the entry should read "builder, the split the spec names". Owner to confirm.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Column, FK | `agency_id uuid NULL`, FK → `agency(id)` (0024) | matches Decision 33 |
| CHECKs | change kind ⇔ agency_id NOT NULL; change kinds have both HMACs NULL; ten kinds = Decision 30 list | matches; frozen copies pinned by `makemigrations --check` and the deparsed text in `check.py` |
| RLS / policies | ENABLE + FORCE; RESTRICTIVE `security_event_tenant` FOR ALL USING P WITH CHECK P; PERMISSIVE `_sel` SELECT, `_ins` INSERT; all TO skiw_app; no UPDATE/DELETE policy; grants unchanged | exactly Decision 33 |
| Existing writers | `record_event` in A, B and autocommit (all KINDS) writes NULL-agency rows; both `guard.auth_lookup_*` definers in three contexts; owner helpers moved to NO FORCE in a transaction (FORCE asserted on first) | matches "each existing path keeps working" |
| §7 three-context tests | A/B/none see pre-tenant + own change rows only; cross-agency and no-token change inserts 42501; UPDATE/DELETE/TRUNCATE 42501 in all contexts; CHECK refusals 23514 with constraint names; FORCE binds the owner | matches; probe-trigger planting moves to 1c-ii (choice 7, consistent with the split) |
| Schema-check rule | RLS on + forced, column, FK, both CHECKs (validated only), exactly the three policies and no policy for another role; 12 mutants flagged incl. no IS NULL branch, extra `true` policy, UPDATE/DELETE policy | matches "Schema check" item |
| Index 0023 | not in the spec; needed by the existing RLS-index check; CONCURRENTLY, non-atomic | acceptable (recorded choice 1) |
| `test_queue_grants` | listed globals with `agency_id` stay global (as `check.py`) | consistent; the list is closed |
| Login path | skiw_app with no token inserts NULL-agency rows (P's IS NULL branch) | unbroken, tested |
| Prompt injection, secrets, PII | none | ok |
| `git diff --check` | clean | — |
| CI on e61a0b9 | checks, security, image, host: success; publish, deploy-staging skipped | — |
| Size | 544, under 600, after the spec-named split | acceptable |

Not run by the reviewer: local suites (CI green on the head).

### Residual risks and test gaps
- Until M4r-1c-ii merges, `skiw_app` can insert a well-formed change-kind row for its own agency directly (the test `test_a_change_row_for_the_own_agency_passes_the_policies` shows it). No real data and nothing writes these rows yet; 1c-ii should follow straight after and before 1d/1e.
- 1c-ii must switch the TEN-08 harness case `_change_event` to the probe trigger, or the depth rule will refuse it.

### Required before merge
- none

### Deferred conditions
- P2: reverse of 0022 refuses while change rows exist, with a live test — in M4r-1g.

### Optional improvements
- P3 wording of the DECISIONS "Decided by" line.

