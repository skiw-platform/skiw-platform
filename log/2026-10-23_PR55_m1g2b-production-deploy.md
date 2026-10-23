# PR 55 — feat(infra): M1g-2b production deploy, staging check, accepted-digest record and rollback

- **Merged:** 2026-10-23T06:13:25Z (GitHub) · **Merge commit:** `c5647a4c04ee4e19dda59cc02fbdc0528ae5ad56` · **Branch:** `feat/m1g-2b-production-deploy` (final head `79825b9b41fb161c72ad98ff9a7cef31b98b0254`)
- **Gate breaches:** none (owner-approved size: one PR, about 1,300 lines)
- **Approval receipt:** `reviews/PR-55.receipt` on `agent-logs` (written before the merge); names head `79825b9…`, review `reviews/PR-55.md`, CI green on that exact head (run 39813472521: checks, host, image, security).
- **Merge evidence:** `gh pr view 55` → MERGED, merge commit `c5647a4`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 79825b9 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder; pre-review and round 1 fixes by the builder · **Final verdict:** Approved (Round 2)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1g-2b (M1g complete in code; host proof M1k)

## What changed
Production deploys with the G11 (b) staging check (forced-command `staging_status_key`, pinned staging host key under `HostKeyAlias=skiw-staging`); staging status line (G12) written after a healthy switch and removed before each switch; append-only accepted-digest record (`chattr +a`, checked with `lsattr`), one line per healthy production deploy; applied-contracts written and synced before `migrate`; `rollback <digest>` (production key, digest in the record, commit label match, no staging check, no `migrate`); every deploy and rollback refused across an applied contract migration. Every tool call bounded (dump by `SKIW_DEPLOY_DUMP_TIMEOUT_S` with `docker rm --force skiw-predeploy`); `migrate` unbounded by design. Root-written files use `O_NOFOLLOW`, owner/mode/link checks and fsync of file and directory. Production log line carries the owner key fingerprint (H3 step 11). PR 54 conditions: `AlterModelTable` contract flag, `pg_dump --lock-wait-timeout`.

## Review rounds
- Pre-review: first push failed gitleaks (fake key literal in a test) → test uses a format template, commit amended before review. Automated security scan → deploy of an older digest across a contract refused; status key body lines searched one by one.
- R1 (Revision required): P1 self-check rows for PROJECT §9/§11; P2 key fingerprint in the log line; P2 staging SSH allowlist runbook step; three P3 (two guard tests, exit-3 duplicate, doc drift) → all fixed.
- R2: Approved.

## Deferred conditions
- none.

## Decisions worth keeping
- The green-`main` CI-run check for a production deploy is not on the host: `scripts/deploy-prod` in M1h.
- Production stays refused until M1h adds the image labels `org.opencontainers.image.revision` and `skiw.migration-head`, publishes the dump image and sets `SKIW_BACKUP_IMAGE`.
- Staging must allow production's address in `SKIW_SSH_ALLOW` (allowlist), or risk a fail2ban ban.
- Open for M1k: a migration squash that deletes an applied contract's file needs a hand repair of `/var/lib/skiw/applied-contracts` (no runbook step yet); real ext4, host-to-host SSH, power-loss durability unproven.
