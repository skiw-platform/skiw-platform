# PR 40 — feat(infra): bootstrap-db and the closed DB role set (M1e-1)

- **Merged:** 2026-10-15T03:46:27Z (GitHub) · **Merge commit:** `a39df6d30655d6e12beaa03918f7d167aece65e8` · **Branch:** `feat/m1e-bootstrap-db` (final head `0cad66855e460cc77e3120b7282656f2b5a0796d`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-40.receipt` on `agent-logs` (written before the merge); names head `0cad668…`, review `reviews/PR-40.md`, CI green on that exact head (run 38676989354: checks, host, image, security).
- **Merge evidence:** `gh pr view 40` → MERGED, mergedAt 2026-10-15T03:46:27Z, merge commit `a39df6d`, final head equals the reviewed head of Round 2; `origin/main` log shows `a39df6d`, `0cad668`, `53c0a8c`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier) · **Final verdict:** Approved (Round 2; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1e-1 (roles half of plan M1e; the owner split the 700-line build)

## What changed
`infra/host/db/roles.sql`: one idempotent, password-free file for the closed role set, used by hosts, local dev and CI (`docker/postgres/10-roles.sh` runs it too). `infra/host/bootstrap-db prepare|apply`: `prepare` mints missing DB password files (0400, inventory owner, never replaced); `apply` checks all five password files, runs `roles.sql` in the db container as `postgres`, then sets each password as a SCRAM-SHA-256 verifier computed in Python and sent on stdin. Runbook database section, `local-dev.md`, DECISIONS entry (2026-10-15). 155 pytest, 75 host tests, 57 live DB tests, 11 live host tests.

## Review rounds
- R1 (Revision required): [P1] `PGPASSWORD` put the superuser password in the psql environment (H4) → a 0600 libpq password file made in the db container and removed on exit; a test runs the real wrapper and reads the child's environment. [P1] `roles.sql` kept forbidden memberships → it now refuses, atomically, any membership except `skiw_backup` in `pg_read_all_data`; three live drift tests. [P1] UNI-08 missing from the self-check → row added.
- R2: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- **M1e-2 (next):** per-role `pg_hba.conf`, `render_hba` and the hba part of `prepare`, the Compose db config, the `test_compose_config.py` hba check, the `test_edge_live.py` hba override, `conftest.py`, live pg_hba tests and docs. Rebuild from the backup files; the real socket-authentication proof (independent of `verifier()`) belongs there.
- **Owner action:** run `make clean` once; the local role set changed.
- Recorded limit: a failed `ALTER ROLE` can leave a password verifier (never plaintext) in PostgreSQL server logs; wrapper output is suppressed but server logs are not. Set and test a logging policy with the live host tests.
- Follow-ups: `bootstrap-db` journal and deploy-log line and the installed DB-file path (M1f); `skiw_readonly` read-only default with its first grants; PROJECT.md sections 8 and 9 role names and a `make clean` note.
- My first live-test run tried port 5433 (the CRM container) once; one login failed and nothing changed. Agents must replace every `5433` in the worktree `.env`, including the URLs.
