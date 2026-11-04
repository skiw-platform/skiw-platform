# PR 111 — feat(accounts): M3e-1b guard.auth_lookup_login and its decoy (pinned oldest decoy key, column grant, Semgrep rule)

- **Merged:** 2026-11-04 (13:34:12 UTC) · **Merge commit:** 895a5f040273e8d112c9cf2e23d444c135584977 · **Branch:** feat/m3e-1b-auth-lookup-login
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-111.receipt on agent-logs (log-branch commit 7e385f3, receipt time 2026-11-04T13:33:31Z, before merge; reviewed head 6fbd793ce2c9b9094ad986df3788d6dd3d8e5539, review-file hash 8c75210afd7b21a4be4c025ca65d2699a31d1e1e, review commit 9a32a56)
- **Merge evidence:** `gh pr view 111` state MERGED, base main; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 6fbd793. The reviewer's merge condition (base retargeted from `feat/m3e-1a-blob-without-header` to `main`) was met before the receipt (`gh pr edit 111 --base main`, at the owner's request).
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1); CI checks, security, image, host pass at 6fbd793
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3e · **Milestone:** M3, M3e-1b (part 2 of 4)

## What changed
- `accounts.0009`: `guard.auth_lookup_login(address public.citext) RETURNS bytea`, plpgsql `SECURITY DEFINER`, `VOLATILE STRICT`, owner `skiw_auth_lookup` (BYPASSRLS, NOLOGIN) through `as_owner`, `search_path = pg_catalog, pg_temp`, citext equality named `OPERATOR(public.=)`; EXECUTE revoked from PUBLIC, granted to `skiw_app`. Returns the row's `login_blob_ct`, or a 220-byte decoy (HMAC-SHA-256 counter mode, blocks 1–7 over `lower(address)`, under the oldest `guard.lookup_decoy_key` version) for an unknown email or a user with no password. No decoy key → RAISE before the lookup. One identical `security_event` (`login.lookup`, no HMACs, `{}`) per call. Column grant `SELECT (email, login_blob_ct) ON app_user TO skiw_auth_lookup`.
- `accounts/auth/lookup.py`: `lookup_login(email)`, the only caller (passes `normalise_email`, raises on NULL). Semgrep `auth-lookup-accounts-auth-only` refuses SQL calling the lookup outside it, the accounts migrations and tests.
- Tests: `test_auth_lookup_login_live.py` (10: hardening, length, column privileges, case handling, stable decoy vs a Python reference, no-password user, no fixed leading bytes, identical events, decoy-key rotation, missing key); the grant audit pins the two column grants.
- `docs/runbooks/host-rebuild.md`: remove the oldest `lookup_decoy_key` line only together with re-sealing every login blob. DECISIONS "M3e-1b". +377 −4 code/test, +24 docs. 11 mutants killed.

## Why
Spec v1.21 §4.1 "Pre-tenant lookups", Flow 5.1 (0), (1), AUTH-05, TEN-03, TEN-10, TEN-12; plan M3 §3 M3e, §4 M3e row, Risk 2; owner decision 2026-11-04 (pin the decoy key version); PR 103 R1 note (`public.citext`).

## Review rounds
- R1: Approved (head 6fbd793), merge condition: retarget the base to `main`. The reviewer checked `proacl` with `\df+`, probed the function as `skiw_app` (unknown email → 220 bytes, same in another case) and probed `callproc` against the Semgrep rule (not flagged → P3 #2). Two P3 findings, both deferred to M3e-2.

## Deferred conditions
- **R1 P3 #1 (open, deferred to M3e-2, must land before M3g; carried from PR 110 R1):** `docs/plans/2026-10-31-m3-auth.md` lines 74, 93, 105 still give the 2-byte-version layout and the 222 / 62 decoy lengths; §6 (line 147) says every M3 migration only adds. Update to the header-free layout, 220 and 60, citing DECISIONS "M3e-1a"; add the in-place CHECK replacement on a column with no rows (0008) to §6.
- **R1 P3 #2 (open, deferred to M3e-2):** Semgrep `auth-lookup-accounts-auth-only` misses `cursor.callproc("guard.auth_lookup_login", …)`. Also match a string literal that is exactly the name (`(?i)^(guard\.)?auth_lookup_(login|credential)$`) or `$C.callproc(...)` outside the allowed paths; add a `# ruleid:` callproc case to the fixture.

## Decisions worth keeping
- `guard.auth_lookup_login` is the only pre-tenant login lookup: a definer function that reads two columns, does the same work for known and unknown emails, and returns a decoy of the real blob's length for unknown emails and users with no password.
- The decoy uses the oldest `lookup_decoy_key` version; that version is removed only together with re-sealing every login blob. Known limit: a leaked decoy key enables enumeration until a re-seal job exists.
- Every lookup writes one identical `login.lookup` event, with no detail that says whether the email was found.
- Migrations keep the decoy length as a literal (not the model constant); a test pins it to `LOGIN_BLOB_LENGTH` (reviewer note). M3g does the same with `LOOKUP_BLOB_LENGTH`.

## Follow-ups
- M3e-2: R1 P3 #1 and #2; the login step runs outside `with_agency()`, so the lookup's event commits with the request; the timing band (including the one-exception residual from PR 110); the rotated CSRF token in the login response; the first public mutating route (reviewer sign-off in `PUBLIC_ROUTES`); the PR 107 pending-row note.
- M3g: `guard.auth_lookup_credential` with the same hardening and a 60-byte decoy pinned to `LOOKUP_BLOB_LENGTH`.
- Re-seal job (spec T16): reports the opening version per blob; the only safe way to retire a `login_blob_key` version or the oldest `lookup_decoy_key` version.
- Earlier, still open: M4-rest disable → `revoke_user()`; spec §4.1 / D6 gap (plan §9 item 2); `login()` is sync only; the clock rule assumes one host; PR 78, 77, 81 items; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3e-1b" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M3e, part 1b of 4)
- **Code review:**
  - **Base:** the PR's base is still `feat/m3e-1a-blob-without-header`. PR 110 is merged into main as
    9387ee2, so the merge base with origin/main is abbdb131d7fa3c931189a9272fd65768f82dedcd (the PR 110
    head), and `git log origin/main..HEAD` shows only this PR's commit.
  - **Head:** 6fbd793ce2c9b9094ad986df3788d6dd3d8e5539, one commit. 8 files, +401 −4. Re-checked at the
    end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). §4.1 "Pre-tenant lookups", Flow 5.1 (0), AUTH-05, TEN-03,
  TEN-10, TEN-12, UNI-15; plan `docs/plans/2026-10-31-m3-auth.md` §3 M3e, the §4 M3e row, Risk 2; the
  owner's decision (2026-11-04) to pin the decoy key version.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Merge condition:** retarget the PR's base to `main` before merging. With the base still on the 1a
  branch, a merge would land on that branch, not on main.
- **Then:** `approved 111` (builder), then merge. Then M3e-2, which carries both P3s.

### PR 110 follow-ups
- **The decoy key version is pinned to the oldest** (owner point 4): done. The rotation test shows that
  adding a version changes no decoy and removing the oldest changes them all. `host-rebuild.md` keeps the
  oldest line until a re-seal job exists. `lookup_decoy_key` has no `retired_at`, and `migrate` deletes
  versions that aren't in the file, so "oldest" is always a version in the key file.
- **Decoy-side tests on the real function:** done. They check the length against `LOGIN_BLOB_LENGTH`, no
  fixed leading bytes, the same decoy on repeated calls and case variants, a match with a Python
  reference, and that a decoy never opens.
- **Decoy length from the model constant:** done in effect. The SQL has the literal 220, but a test pins
  it to `LOGIN_BLOB_LENGTH`, and the 222-byte mutant is killed.
- **PR 110 R1 P3 #1 (stale plan text):** **not done.** `docs/plans/2026-10-31-m3-auth.md` lines 74, 93,
  105 and §6 are unchanged, and the PR body doesn't mention them. It is carried as P3 #1 below.

### What was checked
- **Hardening:**
  - `SECURITY DEFINER`, owner `skiw_auth_lookup`, `SET search_path = pg_catalog, pg_temp`.
  - Every function and table is schema-qualified, including `guard.hmac` (pgcrypto lives in `guard`)
    and the citext equality `OPERATOR(public.=)`. The rest (`||`, `::bytea`) resolves in `pg_catalog`,
    which comes first.
  - `proacl` (reviewer `\df+`) is exactly the owner and `skiw_app` with EXECUTE.
- **Same work on both paths:**
  - The key read, the 7 HMAC blocks, the unique-index lookup and the event insert all run on every
    call.
  - A missing key raises before the lookup, so it is the same error for both.
  - Only the final `RETURN` differs.
- **Case handling:**
  - The caller passes `normalise_email()` (NFKC, strip, lower), which is what the AAD binds.
  - A direct SQL call works through citext's `=`, and the decoy's `lower()` follows the same rule.
  - The builder's two mutants on this (text `=`, no `lower()`) are killed by the direct-call cases.
  - Reviewer probe as `skiw_app`: an unknown email gives 220 bytes, and the same bytes in another case.
- **A user with no password gets the decoy.** The caller can't tell "invited" from "unknown". When the
  user enrols, the answer for that email changes from decoy to real blob; that is inherent, and
  enrolment is the M3e-3 event that reveals it anyway.
- **Events:** one identical `login.lookup` row per call, with `{}`. A `NULL` argument (STRICT) returns
  `NULL` with no event. The caller can't send one (it takes `str`) and raises on a `NULL` result.
- **Privileges:**
  - The owner has a column grant on `email` and `login_blob_ct` only, and the grant audit now pins that
    exact set.
  - The owner has INSERT only on `security_event` (TEN-03).
  - The migration reverses with `DROP` and `REVOKE`.
- **The Semgrep rule:** see P3 #2. A string concatenation and an f-string with a constant variable are
  caught, because Semgrep folds constants.
- **Known limit, disclosed:** a leaked `lookup_decoy_key` allows enumeration until a re-seal job exists.
  That is correct, and it is in DECISIONS.

### Checks
- `make test-live` at 6fbd793 on a disposable DB: 479 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- `make -o check-node test`: pytest gave 1561 passed, which matches. pnpm isn't installed here; this PR
  has no web change, and CI runs the web tests.
- **SQL probe** as `skiw_app` (reviewer): length 220; case variants give equal decoys; `NULL` gives
  `NULL`; 3 events for 3 non-`NULL` calls; `\df+` shows the ACL above.
- **Semgrep probe** (reviewer): a temporary `app/zz_review_probe.py` with four call forms, run with the
  pinned Semgrep 1.179.0 and this rule, then deleted:
  - `execute("SELECT …")`: flagged (control);
  - a `+` concatenation: flagged;
  - an f-string with a constant variable: flagged;
  - `callproc("guard.auth_lookup_login", …)`: **not flagged** (P3 #2).
- The worktree is clean.

### Findings

### [P3] #1 — The M3 plan still gives the old blob layout and decoy lengths (carried from PR 110 R1)
- **Category:** docs accuracy
- **Evidence:** `docs/plans/2026-10-31-m3-auth.md`:
  - line 74 gives the 2-byte-version layout;
  - line 93 gives "decoy of length L (222)";
  - line 105 gives "decoy length 62";
  - §6 (line 147) says "every M3 migration only adds tables, functions and grants".
  - PR 110 R1 deferred this to M3e-1b, but this PR doesn't change the plan.
- **Failure scenario:** M3g builds `guard.auth_lookup_credential` from line 105 with a 62-byte decoy.
  The credential decoy then has a different length from a real 60-byte blob, which tells known passkey
  credential IDs from unknown ones.
- **Required correction:** as in PR 110 R1. Update the three lines to the header-free layout and to 220
  and 60, citing DECISIONS "M3e-1a". Add to §6 the in-place CHECK replacement on a column with no rows
  (0008).
- **Owner:** builder · **Disposition:** deferred to M3e-2 (the next PR). It must land before M3g at the
  latest. · **Status:** open (deferred)

### [P3] #2 — The Semgrep rule misses `cursor.callproc`
- **Category:** guard rule gap (TEN-10)
- **Evidence:**
  - The SQL-text branch needs `select`, `from`, `perform` or `call` before the name.
  - `callproc("guard.auth_lookup_login", [email])` passes only the name, so it isn't flagged (probe
    above).
  - Django's cursor wrapper has `callproc`, and `skiw_app` has EXECUTE, so the rule is the only thing
    stopping another module from calling the lookup.
- **Failure scenario:** a later module calls the lookup through `callproc`, bypassing
  `accounts.auth.lookup` and its normalising. With a non-normalised email it gets a decoy for a real
  account, which is a login bug. It also widens the TEN-10 boundary, and lint stays green.
- **Required correction:** also match a string literal that is exactly the function name, schema
  qualified or not (`(?i)^(guard\.)?auth_lookup_(login|credential)$`), or any `$C.callproc(...)` outside
  the allowed paths. Add a `callproc` case (`# ruleid:`) to the fixture.
- **Owner:** builder · **Disposition:** deferred to M3e-2 (the next PR) · **Status:** open (deferred)

### Notes (no action)
- **The `DECOY_LENGTH` literal** in 0009 is fine: a migration must not import the model constant, which
  could change later, and the test pins the two together. M3g's credential function should do the same
  with `LOOKUP_BLOB_LENGTH`.

### Follow-ups
- **M3e-2:**
  - P3 #1 and P3 #2;
  - the login step, run outside `with_agency()`, so the lookup's event commits with the request;
  - the timing band;
  - the rotated CSRF token in the login response;
  - the first public mutating route, which needs reviewer sign-off in `PUBLIC_ROUTES`.
- **M3g:** `guard.auth_lookup_credential`, with the same hardening and a 60-byte decoy pinned to
  `LOOKUP_BLOB_LENGTH`.
