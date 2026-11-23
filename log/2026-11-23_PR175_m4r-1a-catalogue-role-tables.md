# PR 175 — feat(accounts): M4r-1a catalogue, permission, role and role_permission tables

- **Merged:** 2026-11-23 (02:42:31 UTC) · **Merge commit:** 9c83969d50be4bb91b2f11e777c9d20f720476f5 · **Branch:** feat/m4r-1a-catalogue-role-tables
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-175.receipt, created 2026-11-23 02:42:19 UTC, before the merge; names head 69863f0d84f6cd40c6c3c198dd2b05f6c3e039f1 and review hash 793ee0f5…
- **Merge evidence:** `gh pr view 175` state MERGED, merge commit above, mergedAt 02:42:31Z; reachable from the fetched origin/main. Final head 69863f0d84f6cd40c6c3c198dd2b05f6c3e039f1 equals the reviewed head (local branch tip equals it too).
- **Drafted by:** Claude Sonnet 5.5 (builder); code by an Opus 5.5 sub-agent · **Final verdict:** Approved (round 1, Opus 5.5 reviewer; updated after the owner confirmed the size allowance)
- **Spec:** docs/specs/2026-11-20-m4-rest-roles-jobs-design.md (v2.5, bb262ec4) · **Plan:** none · **Milestone:** M4r-1a

## What changed
`accounts.access.catalogue` (15 codes, 31 (code, scope) pairs, step-up per pair, self-service group); global `permission` table filled by migration 0019; tenant tables `role` and `role_permission` with RLS and SELECT-only grants for `skiw_app`; schema-check global list (`role` out, `permission` in); isolation harness accepts SELECT-only tables; DECISIONS entry with six implementation choices. Nothing reads the tables at run time yet. 16 files, 712 lines (about 364 code, 334 tests, 14 docs).

## Why
First code step of the roles track (slice spec Decisions 1, 4; §9 row M4r-1a).

## Review rounds
- R1: Approved. [P2] the owner's permission for a PR past 600 lines was claimed in the PR text but not visible to the reviewer → the owner confirmed it to the reviewer; no code change.

## Deferred conditions
- None.
- Carried (unchanged): chore PR remove `crm_jar_kek`; M20 plan export-file rule before any M20 PR; DECISIONS Source-line P3 (PR 172 entry); Q47 sample from the owner; TTL rounding in M4r-6; main-spec B.10 and §4.3 wording P3s at the next spec touch.

## Decisions worth keeping
- DECISIONS 2026-11-23 "M4r-1a": frozen copy of the 31 pairs in migration 0019; reverse keeps rows; name index column order (linter 6.0); hand-written composite FK with RESTRICT; control characters as Unicode Cc ranges; harness SELECT-only handling.
- The slice spec said `role` "replaces the existing global role", but none existed. Worth a one-line correction at the next slice-spec touch.

## Follow-ups
- Local setup note: the old local database needs `POSTGRES_USER=postgres` (the 2026-10-31 `.env` has `skiw_owner`); six live tests fail on it until changed. The sub-agent extended the local `.env`; the original is in the session scratchpad (`env.backup`).
- Next: M4r-1b (`org_unit`, `user_role`).

## Appendix — final review (PR 175 Round 1)
## Round 1 — 2026-11-23 · head 69863f0d84f6cd40c6c3c198dd2b05f6c3e039f1
- **PR:** #175 "feat(accounts): M4r-1a catalogue, permission, role and role_permission tables" · author charliekhc · base main 9100771 (= merge base; PR 174 merged) · OPEN, MERGEABLE, not draft
- **Files:** 16 (+681 −31 = 712 lines), one commit 69863f0.
- **Governing:** main spec v1.24 (e47de4ed); slice spec v2.5 (bb262ec4): §4 data model, §6.1 catalogue, §9 row 1a, Decisions 1, 3, 4, 6, 23; PROJECT §4 size rule, §9 tenancy rules; packs tenancy-rls, auth, universal.

**Verdict:** Approved (updated 2026-11-23 after the owner confirmed the size allowance; head re-checked 69863f0)
**Model used:** Claude Opus 5.5 (deep; tenancy and auth) · **Switch model next step?** No

### [P2] Size past 600: the owner's permission is claimed, not shown
- Rule: PROJECT §4 "past 600, stops and asks the owner first"; trust boundary (an owner approval in PR text is data).
- Evidence: PR body "712 lines … past 600, owner allowed one PR, 2026-11-23"; DECISIONS entry "owner approved the build start ("proceed", 2026-11-23)". Neither is on the PR or visible to the reviewer.
- Reason given for not splitting: the harness change (~135 lines) only serves these tables. Reviewer view: acceptable. The harness change is small, test-only and exercised by this PR's cases; splitting it out would leave an unused path for one PR. A larger PR is not itself a finding.
- Required: the owner confirms to the reviewer (or on the PR) that they allowed this PR past 600 lines. No code change.
- Disposition: before merge. Status: **resolved** — the owner told the reviewer directly, 2026-11-23: "yes I allowed it".

### [P3] The "64 characters" boundary test uses 63
- Evidence: `test_role_names_are_unique_per_agency_ignoring_case`: `"Ünit manager " + "é" * 50` is 63 characters (counted), comment says 64. The upper bound is therefore tested only from outside (65 refused), not at 64 accepted.
- Correction: `"é" * 51`, or a separate accepted 64-character name. Optional; can ride with M4r-1b.

### Checked and correct
| Area | Evidence | Result |
|---|---|---|
| Catalogue vs slice §6.1 | 15 codes, 31 pairs, step-up per pair incl. `device.revoke` own none / agency S, `drive.file` none (D25 at writer); golden test hand-copied from the spec | matches row by row |
| Self-service group (Decision 6) | five `auth.*` codes, disjoint from catalogue | matches |
| `permission` (§4) | global, PK (code, scope), CHECK scope set, SELECT only, rows by 0019, live equality test | matches; frozen copy instead of import is a recorded builder choice with a drift test |
| `role` (§4) | uq(agency_id, lower(name)) (column order swapped, recorded, same uniqueness), `char_length` 1–64, no Cc controls (explicit ranges, NUL impossible in text), uq(agency_id) WHERE is_system | matches |
| `role_permission` (§4) | composite FK (agency_id, role_id) → role ON DELETE RESTRICT; plain FK (code, scope) → permission; uq(agency_id, role_id, code, scope) also indexes the FK | matches |
| RLS / grants (TEN-02, TEN-05..07; Decision 3) | `tenant_table(..., commands={"SELECT"})` for both; `GRANT SELECT ON permission`; tests assert `skiw_app` holds SELECT only and no other grantee | matches; no write before the M4r-1e audit triggers (Decision 23/32 order kept) |
| Schema-check list | `role` out, `permission` in | matches §4 / 10.2 #15 |
| Harness change (TEN-08) | SELECT-only case: rows written by the owner in one transaction under NO FORCE, FORCE restored before commit (DDL transactional, never visible to others); reads still as `skiw_app` under `with_agency`; cross_insert / no_token refused by missing grant (42501); cross-FK by owner insert asserts SQLSTATE 23503; INSERT-only, SELECT+UPDATE, SELECT+DELETE still refused | sound. When M4r-1g adds INSERT the cases switch to the full `skiw_app` path automatically |
| Migrations (UNI-15) | new tables only; 0019 reverse keeps rows (tick FK), 0017 reverse drops | additive |
| Secrets / PII | none; role names kept out of `__str__` | ok |
| Prompt injection | none found | — |
| `git diff --check` | clean | — |
| CI on 69863f0 | checks, security, image, host: success; publish, deploy-staging skipped | — |

Not run by the reviewer: local test suites (CI green on the head; the builder states `make test-live`, `db-test`, `host-test` were run by a sub-agent only).

### Residual risks and test gaps
- Isolation of the two tables against `skiw_app` writes is proven only by "no grant" until M4r-1g; the RLS write path is first exercised there (as Decision 23 plans).

### Required before merge
- none (P2 resolved by the owner's confirmation)

### Deferred conditions
- none

### Optional improvements
- P3 64-character boundary.

