# PR 93 — feat(tenancy): M4c-4b-2 with_agency(), start-up key checks, forged-tenant tests

- **Merged:** 2026-11-03 (10:18:26 UTC) · **Merge commit:** 54d7387004975b922e65b882896a76ddcd4780fe · **Branch:** feat/m4c-4b-2-with-agency
- **Gate breaches:** none
- **Approval receipt:** reviews/PR-93.receipt on agent-logs (log-branch commit 1d7842d, receipt time 2026-11-03T10:16:51Z, before merge; reviewed head 1ea7fb6015f382069aaa79a48e744fcd3aaf93ce, review-file hash 4fa69cbdebb89e0489612053fb21feb94e297b90, review commit 709e381)
- **Merge evidence:** `gh pr view 93` state MERGED; merge commit is an ancestor of fetched origin/main; merged head equals reviewed head 1ea7fb60
- **Drafted by:** Opus 5.5 builder (deep tier) · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.21, hash d95cb271 (= PROJECT.md §2) · **Milestone:** M4-core, M4c-4b (second half; first half PR 92)

## What changed
- `app/tenancy/binding.py` (new):
  - `with_agency(agency_id)` refuses a non-UUID and an open atomic block (so nesting too);
  - it mints under the newest `tenant_token_key` version for this xid and database;
  - it sets the token with `set_config(…, true)` on the driver cursor, so Django's debug cursor never logs it;
  - `token_keys()` reads the key once per process (`functools.cache`).
- Start-up: `config/asgi.py` and `runworker` call `token_keys()` before the migration check.
- Compose:
  - host `x-app-env` gains `TENANT_TOKEN_KEY_FILE`;
  - local `app` and `worker` take `TENANT_TOKEN_KEY`.
- Semgrep (PR 92 R1 P3, commit 1ea7fb6):
  - new rule `tenancy-token-key-reader`, with pinned excludes;
  - the import rule also catches `importlib.import_module(".token", …)`.
- Tests:
  - `test_binding_live.py`: 22 function-level forged-tenant tests, with a control token;
  - start-up refusals;
  - env and compose wiring;
  - a `tenancy/tests/conftest.py` holding `vector_keys`.
- Runbooks `host-rebuild.md` and `local-dev.md`; the plan's Semgrep table; the DECISIONS "M4c-4b-2" entry.

## Why
Spec v1.21 §4.2 "Tenant binding" items 1, 2 and 4; TEN-09; plan M4c-4b; PR 91 review follow-up (mint under the newest key); PR 92 review R1 P3.

## Review rounds
- R1: Approved (head 1ea7fb6). One P3, open, disposition the next tenancy PR (M4c-5).

## Deferred conditions
- M4c-5, from R1 P3: the key-reader rule has side doors.
  - `token_keys()` is public and returns every key; fix it by making the start-up hook return nothing (`require_token_key() -> None` over a private `_token_keys()` that `with_agency()` uses).
  - `env.versioned_keys("TENANT_TOKEN_KEY")`, `os.environ["TENANT_TOKEN_KEY"]` and the secret-file path are not flagged; fix it by adding the strings `"TENANT_TOKEN_KEY"` and `"TENANT_TOKEN_KEY_FILE"` to the rule, allowed in `config/settings.py`, with fixture lines.

## Decisions worth keeping
- The start-up code calls the cached `token_keys()`, not `SKIW_TENANT_TOKEN_KEYS()` (a deviation from the plan), so the start-up check is the same read that minting uses.
- The token is set through the driver cursor, not a `connection.execute_wrapper`, because the debug wrapper still logs inside one.
- `with_agency()` is refused inside an open atomic block, because the outer block may already hold another agency's token on the same xid.

## Follow-ups
- M4c-5 (`agency` root) is next. It needs the owner's Q2 answer (recorded in the plan) and carries the R1 P3 above.
- Open from earlier: PR 88 optional P3 (`owner_role` reset only when INTRANS); PR 78 P2 → M3d; PR 78, 77, 81 items → M3e; M2c deferred P2 → first M3 PR; M2c owner Q1=A, Q2=A to record in DECISIONS; Dependabot alert security/dependabot/1.
- Decisions check: the lasting decisions are in the merged `docs/DECISIONS.md` "M4c-4b-2" entry.

## Appendix — final review round
## Round 1 — 2026-11-03 · scope: slice (M4c-4b-2; second half of M4c-4b, plus the PR 92 R1 P3 fix)
- **Code review:** base origin/main 6720b37 (PR 92 merged; the merge base is PR 92's head d89453b, so the diff
  against main is only this PR's two commits `ed01d63` and `1ea7fb6`) · head
  1ea7fb6015f382069aaa79a48e744fcd3aaf93ce · 19 files · head re-checked at end: yes (unchanged). Review
  worktree `.agent/worktrees/review-91`, detached at the head; disposable DB (port 5441) removed after;
  temporary probe files deleted, worktree clean.
- **Spec:** v1.21, hash d95cb271 (= PROJECT.md §2). Plan M4c-4b.
- **CI:** checks, security, image, host: pass; publish, deploy-staging: skipped.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier) · **Switch model next step?** No. Next is `approved 93`, then
M4c-5 (`agency` root). The P3 below can ride along with any later tenancy PR.

### What was checked
- **`with_agency()`** (`app/tenancy/binding.py`) against spec §4.2 item 2 and plan M4c-4b:
  - refuses a non-`uuid.UUID` (TEN-11 primitive) and `connection.in_atomic_block` (so nesting too).
    `ATOMIC_REQUESTS` is not set, so this doesn't refuse every view;
  - `transaction.atomic()` → `pg_current_xact_id()` and `current_database()` → `mint` → `set_config(…, true)`
    → yield. Errors roll back through `atomic`; inner `atomic()` is a savepoint and keeps the xid (tested);
  - mints under `token_keys()[0]`, and `parse_key_lines` sorts newest first (`env.py:113`), so this is the
    newest version. That is what the PR 91 runbook rule (separate deploys) depends on. A mutant test covers it;
  - `set_config` goes through `cursor.cursor`, so Django's debug wrapper doesn't log the token (tested with
    `force_debug_cursor`). With client-side binding the token text does reach the server, but PostgreSQL
    statement logging is at its defaults (none found in `infra/`), `set_config` cannot raise, and the token
    is bound to its own xid anyway.
- **Forged-tenant tests** (`test_binding_live.py`): there is a control (a correct token under an active key
  does switch), so each forged NULL is caused by the one thing it gets wrong. Covered: random, B-shaped,
  truncated, extra field, zero MAC, unknown and retired versions, replay from another transaction,
  `app.agency_id`, `COMMIT; BEGIN`, no token after the block or after an error. Row-level cases are M4c-7b
  and async is M4c-8, as the plan's done-when table says.
- **Start-up:** `config.asgi` and `runworker` call `token_keys()` before the migration check. Tests cover a
  missing, short, seven-digit-version or unversioned key, and check that the key isn't echoed. Compose:
  `web`, `worker` and `migrate` read `TENANT_TOKEN_KEY_FILE` and mount the secret; no service has the value
  in its environment (host test). Locally, `app` and `worker` get `TENANT_TOKEN_KEY`.
- **PR 92 R1 P3:** the new `tenancy-token-key-reader` rule, its pinned excludes and the plan row are in
  place; the import rule now has the relative `importlib` form.
- **Runbooks:** `host-rebuild.md` (newest-version minting, start-up refusal) and `local-dev.md` are correct.
- **Local runs:** `make test-live` 248 passed; the start-up, worker-key and Semgrep-path tests 47 passed;
  `semgrep --test` 17/17.

### Findings

### [P3] The key-reader rule still has easy side doors
- **Evidence:** a probe under `app/` (Semgrep 1.179.0) shows the rule catches `s.SKIW_TENANT_TOKEN_KEYS()` and
  `getattr(s, "SKIW_" + "TENANT_TOKEN_KEYS")`, but not:
  - `from tenancy.binding import token_keys; token_keys()`: the public cached reader returns every
    `(version, key)`, and any module may import `tenancy.binding` (asgi and runworker do). The rule message
    says "call token_keys() only for the start-up check", but nothing enforces it;
  - `env.versioned_keys("TENANT_TOKEN_KEY")`, `os.environ["TENANT_TOKEN_KEY"]` and the secret-file path.
- **Impact:** hygiene only, as in PR 92: the MAC is the boundary against injected SQL, and app code holds
  the key in-process. But the PR's TEN-10 self-check and the rule message claim more than the rule does.
- **Correction:** make the start-up hook return nothing (for example `require_token_key() -> None`, calling a
  private `_token_keys()` that `with_agency()` uses). Add the strings `"TENANT_TOKEN_KEY"` and
  `"TENANT_TOKEN_KEY_FILE"` to the rule, with `config/settings.py` as the allowed path, plus fixture lines.
- **Owner:** builder · **Disposition:** next tenancy PR (M4c-5), or here if the builder prefers · **Status:** open
