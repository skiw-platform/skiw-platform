# PR 116 — feat(accounts): M3f-1 TOTP codes, the factor-secret subkey, password NFKC (PR 115 R1 P3 #1)

- **Merged:** 2026-11-05T09:10:50Z · **Merge commit:** 59af95b657d28fab5146e41190efdcffe90d6df3 · **Branch:** feat/m3f-1-totp-primitives
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-116.receipt, commit 3e2d4cc (2026-11-05T09:07:32Z, before the merge; head 266a3f5 and review hash 6602fa11 match)
- **Merge evidence:** `gh pr view 116` (state MERGED, mergedAt, mergeCommit, headRefOid 266a3f5726dfe9bf50b1695c51e193288554300a); `git merge-base --is-ancestor 59af95b origin/main` succeeded after a fresh fetch
- **Drafted by:** Claude Opus 5.5 (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md (v1.21, d95cb271) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3f · **Milestone:** M3 (M3f, part 1 of 3)

## What changed
`accounts.auth.totp`: RFC 6238 / RFC 4226 TOTP primitives (6 digits, 30 s, ±`SKIW_TOTP_SKEW_STEPS`, a 20-byte secret, replay refusal against the last accepted step, six ASCII digits only, constant-time comparison over the whole window). `blob.seal_factor_secret` / `open_factor_secret` seal a TOTP secret under the HKDF subkey `skiw-factor-secret-v1` of every `login_blob_key` version (48 bytes, AAD bound to factor, user and agency). Passwords are NFKC-normalised in `passwords.hash_password`/`verify`, and `enrol.redeem` counts the minimum after normalising (PR 115 R1 P3 #1). `views._fields` refuses a JSON field with a lone surrogate, which used to answer 500.

## Why
Flow 5.1 (2) TOTP second factor; spec §4.1 `secret_ct` (C3); AUTH-04 and PR 115 R1 P3 #1 (NIST SP 800-63B-4 normalisation, before any host has a hash); AUTH-05 and UNI-03 for the lone-surrogate defect.

## Review rounds
- R1: Approved, no findings. PR 115 R1 P3 #1 closed; the lone-surrogate fix (outside the plan) accepted.

## Deferred conditions
- none

## Decisions worth keeping
- M3f is split into three PRs: M3f-1 (this), M3f-2 (recovery codes), M3f-3 (TOTP enrolment, the second-factor endpoint, the stored step, AUTH-07 on a factor change, the `otpauth://` link). DECISIONS "M3f-1".
- `blob.require_key(label)` derives one cipher set per HKDF info; the TOTP secret never shares an AES key with the lookup blobs.
- Passwords: NFKC only (no strip, no case folding), in one place (`passwords`).
- The lasting decisions are in the merged DECISIONS ("2026-11-05 — M3f-1"); nothing missing.

## Follow-ups
- M3f-3: store the accepted step with a conditional update (`sign_count < step`) and test that two concurrent uses of one code let exactly one through; check `_skiw_pending_until`; only an `_skiw_pending_enrol` session may add a first factor (making the user `active`); a login's pending session uses only a factor it already has; mark the pending key, then `login()`; AUTH-07 revocation on a factor change; the `otpauth://` link.
- M3f-3 (optional, R1 note): a `length(secret_ct) = 48` CHECK for TOTP rows when it adds a migration.
- Optional (R1 note): refuse unassigned code points (category Cn) at enrolment, if NFKC drift across Unicode versions is ever worth closing.
- M3f-2: recovery codes. M3g: `guard.auth_lookup_credential` with a 60-byte decoy. M3i: the `/enrol` page (minimum, pending time limit, "ask for a new link").
- Owner: confirm to the reviewer that "12, build" was their answer (PR 115 R1, repeated in PR 116 R1).

## Appendix — final review round
## Round 1 — 2026-11-05 · scope: slice (M3f, part 1 of 3)
- **Code review:**
  - **Base:** `main`. Merge base ddf613209fa4ae28232560a70074bd5ed4616b18 (origin/main, PR 115 merged).
  - **Head:** 266a3f5726dfe9bf50b1695c51e193288554300a, one commit. 11 files, +404 −19. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). Flow 5.1 (2), AUTH-04, AUTH-05, §4.1 `secret_ct` (C3),
  UNI-02, UNI-03, UNI-06; plan `docs/plans/2026-10-31-m3-auth.md` §2 (pyotp rejected), §3 M3f; PR 115
  R1 P3 #1.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 116` (builder), then merge. Then M3f-2 (recovery codes).
- **Still open:** your confirmation of the "12, build" answer (PR 115 R1). The PR rightly leaves it to
  you.

### PR 115 R1 P3 #1 (password normalisation): resolved
- `passwords.normalise` is NFKC only: no strip and no case folding, which is right for a password.
- `hash_password` and `verify` both use it, so `dummy_verify`, which calls `verify`, does too. The
  known and unknown paths stay the same work.
- `redeem` counts the minimum on the normalised form, the form that is hashed.
- NFC and NFD each verify the other, in unit and live tests.
- No host has a hash yet, so no fallback verify is needed. That holds because staging and production
  have had no enrolment.
- The 4 mutants on it are killed.
- **Status:** closed.

### The lone-surrogate fix (outside the plan): accepted
- `json.loads` accepts `"\ud800"`, which UTF-8 can't encode. Before this PR, Argon2 or PostgreSQL then
  raised and the route answered 500 instead of the uniform refusal.
- This is a defect in our own input boundary (UNI-03, AUTH-05).
- The fix is one helper in `_fields`, which both routes and all four of their fields use. It runs
  before any query and is tested with no query.
- A form post can't carry one, because Django decodes form bodies with `replace`.
- It's small and well contained, and right to fix here.

### What was checked
- **`totp.code`** follows RFC 4226 §5.3:
  - the counter is 8 bytes, big-endian;
  - the offset is the low nibble of the last byte;
  - a 31-bit mask, then the last 6 digits with zero padding.
  - The Appendix D and RFC 6238 Appendix B SHA-1 vectors are tested, and the vector secret is public.
- **`accept`:**
  - It compares only exactly six ASCII digits. That guard also keeps `compare_digest` safe, because it
    raises on a non-ASCII `str`.
  - Every step in ±skew is computed and compared, with no early exit.
  - A match must be later than `last`, so a replay of the same step or an earlier one is refused.
  - The skew comes from `SKIW_TOTP_SKEW_STEPS` (bounded 0 to 1).
  - The returned step fits `user_factor.sign_count` (`BigIntegerField`, default 0, CHECK ≥ 0).
  - The PR says M3f-3 must store the step with a conditional update so two concurrent uses can't both
    pass. That is the right requirement; see Follow-ups.
- **The factor-secret seal:**
  - It uses an HKDF subkey with its own info, `skiw-factor-secret-v1`, so it never shares an AES key
    with the login or credential blobs.
  - The AAD is version ‖ purpose ‖ factor id ‖ user id ‖ agency id.
  - The ids are fixed-width, so their order is unambiguous, and the binding is tested.
  - The newest version seals, and every version is tried on open.
  - A secret that isn't 20 bytes is refused when sealing. The sealed form is 48 bytes.
  - `require_key` is now cached per label. `require_key()` and `require_key(LABEL)` are two cache
    entries for the same key, which is harmless.
- **UNI-06:** only the standard library and the existing `cryptography`; `pyotp` stays out, as the plan
  says.

### Checks
- `make -o check-node test-live` at 266a3f5 on a disposable DB: 583 passed, and migrate printed
  `tenancy schema check: ok`. Both match the PR body.
- `make -o check-node test`: pytest gave 1648 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- As in PR 115, I passed `SKIW_PW_MIN_LENGTH=12` in the environment, because the review worktree's local
  `.env` predates it. I didn't edit the file.
- The worktree is clean.

### Findings
None.

### Notes (no action)
- **NFKC depends on the Unicode version.**
  - Unicode guarantees that the normalised form of an assigned character won't change.
  - A code point that is unassigned today could normalise differently after a Python upgrade that adds
    it. A password containing one could then stop verifying.
  - That is very unlikely. If it's ever worth closing, refusing unassigned code points at enrolment
    (`unicodedata.category == "Cn"`) would do it.
- **`user_factor.secret_ct` has no length CHECK,** unlike the two lookup blobs (220 and 60). When M3f-3
  adds a migration anyway, a `length(secret_ct) = 48` CHECK for TOTP rows would match the blob
  practice. Optional.

### Follow-ups
- **M3f-3:**
  - store the accepted step with a conditional update (`UPDATE … SET sign_count = <step> WHERE id = …
    AND sign_count < <step>`), and test that two concurrent uses of one code let exactly one through;
  - the second-factor endpoint checks `_skiw_pending_until`;
  - only an `_skiw_pending_enrol` session may add a first factor, which makes the user `active`;
  - a login's pending session may use only a factor it already has;
  - mark the pending key, then `login()`;
  - the AUTH-07 revocation on a factor change;
  - the `otpauth://` link.
- **M3f-2:** recovery codes.
- **M3g:** `guard.auth_lookup_credential`, with a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- **M3i:** the `/enrol` page: the minimum, the pending time limit, and "ask for a new link".
