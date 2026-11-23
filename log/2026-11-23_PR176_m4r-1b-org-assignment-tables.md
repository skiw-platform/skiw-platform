# PR 176 — feat(accounts): M4r-1b org_unit and user_role tables

- **Merged:** 2026-11-23 (12:56:04 UTC) · **Merge commit:** 4f3093d7d94f078139aad0ee4bf967d355eace97 · **Branch:** feat/m4r-1b-org-assignment-tables
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-176.receipt, created 2026-11-23 12:55:32 UTC, before the merge; names head 2c3642bdb31a85c3a2fa1bd78fa1eb43001c6506 and review hash d0414c09…
- **Merge evidence:** `gh pr view 176` state MERGED, merge commit above, mergedAt 12:56:04Z; reachable from the fetched origin/main. Final head 2c3642bdb31a85c3a2fa1bd78fa1eb43001c6506 equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1b

## What changed
Tenant tables `org_unit` (one root per agency, kinds agency/unit/team, self-referencing composite FK, name rules) and `user_role` (user, role, unit, line; composite FKs with ON DELETE RESTRICT; unique assignment) with RLS and SELECT-only grants for `skiw_app`; models and migrations 0020 and 0021; isolation harness supports a self-referencing FK; DECISIONS entry with five implementation choices. Nothing reads the tables at run time yet. 586 lines (about 306 code, 260 tests, 12 docs).

## Why
Second step of the roles track (slice spec §9 row M4r-1b; needs M4r-1a, PR 175).

## Review rounds
- R1: Approved, no findings.

## Deferred conditions
- None.
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule before any M20 PR; DECISIONS Source-line P3 (PR 172 entry); Q47 sample from the owner; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s and the slice-spec "replaces the existing global role" correction at the next spec touch.

## Decisions worth keeping
- DECISIONS 2026-11-23 "M4r-1b": unit names reuse the role-name rules; hand-written RESTRICT FKs; harness self-referencing FK support; no extra indexes; generated migration 0020 kept as generated.

## Follow-ups
- Next: M4r-1c (audit triggers on the role tables and `security_event` RLS), the largest piece of the roles track.
- Local note: the old local database still needs `POSTGRES_USER=postgres` in `.env` for six live tests (see the PR 175 log).

## Appendix — final review (PR 176 Round 1)
## Round 1 — 2026-11-23 · head 2c3642bdb31a85c3a2fa1bd78fa1eb43001c6506
- **PR:** #176 "feat(accounts): M4r-1b org_unit and user_role tables" · author charliekhc · base main 9c83969 (= merge base; PR 175 merged) · OPEN, MERGEABLE, not draft
- **Files:** 9 (+578 −8 = 586 lines), one commit 2c3642b.
- **Governing:** main spec v1.24 (e47de4ed); slice spec v2.5 (bb262ec4): §4 rows `org_unit`, `user_role`; §9 row 1b; Decisions 2, 3, 23; PROJECT §4 size rule, §9 tenancy rules.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep; tenancy) · **Switch model next step?** No

### Findings
No blocking findings.

### [P3] No index for lookups of `user_role` by role or by unit
- Evidence: recorded choice 4 in the DECISIONS entry. The composite FKs (agency_id, role_id) and (agency_id, org_unit_id) have no supporting index; the unique key leads with (agency_id, user_id). RESTRICT checks on deleting a role or unit, and the Decision 28 `user_role_owner_remains` check ("an assignment to that role exists"), will scan `user_role`.
- Impact: none at one agency of ~5 users. Worth one line in M4r-1d/1e when the deferred check lands, if the plan expects growth. Optional.

### Carried from PR 175 (optional)
- The `role` name boundary test still uses 63 characters, not 64 (PR 175 P3). This PR's `org_unit` test gets it right (`"Ünit " + "é" * 59` = 64).

No prompt-injection text found.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| `org_unit` vs §4 / Decision 2 | idx(agency_id, parent_id); uq(agency_id) WHERE parent_id IS NULL; CHECK kind='agency' ⇔ parent_id IS NULL; CHECK parent_id <> id; kind IN (agency, unit, team); composite self-FK ON DELETE RESTRICT (root's NULL skips it, MATCH SIMPLE) | matches; no kind-order rule added (spec gives none) |
| `org_unit` name rule | 1–64 chars, no Cc; spec silent, choice recorded (DECISIONS item 1) | acceptable |
| `user_role` vs §4 | composite FKs to `app_user`, `role`, `org_unit`, all ON DELETE RESTRICT (test reads `confdeltype = 'r'` for all four); uq(agency_id, user_id, role_id, org_unit_id); line NOT NULL, no default, CHECK in three values (null and omitted both refused) | matches |
| RLS / grants (TEN-02, 05–07; Decision 3) | `tenant_table(..., {"SELECT"})`; grant audit extended to both tables, SELECT only, no other grantee | matches; no write before the audit triggers |
| TEN-08 | harness cases for both; self-FK parent = agency root (got-or-created), cross-FK case for `parent_id` inserts A's unit under B's unit and expects 23503; user/role/unit cross-agency FK tests | sound; recursion ends at the root |
| Live fixture | owner, NO FORCE on four tables, own agencies X, Y, all rolled back | no residue except the harness roots under A and B (recorded) |
| Migrations (UNI-15) | new tables only | additive |
| Size | 586, under 600; reason given (tables with their tests) | acceptable |
| Secrets / PII | none; names kept out of `__str__` | ok |
| `git diff --check` | clean | — |
| CI on 2c3642b | checks, security, image, host: success; publish, deploy-staging skipped | — |

Not run by the reviewer: local suites (CI green on the head; builder states live suites run by a sub-agent only).

### Residual risks and test gaps
- As M4r-1a: isolation against `skiw_app` writes rests on "no grant" until M4r-1g; the no-cycle tree guard (Decision 27) is M4r-1d, so until then a cycle is possible only for the table owner.

### Required before merge
- none

### Deferred conditions
- none

### Optional improvements
- The P3 index note; the carried PR 175 boundary fix.

