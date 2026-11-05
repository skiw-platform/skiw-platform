# PR 115 — feat(accounts): M3e-3b POST /api/auth/enrol, the pending enrolment state and the password minimum (owner: 12)

- **Merged:** 2026-11-05 (04:52:16 UTC) · **Merge commit:** ddf613209fa4ae28232560a70074bd5ed4616b18 · **Branch:** feat/m3e-3b-enrol-route
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-115.receipt on agent-logs (log-branch commit c6d0372, receipt time 2026-11-05T04:46:51Z, before merge; reviewed head 37389ccba8440162faadd8a8f304167cc9f1be8f, review-file hash 94b36a1b105f423a1cbcdb30df45bc482e80359e, review commit 5ab321a)
- **Merge evidence:** `gh pr view 115` state MERGED at 2026-11-05T04:52:16Z, base main; merge commit ddf6132 (parents 486b5c0, 37389cc) is an ancestor of fetched origin/main; merged head equals reviewed head 37389cc.
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1), one P3 deferred to M3f; CI checks, security, image, host pass at 37389cc
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3e (enrolment), §4 M3e row · **Milestone:** M3, M3e-3b (part 6 of 6; M3e complete)

## What changed
- `SKIW_PW_MIN_LENGTH` = 12 (owner 2026-11-05, "12, build"), bounded 12–64, wired into every context the other auth values use. Named `PW`, not `PASSWORD`, so the host Compose secret-name guard stays as it is.
- `enrol.redeem` refuses a password shorter than the minimum (code points), writing nothing, so the link keeps working.
- `POST /api/auth/enrol` (`accounts.views.enrol_password`, JSON or form `{token, password}`): every refusal is one 401 `{"error": "enrol-failed"}`, `no-store`, no cookie, the session untouched; a malformed body runs no query. Success: `start_pending(..., enrol=True)` (the M3e-2b pending state plus `_skiw_pending_enrol`) and 200 `{"next": "enrol_factor", "csrf": <rotated token>}`. Not signed in; the user stays `invited`.
- `PUBLIC_ROUTES["auth-enrol"]` (reviewer signed off), CSRF fixture `answers=401`. Body parsing shared with the login route (`_fields`).
- Runbooks: `host-rebuild.md` (the minimum; a short password leaves the link; two concurrent invites; the interim-values list), `local-dev.md` (the new `.env` line). DECISIONS "M3e-3b".
- Tests: `test_enrol_route_live.py` (new), `test_enrol_live.py` (short-password cases), registry, CSRF and settings tests. +342 −27 code, tests and config, 29 docs. 18 mutants killed.

## Why
Spec v1.21 AUTH-02, AUTH-05, AUTH-08, Flow 5.1 (4), D7, FE-32, UNI-02, UNI-03, UNI-19; plan M3 §3 M3e, §4 M3e row; owner answer 2026-11-05; PR 114 R1 notes and ASK.

## Review rounds
- R1: Approved (head 37389cc). `PUBLIC_ROUTES["auth-enrol"]` signed off; no throttle accepted. The reviewer re-ran test-live (577 vs the body's 574: a miscount in the body, not a defect), test (1596) and host-test (847) on a disposable DB. One finding, P3 #1 (password Unicode normalisation), deferred to M3f. The reviewer asked the owner to confirm the "12, build" answer, since it was given in the builder chat.

## Deferred conditions
- **PR 115 R1 P3 #1 → M3f (next PR), status open:** NFKC-normalise passwords in one place (`passwords.hash_password`, `verify`, `dummy_verify`), count the minimum after normalising, test that NFC and NFD forms both verify, record it in DECISIONS. Must land before the first enrolment on a host. Must be listed in M3f's "Carried review items" table.

## Decisions worth keeping
- The password minimum is an owner value (12) in a bounded setting whose weak end fails closed; no composition rules; counted in code points.
- One uniform refusal for the enrol route, "too short" included; the page (M3i) states the minimum up front.
- No throttle on the enrol route: the link is an HMAC, so there is nothing to guess, and only a valid unused link runs Argon2.
- An enrolment's pending state is the login's pending state plus `_skiw_pending_enrol`; only that marker lets M3f/M3g add a first factor.
- Env names avoid `SECRET|PASSWORD|TOKEN|KEY|KEK` unless the value is a secret file, rather than exempting names from the host guard.

## Follow-ups
- **M3f:** P3 #1 above (first); check `_skiw_pending_until`; only a session with `_skiw_pending_enrol` may add a first factor, which makes the user `active`; a login's pending session may use only a factor it already has; mark the pending key, then `login()`.
- **M3g:** `guard.auth_lookup_credential` with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- **M3i:** the `/enrol` page (only `/` serves the shell today); state the minimum and the pending time limit ("if this times out, ask for a new link").
- **Owner:** confirm the "12, build" answer to the reviewer.
- Earlier, still open: re-seal job (T16); M4-rest disable → `revoke_user()`; spec §4.1 / D6 gap; `login()` sync only; the clock rule assumes one host; PR 78, 77, 81 items; M2c deferred P2; Dependabot alerts security/dependabot/1 and /2 (2 reported on push 2026-11-05); M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3e-3b" entry.

## Appendix — final review round
## Round 1 — 2026-11-05 · scope: slice (M3e, part 3b of 6)
- **Code review:**
  - **Base:** `main`. Merge base 486b5c0e50710bb4c89788f44c5298ed169a4186 (origin/main, PR 114 merged).
  - **Head:** 37389ccba8440162faadd8a8f304167cc9f1be8f, one commit. 23 files, +372 −31. Re-checked at
    the end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). AUTH-02, AUTH-05, AUTH-08, Flow 5.1 (4), D7, FE-32,
  UNI-02, UNI-03, UNI-19; plan `docs/plans/2026-10-31-m3-auth.md` §3 M3e and the §4 M3e row; PR 114 R1
  notes and ASK.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 115` (builder), then merge. That completes M3e. Then M3f, which carries P3 #1.
- **Owner check:** the PR and DECISIONS record your answer as "12, build" (2026-11-05). That answer
  wasn't given in the review chat, so I can't check it. Please confirm it's yours.

### `PUBLIC_ROUTES["auth-enrol"]`: signed off (reviewer, AUTH-02)
- The route runs before the user has any credential. What protects it:
  - the link's `TimestampSigner` HMAC under `SECRET_KEY`;
  - the link is single use (the blob fingerprint and the row lock) and lasts 30 minutes;
  - CSRF (`auth="cookie"`, in the CSRF gate with `answers=401`);
  - one answer for every refusal.
- Success leaves only a pending state that the wrapper refuses as signed out (tested with
  `wrapper._signed`), and the user stays `invited`.
- The reason in the entry is accurate. **Approved as listed.**
- **No throttle:** I accept this.
  - Without a valid link, a request costs one HMAC check and no query.
  - With a used link it costs one locked row read and no Argon2, because the fingerprint check comes
    before the hash.
  - Only a valid, unused link with a long enough password runs Argon2, and success kills the link.
  - There is no account for a throttle to count against.

### PR 114 items
- **Password minimum:** 12 (`SKIW_PW_MIN_LENGTH`, bounds 12 to 64; the weak end is the owner value and
  fails closed, tested). Done, pending your confirmation above.
- **One uniform refusal:** done. 401 `enrol-failed`, `no-store`, no cookie, the session untouched;
  byte-equal tests across the refusal kinds.
- **Not signed in until the second factor:** done.
- **The runbook sentence on two invites at once:** done.
- **The name `PW`, not `PASSWORD`:** the right call. Exempting the name from the host Compose
  secret-name guard would have weakened it.

### What was checked
- **`redeem`:**
  - The length check (`len`, code points) comes after the signature and before any query, so a short
    password writes nothing and leaves the link working.
  - The order is: the signature, the length, the locked row, the fingerprint, then Argon2 and the seal.
    A timing difference between those steps tells only the link holder that their link is genuine,
    which they already know.
- **The view:**
  - `_fields` takes two string fields from a JSON object or a form, and the login route uses it too.
  - The login route's checks are unchanged: an email of 1 to 254 characters with no NUL, a non-empty
    password. It doesn't enforce the minimum, which is right: a login must not reveal the length rule.
- **`start_pending(…, enrol=True)`:**
  - It adds `_skiw_pending_enrol` after the flush and before `rotate_token()`.
  - A login's pending state still has exactly three keys (mutant killed).
  - A signed-in session is retired with a marker; a refusal leaves it alone (tested).
- **Env wiring:** every context the other auth values use, and the host and settings tests.
  `local-dev.md` names the line that an older `.env` needs.

### Checks
- `make -o check-node test-live` at 37389cc on a disposable DB:
  - **577 passed**; the PR body says 574.
  - migrate printed `tenancy schema check: ok`.
  - The two enrol files collect 52 tests (26 of them new, where the body says 23). The 3 extra likely
    come from parametrized cases.
  - It's a small miscount in the body, not a defect.
- `make -o check-node test`: pytest gave 1596 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- `make -o check-node host-test`: 847 passed, which matches.
- **Local `.env` (reviewer):** the review worktree's `.env` predates the new line, so Compose refused to
  start. I passed `SKIW_PW_MIN_LENGTH=12` in the environment for these runs and left the file
  unchanged. Any developer `.env` made before this PR needs the line, as `local-dev.md` says.
- The worktree is clean.

### Findings

### [P3] #1 — Passwords are hashed without Unicode normalisation
- **Category:** usability, a latent lock-out (AUTH-04, T5)
- **Evidence:**
  - `passwords.hash_password` and `verify` pass the raw `str` to Argon2. `redeem` counts `len` on the
    raw string.
  - Emails are NFKC-normalised (`blob.normalise_email`); passwords aren't.
  - DECISIONS has no entry on it.
  - NIST SP 800-63B-4 says a verifier SHOULD apply NFKC or NFKD normalisation to a password before
    hashing it.
- **Failure scenario:**
  - A user enrols a password with an accented letter on one device, which sends NFC (`é` as U+00E9).
  - Later they sign in from a device or input method that sends NFD (`e` + U+0301).
  - Argon2 sees different bytes, so the password fails, and the lock run counts it.
  - The user is locked out with no way to tell why, and recovery is an owner reset.
  - This PR makes it reachable: it is the first route that sets a real password.
- **Required correction:**
  - Normalise the password in one place, in `passwords` (`hash_password`, `verify`, `dummy_verify`),
    with NFKC to match the email.
  - Count the minimum after normalising.
  - Record it in DECISIONS.
  - Test that an NFC password and its NFD form both verify.
  - **It must land before the first enrolment on a host.** Changing it after hashes exist would need a
    fallback verify.
- **Owner:** builder · **Disposition:** deferred to M3f (the next PR); must be listed in its "Carried
  review items" table. · **Status:** open (deferred)

### Notes (no action)
- **An expired pending enrolment:**
  - `SKIW_LOGIN_PENDING_MIN` (5 minutes) after setting the password, a user who hasn't added a factor
    has an invited account with a password, and a link that is now used up.
  - Re-inviting gives a new link that resets the password, which is the recovery path in the runbook.
  - When M3i writes the page, it should say so ("if this times out, ask for a new link").
- **The route path `/api/auth/enrol` and `next: "enrol_factor"`:** fine as builder values.

### Follow-ups
- **M3f:**
  - P3 #1;
  - check `_skiw_pending_until`;
  - only a session with `_skiw_pending_enrol` may add a first factor, which makes the user `active`;
  - a login's pending session may use only a factor it already has;
  - mark the pending key, then `login()`.
- **M3g:** `guard.auth_lookup_credential`, with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- **M3i:** the `/enrol` page; it states the minimum and the pending time limit.
