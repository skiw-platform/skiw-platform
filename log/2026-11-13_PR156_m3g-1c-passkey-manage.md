# PR 156 — feat(accounts): M3g-1c add, list and remove a passkey behind step-up

- **Merged:** 2026-11-13 (14:31:24 UTC) · **Merge commit:** ea9313052b157398199a0591424e28881f0270d5 · **Branch:** feat/m3g-1c-passkey-manage (final head 3f0bff432928a751d79c11ef1a84da0ebaef7f24)
- **Gate breaches:** none. The final round (R1) head SHA equals the PR's final head; the receipt (2026-11-13T14:28:44Z, review-file hash 0a3c012f, log-branch commit 5c692b8) precedes the merge by 2 minutes 40 seconds.
- **Approval receipt:** `reviews/PR-156.receipt` on agent-logs (review at commit 5c692b8).
- **Merge evidence:** `gh pr view 156` (skiw-dev1/skiw-platform) state MERGED, mergedAt 2026-11-13T14:31:24Z, merge commit ea93130; reachable from fetched origin/main.
- **Drafted by:** a deep-tier (Opus) sub-agent for the design and code, Sonnet 5.5 for the gates, mutant re-runs and PR body · **Reviewed by:** Claude Opus 5.5 (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** v1.22 (unchanged) · **Plan:** M3 §1 M3g row, amended 2026-11-13 · **Milestone:** M3, package M3g (fourth server PR, 1c)

## What changed
Begin and confirm routes to add a passkey (`/api/auth/factors/passkey/...`) behind a fresh `factor.change` step-up: single-use `register` challenge, verify, insert with the sealed lookup blob, other sessions ended, this one re-issued; the factor list shows passkeys (ids); removing a passkey retires it and a TOTP always stays. A duplicate credential id, a failed verify and a missing challenge all give one 400 `passkey-refused`. The `webauthn` import contract gains one ignored edge (`config.urls -> accounts.views`); the PR 155 test-only P3s are folded in. +649/−40 over 12 files (about 690 changed, over the 600 stop; the owner chose one PR).

## Why
Plan M3g and owner decision Q8: optional passkeys on top of the required TOTP, added and removed only behind step-up with session revocation (AUTH-07, AUTH-09).

## Review rounds
- R1: Approved, no P0 to P2. One P3 and nits, below. PR 155 R1 P3 #1 and P3 #2 (1c note) resolved.

## Deferred conditions
none. P3 #1: an end-to-end case that registers with a non-zero sign count and asserts it is stored (mutant M15, count stored as 0, is killed only by the direct `_stored` test; the soft authenticator always registers with 0). Low stakes. Nit: the `webauthn` contract ignores the whole `config.urls -> accounts.views` edge, as the TEN-10 session contract does.

## Decisions worth keeping
- All credential failures are one 400 `passkey-refused`; failed registrations are not counted against the code budget [A]; the list shows ids only, with the created time or label to be settled in M3g-2 (owner, 2026-11-13).
- A passkey never makes removing the last TOTP allowed (TOTP is required, D7).
- Only the `user_factor_credential_id_key` violation is mapped to a refusal, inside a savepoint; the constraint detail is never logged.
- Recorded in DECISIONS "2026-11-13 — M3g-1c".

## Follow-ups
- 1d (deep tier): the DECISIONS "M3g-1b" binding notes (owner match with the pending session, `own_transaction`, strict `<` on `last_challenge_at` in the conditional update, the stale-save replay test from PR 154 R1 P2 #2, the throttle in front of the lookup, id passes `_credential_id`), and `stepup.FACTOR_KINDS` gains `passkey`.
- M3g-2: one challenge per session (`begin_registration` and `begin_assertion` share one key), so a passkey add begun in one tab replaces a step-up begun in another and the other answer is refused (fails closed); the screens must expect it and not show it as a wrong passkey. Settle the created time or label for the list.
- Then the M3 gate review. Carried: owner checks (`ghcr_read_token`, fix the G9 hostname before the first passkey, main checkout `.env`); PR 152 conditions; older P3s; Dependabot PR 14 and alerts 1 and 2.

## Appendix — final review round
## Round 1 — 2026-11-13 · scope: slice (M3g-1c; `accounts.auth.factor_change`, `accounts.views`, three routes in `config.urls`, the factor list, the `webauthn` import contract, the PR 155 test-only P3s, tests, DECISIONS, host-rebuild runbook; no migration, setting or dependency)
- **Code review:** base (merge base) aa05585acac3f87ce6ba9aed74db00e1cf84d394 (= `origin/main`, PR 155 merged) · head 3f0bff432928a751d79c11ef1a84da0ebaef7f24 · one commit · +649/−40 over 12 files · head re-checked at end: yes (PR open, main unmoved)
- **Spec:** D7 (optional passkeys, TOTP required), AUTH-07, AUTH-09, §4.1 `uq(credential_id)`. Plan M3 §3 M3g and §4 M3g row. DECISIONS "M3g-1", "M3g-1a-2", "M3g-1b", and the new "M3g-1c". Carry-over: PR 155 R1 P3 #1 and P3 #2 (1c parts).
- **CI:** green on this head: `checks`, `security`, `image`, `host` success; `publish`, `deploy-staging` skipped (PR event).
- **Size:** about 690 changed lines, over the 600 stop line. The owner chose "open it as one PR" (2026-11-13), and the body says so. Code is about 225 lines; 387 lines are one test file. Not a finding.

**Verdict:** Approved. There is no P0, P1 or P2. The P3 is a small test gap and forward notes; none needs action before merge.
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** Use the deep tier for 1d (passkey sign-in and step-up branches). It carries the binding notes from DECISIONS "M3g-1b" and PR 154's open condition.

### Carry-over
- **PR 155 R1 P3 #1 (equal work, reversed grant): resolved.**
  - A new catalog test reads `prosrc` of both lookup functions. It pins the decoy loop before `INTO found` / `INTO stored` and outside every `IF`.
  - The 0015 reversal test now asserts that at 0014 the lookup role holds no `user_factor` column privilege.
  - I re-ran my three R1 survivors against this head with the same script. **S1 (grant kept on reverse), S2 (decoy after the lookup) and S3 (decoy only for a miss) are all killed.** I checked each mutant was installed in `pg_proc` while the tests ran.
- **PR 155 R1 P3 #2, 1c note (duplicate id → the ordinary refusal, no log): resolved.**
  - Only `user_factor_credential_id_key` is mapped, inside a savepoint. It answers 400 `passkey-refused`, the same as a failed verify or a missing challenge.
  - The test covers four holders (own in use, own retired, same agency, other agency) and captures logs at DEBUG: no constraint name, no id.
  - My mutant M17 (map any `user_factor` constraint) is killed.
- **PR 154 R1 P2 #2 (stale save):** still open for 1d. For registration it is harmless: a challenge put back by a stale save can only replay the same credential, which the unique key refuses. Or it lets the session's own holder add a passkey for themselves after a fresh step-up, which `begin` would let them do anyway.

### Applicability (reviewer's own list) and self-check audit
- **UNI-01/04/05:** met. 11 contracts kept; the webauthn contract has one ignored edge, see the nit.
- **UNI-03:** met. The body is exactly `{"credential": object}` (four malformed bodies tested); the credential itself is judged by `passkey.verify_registration` (PR 154, fuzzed there).
- **UNI-07 (hard):** met (CI gitleaks green).
- **UNI-09:** met (tested with a log capture).
- **UNI-13:** met, run twice on one DB.
- **UNI-16:** met (DECISIONS; runbook "Add or remove a passkey").
- **AUTH-03/D7:** met. A passkey never stands in for the TOTP, both ways, with a test; mutant M18 killed.
- **AUTH-07:** met. Add and remove both end every other session and re-issue this one with the same deadline.
- **AUTH-09:** met. Begin, confirm and remove all need a fresh `factor.change` step-up of this session.
- **TEN:** met. Rows are RLS-scoped in `with_agency()`; only the global unique key sees other agencies.
- **UNI-15:** n/a (no migration). **FE:** n/a.

I agree with the self-check.

### What I checked (and the builder's three questions)
1. **Challenge before step-up in `confirm_passkey`: right.**
   - `SessionStore.take` must run outside a transaction, and `hold` / `recent` must run inside the change transaction, in the M3h-4 order. So the take has to come first.
   - A stale step-up spending the challenge costs nothing: `begin` needs a fresh step-up too.
   - The order inside the transaction is right: `hold`, `recent`, insert, marker, re-issue. Mutant M1 (insert before the step-up check) is killed by both step-up tests. Mutant M9 (sessions ended before the insert) is killed by the duplicate tests, which assert no marker.
   - `hold` locks the user row and refuses a user who stopped being `active` or a revoked session. That is the same re-check TOTP gets from `second_factor.counted`.
2. **The last-factor rule: right.** `not set(totps) - {factor}` refuses removing the only TOTP, and refuses removing a passkey when no TOTP is in use. That state can't arise through a route; the test forces it by direct update. Removing a passkey while a TOTP stays is allowed. Mutant M12 (remove ignores the kind) is killed by the cross-route not-found cases.
3. **Duplicate mapping: right.** Only the one constraint, read from `__cause__.diag` without importing psycopg. Another integrity error still raises (tested with a count over 2³²−1). The savepoint keeps the transaction usable. Whether a duplicate exists in another agency shows only through the global key, and only to someone holding a credential id, which is random and minted by the authenticator.

Also checked:
- **`begin` excludes only the user's passkeys in use (mutant M2 killed).** That is the right call. Excluding a retired id would make the device refuse to create a new credential, and not excluding an in-use one would let the same device overwrite its own discoverable credential for this user.
- **The stored row:** the verified id, key and count, and a blob sealed with the id as AAD. The test opens it through `lookup_credential` and verifies a new assertion with the stored key.
- **Retire** clears the key and blob and keeps the id, so the lookup then gives the decoy (tested). The list shows passkeys in use only (mutant M7 killed).
- **Challenge binding:** the purpose and user are checked; a challenge for another user is refused (mutant M19 killed).
- **No other code counts factors regardless of kind.** I checked every `UserFactor` and `user_factor` query outside tests: sign-in reads `kind="totp"`, step-up `kind__in=FACTOR_KINDS` (TOTP only), and recovery deletes are scoped to `kind = 'recovery'`. So an added passkey changes nothing at sign-in or step-up until 1d.
- **The web client doesn't read `GET /api/auth/factors` yet,** so the new `passkey` key breaks no parser.

### Findings

#### P3 #1 — test gap and forward notes (no action required before merge)
- **Registration count.** The count a registration reports is stored as verified, but only the direct `_stored` integrity-error test kills mutant M15 (store 0). The soft authenticator always registers with count 0, as the builder notes. One end-to-end case would close it: register with a non-zero count and assert it is stored. Low stakes: storing 0 only weakens clone detection on the first assertion.
- **For 1d and M3g-2: one challenge per session.** `begin_registration` and `begin_assertion` share the one `CHALLENGE` key. A passkey add begun in one tab silently replaces a passkey step-up begun in another, and the other tab's answer is then refused. It fails closed, so it is safe, but M3g-2's screens should expect it rather than show it as a wrong passkey.
- **For 1d: still binding.** The DECISIONS "M3g-1b" notes: the owner match, `own_transaction`, the strict `<` on `last_challenge_at` in the conditional update, the stale-save replay test, and the throttle in front of the lookup. Step-up with a passkey also needs `stepup.FACTOR_KINDS` widened; the retire path already keeps the row, so step-up evidence naming a passkey stays valid.

### Nits (no action required)
- The `webauthn` contract ignores the whole edge `config.urls -> accounts.views`, so any future path through that edge is also unchecked. That is the same trade the TEN-10 session contract already makes, and a direct import from `config`, `health` or the others still fails.
- I agree with all three [A]s: failed registrations are not counted; one 400 covers a missing or expired challenge too; the list has ids only until the owner settles `created_at` or a label in M3g-2.

### Verification performed
In a detached checkout at the head with its own DB (`review-156`, port 5463), `make install lint typecheck test test-live`:
- lint, Semgrep 21/21 (0 findings), import-linter 11 kept, eslint clean; mypy 250 files;
- **1907 passed**; vitest 45 passed;
- test-live **1017 passed**, and 1017 again on the same DB after the mutants (no committed-row order trap with the tenancy reversal test).

`git diff --check` clean.

**Mutants** (scratch copy, bytecode off, caches cleared; live suites `test_passkey_change_live`, `test_factor_change_live`, `test_factor_remove_live`, 69 tests). All killed:
- M1 (insert before the step-up check), M2 (exclude retired too), M7 (list retired), M9 (sessions ended before the insert);
- M12 (remove ignores the kind), M15 (count stored as 0; killed only by the direct test, P3 #1), M17 (any `user_factor` constraint mapped to refused);
- M18 (passkeys counted for the last-factor rule), M19 (challenge user unchecked).

**PR 155 R1 survivors:** S1, S2 and S3 (migration mutants, applied by migrating to 0014 and back) are now killed, by the new pins.

Not run: `host-test` (no host file), `e2e` (no screen), gitleaks locally (CI green). Not verified in a real browser: M3g-2's virtual authenticator.

### Residual risks
- Passkey sign-in and step-up, and one challenge, one use for assertions, are still to come (1d).
- A user with two passkeys can't tell them apart in the list until M3g-2 (owner question on `created_at` or a label).
- Lost-authenticator recovery is still unbuilt (owner reset, M4-rest must-have before real data).
