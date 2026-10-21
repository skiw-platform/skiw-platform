# PR 47 — feat(infra): skiw-deploy core: forced command, pull by digest, migrate, switch, health check and automatic rollback (M1g-1)

- **Merged:** 2026-10-21T14:22:02Z (GitHub) · **Merge commit:** `0f5715baed3c5db321dab264ba395251d1514676` · **Branch:** `feat/m1g1-deploy-core` (final head `c2fdaf1f3435032b5750148b719d526be3825226`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-47.receipt` on `agent-logs` (written before the merge); names head `c2fdaf1…`, review `reviews/PR-47.md`, CI green on that exact head (run 39606036358: checks, host, image, security).
- **Merge evidence:** `gh pr view 47` → MERGED, mergedAt 2026-10-21T14:22:02Z, merge commit `0f5715b`, final head equals the reviewed head of Round 3; `git merge-base --is-ancestor c2fdaf1 origin/main` succeeded; `main` log shows `0f5715b`, `c2fdaf1`, `04fd446`.
- **Drafted by:** Claude Sonnet 5.5 (builder; code by an Opus subagent, deep tier; gates, merge with main and PR text by the builder) · **Final verdict:** Approved with conditions (Round 3; reviewer Codex GPT-6)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1g-1 (first of two PRs of plan M1g)

## What changed
`skiw-deploy-ssh` (forced command: only `deploy <digest> [<run-id>]` or `rollback <digest>`, key role from the `authorized_keys` `--key` argument), one pinned sudoers rule, and `skiw-deploy` with `skiw_host/deploy.py` for staging: digest and repository checks, deploy lock, pull by digest with the GHCR token on stdin, `migrate --plan`, pre-migration dump hook, `migrate`, switch (`SKIW_IMAGE` in the state file, `compose up -d`), bounded `/readyz` and worker-heartbeat checks, automatic recovery to the previous image (a failed first deploy stops web and worker and removes the state), journal and deploy-log line. `apply` installs the programs, the sudoers rule, `/srv/skiw/compose.yml` and `/srv/skiw/caddy/`; `check-hardening` `role-set` defaults to the installed compose path. Runbooks `deploy.md`, `rollback.md`, `host-rebuild.md`; DECISIONS entry (2026-10-21). 1,041 lines added, 32 removed.

## Review rounds
- R1 (Revision required): [P1] a failing `compose up` bypassed recovery → switch and state inside the recovery boundary, exact previous bytes restored, recovery failure has its own alert. [P1] a failed first image stayed as the next rollback target → state removed. [P1] a same-digest retry failed falsely → fresh-heartbeat check for an unchanged digest, no force-recreate. [P1] the worker probe could hang or finish late → every probe bounded by the remaining deadline, late results rejected. [P1] self-check lacked TEN-01 → added. [P2] `bootstrap-db apply` lacked `SKIW_IMAGE` in the runbook → both commands get it.
- R2 (Revision required): [P1] the worker query was mapped to TEN-02 and TEN-10 was marked n/a → PR body only: TEN-10 row for the worker probe, TEN-02 row for the app role.
- R3: Approved with conditions; two P2s deferred (below).

## Deferred conditions
- Both P2s go to the image-path follow-up PR, before M1h starts: (1) record the worker probe as a TEN-10 ops database path in the closed mapping (`agents/PROJECT.md`, DECISIONS); (2) image repository and remote still name the old owner: `ghcr.io/skiw-platform/skiw-platform` in `infra/host/env/*.env` and tests, `agents/PROJECT.md` line 66, the DECISIONS repo entry, plan line 178.

## Decisions worth keeping
- **Size:** the owner chose to keep M1g-1 as one PR at 875 lines; review fixes took it to 1,041.
- **M1g-2 (next):** the pre-migration dump image (`infra/host/backup/predeploy/`), production deploys with the G11 staging check (default: forced-command key printing the last staging state line) and the accepted-digest record, `--rollback`, the contract-migration refusal and `migration_labels`, the key fingerprint in the log line, and the restore.md section. Until it lands, a deploy with a pending migration stops before `migrate`, and production deploys and `--rollback` are refused.
- **Not proven, needs a real host (M1k):** sudo regex on Ubuntu's sudo 1.9.15; real Compose keeping an unchanged worker; whether 300 s is enough for `up`; a stray `psql` after a killed `docker compose exec`; a killed process mid-switch has no in-process recovery (the next deploy starts from the state file).
- Lessons kept: a deploy step that can fail halfway needs the state change inside the recovery boundary; every wait in a health phase needs a timeout from the remaining deadline; a test fake must model what the real tool leaves unchanged (Compose keeps unchanged containers).
- Repo moved to the organization `skiw-platform/skiw-platform` on 2026-10-21 (free plan: no enforced branch protection on private repos).
