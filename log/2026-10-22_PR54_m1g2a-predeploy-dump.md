# PR 54 — feat(infra): M1g-2a pre-migration dump image and migration labels

- **Merged:** 2026-10-22T10:21:04Z (GitHub) · **Merge commit:** `fb1e38286f6938b4f64a842e70166651bd35ba2c` · **Branch:** `feat/m1g-2a-predeploy-dump` (final head `085d518d8711f55400108a56bb5bed9444d79f21`)
- **Gate breaches:** none
- **Approval receipt:** `reviews/PR-54.receipt` on `agent-logs` (written before the merge); names head `085d518…`, review `reviews/PR-54.md`, CI green on that exact head (run 39760030759: checks, host, image, security).
- **Merge evidence:** `gh pr view 54` → MERGED, merge commit `fb1e382`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 085d518 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder; the builder re-ran every gate · **Final verdict:** Approved with conditions (Round 2)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1g-2a (Part A of the owner-chosen M1g-2 split)

## What changed
Pre-migration dump image `infra/host/backup/predeploy/` (pinned postgres 17.11 and python digests, age by checksum): `pg_dump -Fc` as `skiw_backup` without guard key data; the whole stream goes to `age -r` and to the validator `pg_restore -f /dev/null`, whose exit code decides; 1 MiB incremental hash; fsync of file, checksum and directory before the success line. Compose `backup` runs `${SKIW_BACKUP_IMAGE:?}`; env keys `SKIW_BACKUP_IMAGE`, `SKIW_DUMP_RECIPIENTS`; `apply` makes `/srv/skiw/backups/predeploy`. `migration_labels` prints head and contract list with no DB; the guard recurses into `SeparateDatabaseAndState` and fails closed on unknown operations. `restore.md` "Restore the pre-migration dump" (stdin, temporary libpq file, `--single-transaction`).

## Review rounds
- R1 (Revision required): 5 P1 (validator not a whole-stream consumer, whole-file hash, no durability barrier, nested contract operations missed, self-check rows) and 1 P2 (restore command not executable) → all fixed; real 100,000-row dump and restore proven.
- R2: Approved with conditions.

## Deferred conditions
- P2 `AlterModelTable` in `CONTRACT_OPERATIONS` (plus plan sentence and test) → M1g-2b.
- P3 (non-blocking): `pg_dump --lock-wait-timeout`.

## Decisions worth keeping
- The validator is `pg_restore -f /dev/null`, not `--list` (which reads only the table of contents). The plan wording follows; the spec line 910 still says `--list` (owner's call).
- `infra/host/backup` is outside import-linter; an AST test keeps it standard-library only.
- M1h must publish the dump image, set `SKIW_BACKUP_IMAGE`, and add labels `org.opencontainers.image.revision` and `skiw.migration-head`.
- `restore.md` must be re-proven once M4 adds objects owned by other roles (restore drill, M6).
