# PR 113 — feat(accounts): M3e-2b POST /api/auth/login (uniform answers, pending state, rotated CSRF token, timing band)

- **Merged:** 2026-11-04 (23:06:05 UTC) · **Merge commit:** 329d89f7f0ed1ef433eb42413fed221e7a018270 · **Branch:** feat/m3e-2b-login-route
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-113.receipt on agent-logs (log-branch commit 6759803, receipt time 2026-11-04T22:54:33Z, before merge; reviewed head 8b9dea66c115f46b076ee5dc9a9719a258d6331c, review-file hash b7577d988dd1461dfd1fe72b5a8ca4b944c14833, review commit 4985800)
- **Merge evidence:** `gh pr view 113` state MERGED at 2026-11-04T23:06:05Z, base main; merge commit 329d89f (parents d339238, 8b9dea6) is an ancestor of fetched origin/main; merged head equals reviewed head 8b9dea6.
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1); CI checks, security, image, host pass at 8b9dea6
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3e, §4 M3e row, carry-over (h) · **Milestone:** M3, M3e-2b (part 4 of 5)

## What changed
- `accounts.views.login_password` at `POST /api/auth/login` (`auth-login`, cookie auth): JSON or form post (FE-32). Three answers, all `Cache-Control: no-store`: malformed input → the 401 `{"error": "login-failed"}` with no query; `"limited"` → 429 `{"error": "limited"}`; `"failed"` → 401; `Verified` → `start_pending` → 200 `{"next": "second_factor", "csrf": get_token()}`.
- `password_step.start_pending`: retires a signed-in session (marker + row delete in one `with_agency()`), then `flush()` (new key, own lifetime), writes only `_skiw_pending_user`, `_skiw_pending_agency`, `_skiw_pending_until` (+`SKIW_LOGIN_PENDING_MIN`), then `rotate_token()`.
- `PUBLIC_ROUTES["auth-login"]` (signed off by the reviewer). CSRF gate fixtures gain `Fixture.answers` (401 for this route) and `assert_past_csrf`.
- import-linter: `config.urls → accounts.views` is the one allowed edge; `unmatched_ignore_imports_alerting = "warn"` removed, so a stale ignore fails the lint (pinned by a test; the contract tests' stub tree carries the edge).
- Tests: `test_login_password_live.py` (24, incl. byte-equal 401/429 and the statistical timing band); changed CSRF gate, route registry and import-contract tests. +400 −20 Python, 19 docs lines. 19 mutants killed. DECISIONS "M3e-2b" (incl. no password cap beyond the body limit).

## Why
Spec v1.21 Flow 5.1 (0)–(1), AUTH-02, AUTH-05, AUTH-06, FE-32, UNI-03, UNI-19, TEN-09, TEN-10; plan M3 §3 M3e, §4 M3e row (timing (2) statistical), carry-over (h), Risk 2; PR 112 R1 notes.

## Review rounds
- R1: Approved (head 8b9dea6), no merge conditions. The reviewer re-ran test-live (517) and test (1570) on a disposable DB and ran the timing band 3 more times (3/3 passed, ≈6.1 s each). `PUBLIC_ROUTES["auth-login"]` signed off. The PR 112 password-length note was accepted as a decision (Argon2 pre-hashes with BLAKE2b, so length costs a linear pass). PR 112 R1 P3 #1 was not done and is carried again as P3 #1.

## Deferred conditions
- **R1 P3 #1 (open, deferred to M3e-3, the next PR; must be listed in that PR's body):** no stored hash is upgraded after an Argon2 parameter change, so after `SKIW_ARGON2_*` is raised, accounts that haven't logged in since answer a wrong password at the old cost and unknown emails at the new cost (latent: all hashes use T5 today; `needs_rehash` has no caller). Fix (a, reviewer's recommendation): on a verified password with `needs_rehash`, re-hash and re-seal the blob in the `with_agency()` that reads the status, tested with a lower-parameter hash; or (b) the owner accepts the limit and a parameter change requires re-enrolment. Record the choice in DECISIONS.

## Decisions worth keeping
- Malformed input gets the same 401 as a failed login and does no work at all (no query), since it names no account to count against.
- A verified password leaves only a pending session: a fresh `flush()` session (own lifetime) with three pending keys and a rotated CSRF token; no `_skiw_user`, so the wrapper treats it as signed out. A signed-in session is retired first with a revocation marker; a failed attempt leaves any session alone.
- No password length cap beyond `DATA_UPLOAD_MAX_MEMORY_SIZE` (reviewer accepted).
- The statistical timing band is max(15 ms, 15 %) on medians of 20 interleaved pairs, fresh account and IP per request, no retries.
- An import-linter ignore that matches nothing is an error again.

## Follow-ups
- **Carried review items** (reviewer note, PR 113 R1): every PR body lists each open deferred item and its status, because PR 110 R1 P3 #1 and PR 112 R1 P3 #1 were each missed by the next PR.
- M3e-3: R1 P3 #1; enrolment (AUTH-08), the second public route (`PUBLIC_ROUTES` sign-off); its tests must `unseal()` blobs.
- M3f: the second factor checks `_skiw_pending_until`, marks the pending key (PR 107 note, DECISIONS M3e-2b), then calls `login()`. M3g: `guard.auth_lookup_credential` with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- Earlier, still open: re-seal job (T16); M4-rest disable → `revoke_user()`; spec §4.1 / D6 gap; `login()` sync only; the clock rule assumes one host; PR 78, 77, 81 items; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3e-2b" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M3e, part 2b of 5)
- **Code review:**
  - **Base:** `main`. Merge base 53ad168096f86cd86d2e3076e771cb5d35d2df48 (the PR 112 head; PR 112 is
    merged as d339238). `git log origin/main..HEAD` shows only this PR's two commits.
  - **Head:** 8b9dea66c115f46b076ee5dc9a9719a258d6331c, two commits (`bd9a1d8`, `8b9dea6`). 11 files,
    +421 −20. Re-checked at the end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Flow 5.1 (0)–(1), AUTH-02, AUTH-05, AUTH-06, FE-32,
  UNI-03, UNI-19, TEN-09, TEN-10; plan `docs/plans/2026-10-31-m3-auth.md` §3 M3e, the §4 M3e row
  (timing (2)), carry-over (h), Risk 2.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 113` (builder), then merge. Then M3e-3, which carries P3 #1.

### `PUBLIC_ROUTES["auth-login"]`: signed off (reviewer, AUTH-02)
- The route runs before any session exists, and a verified password leaves only a pending state. The
  wrapper refuses that state as signed out, because it has no `_skiw_user`.
- What protects it is CSRF (it is in the cookie-auth gate, signed out and signed in), the throttle and
  the uniform answers.
- The reason in the entry is accurate. **Approved as listed.**

### PR 112 follow-ups
- **The password length:** resolved as a decision (`8b9dea6`). There is no cap beyond
  `DATA_UPLOAD_MAX_MEMORY_SIZE`. Argon2 pre-hashes the password with BLAKE2b, so a long one costs a
  linear pass, not more memory-hard work. I accept that.
- **The route, `flush()` and the pending state, the rotated token, byte-equal answers and the timing
  band:** done; see below.
- **PR 112 R1 P3 #1 (no rehash after an Argon2 parameter change):** **not done.** `needs_rehash` still
  has no caller, and neither the PR body nor DECISIONS mentions it. It is carried as P3 #1. This is the
  second deferred P3 in a row that the next PR didn't list (after PR 110 R1 P3 #1). See Notes.

### What was checked
- **The three answers:**
  - Malformed input returns `_failed()` before any query. The 11 cases plus the 254-character boundary
    are tested.
  - `limited` → 429 and `failed` → 401, both byte-equal across the failure kinds and with no cookie.
  - Every answer is `no-store`.
  - A malformed body answers faster, because it does no work. That says something about the input,
    not about any account, which is fine.
- **`start_pending`:**
  - `flush()` gives a new key and its own lifetime; the builder's mutant shows `cycle_key()` would
    keep the old deadline.
  - Exactly three pending keys, with an ISO UTC expiry.
  - `rotate_token()` is followed by `get_token()`, so the 200 carries the new masked token, and the
    pre-login token gets `token-invalid`.
  - A signed-in session is retired with a marker and the row delete in one `with_agency()`, mirroring
    `login()`. A failed attempt doesn't touch the session.
- **TEN-09:** the only tenant work is the status read (PR 112) and the retire step, both inside
  `with_agency()`. The view runs no atomic block (`ATOMIC_REQUESTS` is unset), so `with_agency()` can
  open.
- **The CSRF gate:** `Fixture.answers = 401` for `auth-login`, and `assert_past_csrf` checks the
  status and that the marker header is absent. Both gate files use it.
- **import-linter:** dropping `"warn"` is what the M3a comment planned, and
  `test_an_ignore_that_matches_nothing_fails_the_lint` pins it.
- **The timing band** is interleaved, gives each request its own account and IP, and has no retries.
  Its 15 ms / 15 % band against a gap of about 70 ms is a sound margin.

### Checks
- `make test-live` at 8b9dea6 on a disposable DB: 517 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- `make -o check-node test`: pytest gave 1570 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- **Timing-band stability** (reviewer): `test_known_and_unknown_answer_within_one_timing_band` run 3 more
  times on its own: 3/3 passed, about 6.1 s each.
- `git grep needs_rehash app` outside the tests: only its definition (P3 #1).
- The worktree is clean.

### Findings

### [P3] #1 — No stored hash is upgraded after an Argon2 parameter change (carried from PR 112 R1)
- **Category:** uniformity (AUTH-05, plan Risk 2), latent
- **Evidence:** as in PR 112 R1 P3 #1.
  - `dummy_verify` uses the current parameters, while `verify` costs whatever the stored hash was made
    with.
  - `passwords.needs_rehash` has no caller (`git grep`).
  - Neither DECISIONS nor the plan says when a stored hash is upgraded.
- **Failure scenario:** after `SKIW_ARGON2_*` is raised, accounts that haven't logged in since answer a
  wrong password at the old cost, and unknown emails at the new cost. The timing band would catch the
  difference only if a test used an old-parameter hash.
- **Required correction:** choose one and record it in DECISIONS:
  - (a) on a verified password with `needs_rehash`, re-hash and re-seal the blob in the
    `with_agency()` that reads the status, and test it with a hash made under lower parameters; or
  - (b) the owner accepts the limit, and a parameter change requires re-enrolment.
  - I recommend (a). M3e-3 writes the blob at enrolment, so the re-seal helper fits there.
- **Owner:** builder; (b) needs the owner · **Disposition:** deferred to M3e-3 (the next PR). **It must be
  listed in that PR's body.** · **Status:** open (deferred)

### Notes (no action)
- **Carry deferred findings explicitly.** Twice now (PR 110 R1 P3 #1, PR 112 R1 P3 #1) the next PR didn't
  pick up a deferred P3, or say it hadn't. A short "Carried review items" section in each PR body, with
  every open deferred item and its status, would prevent this. This is advice; the kit already requires
  a named follow-up.
- **M3f must mark the pending key** when the second factor completes (the PR 107 note, now in DECISIONS
  M3e-2b), and check `_skiw_pending_until`.

### Follow-ups
- **M3e-3:** P3 #1; enrolment (AUTH-08), which is the second public route (`PUBLIC_ROUTES` sign-off).
- **M3f:** the second factor reads and checks the pending keys, marks the pending key, then calls
  `login()`.
- **M3g:** `guard.auth_lookup_credential`, with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
