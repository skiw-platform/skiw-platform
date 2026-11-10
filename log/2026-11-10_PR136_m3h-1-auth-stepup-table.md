# PR 136 — feat(accounts): M3h-1 auth_stepup table (append-only, factor FK NO ACTION)

- **Merged:** 2026-11-10 (13:04:16 UTC) · **Merge commit:** 3f72512368d11c18976d6731526eace8af38b5cd · **Branch:** feat/m3h-1-stepup-table (final head ca253e4eda1a2e7a7ca496464da36b3e3e7cba38)
- **Gate breaches:** none. The final round's head SHA equals the PR's final head; the receipt (`reviews/PR-136.receipt`, 2026-11-10T13:01:52Z, review-file hash dea065bb, review commit 2175e23) precedes the merge by about 2 minutes 20 seconds.
- **Approval receipt:** `reviews/PR-136.receipt` on agent-logs (written by `approved 136` after the whole review file, both rounds, was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 136` state MERGED, mergedAt 2026-11-10T13:04:16Z, merged by charliekhc, merge commit 3f72512; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** Sonnet 5.5 builder on an Opus 5.5 deep-tier design (reviewed by Claude Opus 5.5) · **Final verdict:** Approved (Round 2; Round 1 was Revision required)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3h-1 (first of six M3h PRs)

## What changed
Adds the `auth_stepup` table (spec §4.1) and nothing that uses it: model `AuthStepup`, migrations `accounts.0011` (table) and `0012` (RLS through `tenant_table()`, SELECT and INSERT only for `skiw_app`, plus the composite FK `(agency_id, factor_id)` to `user_factor` with NO ACTION), a TEN-08 isolation case, an existence assertion in the TEN-03 grant audit, and 31 live tests. CHECKs: `session_key_hash` is 64 lower-case hex, `purpose` has a shape only, `evidence_mac` is exactly 36 bytes (4-byte `tenant_source_key` version + HMAC-SHA-256). Docs: DECISIONS "M3h split into six PRs" and "M3h-1", plan amendment, runbook (key rotation, M3g wording). +431/−5 over 10 files. No route, no setting, no dependency.

## Why
Spec §4.1 `auth_stepup` and the M3h plan: factor changes, and later approvals (M9) and Drive operations (M16), need server-side evidence that the session's user re-verified a factor within the last few minutes. The owner approved the six-PR split on 2026-11-10.

## Review rounds
- R1: [P2] `ON DELETE SET NULL (factor_id)` voids genuine step-up evidence that the M9 executor and the M16 `drive_writer` verify later → factor FK is NO ACTION, model `PROTECT`; DECISIONS rationale withdrawn and corrected; retire-not-delete plan recorded for M3h-6 and M3g (new live tests: delete refused as `skiw_app`, catalog pin with no ON DELETE action, ORM `ProtectedError`).
- R1: [P3 #1] runbook key-rotation paragraph overstated "voids at most 5 minutes" → scoped to "until M9 and M16 store step-up ids".
- R1: [P3 #2] DECISIONS claimed a by-hand lost-authenticator step that does not exist → says there is no reset before M4-rest; the reset is a must-have M4-rest item before real data.
- R2: Approved on ca253e4e. All R1 findings resolved. Two new P3s deferred to M3h-2.

## Deferred conditions
- **P3 #1 (optional) → M3h-2:** only a TOTP (later a passkey) may be named by a step-up; recovery rows are deleted by raw SQL, and a named one would now break sign-in by recovery code and regenerating codes. `record()` must refuse a recovery factor, with a test.
- **P3 #2 (optional) → M3h-2:** `auth_stepup.factor_id` has no remaining reason to be nullable. Make it NOT NULL (a cheap migration while the table is empty) or have `record()` require a factor.
- Standing from earlier: M3h-6 states and tests that removing a user's last TOTP is refused (PR 135 P3 #2); PR 134 R1 P3 wording ("the pending login is as it was") at the next touch of DECISIONS "M3f-3c-2" or the `login_second_factor` docstring; spec D20 P3 and the M3 row "AUTH-01..09" at the next spec touch; owner Q4 (a) alert path before M17.

## Decisions worth keeping
- A factor a step-up names is never deleted (FK NO ACTION, model `PROTECT`). Factors are retired, not deleted: M3h-6 adds the retired marker to `user_factor` (clears `secret_ct`; every lookup refuses a retired row; the last-TOTP refusal stays), and M3g retires passkeys the same way. In DECISIONS "2026-11-10 — M3h-1" and plan §3 M3h.
- `evidence_mac` layout is fixed (built in M3h-2): 4-byte big-endian key version, then HMAC-SHA-256 over `skiw-stepup-v1` ‖ field(id) ‖ field(agency) ‖ field(user) ‖ field(factor or "") ‖ field(purpose) ‖ field(verified_at UTC µs) ‖ field(session_key_hash). The version is a prefix, not a column [A], as for recovery codes.
- The purpose CHECK is a shape; the closed list is in Python (M3h-2). `verified_at` has no database default: the app signs the value it sets.
- Runbook: until M9 and M16 store step-up ids, removing a `tenant_source_key` version voids at most 5 minutes of step-ups; from then, only after no pending approval or Drive operation references a step-up under it.
- There is no lost-authenticator reset before M4-rest; Ying decides case by case. It is a must-have M4-rest item before real data (the M7 import or cutover). Owner answers of 2026-11-10: six PRs yes; reset later in M4-rest.
- Migrations 0011 and 0012 were edited in place during R1 (unmerged, nothing deployed).

## Follow-ups
- Next: M3h-2 (`app/accounts/auth/stepup.py`: `evidence`, `record`, `recent`, `StepUp`, `PURPOSES`; Semgrep rule `auth-stepup-insert-stepup-only`), deep tier, taking the two deferred P3s above. Then M3h-3 … M3h-6, M3i, M3g.
- Add the lost-authenticator reset to the M4-rest plan when it is written.
- Progress page: M3h-1 done; republish.

## Appendix — final review round

## Round 2 — 2026-11-10 · scope: re-review of the R1 fix
- **Code review:** base (merge base) ae469ff1140721b112889db685fc7fbe844d85ee (still `origin/main`) · head ca253e4eda1a2e7a7ca496464da36b3e3e7cba38 · R1 head db64cd5d · head re-checked at end: yes (host head unchanged, PR open, CI finished; detached checkout `git status --untracked-files=no` clean)
- **Spec:** v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38, unchanged.
- **Fix commit:** ca253e4e "Review R1 fix: factor FK NO ACTION, retire factors instead of deleting them". It changes 7 files, +67 / −70.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. M3h-2 (the evidence MAC, `record`, `recent`) is auth work and stays deep.

### R1 findings (re-inspected at ca253e4e)
- **P2 #1 (`SET NULL (factor_id)` voids genuine evidence): resolved, with option 1.**
  - 0012 adds the composite FK with no referential action (NO ACTION). The model says `PROTECT`, and 0011 matches, so `makemigrations --check` finds no changes.
  - `test_a_factor_a_step_up_names_cannot_be_deleted`, as `skiw_app`: deleting a named factor raises `IntegrityError` on `auth_stepup_factor_id_fk`, and nothing moves. A factor no step-up names is still deleted. The other factor's rows are untouched.
  - `test_the_factor_key_has_no_referential_action` pins the catalog definition exactly, so putting `SET NULL` or `CASCADE` back fails it.
  - `test_deleting_a_named_factor_through_the_orm_is_refused_before_the_database`: `ProtectedError`, and `factor_id` is unchanged. Changing `PROTECT` back to `DO_NOTHING` fails this test.
  - DECISIONS withdraws the "harmless" rationale, and names the consumers that verify later: approval and the executor (§4.3, T10) and `drive_writer` (D25).
  - The retire-not-delete plan is recorded for M3h-6 and M3g: a retired marker, `secret_ct` cleared, every lookup refusing a retired row, and the last-TOTP refusal kept. It is in both DECISIONS and plan §3 M3h. Stated as inside spec §4.1, with no owner decision needed: agreed.
- **P3 #1 (runbook, key rotation): resolved.** The paragraph is now scoped "until M9 and M16 store step-up ids". It then says a version is removed only after no pending approval or Drive operation references a step-up under it, and that until the report exists, no version is removed while any does.
- **P3 #2 (the lost-authenticator record): resolved.** DECISIONS now says there is no reset before M4-rest, gives the runbook's facts, and says Ying decides if a real person needs one earlier. It makes the reset a must-have M4-rest item before real data. The plan's amendment note says the same.

### Findings

### [P3] Two follow-ups for M3h-2, now that a named factor can never be deleted
1. **Only a TOTP (later a passkey) may be named.** `recovery.py` deletes recovery rows with raw `DELETE … WHERE kind = 'recovery'` (one code at sign-in, all of them on regenerate). If a step-up ever named a recovery row, the NO ACTION FK would make that delete fail, and sign-in by recovery code or regenerating codes would break for that user. Recovery codes are excluded from step-up by design [A], so `record()` in M3h-2 should refuse any factor that isn't TOTP (or a passkey from M3g), with a test.
2. **`factor_id` is nullable with no remaining use.** Its only null case was the old `SET NULL`. A step-up is by definition the re-verification of a factor, and the new test docstring ("a step-up that no factor proved is still evidence") describes a case nothing should produce. Either make the column NOT NULL (a cheap migration while the table is empty, in M3h-2) or have `record()` require a factor and say why the column stays nullable.
- Owner: builder · Disposition: deferred to M3h-2 · Status: open

No prompt-injection text found in the fix commit or the changed text.

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-136-ca253e4e` at ca253e4e | created, reviewed, ignored output cleaned, disposable DB removed (`down -v`), worktree removed without `--force` |
| `git diff db64cd5d ca253e4e` | only the R1 fix sites (FK clause, model, tests, DECISIONS, plan, runbook) |
| `git diff --check ae469ff...ca253e4` | clean |
| `make install lint typecheck test test-live` (Compose DB on port 5436) | pass; Semgrep 0 / 20 rules, rule tests 20/20; test 1702 + web 4; test-live 755 |
| `pytest -m live` on the step-up, grant, tenancy and `accounts` test files, 3 runs | 674/674 passed each run |
| `migrate accounts 0010`, then `migrate`; `check_tenancy_schema`; `makemigrations --check` | down and up OK; schema check ok; no changes |
| `git grep` at ca253e4e for deletes of `user_factor` outside tests | only `recovery.py` (kind `recovery`), the basis for P3 #1 |
| CI on head ca253e4e | checks, security, image, host: pass; publish/deploy-staging skipped |
| Host head SHA at end | ca253e4eda1a2e7a7ca496464da36b3e3e7cba38, unchanged |
| Not run | builder's mutants (the two FK mutants are killed by the catalog and ORM tests, checked by reading); `host-test`, `secrets-test`, `e2e` (CI covers the first two; no UI) |

### Residual risks and test gaps
- Until M3h-6 adds the retired marker, nothing can remove a TOTP an active user has stepped up with. Nothing tries to: removal is M3h-6, and enrolment restarts only touch `invited` users, who have no step-ups.
- The MAC itself is built and tested in M3h-2. This PR pins only its length.

### Required before merge
- None.

### Deferred conditions
- P3 #1 and #2: deferred to M3h-2 (optional, but cheap there).

### Optional improvements
- None.
