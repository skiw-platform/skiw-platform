# PR 114 — feat(accounts): M3e-3a enrolment links (accounts_invite, enrol.invite/redeem) and the stored-hash upgrade (PR 112/113 R1 P3 #1)

- **Merged:** 2026-11-05 (03:04:40 UTC) · **Merge commit:** 486b5c0e50710bb4c89788f44c5298ed169a4186 · **Branch:** feat/m3e-3a-invite-link
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-114.receipt on agent-logs (log-branch commit 88325ee, receipt time 2026-11-05T03:03:26Z, before merge; reviewed head fa7a0db4942d502094eb2ebfb5b2abc9d8c1f024, review-file hash 63bc8ccb257ba5ed59b9a487d14dfce668465de2, review commit 973aeb0)
- **Merge evidence:** `gh pr view 114` state MERGED at 2026-11-05T03:04:40Z, base main; merge commit 486b5c0 (parents 329d89f, fa7a0db) is an ancestor of fetched origin/main; merged head equals reviewed head fa7a0db.
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1), no findings; CI checks, security, image, host pass at fa7a0db
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3e (enrolment), §4 M3e row · **Milestone:** M3, M3e-3a (part 5 of 6)

## What changed
- `accounts/auth/enrol.py`: `invite(email, name)` (normalised email, `validate_email`, ≤ 254 = `blob.EMAIL_MAX`; name 1–200 trimmed, no NUL; in `with_agency(<deployment agency>)` under a row lock: a new `invited` user, a new link for an `invited` one, refusal for `active`/`disabled` or an email another agency holds). Token = `TimestampSigner(salt="skiw-enrol-v1")` over user id, agency id and the SHA-256 of `login_blob_ct` (empty while NULL). `redeem(token, password) -> Verified | None`: `max_age = SKIW_ENROL_LINK_MIN`, row lock, `status = invited`, fingerprint equal, then the blob is written; one `None` for every refusal. The user stays `invited` until the first second factor.
- `manage.py accounts_invite <email> --name <name>` prints only `https://<ALLOWED_HOSTS[0]>/enrol#<token>` (token in the fragment).
- `password_step`: after a verified password and an `active` status, a hash with `needs_rehash` is re-made and re-sealed in the same `with_agency()`, by `UPDATE … WHERE id AND login_blob_ct = <the opened blob>` (PR 112/113 R1 P3 #1, option (a)).
- Runbook `host-rebuild.md` "Enrol a user" (`compose exec`, not `run`, so the link stays out of journald; treat it as a password; single use, 30 min; re-invite; the Argon2 residual limit). DECISIONS "M3e-3a".
- Tests: `test_enrol_live.py` (26), `test_password_step_live.py` +3. +426 −4 Python, 49 docs. 20 mutants killed.

## Why
Spec v1.21 AUTH-04, AUTH-05, AUTH-08, Flow 5.1 (4), D7, TEN-09, UNI-09; plan M3 §3 M3e, §4 M3e row ("works once, expired, tampered, reused"); owner Q5 (a); PR 112 R1 and PR 113 R1 P3 #1.

## Review rounds
- R1: Approved (head fa7a0db), no findings, no merge conditions. The reviewer re-ran test-live (546) and test (1570) on a disposable DB. P3 #1 closed. `compose exec` over the plan's one-off container accepted. The "Carried review items" table noted as done.

## Deferred conditions
- None.

## Decisions worth keeping
- Single use comes from the signed blob fingerprint plus the row lock; no token table.
- The user stays `invited` after setting a password; only the first second factor activates, so a password alone never signs in (D7).
- The enrolment token travels in the URL fragment, and the operator runs the command with `compose exec`, so the link reaches no request line, `Referer`, Caddy log or journald.
- A stored hash with older Argon2 parameters is upgraded at the next successful sign-in, never over a password set meanwhile; users who haven't signed in since a parameter change keep the old cost (recorded limit).

## Follow-ups
- **Owner ASK, before M3e-3b:** minimum password length at enrolment (reviewer recommends 12, no composition rules, bounded setting; owner's call).
- M3e-3b: `POST /api/auth/enrol`, the second `PUBLIC_ROUTES` entry (reviewer sign-off), one uniform refusal, a pending enrolment session that isn't signed in until the second factor. Reviewer note: a runbook sentence on two concurrent invites for a new email (the second is told "cannot be invited"; re-running gives the right answer).
- M3f: mark the pending key and check `_skiw_pending_until`; the first second factor makes the user `active`. M3g: `guard.auth_lookup_credential` with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- Earlier, still open: re-seal job (T16); M4-rest disable → `revoke_user()`; spec §4.1 / D6 gap; `login()` sync only; the clock rule assumes one host; PR 78, 77, 81 items; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3e-3a" entry.

## Appendix — final review round
## Round 1 — 2026-11-05 · scope: slice (M3e, part 3a of 6)
- **Code review:**
  - **Base:** `main`. Merge base 329d89f7f0ed1ef433eb42413fed221e7a018270 (origin/main, PR 113 merged).
  - **Head:** fa7a0db4942d502094eb2ebfb5b2abc9d8c1f024, one commit. 11 files, +475 −4. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). AUTH-04, AUTH-05, AUTH-08, Flow 5.1 (4), D7, TEN-09,
  UNI-09; plan `docs/plans/2026-10-31-m3-auth.md` §3 M3e (enrolment) and the §4 M3e row ("works once,
  expired, tampered, reused"); owner Q5 (a).
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 114` (builder), then merge. Then M3e-3b. The owner's answer on the minimum
  password length (the PR's ASK) is needed before M3e-3b.

### Carried review items
- **The PR body now has a "Carried review items" table,** as PR 113 R1 suggested. Each item is listed
  with its status, and the open ones name their PR.
- **PR 112 R1 / PR 113 R1 P3 #1 (stored-hash upgrade): resolved with option (a).**
  - **When:** after a verified password and an `active` status, inside the same `with_agency()` that
    reads the status.
  - **How:** a hash with `needs_rehash` is re-made and re-sealed by an `UPDATE … WHERE id = … AND
    login_blob_ct = <the blob this login opened>`, so a password set in the meantime wins.
  - **Failure paths are unchanged.** It runs only after a right password, and the PR 112 structural
    test still passes.
  - **Tests:** an older-parameter hash is upgraded at sign-in, and not on a wrong password or a
    disabled user's right one; a current hash is left alone; a concurrent password change isn't
    overwritten.
  - **The residual limit is recorded:** accounts that haven't signed in since a parameter change still
    differ in timing. It is in DECISIONS and in `host-rebuild.md`.
  - **Status:** closed.

### What was checked
- **The token** is `TimestampSigner(salt="skiw-enrol-v1")` over the user id, the agency id and the
  SHA-256 of `login_blob_ct` (empty while it is NULL), with `max_age` in minutes.
- **Single use comes from the blob fingerprint and the row lock**, so no new table is needed:
  - setting the password changes the blob, which kills this link and every other unused link for the
    user;
  - two uses at once queue on `select_for_update` (tested 8/8).
- **`redeem` returns `None` for every refusal:** a bad signature, an expired, tampered or wrong-shape
  token, a user who is no longer `invited`, a fingerprint that doesn't match, an empty password.
- **The agency comes from the signed token**, and RLS inside `with_agency()` makes the row lookup match
  it.
- **The user stays `invited` after `redeem`.** Together with PR 112's "not `active` is a failure", a
  password alone can't sign anyone in before a second factor (D7, Flow 5.1 (4)). This is correct.
  - It does mean an invited user with a password, signing in with the right password, does the status
    read before failing. Only someone who has the password can see that.
- **`invite`:**
  - It stores the normalised email (`validate_email`, at most 254 characters) and the trimmed name (1 to
    200 characters, no NUL).
  - It refuses `active` and `disabled` users.
  - Re-inviting an `invited` user gives a new link over the row as it is now, which is the recovery
    path for a lost or expired link.
  - A unique clash with another agency's user is refused without naming that user. The operator learns
    only that the email "cannot be invited", which is fine for a trusted operator in a single-agency
    v1.
- **The command and runbook:**
  - The token is in the URL fragment, so it isn't in request lines, `Referer` or the Caddy logs.
  - `compose exec`, rather than `compose run`, is right: `run` output also goes to the journald logging
    driver, while `exec` output reaches only the terminal.
  - The link itself is printed only to stdout. The runbook's "treat it as a password" guidance is
    clear.
- **TEN-09:** `invite`, `redeem` and the upgrade each write inside one `with_agency()`.

### Checks
- `make test-live` at fa7a0db on a disposable DB: 546 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- `make -o check-node test`: pytest gave 1570 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- The worktree is clean.

### Findings
None.

### Notes (no action)
- **Two concurrent invites for a new email:** `select_for_update` on a missing row locks nothing, so
  both insert. The second hits the unique email and is told "this email cannot be invited". It's safe
  but misleading. Running the command again gives the right answer, so no change is needed. A sentence
  in the runbook would do.
- **The token is signed, not encrypted.** Whoever holds the link can read the user and agency UUIDs in
  it. That's only the recipient, and the ids aren't secret, so this is acceptable.
- **For M3e-3b:**
  - the enrol route is the second public mutating route and needs my `PUBLIC_ROUTES` sign-off;
  - its refusal should be one uniform answer, like the login route's;
  - the session it starts must not count as signed in until the second factor.

### Owner decision needed (relayed from the PR's ASK)
- **A minimum password length at enrolment.** The spec sets none, and `redeem` refuses only an empty
  password.
  - My recommendation: a minimum of **12 characters**, with no composition rules.
    - NIST SP 800-63B-4 sets at least 8 characters when the password is one of two factors, as it is
      here, and 15 when it is the only factor. 12 gives a margin above 8.
    - Make it a bounded setting (UNI-02), checked in M3e-3b's route, with the same uniform refusal.
  - This is your decision.

### Follow-ups
- **M3e-3b:** the route, the pending enrolment state, the `PUBLIC_ROUTES` sign-off, and the password
  minimum once you've decided.
- **M3f:** mark the pending key and check `_skiw_pending_until`; the first second factor makes the user
  `active`.
- **M3g:** `guard.auth_lookup_credential`, with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
