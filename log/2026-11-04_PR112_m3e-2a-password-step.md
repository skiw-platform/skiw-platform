# PR 112 — feat(accounts): M3e-2a password_step.attempt (throttle, lookup, verify, uniform failure records) and the PR 111 P3s

- **Merged:** 2026-11-04 (15:36:50 UTC) · **Merge commit:** d339238eab69f7ee13bdf750b3ce4de657a6afea · **Branch:** feat/m3e-2a-password-step
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-112.receipt on agent-logs (log-branch commit b7a5298, receipt time 2026-11-04T15:36:15Z, before merge; reviewed head 53ad168096f86cd86d2e3076e771cb5d35d2df48, review-file hash 7be04a1ab647f417d74eba0063464f3a89da7cee, review commit fa1619e)
- **Merge evidence:** `gh pr view 112` state MERGED at 2026-11-04T15:36:50Z, base main; merge commit d339238 (parents 895a5f0, 53ad168) is an ancestor of fetched origin/main; merged head equals reviewed head 53ad168.
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1); CI checks, security, image, host pass at 53ad168
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3e · **Milestone:** M3, M3e-2a (part 3 of 5)

## What changed
- `accounts/auth/password_step.py` `attempt(email, password, ip) -> Verified | "limited" | "failed"`: throttle (limited = one query, nothing counted) → `lookup_login` → `blob.open_login` → one Argon2 verify or `dummy_verify` → after a verified password, `status` read in `with_agency()` (not active = full failure) → any failure: three counters + one `login.failed` event (HMACs, `{}`) → success: lock run reset. `events.KINDS` gains `login.failed`; `AccountsConfig.ready()` warms the dummy hash.
- PR 111 R1 P3s closed: plan text (220/60, no header, version in AAD, §6 in-place CHECK exception) and Semgrep `auth-lookup-accounts-auth-only` matching a bare-name literal (`callproc`).
- Tests: `accounts/tests/logins.py` (helpers; `unseal()` clears sealed blobs so the tenancy reversal test still runs), `test_password_step_live.py` (9, incl. the structural same-work test), `test_auth_passwords.py` +1. +314 Python, 28 docs. 13 mutants killed. DECISIONS "M3e-2a".

## Why
Spec v1.21 Flow 5.1 (1), §4.1 "Pre-tenant lookups", AUTH-05, AUTH-06, TEN-09, TEN-10, UNI-09; plan M3 §3 M3e steps (2)–(7), §4 M3e row (structural timing), Risk 2; PR 111 R1 P3s.

## Review rounds
- R1: Approved (head 53ad168), no merge conditions. The reviewer re-ran test-live (488) and test (1562) on a disposable DB and probed the Semgrep rule (callproc, concatenated and %-formatted names all flagged). PR 111 P3 #1 and #2 closed (also closes PR 110 R1 P3 #1). One new P3, deferred to M3e-2b.

## Deferred conditions
- **R1 P3 #1 (open, deferred to M3e-2b, PR 113):** after an Argon2 parameter change, `dummy_verify` pays the new cost while a stored hash keeps its old cost, so known and unknown emails take different times (latent: all hashes use T5 today; `needs_rehash` has no caller). Fix (a, reviewer's recommendation): on a verified password with `needs_rehash`, re-hash and re-seal the blob in the same `with_agency()`, with a DECISIONS entry and a runbook line on the residual window; or (b) an accepted limit (parameters change only with forced re-enrolment), which is an owner decision.

## Decisions worth keeping
- Every failure path that does not get past the password does the same work: one lookup, one 220-byte open, one Argon2 verify at the current parameters, no Argon2 hash, the same three counter upserts and one `login.failed` event; a structural test pins it.
- A disabled or invited user with the right password is a full failure (counted and logged), stricter than plan [A]; only the status read is extra, after a right password.
- A limited attempt is one query and is not counted again, so retrying while locked does not extend the lock.
- Tests that seal a login blob into a kept row must clear it afterwards (`unseal()`), because `accounts.0008` reversed refuses 220-byte blobs.

## Follow-ups
- M3e-2b (PR 113, stacked; retarget to main next): R1 P3 #1; reviewer notes: bound the password length before `attempt()` (a field limit, the same refusal as other malformed bodies; PR 113 currently says "no cap beyond the body limit"); the view must run `attempt()` outside any atomic block; the `PUBLIC_ROUTES` entry needs sign-off; byte-equal 401/429 and the timing band.
- M3e-3: enrolment (AUTH-08); its tests must `unseal()` blobs too. M3f: the second factor must mark the pending key (PR 107 note). M3g: `guard.auth_lookup_credential`, 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- Earlier, still open: re-seal job (T16); M4-rest disable → `revoke_user()`; spec §4.1 / D6 gap; `login()` sync only; the clock rule assumes one host; PR 78, 77, 81 items; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3e-2a" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M3e, part 2a of 5)
- **Code review:**
  - **Base:** `main`. Merge base 895a5f040273e8d112c9cf2e23d444c135584977 (origin/main, PR 111 merged).
  - **Head:** 53ad168096f86cd86d2e3076e771cb5d35d2df48, one commit. 11 files, +345 −11. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Flow 5.1 (0)–(1), AUTH-05, AUTH-06, TEN-09, TEN-10, UNI-09;
  plan `docs/plans/2026-10-31-m3-auth.md` §3 M3e steps (2)–(7), the §4 M3e row (structural timing),
  Risk 2.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 112` (builder), then merge. Then M3e-2b, which carries P3 #1.

### PR 111 R1 P3s: resolved
- **P3 #1 (plan text):** lines 74, 93 and 105 now give the header-free layout, 220 and 60 bytes, the
  version in the AAD, and every version tried. Line 105 says M3g pins its literal to
  `LOOKUP_BLOB_LENGTH`. §6 records the in-place CHECK replacement (0008). The text matches `blob.py`.
  **Status:** closed. This also closes PR 110 R1 P3 #1.
- **P3 #2 (Semgrep `callproc`):** the second branch now matches any string literal that is exactly the
  name, with or without `guard.`. That also covers the `Identifier` arguments the old branch matched.
  - **Reviewer probe:** a temporary `app/zz_review_probe.py`, run with the pinned Semgrep 1.179.0 and
    then deleted. These were all flagged:
    - `callproc("guard.auth_lookup_login", …)`;
    - a module constant built as `"guard." + "auth_lookup_login"` and passed to `callproc`;
    - a `%`-formatted name.
  - The fixture's `ok` case (`auth_lookup_logins`) shows the anchors hold.
  - **Status:** closed.

### What was checked
- **The order matches plan (2)–(7):**
  1. throttle;
  2. lookup;
  3. open;
  4. exactly one Argon2 verify (the record's hash, or `dummy_verify`);
  5. the status read only after a verified password, inside `with_agency(record.agency_id)`;
  6. on any failure, the three counters and one `login.failed` event with HMACs and `{}`;
  7. on success, only the lock run is reset.
- **A limited attempt is one query** and does no lookup, no open, no Argon2 and no event, for known and
  unknown emails alike. Being limited isn't counted again, so a locked attacker can't extend the lock
  by retrying. The lock still ends `SKIW_AUTH_LOCK_MIN` after the 10th failure (tested past the window).
- **The structural test** (plan Risk 2) is the right first line:
  - Known-wrong, unknown and invited each do one verify with the T5 parameters `(3, 65536, 1)`, no hash,
    and one 220-byte open, with the same SQL statement shapes in the same order.
  - The 13 builder mutants cover each way the three paths could diverge.
- **A disabled user with the right password fails fully** (counters and event), so their records match a
  wrong password's. That is stricter than plan [A], and correct.
- **The dummy hash is made at start-up** in `AccountsConfig.ready()`, and a test pins it.
- **TEN-09:** the only tenant read is in `with_agency()`. The rest is the spec's pre-tenant path.
  `attempt()` must therefore run outside any atomic block, which M3e-2b's view must respect.
- **Test hygiene:** `logins.unseal()` clears the blobs that tests write, so the tenancy reversal test
  (0008 reversed back to 222) still runs. Leaving users with a `NULL` blob is fine: they then count as
  "invited".

### Checks
- `make test-live` at 53ad168 on a disposable DB: 488 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- `make -o check-node test`: pytest gave 1562 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- The Semgrep probe above.
- The worktree is clean.

### Findings

### [P3] #1 — After an Argon2 parameter change, known accounts and unknown emails take different times
- **Category:** uniformity (AUTH-05, plan Risk 2), latent
- **Evidence:**
  - `dummy_verify` uses the **current** parameters.
  - `verify(record.password_hash, …)` costs whatever the stored hash was made with. Argon2's cost
    follows the parameters in the encoded hash.
  - `passwords.needs_rehash` exists, but nothing calls it, and neither the plan nor DECISIONS says when a
    stored hash is upgraded.
  - The fixed blob size hides a parameter change in the **length** (plan M3b). It doesn't hide it in the
    **time**.
- **Failure scenario:** the owner raises `SKIW_ARGON2_MEMORY_KIB` or `TIME_COST`, as T5 hardening
  expects over time. Every account that hasn't logged in since keeps a hash with the old cost, while an
  unknown email pays the new cost. An attacker timing wrong-password attempts (throttled, but 5 per
  account per window is enough for a timing sample) separates existing accounts from non-existent
  ones. Today all hashes use the T5 values, so nothing leaks yet.
- **Required correction:** in M3e-2b, either:
  - (a) on a verified password, if `needs_rehash`, re-hash and re-seal the blob in the same
    `with_agency()`, and record in DECISIONS (with a runbook line) that a parameter change leaves a
    timing difference for accounts that haven't logged in, until they do; or
  - (b) record it as an accepted limit, saying parameters don't change without a forced re-enrolment.
  - Either way, state it in DECISIONS. (a) is the usual practice, and I recommend it.
- **Owner:** builder (the accepted-limit wording in (b) is an owner decision) · **Disposition:**
  deferred to M3e-2b (the next PR, stacked on this one) · **Status:** open (deferred)

### Notes (no action)
- **A disabled user with the right password does a little more work** (`with_agency()` and one status
  query) before failing. Only someone who already has the password can see that, and all it tells them
  is that the account isn't active. Acceptable.
- **For M3e-2b:**
  - bound the password length before `attempt()`, so a large body doesn't become Argon2 work;
  - `DATA_UPLOAD_MAX_MEMORY_SIZE` caps it today, but a field limit (and the same refusal for every
    malformed body) is clearer;
  - the HTTP byte-equal test and the timing band are in M3e-2b's scope.

### Follow-ups
- **M3e-2b:**
  - P3 #1;
  - the route `POST /api/auth/login` (a public mutating entry in `PUBLIC_ROUTES`, which needs my
    sign-off, with its reason in the PR body);
  - `cycle_key()` and the pending state;
  - the rotated CSRF token in the response;
  - the byte-equal 401 and 429 bodies, and the timing band;
  - the view runs `attempt()` outside any atomic block.
- **M3e-3:** enrolment (AUTH-08).
- **M3g:** `guard.auth_lookup_credential` with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
