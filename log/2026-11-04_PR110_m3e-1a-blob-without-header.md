# PR 110 — feat(accounts): M3e-1a login and credential blobs without a cleartext key version (corrects M3b)

- **Merged:** 2026-11-04 (13:25:07 UTC) · **Merge commit:** 9387ee2672786455ffbde50344e7cbc5c1711047 · **Branch:** feat/m3e-1a-blob-without-header
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-110.receipt on agent-logs (log-branch commit 83e088a, receipt time 2026-11-04T13:23:51Z, before merge; reviewed head abbdb131d7fa3c931189a9272fd65768f82dedcd, review-file hash 2dd1c4f1b2f9d1f9c2f1f7e7dbfe55c279d7ea18, review commit b172261)
- **Merge evidence:** `gh pr view 110` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head abbdb13
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1); CI checks, security, image, host pass at abbdb13
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3e · **Milestone:** M3, M3e-1a (part 1 of 4)

## What changed
- `app/accounts/auth/blob.py`: blob = 12-byte nonce ‖ AES-256-GCM ciphertext ‖ 16-byte tag, nothing in clear. Login blob 220 bytes (was 222), credential blob 60 (was 62). The AAD stays version ‖ purpose ‖ value with each tried key's own version; the newest version seals; `open_*` tries every listed version every time, with no early stop.
- `accounts.0008` replaces the two length CHECKs (`app_user_login_blob_ct_length` 220, `user_factor_lookup_blob_ct_length` 60), in place, on columns that hold no row anywhere; it reverses.
- Tests (`test_auth_blob.py`): attempt count `[3, 2, 1]` for a newest-version blob, a random decoy, an oldest-version blob and a credential decoy; no fixed leading bytes; the version bound by the AAD; the newest key alone opens the new blob. Lengths follow in `test_auth_passwords.py` and `test_user_tables_live.py`.
- `docs/runbooks/host-rebuild.md`: without a header SQL can't show a row's version; before a `login_blob_key` version leaves the file, the re-seal job (spec T16, not built) must open every blob and report the version that opened it.
- DECISIONS "M3e-1a" (the four-PR split of M3e, the M3b correction). +135 −35 code/test, +21 docs. 4 mutants killed.

## Why
Spec v1.21 §4.1 "Pre-tenant lookups" (a decoy of identical length that teaches nothing), AUTH-05; plan M3 §3 M3e, §4 M3e row. The M3b header let SQL as `skiw_app` tell a real account (`00 01 …`) from the lookup decoy, an enumeration oracle; the owner chose to drop the header (builder chat, 2026-11-04).

## Review rounds
- R1: Approved (head abbdb13). The reviewer re-ran `make test-live` (469, schema check ok) and pytest unit (1561) on a disposable DB. One P3 finding, deferred to M3e-1b.

## Deferred conditions
- **R1 P3 #1 (open, deferred to M3e-1b, owner builder):** `docs/plans/2026-10-31-m3-auth.md` still gives the old layout and lengths — line 74 (layout), line 93 (login decoy 222), line 105 (credential decoy 62) — and §6 says every M3 migration only adds. Update the three lines to the new layout, 220 and 60 (pointing to DECISIONS "M3e-1a"); add to §6 that a CHECK on a column that holds no row may be replaced in place, citing 0008; in M3e-1b derive the decoy lengths from `LOGIN_BLOB_LENGTH` / `LOOKUP_BLOB_LENGTH`, not literals.

## Decisions worth keeping
- Login and credential blobs carry no key version in clear; the version is bound only in the AAD, and opening tries every listed version every time, so a real blob, a decoy and an oldest-version blob do the same work.
- Because SQL can't see a blob's version, retiring a `login_blob_key` version needs the re-seal job to open every blob and report the version that opened it.
- A CHECK on a column that holds no row may be replaced in place (0008; the plan §6 note comes with M3e-1b).

## Follow-ups
- M3e-1b (PR 111, stacked; base to be moved to main): R1 P3 #1 above; pin the decoy key version (owner point 4, done in 111 as the oldest version); the decoy-side tests (equal length, no fixed leading bytes, the same decoy on repeated calls).
- M3e-2: the residual timing difference (one Python `InvalidTag` exception between a real blob and a decoy) belongs to the timing-band test (reviewer note, no action now).
- Re-seal job (spec T16): open every blob, report the opening version; also the only safe way to retire the oldest `lookup_decoy_key` version.
- Earlier, still open: M3e login steps as public `PUBLIC_ROUTES` entries (reviewer sign-off), rotated CSRF cookie on the real login response, PR 107 pending-row note; M4-rest disable → `revoke_user()`; spec §4.1 / D6 gap (plan §9 item 2); `login()` is sync only; the clock rule assumes one host; PR 78, 77, 81 items; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3e-1a" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M3e, part 1a of 4)
- **Code review:**
  - **Base:** merge base d9c104df00183e33e31095ca4987a3ea30310238 (origin/main, PR 109 merged).
  - **Head:** abbdb131d7fa3c931189a9272fd65768f82dedcd, one commit. 9 files, +158 −39. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). §4.1 "Pre-tenant lookups", AUTH-05, UNI-15, §8.4 H4; plan
  `docs/plans/2026-10-31-m3-auth.md` §3 M3e and the §4 M3e row; the owner's decision (2026-11-04) to drop
  the header, with my six advisory points from the same chat.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 110` (builder), then merge. Then M3e-1b, which carries P3 #1 and the decoy-key
  follow-up.

### What was checked
- **The layout** is 12-byte nonce ‖ AES-256-GCM ciphertext ‖ 16-byte tag. With the fixed plaintexts
  (192 and 32 bytes), a login blob is 220 bytes and a credential blob 60. Nothing in a blob is in clear,
  so a real blob and an HMAC-expanded decoy look alike.
- **Every version, every time:**
  - `_open` loops over every listed version and keeps the first plaintext, with no early exit.
  - The length check comes first, but the length is the same for real blobs and decoys, so it reveals
    nothing.
  - The attempt-count test (`[3, 2, 1]` for a newest-version blob, a random decoy, an oldest-version blob
    and a credential decoy) is the right way to pin this. Patching `_attempt` is acceptable in a test.
- **Version binding:** the AAD is still version ‖ purpose ‖ value, using each tried key's own version.
  The test that seals under `v2` and opens the same key bytes under `v1` proves that the version is
  bound.
- **Sealing:** the newest version seals (the first entry from `require_key()`, as before). The test now
  opens the new blob with the newest key alone and the old blob with it fails, so the "oldest seals"
  mutant is killed.
- **Residual timing:** a real blob costs one successful decrypt and N−1 `InvalidTag` exceptions; a
  decoy costs N exceptions. The difference is one Python exception, microseconds against an Argon2
  verify or `dummy_verify`. M3e-2's timing-band test is where this belongs; I'm not asking for more.
- **Migration 0008:**
  - It replaces both CHECKs, keeping their names. The model constants follow `OVERHEAD`, so the model
    state and the migration agree.
  - If any environment did hold a 222-byte row, `AddConstraint` would fail and `migrate` would stop.
    That fails closed.
- **UNI-15:** I agree this isn't an exception to the hard rule.
  - The columns hold no row anywhere: nothing seals a blob before M3e-3.
  - The migration reverses (checked below).
  - A rollback to the M3d image runs on this schema, because no M3d code writes a blob.
  - It does depart from the plan's wording (§6: "every M3 migration only adds tables, functions and
    grants"). That is part of P3 #1.
- **My owner-chat points:** 1 (all versions), 2 (version in the AAD), 3 (rotation reporting, in
  `host-rebuild.md` and DECISIONS), 5 (no fixed leading bytes, blob side) and 6 (credential blobs too)
  are done. Point 4 (pin the decoy key version) and the decoy side of point 5 belong to M3e-1b; see
  Follow-ups.
- **No stale code:** no code in `app/` or `infra/` slices a header (`blob[:2]`) any more.

### Checks
- `make test-live` at abbdb13 on a disposable DB: 469 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- `make -o check-node test`: pytest gave 1561 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- **Migration round trip** (reviewer, as the migrator), reading `pg_get_constraintdef` at each step:
  - at 0008: `length(login_blob_ct) = 220` and `length(lookup_blob_ct) = 60`;
  - after `migrate accounts 0007`: 222 and 62;
  - after migrating forward again: 220 and 60.
- **Stale references:** `git grep` for the old lengths and header found three lines in the plan, and
  nothing in code (P3 #1).
- The worktree is clean.

### Findings

### [P3] #1 — The M3 plan still gives the old layout and lengths
- **Category:** docs accuracy (the plan is the build source for M3e-1b and M3g)
- **Evidence:** `docs/plans/2026-10-31-m3-auth.md`:
  - line 74: "Layout: 2-byte version ‖ 12-byte random nonce ‖ …";
  - line 93: `guard.auth_lookup_login` returns "a decoy of length L (222)";
  - line 105: `guard.auth_lookup_credential` has "decoy length 62";
  - §6 (line 147): "every M3 migration only adds tables, functions and grants", which 0008 departs
    from.
- **Failure scenario:** M3e-1b or M3g is built from the plan text, and its decoy is 222 or 62 bytes.
  That makes the decoy a different length from a real blob, which is the same enumeration oracle in
  another form. The M3e-1b length test would catch it, but only if the test uses `LOGIN_BLOB_LENGTH`
  rather than a literal from the plan.
- **Required correction:**
  - Update lines 74, 93 and 105 to the new layout and to 220 and 60, pointing to DECISIONS "M3e-1a".
  - Add to §6 that a CHECK on a column that holds no row may be replaced in place, citing 0008.
  - In M3e-1b, derive the decoy lengths from `LOGIN_BLOB_LENGTH` and `LOOKUP_BLOB_LENGTH`, not from
    literals.
- **Owner:** builder · **Disposition:** deferred to M3e-1b (the next PR, stacked on this one) ·
  **Status:** open (deferred)

### Notes (no action)
- **The 2-byte AAD field caps versions at `v65535`.** The runbook now says so, with the right reason.

### Follow-ups
- **M3e-1b:**
  - P3 #1 above;
  - **pin the decoy key version** (owner-chat point 4). A `lookup_decoy_key` rotation would change every
    unknown email's decoy while real blobs stay the same, so a before/after comparison separates them.
    Use one fixed decoy version, or record that a decoy-key rotation happens together with re-sealing
    every blob. Record the choice in DECISIONS.
  - the decoy-side tests: equal length and no fixed leading bytes, on the real function. The decoy
    must be the same on repeated calls (spec §4.1).
- **M3e-2:** the timing band (it covers the one-exception difference above).
- **M3e:** the carried items from PR 109 (public mutating routes with reviewer sign-off, the CSRF cookie
  on the login response, the PR 107 pending-row note, `public.citext`, the open items from PRs 77, 78
  and 81).
