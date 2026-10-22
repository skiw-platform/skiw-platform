# Runbook — restore from backup

The pre-migration dump restore is in place (M1g; iCore VPS, spec §8.4 H3); full backups and the restore drill arrive in M6.

## What is backed up
## Restore the database
## Restore the pre-migration dump
Every deploy with a pending migration first writes `/srv/skiw/backups/predeploy/<UTC
time>.dump.age` and `<name>.sha256` (`pg_dump -Fc` as `skiw_backup`, data of
`guard.tenant_mac_key`, `guard.approval_mac_key` and `guard.lookup_decoy_key` left out, encrypted to
the owner's dump recipient, G5). The private dump key never reaches a host.
1. Stop writers: `sudo env SKIW_IMAGE=<running> docker compose -f /srv/skiw/compose.yml --env-file
   /etc/skiw/host.env stop web worker`.
2. Copy the dump and its `.sha256` to the owner's machine; check with `sha256sum -c`; decrypt
   there: `age -d -i <dump identity> <name>.dump.age > predeploy.dump`. Read the table of contents
   (`pg_restore --list predeploy.dump`) before going on.
3. Bring the plaintext dump back over SSH into a root-only directory, and restore it as
   `skiw_migrator`, the owner of the schema: `pg_restore --clean --if-exists --no-owner
   --role=skiw_migrator -d <db> predeploy.dump` inside the `db` container (`docker compose exec -T`,
   the dump on stdin). The guard key tables come back empty: the app keys that fill them are
   restored by `bootstrap-secrets` (host-rebuild.md), not by this dump.
4. Delete the plaintext dump on both machines (`shred -u`).
5. Deploy the digest that matches the restored schema (`deploy <digest>`); `migrate` brings it to
   that digest's head.
6. Record the restore (date, dump name, digest) in the incident notes.

## Restore object storage
## Drill log
