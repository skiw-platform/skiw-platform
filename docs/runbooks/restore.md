# Runbook — restore from backup

The pre-migration dump restore is in place (M1g; Hostinger VPS, spec §8.4 H3); full backups and the restore drill arrive in M6.

## What is backed up
## Restore the database
## Restore the pre-migration dump
Every deploy with a pending migration first writes `/srv/skiw/backups/predeploy/<UTC
time>.dump.age` and `<name>.sha256` (`pg_dump -Fc` as `skiw_backup`, data of
`guard.tenant_mac_key`, `guard.approval_mac_key` and `guard.lookup_decoy_key` left out, encrypted to
the owner's dump recipient, G5). When it was written, `pg_restore` read its header, table of
contents and data blocks without error; it was not test-restored, so check it here. The private
dump key never reaches a host. The owner's machine needs `age` and the PostgreSQL 17 client tools.

1. Stop writers: `sudo env SKIW_IMAGE="$(sudo sed -n 's/^SKIW_IMAGE=//p' /var/lib/skiw/deploy.env)"
   docker compose -f /srv/skiw/compose.yml --env-file /etc/skiw/host.env stop web worker`
   (`SKIW_IMAGE` is the running image; `/etc/skiw/host.env` holds `SKIW_BACKUP_IMAGE`,
   `SKIW_POSTGRES_DB` and the other values Compose needs).
2. On the owner's machine, with `<name>.dump.age` and `<name>.sha256` copied from the host: each
   command must succeed before the next.
   ```sh
   sha256sum -c <name>.sha256                     # must print "<name>: OK"
   age -d -i <dump identity> -o predeploy.dump <name>.dump.age
   pg_restore -f /dev/null predeploy.dump         # exit 0: header, contents and data read
   pg_restore -f - -a -t django_migrations predeploy.dump |
     sed -n '/^COPY /,/^\\\.$/p' | sed '1d;$d' | wc -l  # note this count: the migrations restored
   scp predeploy.dump <host>:
   ```
3. On the host, move the dump into a root-only directory:
   `sudo install -d -m 0700 /root/skiw-restore && sudo install -m 0600 ~/predeploy.dump
   /root/skiw-restore/ && shred -u ~/predeploy.dump`.
4. Restore it as `skiw_migrator`, the owner of the schema. `pg_restore` runs in the `db` container
   as the superuser over the socket (pg_hba.conf allows `postgres` only there) and switches to
   `skiw_migrator` with `--role`; the dump arrives on stdin (no file name); the password goes from
   the container's secret file into a 0600 libpq password file in its `/tmp`, removed on exit, never
   in argv or the environment. One transaction: on any error nothing changes.
   ```sh
   sudo -v
   running="$(sudo sed -n 's/^SKIW_IMAGE=//p' /var/lib/skiw/deploy.env)"; test -n "$running"
   compose() { sudo env SKIW_IMAGE="$running" docker compose -f /srv/skiw/compose.yml \
     --env-file /etc/skiw/host.env "$@"; }
   restore='set -eu; umask 077; f=$(mktemp); trap "rm -f \"\$f\"" EXIT
   printf "*:*:*:postgres:%s\n" "$(sed -e "s/[\\\\:]/\\\\&/g" /run/secrets/postgres_password)" > "$f"
   PGPASSFILE="$f" pg_restore --clean --if-exists --no-owner --role=skiw_migrator \
     --single-transaction --exit-on-error -U postgres -d "$POSTGRES_DB"'
   sudo cat /root/skiw-restore/predeploy.dump | compose exec -T db sh -c "$restore" \
     && echo "restore: ok" || echo "restore: FAILED, database unchanged"
   ```
   Go on only after `restore: ok`. Then the count must equal the one from step 2:
   ```sh
   count='set -eu; umask 077; f=$(mktemp); trap "rm -f \"\$f\"" EXIT
   printf "*:*:*:postgres:%s\n" "$(sed -e "s/[\\\\:]/\\\\&/g" /run/secrets/postgres_password)" > "$f"
   PGPASSFILE="$f" psql -X -At -U postgres -d "$POSTGRES_DB" -c "SELECT count(*) FROM django_migrations"'
   compose exec -T db sh -c "$count"
   ```
   The guard key tables come back empty: the app keys that fill them are restored by
   `bootstrap-secrets` (host-rebuild.md), not by this dump.
5. Delete the plaintext dump on both machines: `sudo shred -u /root/skiw-restore/predeploy.dump`
   on the host, `shred -u predeploy.dump` on the owner's machine.
6. Deploy the digest that matches the restored schema (`deploy <digest>`); `migrate` brings it to
   that digest's head.
7. Record the restore (date, dump name, digest) in the incident notes.

## Restore object storage
## Drill log
