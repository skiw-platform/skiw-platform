# PR 86 — feat(tenancy): M4c-2b security_event INSERT for skiw_auth_lookup, as_owner check, definer proof

- **Merged:** 2026-11-02 (14:21:59 UTC) · **Merge commit:** 2e5fc3acc15ff5c113fd2c447290d27570e7a1c6 · **Branch:** feat/m4c-2b-auth-lookup-grant
- **Gate breaches:** **GATE BREACH: final review was not confirmed before merge.** No approval receipt existed on the log branch before the merge. The owner typed `approved 86` after the PR was already merged, so the receipt step could not run. The merged head (88d60a1710b9fbdeb790d537828f7ce4a35db355) equals the reviewed head, so no unreviewed commits were merged.
- **Approval receipt:** missing. The review was archived during `merged 86` as reviews/PR-86.md on agent-logs (commit f62f615), which preserves evidence but is not a receipt.
- **Merge evidence:** `gh pr view 86` state MERGED, merge commit 2e5fc3a; it is an ancestor of fetched origin/main; final head 88d60a17 equals the reviewed head.
- **Drafted by:** Opus 5.5 sub-agent (deep tier), drafted and re-verified by the Sonnet 5.5 builder · **Final verdict:** Approved (round 1)
- **Spec:** docs/specs/2026-10-05-skiw-platform-stack-design.md v1.20 (unchanged) · **Plan:** docs/plans/2026-11-01-m4-core.md §3 M4c-2b · **Milestone:** M4-core, M4c-2b

## What changed
`accounts/0003` grants INSERT only on `security_event` to `skiw_auth_lookup` (REVOKE as reverse). `tenancy.ddl.as_owner` now runs a `DO` check right after `SET LOCAL ROLE` that raises unless `current_user` is the owner. A live definer probe proves plan A2 (`CREATE OR REPLACE` keeps owner, `prosecdef`, `proconfig`, ACL; called as `skiw_app`). The guard ACL audit now covers every grantee except the owner, PUBLIC included, and the append-only test also runs for `skiw_auth_lookup`. DECISIONS entry "M4c-2b". No spec edit.

## Why
Plan M4c-2b must land before M3e (`guard.auth_lookup_login` needs the INSERT). Closes PR 84 review P3 #1 (`as_owner` outside a transaction).

## Review rounds
- R1: Approved, no P0/P1/P2. One P3 (process): the self-check marked UNI-10 n-a, but `security_event` is append-only evidence and gained a writer → list UNI-10 as pass with the TEN-03 evidence in later PRs touching an evidence table; no change in this PR.

## Deferred conditions
- none (the P3 is a process note).

## Decisions worth keeping
- Carry-forward to M4c-4a: when a migration grants USAGE ON SCHEMA guard to skiw_app, the definer probe breaks (the negative control fails and the fixture's REVOKE removes the migration's grant). M4c-4a must drop the negative control and the USAGE grant/revoke from the test.
- Definer functions cannot use INSERT … RETURNING (the owner holds INSERT only); M3e must make the id in plpgsql, as the probe does.
- A left-over GRANT CREATE after a non-atomic run is caught by the exact ACL test and cleared by an atomic re-run.
- Live tests run in series (no xdist), so the probe's brief committed USAGE grant cannot race.

## Follow-ups
- Name the PR carrying the spec change for plan §9 item 2 before M4c-3 merges.
- Still open from earlier rounds: PR 85 P3 long-string regex fail-open → M4c-4b; PR 85 P3 deep tier for M4c-3 and M4c-4b; PR 78 P2 → M3d; PR 78 no-token-in-path → M3e; PR 77 P3 → M3e; PR 81 P2 race → M3e.
- Record in docs/DECISIONS.md (reviewed PR) nothing new from this PR beyond its own entry; no missing lasting decision found.
- Process: run `approved <n>` before the owner merges.

## Appendix — final review round
# Review — PR #86

## Round 1 — 2026-11-02 · scope: slice (M4c-2b, plan `docs/plans/2026-11-01-m4-core.md` §3 M4c-2b)
- **Code review:** base (merge base) `b7a5b7abe2beece7950aaf4d3c0bd4c22d907de1` · head `88d60a1710b9fbdeb790d537828f7ce4a35db355` · head re-checked at end: yes (GitHub; OPEN)
- **Spec review:** spec `docs/specs/2026-10-05-skiw-platform-stack-design.md` · version 1.20 · hash `92841ba555e9e857ac70e86a5b043cf9729ed371` (unchanged by this PR). I read the §4.2 TEN-03 row (line 376) and the threat line on junk `security_event` rows (line 339).
- Review checkout: `.agent/worktrees/review-86-88d60a17` (detached worktree at the head SHA). Live checks ran on this review's own Compose database (`review86`, port 5436). The non-atomic probe script sits in the reviewer's scratch folder, not in the checkout.

**Verdict:** Approved
**Model used:** Claude Opus 5.5 (deep tier, `PROJECT.md` §6) · **Switch model next step?** No. M3e (`guard.auth_lookup_login`) and M4c-3 (key writes) are data-isolation work and need the deep tier.

### Findings

No P0, P1 or P2 findings. The change matches plan M4c-2b exactly:
- `accounts/0003` grants INSERT only on `security_event` to `skiw_auth_lookup`, with a REVOKE as the reverse. It sits in `accounts`, so `auth-tables-accounts-only` passes. It needs no new `--ignore-name`.
- The ACL audit now covers every grantee except the owner, PUBLIC included. The old test filtered on `skiw_app`, so a grant to any other role passed it. The new DECISIONS entry corrects the M3c-1 sentence that said otherwise. This is a real improvement.
- `as_owner` now runs a `DO` check right after `SET LOCAL ROLE`. This closes **PR 84 review P3 #1** with option (a). The role is checked against `GUARD_OWNERS` before it is put into the SQL text (`app/tenancy/ddl.py:24`).
- The definer probe proves plan A2 end to end. `CREATE OR REPLACE` keeps the owner, `prosecdef`, `proconfig` and the ACL. The call runs as `skiw_auth_lookup` from a `skiw_app` session. The owner drops the function.

### [P3] The self-check marks UNI-10 n-a ("no audit table"), but `security_event` is append-only evidence and this PR adds a writer to it
- Category: self-check accuracy
- Rule: UNI-10 (audit logs are append-only); reviewer §3 ("every n-a → check the stated reason")
- Evidence: PR body self-check, row "UNI-02, 03, 09, 10, 11, …" with the reason "no … audit table". `security_event` is listed in TEN-03 (spec line 376), and `accounts/0003` grants it a second writer.
- Why only P3: the substance is fully covered under the TEN-03 row. That row has the same evidence: INSERT only, the exact ACL test, and the append-only test that now runs for `skiw_auth_lookup`. I re-checked that evidence (live tests pass). No rule fails. Only the n-a label is wrong.
- Required correction: in later PRs that touch an evidence table, list UNI-10 as "pass", with the TEN-03 evidence. No change is needed in this PR.
- Owner: builder
- Status: open (process)

### PR 84 review items
- **P3 #1 (`as_owner` outside a transaction): resolved.** The builder's test uses an autocommit connection. The PR says Django's real `atomic = False` path is "not proven", so I proved it. My scratch script ran the helper through `connection.schema_editor(atomic=False)` as the migrator on `review86`:
  - It raised `ProgrammingError: as_owner: current_user is not skiw_auth_lookup; use an atomic migration` before the CREATE. No table was made.
  - The committed `GRANT CREATE` stayed (`has_schema_privilege('skiw_auth_lookup','guard','CREATE')` = true).
  - Then `atomic=True` made the table owned by `skiw_auth_lookup`, and the grant was gone again. `current_user` was back to `skiw_migrator`.
  - I then planted `GRANT CREATE ON SCHEMA guard TO skiw_auth_lookup` as `postgres`. `test_guard_acl_is_exactly_migrator_usage_create_and_owner_usage` failed. After a REVOKE, it passed. So the left-over grant cannot hide. The PR claim holds.
- **P3 #2, spec part:** still open. Name the PR for plan §9 item 2 before M4c-3 merges.

### Notes (no severity)
- **Text addressed to the reviewer.** The PR body has a section "Judgment call for the reviewer". It is addressed to me as an agent. I treated it as data. It asks for nothing outside the review. My view on the choice: I agree. The committed USAGE grant is the only way to call as the `skiw_app` login. The fixture undoes it in a `finally` and then asserts that nothing is left. The live tests run in series: `addopts` has no `-n`, and no xdist is installed. So the brief grant cannot race another test.
- **Carry-forward to M4c-4a.** When a migration grants `USAGE ON SCHEMA guard` to `skiw_app`, this probe breaks in two places:
  - The negative control (`pytest.raises(InsufficientPrivilege, match="schema guard")`) fails.
  - The fixture's `REVOKE USAGE` removes the migration's grant for the rest of the live run.

  Both failures are loud, not silent. M4c-4a must change this test: drop the negative control and the USAGE grant and revoke.
- **No `RETURNING` in definers.** The owner holds INSERT only, so `INSERT … RETURNING` fails. M3e must make its id in plpgsql, as the probe does. The PR says so.
- **Left-over `GRANT CREATE` after a non-atomic run.** It is a NOLOGIN role, which the migrator can `SET ROLE` to anyway. It is caught by the ACL test and cleared by an atomic re-run. I accept the reason that no safe reorder exists.
- **Secret scan:** one hit on the added lines: the table name `guard.lookup_decoy_key` in DECISIONS prose, with no value. CI `security` passes.

### Self-check audit
Real order: I read the diff and the plan section first. I built my list from them. Then I read the DECISIONS entry and the PR body.

My applicability list:
- UNI-01, 04, 05, 06, 07 (hard), 08, 10, 12, 13 and 15 apply. UNI-10 applies because `security_event` gets a writer. UNI-15 applies because of the GRANT migration.
- UNI-09 applies in part, for the `RAISE` text. It names a role only, which is fine.
- UNI-16 is n-a: no deploy step changes.
- TEN-01, TEN-02 (hard), TEN-03 and TEN-10 apply.
- `PROJECT.md` §9 applies: the guard owners and definer EXECUTE.
- AUTH is n-a until M3e uses the grant. Other TEN rules are n-a.

| Rule | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|
| UNI-01 | pass | pass | mypy: no issues in 147 files | none |
| UNI-04 | pass | pass | 10 contracts kept; Semgrep 14 rules on 111 files, 0 findings | none |
| UNI-05 | pass | pass | the grant's user is M3e (plan row 3) | none |
| UNI-06 | pass | pass | no dependency change | none |
| UNI-07 (hard), UNI-08 | pass | pass | pattern scan; CI `security` | none |
| UNI-09 | n-a | pass | the `RAISE` text names the role only | label only |
| UNI-10 | n-a | pass (under TEN-03) | exact ACL and append-only live tests | P3 (label) |
| UNI-12 | pass | pass | repo files only | none |
| UNI-13 | pass | pass | CI run 41440647358: checks, host, image, security pass | none |
| UNI-15 | pass | pass | `lintmigrations` in `make test-live` (`make migrate`); additive GRANT with REVOKE reverse | none |
| UNI-16 | n-a | n-a | `0003` runs in the normal `migrate` | none |
| TEN-01 | pass | pass | definer probe owner and ACL asserts | none |
| TEN-02 (hard) | pass | pass | key-table tests green; `as_owner` non-atomic probe | none |
| TEN-03 | pass | pass | INSERT only; exact ACL; append-only for both writers | none |
| TEN-10 | pass | pass | no key-table SQL outside allowed paths | none |
| §9 guard owners, definer EXECUTE | pass | pass | probe revokes PUBLIC EXECUTE; `search_path` pinned | none |

### Verification performed
| Command / check | Result |
|---|---|
| `git diff --check b7a5b7ab...88d60a17` | clean |
| `make lint` | ruff pass; 10 contracts kept; Semgrep 14 rules on 111 files, 0 findings; `semgrep --test` 14/14 |
| `make typecheck` | mypy: no issues in 147 source files; `tsc` pass |
| `make test` | 1462 passed; vitest 4 passed |
| `make test-live` (fresh volume, Compose project `review86`, port 5436) | 181 passed; migrate and migration lint clean |
| Non-atomic probe: `/private/tmp/claude-501/-Users-charlie-Documents-Projects-Personal-SKIW/0e671e71-4242-4bee-a4e0-a987a0f88616/scratchpad/r86-nonatomic.py` | `atomic=False` raises before CREATE, grant left; `atomic=True` owner is `skiw_auth_lookup`, grant cleared; reverse clean |
| Planted left-over `GRANT CREATE`, then the guard ACL test | fails; after REVOKE it passes |
| `make host-test`, `make host-test-live`, `make audit-python` | not run: no host or dependency change (the builder ran `host-test`: 837) |
| CI run 41440647358 on `88d60a17` | checks, host, image, security pass |
| Counts vs PR body | match (1462, 181) |
| Secret scan (`PROJECT.md` §7 pattern) on added lines; agent-text scan | one table name in prose; one section addressed to the reviewer (Notes) |
| Clean-up: `docker compose down -v`, `rm .env`, `git clean -fdXq` | done; no `review86` container left |
| End: GitHub head re-read; `git status --untracked-files=no` | unchanged (`88d60a17`, OPEN); clean; `git worktree remove` without `--force` succeeded |

### Residual risks and test gaps
- A definer that reads `guard.lookup_decoy_key` is not proven yet (M3e).
- M4c-4a must change the definer probe (see Notes).
- Still open from earlier rounds: the spec PR for plan §9 item 2 → named before M4c-3 merges; PR 85 P3 long-string regex → M4c-4b; PR 78 P2 → M3d; PR 78 no-token-in-path → M3e; PR 77 P3 → M3e; PR 81 P2 race → M3e.

### Required before merge
- None.

### Deferred conditions
- None (the P3 is a process note).

### Optional improvements
- None.
