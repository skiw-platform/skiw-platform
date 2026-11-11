# PR 143 — feat(accounts): M3h-6 retire a TOTP, regenerate recovery codes (migration 0014)

- **Merged:** 2026-11-11 (16:20:22 UTC) · **Merge commit:** cecddf3728c7a4b36ce5c932b3e017a672d66098 · **Branch:** feat/m3h-6-remove-regenerate (final head 022b056c1c80acb7bb073edef507048eb7090fdc)
- **Gate breaches:** none. The review's final round (R2, CI addendum) head SHA equals the PR's final head and Round 1's; the receipt (`reviews/PR-143.receipt`, 2026-11-11T16:19:59Z, review-file hash 84bc8253, review commit 8530bdc) precedes the merge by 23 seconds.
- **Approval receipt:** `reviews/PR-143.receipt` on agent-logs (written by `approved 143` after the whole review file was archived and its hash confirmed equal to the local copy).
- **Merge evidence:** `gh pr view 143` (repo now skiw-dev1/skiw-platform, see Decisions) state MERGED, mergedAt 2026-11-11T16:20:22Z, merge commit cecddf3; `git merge-base --is-ancestor` against fetched origin/main: reachable.
- **Built by:** an Opus 5.5 deep-tier sub-agent wrote the code on the Opus M3h design; the Sonnet 5.5 builder re-ran lint, typecheck, test, test-live and build (not the mutants) and wrote the PR · **Reviewed by:** R1 Claude Opus 5.5 deep tier (code), R2 Claude Opus 5.5 (CI addendum, no code change) · **Final verdict:** Approved (round 2)
- **Spec:** v1.22 (hash 79a9a40e, unchanged) · **Plan:** docs/plans/2026-10-31-m3-auth.md · **Milestone:** M3h-6 (seventh and last M3h PR; M3h done)

## What changed
Migration `0014_factor_retired`: nullable `user_factor.retired_at`, the TOTP length rule exempts a retired row, new CHECK `user_factor_retired_no_secret`; the reverse keeps the column and re-adds the 0010 rule `NOT VALID`. `POST /api/auth/factors/totp/remove` (`hold`, `recent`, 404 for another user's, a recovery or a retired id, 409 `last-factor`, retire, marker, `reissue`) and `POST /api/auth/factors/recovery` (regenerate: `hold`, `recent`, new codes, marker, `reissue`). Every lookup refuses a retired factor (`match_totp` read and use-time update, `stepup.record`, the list, the last-factor count). PR 142's optional P3s (unopenable-secret test, pending-login and CSRF assertions). DECISIONS "M3h-6"; runbook rewritten. +665/-39 over 13 files, not split.

## Why
Spec D7, AUTH-07/09 and PR 136 R2 P2 / PR 135 P3 #2: a factor a step-up names is never deleted, only retired; the last authenticator cannot be removed; replacing an authenticator and regenerating recovery codes need a fresh step-up and end other sessions.

## Review rounds
- R1 (head 022b056, deep tier): Approved (code). One merge condition: CI must be green on this head (owner action; the first CI run failed on the old org's Actions billing limit, not on the code). It confirmed the migration (reverse `NOT VALID` acceptable), `remove`, `match_totp`'s use-time update, `stepup.record`, and regenerate; accepted the size.
- R2 (same head, CI addendum): Approved. CI green: run 43020292996 attempt 2, `checks`, `security`, `image`, `host` success, on the new org. UNI-07 and UNI-13 move from partial to met.

## Deferred conditions
- None. Optional P3s, open: (1) no test proves regenerate takes `hold` (mutant R9 survived): add a race test in the shape of `test_a_confirm_waiting_on_hold_sees_a_marker_committed_meanwhile_and_adds_nothing` (user lock held, regenerate waits, marker commits, expect 401 `signed-out`, old codes valid, no new codes), in the next PR that touches `factor_change` (M3g's passkey retire) or a small follow-up; (2) the comment "ids read after the lock" is not test-proven; mutant R3 is equivalent (every change writes a user-wide marker, so `hold` refuses a second change whatever it read): no action; (3) reviewer suggestion: write the size rule (about 450 split, the stop line, "or say why") into the plan or PROJECT.md so both roles cite one text.

## Decisions worth keeping
- Retire, never delete, a factor a step-up names; a retired row holds no secret by a DB rule; kind-agnostic so M3g retires passkeys the same way; a recovery row is deleted, never retired.
- Replacement flow: add the new TOTP, step up again, remove the old one; the last TOTP cannot be removed. A recovery code is never a step-up, so a user who lost the authenticator can neither add, remove nor regenerate: the owner-performed reset is a **must-have M4-rest item before real data** (tell Ying; on the gate list for the M7 import or cutover).
- Migration reverse keeps the column (`skiw_migrator` cannot repair tenant rows under FORCE RLS); deploys are forward-only (D16).
- **Repo moved (owner, 2026-11-11):** the old org hit the Actions spending limit, so the repo is now https://github.com/skiw-dev1/skiw-platform (private). `agents/PROJECT.md` §4 Remote still names the old URL: update through a reviewed PR.

## Follow-ups
- Next: M3i (sign-in and account screens; frontend, the first PR needs the owner's go-ahead), then M3g (passkeys, last); the M3 milestone gate review on the deep tier.
- A small PR: `agents/PROJECT.md` §4 remote URL, and the size rule text (above).
- PR 142's and 143's optional P3s above; PR 139 P3 (`auth.stepup`, `auth.factors`, `auth.factor-change` in the §6 matrix, M4-rest, all roles, self-service); PR 140's two optional P3s, the removal rule for the `apk add` layers, and its review tier gap (standard instead of deep; no owner reply).
- Progress page: M3h done; republished with this merge.

## Appendix — final review rounds
# Review — PR #143 (M3h-6: retire a TOTP, regenerate recovery codes, migration 0014)

<!-- Newest round at the top. Keep earlier rounds as history. Only the reviewer writes this file. -->

## Round 2 — 2026-11-11 · scope: CI addendum (same head; no code change since Round 1)
- **Code review:** base b09ea49db18d93c52eb4fbeb949c3947f3d00a3d (= `origin/main`, unchanged) · head 022b056c1c80acb7bb073edef507048eb7090fdc (= Round 1 head; PR open). No new commits, so Round 1's code review, mutants and findings stand unchanged.
- **CI: green on this head.** Run 43020292996, attempt 2 (re-run 2026-11-11 12:26 UTC, `pull_request` event): `checks` success, `security` success, `image` success, `host` success; `publish` and `deploy-staging` skipped (PR event). Main has not moved, so the re-run's merge ref is the current one.
- This closes Round 1's only merge condition and fills its CI gaps: gitleaks and trivy (`security`/`image`), the audits, registry Semgrep and `host` now ran in CI. UNI-07 and UNI-13 move from partial to met.

**Verdict:** Approved. Ready for the owner to merge.
**Open (optional, follow-up is fine):** Round 1 [P3] race test for regenerate's `hold`; write the size/stop-line rule into the plan or PROJECT.md.
**Model used:** Claude Opus 5.5 · **Switch model next step?** No review work left on this PR; the standard tier suffices for M3i building, deep tier for the M3 gate review.

## Round 1 — 2026-11-11 · scope: slice (M3h-6, last M3h PR; two signed-in routes, migration `accounts.0014`, retired-factor rule in every lookup; no setting or dependency)
- **Code review:** base (merge base) b09ea49db18d93c52eb4fbeb949c3947f3d00a3d (= `origin/main`, PR 142 merged) · head 022b056c1c80acb7bb073edef507048eb7090fdc · head re-checked at end: yes (host head unchanged, PR open; detached checkout `git status --untracked-files=no` clean)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.22, hash 79a9a40ee1a686ae1082e8d11a73b299deb66d38 (equals PROJECT.md §2): D7 (TOTP required; step-up list), AUTH-07/09, UNI-15. Plan M3 §3 M3h and its 2026-11-10 amendments (retire, not delete; lost-authenticator reset in M4-rest); DECISIONS "M3h-1", "M3h split", "M3h-6". Carry-overs: PR 142 R1 P3 #1, #2.1, #2.2.
- **CI: did not run on this head.** All four jobs in run 43020292996 ended in about 2 seconds, with no steps. The annotation reads: "The job was not started because recent account payments have failed or your spending limit needs to be increased." The red status is GitHub billing, not the code. See "Required before merge" and Verification.

**Verdict:** Approved (the code, at this head). CI must still run green on this head before merge; that is an owner action, not a builder correction.
**Model used:** Claude Opus 5.5 (deep tier, as the PR asked) · **Switch model next step?** Depends on the next plan item. M3i (TOTP and recovery screens) is frontend work, so the standard tier is fine for building it. The review of the M3 milestone gate should be deep.

### Carry-overs (re-inspected, not taken from the PR body)
- **PR 142 P3 #1 (unopenable secret): resolved.** `test_a_begun_secret_that_does_not_open_is_409_and_counts_nothing` seals for another factor id, expects 409 `no-pending`, and checks nothing is counted, added or marked. The builder reports the PR 142 M6 mutant now dies; I read the test but did not re-run that mutant.
- **PR 142 P3 #2.1 (`csrf` at confirm): resolved,** and widened: `test_each_change_rotates_the_csrf_token_and_the_old_one_is_refused` is parametrised over add, remove and regenerate through a CSRF-enforcing browser.
- **PR 142 P3 #2.2 (each change ends a pending login): resolved.** `test_each_change_ends_a_login_waiting_for_its_second_factor` covers add, remove and regenerate.

### Findings

### [P3] No test proves regenerate takes `hold` (the resurrection race)
- Category: test gap
- Rule: AUTH-07; DECISIONS M3h-4 (`hold` before every re-issue)
- Evidence: in a scratch copy I replaced `regenerate`'s `_changing` with a bare `recent` check, so there was no `hold`. **The mutant (R9) survived:** 125/125 passed across the remove, change, sign-in, step-up and recovery live files. The same mutant on remove (R2) is killed by `test_two_parallel_removes_of_the_two_totps_leave_one`. Password change, add and remove each have a race test; regenerate has none.
- Failure scenario: a later edit drops `hold` from `regenerate`. Session S is stepped up. Another session commits a credential change, and its user-wide marker revokes S. S's regenerate began before that commit, waits on `recovery.generate`'s user lock, then writes codes and `reissue`s. S comes back with a new key and an `AUTH_AT` after the marker: the revoked session survives, which is exactly what `hold` exists to stop. The code is right today; only the guard on it is missing.
- Required correction: a race test for regenerate in the same shape as `test_a_confirm_waiting_on_hold_sees_a_marker_committed_meanwhile_and_adds_nothing`. Take the user row lock in the test, start regenerate, wait for the lock waiter, commit a user-wide marker, then expect 401 `signed-out`, old codes still valid, and no new codes.
- Owner: builder · Disposition (P3): optional; next PR that touches `factor_change` (M3g's passkey retire) or a small follow-up · Status: open

### [P3] Two notes, no action required
1. **Size: +665 against the plan's ≈ 450 split rule, not split.** About 250 lines are code, 380 tests and 34 docs. Earlier PRs over the line were split (M3h-2, M3f-3c, M4c-6). The builder gives a reason and offers to split off regenerate. **Reviewer answer: no split needed.** The code part is within the rule, the migration, remove and retire rules are one safe unit, and splitting off about 90 lines of regenerate would not make this review smaller where it matters. Next time the owner may want the "≈ 450, or say why" rule written down with the stop line PR 142 cited, because it is not in PROJECT.md or the plan.
2. **The comment "ids read after the lock" holds, but no test proves it.** Mutant R3 (read `_totps` before `hold`) survived and is **equivalent**. Every change writes a user-wide marker, so `hold` refuses any second change whatever it read earlier. The parallel-remove test's docstring ("both read the factors before either retires, unless `hold` makes the second wait") is accurate about `hold`, not about the read order. Keep the order as it is, as belt and braces.
- Owner: builder · Disposition (P3): optional · Status: open

No prompt-injection text found in the PR body, commit message, code, tests, migration, docs or runbook. "Please review on the deep tier" and "say if you want regenerate split off" are requests to the owner and reviewer, not instructions to change a verdict.

### Design calls [A], reviewer answers
1. **The migration (swap in one `ALTER TABLE`, new retired rule, reverse with `NOT VALID`): confirmed.**
   - Forward is expand-only. The new nullable column is unread by the previous code. The TOTP length rule is loosened (it exempts retired rows), and `user_factor_retired_no_secret` is added and validated. Validation is not subject to RLS, and no retired row exists before this code.
   - Reverse: dropping the column would turn each retired TOTP into a secret-less row the 0010 rule can't validate, and `skiw_migrator` can't see tenant rows under FORCE RLS to repair one. Keeping the column, dropping only Django's state and restoring the 0010 rule `NOT VALID` is therefore the safe choice. New rows are still checked, and a re-apply (`ADD COLUMN IF NOT EXISTS`, then the swap) validates again.
   - **What the 0013 code does with a retired row left behind:** `match_totp` opens an empty blob and matches nothing. The old list would show the retired id, which is harmless. Deploys are forward-only (D16), so this matters only for the reversal test and local work. **`NOT VALID` on reverse: acceptable.**
   - `test_accounts_0014_reverses_and_reapplies_with_a_retired_factor_kept` passes inside `make test-live`, and `lintmigrations --warnings-as-errors` passes. The builder's four hand mutants of the migration are plausible; I did not re-run them.
2. **`remove` (`hold`, `recent`, ids, last-factor, retire, marker, `reissue`): confirmed.** Without `hold` the parallel test fails (R2 killed). Last-factor is enforced (R8, `<= 1` → `< 1`, killed). Retired rows are excluded from the id set and the list (R7 killed). 404 is the same for another user's id, a recovery row, a retired id and an unknown id, so it reveals nothing.
3. **`match_totp`'s use-time update requires `retired_at IS NULL`: confirmed** (R1 killed by `test_a_totp_retired_after_it_was_read_is_not_used`). Step-up doesn't take the user lock, so this conditional update is the one that matters. The read filter is equivalent, as the builder says: a retired row has no secret, by the DB rule.
4. **Remove's `UPDATE` filters by id only: confirmed safe.** The id was already checked against the user's own non-retired TOTPs in the same transaction, under the user lock and RLS.
5. **`stepup.record` refuses a retired factor** (R4 killed). Evidence rows naming a retired factor stay and verify, but `recent` cannot return them: the remove re-issues this key, and the marker ends every other session. Confirmed.
6. **Regenerate: confirmed.** `recovery.generate` locks the user row again (harmless in the same transaction) and deletes every old code before the bulk insert. Step-up is required (R6 killed); the marker and `reissue` are present (R5 killed). See P3 #1 for `hold`.

### Code read (beyond the self-check)
- **Every `UserFactor` lookup in `app/`, outside tests and migrations, was checked for the retired rule:** `second_factor.match_totp` (read and update), `stepup.record`, `factor_change._totps` (list, remove set, last-factor count), and `recovery` (recovery rows only, never retired). Enrolment's `factors.py:198` only creates. No other module reads `user_factor`.
- **Both routes run in the wrapper's transaction** (not `own_transaction`): nothing slow runs inside it (HMAC only, no Argon2). The wrapper's own revocation check runs earlier in that transaction, and `hold` re-checks after the lock with a fresh READ COMMITTED statement.
- **Lost authenticator:** a recovery code is never a step-up, so a user without the authenticator can neither add, remove nor regenerate. This is recorded as a **must-have M4-rest item before real data** (DECISIONS M3h split, M3h-6; runbook: "tell Ying"). It is correct as an owner decision and stays on the gate list for the M7 import or cutover.
- **Runbook:** "Recovery codes are shown once" now gives the regenerate path, "Replace or remove an authenticator" is new, and the emergency `tenant_source_key` rotation step now says how users make new codes. The routes, answers and `last-factor` match the code.
- **The response body of regenerate** carries the codes once, with no-store (the shared `_answer`), and nothing is logged.

### Self-check audit
My applicability list was built from the ticked packs and PROJECT.md §9 against the diff before I read the table.

| Rule | Applies? (why / n-a reason) | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|---|
| UNI-01 | yes | pass | pass | mypy strict, 241 files | — |
| UNI-02/06/08/10/11/12/14 | n/a, no value, dependency, secret source, audit row, external service | n/a | n/a accepted | diff is `app/` and `docs/` only | — |
| UNI-03 | yes | pass | pass | remove `{"id": uuid text}` only (five bad bodies 400); regenerate `{}` | — |
| UNI-04 | yes | pass | pass | contracts 10 kept; Semgrep 21 / 0 findings; rule tests 21/21 | — |
| UNI-05 | yes | pass | pass | `_totps`, `_changing`, `_changed` shared; add-confirm uses them | — |
| UNI-07 (hard) | yes | pass | **pass, not re-verified by CI** | builder: gitleaks v8.30.1 full clone, no leaks. Not run by me (gitleaks not installed); CI `security` did not start (billing). The diff adds no key-shaped literal (test bytes are `b"\0" * n`) | — (owner: CI before merge) |
| UNI-09 | yes | pass | pass | codes only in the response body; nothing logged | — |
| UNI-13 | yes | pass | **partial** | local: lint, typecheck, test 1791, test-live 905, host-test 854 all pass. CI: not started (billing) | — (owner: CI before merge) |
| UNI-15 | yes | pass | pass | expand-only forward; reverse reasoned and tested; `lintmigrations --warnings-as-errors` pass in `test-live` | — |
| UNI-16 | yes | pass | pass | runbook bullets above | — |
| UNI-17 | yes | pass | pass | both POST only; CSRF fixture entries; rotation test per change | — |
| UNI-18/19 | n/a, no header or form | n/a | n/a accepted | — | — |
| AUTH-01 (hard) | yes | pass | pass | wrapper steps 1–4 unchanged | — |
| AUTH-06 | yes | pass | pass | step-up for each change uses the one budget; remove and regenerate check no code themselves | — |
| AUTH-07 | yes | pass | pass, with P3 #1 | other sessions 401 and this one re-issued for both routes (R5 killed); pending logins ended; regenerate's `hold` untested | P3 #1 |
| AUTH-09 | yes | pass | pass | 403 without step-up for both (R6 killed); retired factor cannot step up (R4 killed) | — |
| AUTH-13 (server half) | yes | (in AUTH-07 row) | pass | rotation test over add, remove, regenerate | — |
| TEN-02..08 | yes | pass | pass | live suite as `skiw_app`; table tests for the new rule; no grant change (table-level UPDATE covers the column) | — |
| TEN-09/11 | yes | pass | pass | `with_agency(signed.agency_id)`; identity only from the session; neighbour's id 404 | — |
| TEN-10/12 | yes | pass | pass | both routes in the registry; `auth.factor-change` | — |
| FE-*, MON-*, REC-*, FILE-*, EVT-* | n/a | n/a | n/a accepted | no UI, money, record, file or job | — |

### Verification performed
| Command / check | Result |
|---|---|
| Detached checkout `.agent/worktrees/review-143-022b056c` at 022b056c | created, reviewed, my ignored output cleaned, removed without `--force` |
| `git diff --check b09ea49...022b056` | clean |
| Files outside `app/` and `docs/` in the diff | none (no infra, image, dependency or workflow change) |
| `make install lint typecheck test` | pass: contracts 10 kept, Semgrep 21 / 0 findings, rule tests 21/21, mypy 241 files, pytest 1791, vitest 4 (equals the PR) |
| `make test-live` (own disposable DB, port 5439, project `review-143`; includes migrate, `lintmigrations --warnings-as-errors`) | 905 passed (equals the PR) |
| `make host-test` | 854 passed |
| Targeted baseline in a scratch copy (6 live files) | 125 passed |
| R1 `match_totp` use-time update ignores retired | killed |
| R2 remove without `hold` | killed (parallel test) |
| R3 remove reads ids before `hold` | survived; **equivalent** (P3 #2.2) |
| R4 `stepup.record` accepts retired | killed |
| R5 regenerate without marker and `reissue` | killed |
| R6 regenerate without step-up | killed |
| R7 `_totps` keeps retired | killed |
| R8 last-factor `<= 1` → `< 1` | killed |
| R9 regenerate without `hold` | **survived** (P3 #1) |
| R10 `match_totp` read keeps retired | not applied (pattern differs); builder reports it equivalent, which I accept by the DB rule |
| Mutant hygiene | `PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared before each, scratch copy only, deleted after |
| CI on 022b056c | **not run:** all jobs refused to start (GitHub billing / spending limit); `publish`, `deploy-staging` skipped |
| Not run by me | `secrets` / `secrets-test` (gitleaks not installed), `image-scan` (trivy not installed), `audit-python`, `audit-web`, Semgrep registry rulesets, `host-test-live`, `e2e`. No input to these changed except the source itself (gitleaks scans it) |
| Cleanup | disposable DB `down -v`; scratch copy and `.env` deleted; worktree removed |

### Residual risks and test gaps
- **CI did not run.** The secret scan, dependency audits, registry Semgrep and the image scan are unverified on this head. Lint, typecheck, unit, live and host tests were verified locally. `main` has not moved since b09ea49, so a re-run of this PR's CI after billing is fixed will test the right merge ref (re-running keeps the old merge ref, which is current here).
- **Lost authenticator:** no self-service path, and the owner reset is not built. It is a must-have M4-rest item before real data, and it stays a gate item.
- **The marker window (M3d)** applies to these changes as to the others; it is unchanged.
- **The builder's 14 code mutants and 4 migration mutants** were not re-run as such. My 10 overlap on `hold`, step-up, last-factor, the retired filters, the marker and `reissue`.

### Required before merge
- None from the code.
- **Owner (not a builder correction):** fix the GitHub Actions billing or spending limit, then re-run CI on 022b056c. Merge only when `checks`, `security`, `image` and `host` are green. If any fails for a code reason, send it back for a new round.

### Deferred conditions
- None.

### Optional improvements
- P3 #1 (regenerate race test). P3 #2.1: write the size rule (≈ 450 split, the stop line, "or say why") into the plan or PROJECT.md so both roles cite the same text.

### Handoff block (only when handing off)
Not requested.
