# PR 105 — feat(accounts): M3d-1b user_factor and the session_revocation marker

- **Merged:** 2026-11-04 (06:34:12 UTC) · **Merge commit:** 41aad09395b112735d131d42e08221dbb1493f82 · **Branch:** feat/m3d-1b-factor-revocation-2
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-105.receipt on agent-logs (log-branch commit c8b15e1, receipt time 2026-11-04T06:33:17Z, before merge; reviewed head 84d7fd2754a679890e09a1223edfe86b797bb1f5, review-file hash e3e17a5987ff8aff300d3ce90166835aa13467c7, review commit 28160e0)
- **Merge evidence:** `gh pr view 105` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 84d7fd2
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Plan:** docs/plans/2026-10-31-m3-auth.md §3 M3d · **Milestone:** M3, M3d-1b (part 2 of 3)

## What changed
- `app/accounts/factor_model.py` (new): `UserFactor` (`user_factor`), a `TenantModel`: `kind` `passkey`/`totp`/`recovery`, `credential_id` unique across agencies, `sign_count ≥ 0` (default 0), `lookup_blob_ct` null or exactly 62 bytes; composite FK `(agency_id, user_id)` → `app_user`.
- `app/accounts/revocation_model.py` (new): `SessionRevocation` (`session_revocation`, carry-over (b)): `session_key_hash` lower-case SHA-256 hex, or null to revoke the whole user; `revoked_at` defaults to the database's statement time; composite FK to `app_user`.
- `accounts.0006_factor_and_revocation` (generated) and `accounts.0007_factor_and_revocation_rls` (`tenant_table`: skiw_app gets all four commands on `user_factor` and SELECT/INSERT on `session_revocation`). `test_queue_grants.py` allow-lists the `user_factor` DELETE and lists `session_revocation` as TEN-03 evidence.
- `isolation_cases.py` gains the two TEN-08 cases; `test_user_tables_live.py` gains the column-rule tests for both tables (each refusal pinned to its constraint) and PR 103 R1 P3 #2: the global `UNIQUE (email)` and `UNIQUE (credential_id)` are pinned by catalog shape.
- DECISIONS "M3d-1b"; `local-dev.md`. 10 files, +406 −7.

## Why
Spec §4.1 `user_factor`, carry-over (b) `session_revocation`, TEN-04–08; plan M3 §3 M3d. This is the second of the three M3d PRs (split by the plan §1 size rule). It replaces PR 104, which was closed unmerged: commit 392c138 on 104's branch held a 64-hex test constant that CI's full-history gitleaks scan flagged (PR 104 R1 P1). The owner chose a fresh branch from `main` over a force-push, and this PR rebuilds the same work with the constant derived.

## Review rounds
- PR 104 R1 (Changes requested, head 6eb587b): [P1] CI's full-history secret scan fails on a test constant → `KEY_HASH` derived with `hashlib.sha256(…).hexdigest()` on a new branch from `main` (PR 105). The old remote branch `feat/m3d-1b-factor-revocation` still held 392c138, and CI scans every branch, so security still failed. The owner then approved deleting that remote branch as a one-off exception to the never-delete-remote-branches rule (2026-11-04). The commits survive at `refs/pull/104/head`.
- PR 104 R1: [P3] #1 comments named the wrong migrations → model and test comments name `accounts.0007`.
- PR 104 R1 also closed PR 103 R1 P3 #2 (global uniques pinned).
- PR 105 R1: Approved (head 84d7fd2). Delta against 6eb587b: 5 files, +8 −5, so 104 R1's checks carry over. The reviewer ran `make test-live` (417 passed) and a fresh full-clone gitleaks v8.30.1 scan (483 commits, no leaks, 392c138 absent). No findings.

## Deferred conditions
- none

## Decisions worth keeping
- A gitleaks finding on **any** remote branch fails every PR's security job: CI checks out with `fetch-depth: 0` and `gitleaks git` scans all refs. A local check must scan a full `git clone --no-local` of the remote, not a single-branch clone or the worktree.
- High-entropy test values (hashes, keys) are derived in code, never written as literals.
- Remote branches are still never deleted; `feat/m3d-1b-factor-revocation` was a one-off owner exception, recorded in DECISIONS "M3d-1b".
- `revoked_at` defaults to Django's `Now()`, which compiles to `STATEMENT_TIMESTAMP()` on Postgres, not the transaction time.

## Follow-ups
- Cleanup: the local branch `feat/m3d-1b-factor-revocation` (6eb587b) still holds 392c138, so a local `make secrets` flags it until it is deleted. Delete it, `feat/m3d-1-user-tables` (3c50b0f) and the build worktree (reviewer note in PR 105 R1).
- PR 104's closing comment still says the branch "is kept"; the owner has not yet said whether to post a correction.
- M3d-2: PR 103 R1 P3 #1 (loggers outside `django.*` print exception messages); pin `revoked_at` as statement time and name the clock rule for `revoked_at ≥ _skiw_auth_at` (web clock vs DB clock, and which wins on a tie); `login()`, `authorized_action`, idle timeout, the revocation check; the spec §4.1 / D6 gap for `session_revocation` (plan §9 item 2).
- Reviewer note for M3e (from PR 103): `guard.auth_lookup_login` must name `public.citext`.
- Open from earlier: PR 88 optional P3; PR 78, 77, 81 items → M3e; M2c deferred P2; Dependabot alert security/dependabot/1; M5 waffle m2m tables; M4c-8 floats.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M3d-1b" entry.

## Appendix — final review round
## Round 1 — 2026-11-04 · scope: slice (M3d, part 1b of 3; replaces PR 104)
- **Code review:**
  - **Base:** merge base a7be80debf9a6cb5cf8ba387203e47d04f4c9b60 (origin/main, PR 103 merged).
  - **Head:** 84d7fd2754a679890e09a1223edfe86b797bb1f5, four commits: `867220f`, `cd75c35`, `cdf68a4` and
    `84d7fd2`. 10 files, +406 −7. Re-checked at the end: unchanged.
  - **Where:** detached review worktree `.agent/worktrees/review-91`, on a disposable DB (port 5441),
    removed afterwards (`docker compose down -v`).
- **Spec:** v1.21, hash d95cb271 (unchanged). The scope is the same as PR 104 R1
  (`.agent/reviews/PR-104.md`). The substance was reviewed there; this round checks the delta and the
  secret-scan fix.
- **CI:** checks, security, image, host: pass. publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No.
- **Next:** `approved 105` (builder), then merge. Then M3d-2, which carries the follow-ups below.

### Delta against the reviewed PR 104 head
- `git diff 6eb587b 84d7fd2`: 5 files, +8 −5.
  - `KEY_HASH` is derived with `hashlib.sha256(…).hexdigest()`.
  - The three comments now say `accounts.0007`.
  - DECISIONS gains one line.
- No other code changed. So PR 104 R1's checks of the models, migrations, harness cases and grant audit
  carry over.

### PR 104 R1 P1 (secret scan): resolved
- **The old branch is gone from the remote.** `git ls-remote origin 'refs/heads/feat/m3d-1b*'` lists
  only `feat/m3d-1b-factor-revocation-2`.
- **The commits are still on GitHub.** `refs/pull/104/head` still points at 6eb587b.
- **The head doesn't contain the old commit.** `392c138` is not an ancestor of `84d7fd2`.
- **A fresh full clone is clean** (reviewer). I cloned the remote with every branch, as CI's
  `fetch-depth: 0` does, then ran the pinned `ghcr.io/gitleaks/gitleaks:v8.30.1` with `git`, the repo
  config and `--redact`.
  - Result: 483 commits scanned, no leaks.
  - `392c138` isn't in the clone at all.
  - The clone was deleted afterwards.
- **CI's security job passes** at 84d7fd2.
- **DECISIONS "M3d-1b" records the exception:** the owner's one-off branch deletion, why it was needed,
  where the commits still live, the `git fetch --prune` caveat, and why the local scan missed it.
- **Status:** closed.

### PR 104 R1 P3 #1 (migration names in comments): resolved
`factor_model.py`, `revocation_model.py` and both `test_queue_grants.py` comments name `accounts.0007`.
**Status:** closed.

### Checks
- `make test-live` at 84d7fd2 on a disposable DB: 417 passed, and migrate printed `tenancy schema check:
  ok`. Both match the PR body.
- The fresh-clone gitleaks scan above.
- The worktree is clean.

### Findings
None.

### Notes (no action in this PR)
- **A local branch in the main clone still holds the old commit.** It is
  `refs/heads/feat/m3d-1b-factor-revocation`. CI doesn't see it, but a local `make secrets` run in that
  clone will flag it. Deleting a local branch is outside the owner's remote-branch rule. The builder
  should run `git branch -D` on it, or `git fetch --prune` for the remote-tracking ref, if they want
  local scans to be clean.

### Follow-ups
M3d-2:
- **PR 103 R1 P3 #1:** loggers outside `django.*` still print exception messages.
- **PR 104 R1 note:** pin `revoked_at` as statement time, if the check relies on it. Name the clock rule
  for `revoked_at ≥ _skiw_auth_at` (web clock against DB clock, and which wins on a tie).
- **Plan scope:** `login()`, `authorized_action`, idle timeout and the revocation check.
- **Spec §4.1 / D6 gap** for `session_revocation` (plan §9 item 2): still owed.
