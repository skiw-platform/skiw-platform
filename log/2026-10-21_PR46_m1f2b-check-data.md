# PR 46 — feat(infra): check-hardening checks secret store, container environment, database roles and pg_hba (M1f-2b)

- **Merged:** 2026-10-21T03:58:59Z (GitHub) · **Merge commit:** `c2681b1170dc370478f35443f6d2d34cfa7a9946` · **Branch:** `feat/m1f2b-check-data` (final head `602b596435a6fabeeaf7249f78f37d0f86f060c6`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-46.receipt` on `agent-logs` (written before the merge); names head `602b596…`, review `reviews/PR-46.md`, CI green on that exact head (run 39404997396: checks, host, image, security).
- **Merge evidence:** `gh pr view 46` → MERGED, mergedAt 2026-10-21T03:58:59Z, merge commit `c2681b1`, final head equals the reviewed head of Round 3; `git merge-base --is-ancestor 602b596 origin/main` succeeded; `main` log shows `c2681b1`, `602b596`, `b525552`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier; gates re-run and PR text by the builder) · **Final verdict:** Approved (Round 3; reviewer Codex GPT-6). The review file holds two Round 3 blocks for the same head, both Approved.
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1f-2b (second half of plan M1f-2; M1f is complete)

## What changed
Four read-only checks added to `check-hardening`: `secret-store` (directory and each file: root-owned, no links, 0700/0400, exactly the inventory plus `.restored`), `container-env` (secret values of 16 characters or more searched in every running container's environment; names only in output), `role-set` (every role, setting and membership with options compared with `roles.sql` and the pinned PostgreSQL 17.11 baseline, through `docker compose exec db` and `psql_script`; needs `--compose-file`), `pg-hba` (installed file equals the file rendered from the env text). Fixture `roles-pg17.txt` is real query output from Postgres 17.11. Runbook table, DECISIONS entry (2026-10-20). 634 lines added, 15 removed.

## Review rounds
- R1 (Revision required): [P1] the role query filtered on `skiw_%`, so an extra superuser with another name passed → full inventory, closed allowed set. [P1] unexpected role settings were printed verbatim → diagnostics from controlled fields only; unexpected roles counted, never named. [P1] secrets under 16 characters were skipped → fail closed and compared as whole values; empty file fails. [P1] self-check excluded TEN-02 and TEN-10 → rows added. [P2] malformed `docker inspect` evidence passed as empty → ids matched, types validated.
- R2 (Revision required): [P1] grants between predefined roles were ignored and option columns not read, so a widened or crippled backup role passed → explicit baseline plus `roles.sql` grants, `admin`, `inherit` and `set` options compared, no blanket exception.
- R3: Approved.

## Deferred conditions
- none introduced.

## Decisions worth keeping
- **M1g (next):** `skiw-deploy`; it fixes the compose file path that `role-set --compose-file` needs. M1h GHCR publish and staging deploy, M1i file-store harness, M1j health timer and alerts (runs `check-hardening` monthly), M1k vendor/site gate and real-host proof.
- **Owner values still open:** G7 (SSH port; allow-list or fail2ban), G15 (reboot values), G4 (Ubuntu 24.04 assumed). `apply` refuses on staging and production until G7 and G15 are filled in. Open question: should `apply` remove fail2ban fully under an allow-list.
- **Not proven, needs a real host (M1k):** `docker compose exec` against the real compose file, `docker inspect` JSON from Docker 29.9.1, real secret-file owners; other Postgres majors; `WITH` and `NOINHERIT` grant parsing runs only against the current `roles.sql`.
- Lessons kept: never echo database or tool output in a diagnostic, not even "unexpected" rows; a role or grant list needs the whole inventory, not a name prefix; a membership is its options as well as its pair; a floor on what is searched must fail closed for what is below it.
- Open owner side question (not in M1): host on the VPS or on the client's Mac Studio (spec D3).
