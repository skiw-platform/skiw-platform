# Runbook — deploy

iCore VPS, spec §8.4 H3. Host side for staging and production (M1g); the CI trigger and the
published predeploy image follow in M1h, measured outage in M1k. Nothing deploys before then.

## How a deploy reaches the host
Each deploy key's `authorized_keys` line for user `skiw-deploy` fixes its own role:
```
restrict,command="/usr/local/sbin/skiw-deploy-ssh --key staging" ssh-ed25519 AAAA... staging-deploy
```
(`--key production` on the production host, with the owner's key, G6.) On **staging** a second
line lets production read the staging status (G11 (b)) and nothing else:
```
restrict,command="/usr/local/sbin/skiw-staging-status" ssh-ed25519 AAAA... production-status
```
Its private half is production's `/etc/skiw/secrets/staging_status_key` (root, 0400; owner-made,
host-rebuild.md). The caller can send only
`deploy <digest> [<run-id>]` or `rollback <digest>` (`sha256:` + 64 lowercase hex; run id digits);
anything else, including `id`, an empty command, extra words or shell characters, exits 2 and runs
nothing. The forced command then runs `sudo -n /usr/local/sbin/skiw-deploy --key <role> ...`, the one
command `/etc/sudoers.d/skiw-deploy` allows (its arguments pinned by a regular expression).

## Before you deploy
- `apply` has run (it installs `skiw-deploy`, `skiw-deploy-ssh`, the sudoers rule and
  `/srv/skiw/compose.yml` with `/srv/skiw/caddy/`); `check-hardening` passes.
- Host config in `/etc/skiw/host.env`: `SKIW_ENVIRONMENT` (`staging` or `production`, must equal the
  key role), `SKIW_IMAGE_REPOSITORY` (the one repository, `ghcr.io/<owner>/<name>`; the login user is
  `<owner>`), `SKIW_HOSTNAME` (G9), `SKIW_DEPLOY_HEALTH_TIMEOUT_S` (60),
  `SKIW_DEPLOY_DUMP_TIMEOUT_S` (1800: the bound on the whole pre-migration dump run).
- `/etc/skiw/secrets/ghcr_read_token` placed (host-rebuild.md), root, 0400.
- Production also: `SKIW_STAGING_SSH` (staging `host:port`), `SKIW_STAGING_HOST_KEY` (staging's
  `ssh-ed25519 AAAA...` host key: the first two fields of `/etc/ssh/ssh_host_ed25519_key.pub`
  there), `SKIW_DEPLOY_KEY_FINGERPRINT` (the owner's production deploy key, from
  `ssh-keygen -lf <key>.pub` on the owner's machine: the `SHA256:...` field, G6), and
  `staging_status_key` (host-rebuild.md). `/var/lib/skiw/accepted-digests` is made append-only
  (`chattr +a`, checked with `lsattr -d`) by the first production deploy; a file system without
  that attribute is refused.
- `SKIW_BACKUP_IMAGE` (the published predeploy image, by digest, M1h) and `SKIW_DUMP_RECIPIENTS`
  (the owner's public age recipient(s) for dumps, G5) are set; `apply` made
  `/srv/skiw/backups/predeploy` (uid 10003, 0700).
- First deploy only: `bootstrap-db prepare`, start `db` and `bootstrap-db apply` (host-rebuild.md,
  "Database roles"), giving the digest you are about to deploy as `SKIW_IMAGE`.

## What `skiw-deploy` does
1. Refuses (exit 2, nothing changed) a bad digest or run id, a key role other than the host's,
   a bad host value, any file that is a link, not root-owned or writable by
   group or others (env file, compose file, token, state file, the directories on the way), or a held
   lock (`/run/skiw-deploy.lock`, `flock`: one deploy at a time).
   **Production only:** refuses when the accepted-digest record holds a malformed or cut line or
   cannot be made append-only, without a run id, and unless `ssh skiw-deploy@<staging> status`
   (30 s bound, host key pinned from host config, `BatchMode`) exits 0 and prints exactly one line
   naming this digest with `head=match`, `checks=passed` and `running=yes`. Staging's output is
   never shown. Every tool call from here on is bounded (`docker pull` 900 s, the others 120 s,
   the dump below by its own value) except `migrate`: killing its client would leave the migration
   running in its container after the deploy lock was released.
2. Pulls `<repository>@<digest>`: `docker login` with the token on stdin into a temporary 0700
   config directory, removed after the pull; checks the image carries that digest; reads its labels
   and runs `migration_labels` in it (no database). Production refuses an image without the
   `org.opencontainers.image.revision` commit label.
3. `migrate --plan` in the new image. If anything is planned, the pre-migration dump runs
   (`backup` service, `predeploy`: `pg_dump -Fc` as `skiw_backup` without the guard key tables'
   data, the whole stream encrypted with `age` to `SKIW_DUMP_RECIPIENTS` and read by
   `pg_restore -f /dev/null` (header, table of contents, data blocks; not a test restore); the
   dump, its `.sha256` and the directory are synced to disk); it must print
   `predeploy <time>.dump.age <sha256>`, else the deploy stops (exit 1, nothing changed). pg_dump
   gives up on a table lock after 30 s (`--lock-wait-timeout`); the whole run is bounded by
   `SKIW_DEPLOY_DUMP_TIMEOUT_S`, and on that timeout its container (`skiw-predeploy`) is removed
   with `docker rm --force` (if that fails too, the log line says so: run
   `sudo docker rm --force skiw-predeploy` before the next deploy, which otherwise fails on the
   name).
4. The image's contract migrations join `/var/lib/skiw/applied-contracts` (synced), **before**
   `migrate`, because `migrate` may apply a contract migration and then fail on a later one. Then
   `migrate` as `skiw_migrator`. A failure stops the deploy; the old containers keep serving.
   Staging then removes its old status line, so a failed switch never leaves a stale
   `checks=passed`.
5. Writes `SKIW_IMAGE=<repository>@<digest>` to `/var/lib/skiw/deploy.env` (root, 0644; Compose and
   `check-hardening` read it) and runs `docker compose up -d` (at most 300 s). Compose recreates
   `web` and `worker` only when the image changed; other services are left as they are.
6. Waits for `https://<SKIW_HOSTNAME>/readyz` 200 through Caddy on this host within
   `SKIW_DEPLOY_HEALTH_TIMEOUT_S`, then, within two heartbeat intervals (2 × 10 s), for a worker row
   in `procrastinate_workers` with a fresh heartbeat: for a new digest one newer than the switch, for
   a repeat of the running digest the kept worker. Every probe is bounded by the time left (curl
   `--max-time`, a killed `docker compose exec`, and `statement_timeout`/`lock_timeout` in the
   database); an answer after the deadline counts as a failure.
7. **Recovery.** If step 5 or 6 fails in any way (including `up` exiting non-zero after changing
   some services), it restores the state file's previous content and runs `up -d` with the previous
   digest; on a first deploy it stops `web` and `worker` and removes the state file, so a failed
   image is never a later switch-back target. Each recovery command is bounded (300 s). It sends a
   journal alert (`journalctl -t skiw-deploy -p alert`; delivery off-host in M1j), `... failed its
   switch|health check|staging status line; switched back to <digest>` or `... RECOVERY FAILED ...`,
   and exits 1; the
   deploy lock is released. Migrations are never reversed (UNI-15 keeps the previous digest valid
   on the new schema).
8. After a healthy switch: **staging** writes `/var/lib/skiw/staging-status` (G12):
   `digest=… checked=… readyz=200 worker=registered head=match|differs|unlabelled checks=…`;
   `checks=passed` only when the image's `skiw.migration-head` label equals the head
   `migration_labels` prints (exit 0 either way; production refuses anything but `passed`).
   **Production** appends one line to `/var/lib/skiw/accepted-digests`: digest, commit, run id,
   staging check time, deploy time, `/readyz` result, migration head, contract list, key
   fingerprint. Every file written (state file, applied contracts, status line, record) is synced
   with its directory before the deploy reports success. If the append fails the deploy stays up,
   an alert is sent and the exit is 3; see "If it goes wrong".
9. One line to the journal (`journalctl -t skiw-deploy`) and `/var/log/skiw/deploy.log`: action,
   digest, key role, run id, result, previous digest. No tool output, no secret value.

Exit codes: 0 deployed; 1 failed (read the log line; the previous digest serves unless the alert
says RECOVERY FAILED; fix and deploy again); 2 refused, nothing changed; 3 deployed but the
accepted-digest or log line failed (record it by hand).

## Production
The owner, on the owner's machine, only for a digest staging reports as running with
`checks=passed` (the host checks again), with the green `main` CI run id (M1h adds
`scripts/deploy-prod`, which checks the run first):
```
ssh -i <owner production key> -p <SKIW_SSH_PORT> skiw-deploy@<production host> deploy <digest> <run-id>
```
Rollback: [rollback.md](rollback.md).

## Smoke tests
`/readyz` and the worker are checked by the deploy itself; on staging the status line records the
G12 checks. From production, with the values of `SKIW_STAGING_SSH` (`<host>:<port>`):
```
sudo ssh -F /dev/null -i /etc/skiw/secrets/staging_status_key -p <port> \
  -o IdentitiesOnly=yes skiw-deploy@<host> status
```
prints the one status line with `running=yes|no` (the first connection asks to confirm staging's
host key: compare it with `SKIW_STAGING_HOST_KEY`).

## If it goes wrong
- "RECOVERY FAILED": the state file already holds the previous content (or is removed on a first
  deploy). Run `sudo env SKIW_IMAGE=<previous> docker compose -f /srv/skiw/compose.yml --env-file
  /etc/skiw/host.env up -d` by hand (first deploy: `... stop web worker`), then find the cause in
  `journalctl -u docker` and the container logs. Re-running the same digest is safe: it succeeds
  once the running worker's heartbeat is fresh and `/readyz` answers.
- **Exit 3, "accepted-digest line failed".** The deploy is serving; only its record line is missing.
  The log line ends with `line: digest=…` (checked values only). On production:
  ```
  sudo tail -n 2 /var/lib/skiw/accepted-digests
  sudo lsattr -d /var/lib/skiw/accepted-digests
  ```
  If the last line is cut short (it does not end in `key=SHA256:…`), remove it, keeping the file
  append-only otherwise: `sudo chattr -a /var/lib/skiw/accepted-digests && sudo sed -i '$d'
  /var/lib/skiw/accepted-digests && sudo chattr +a /var/lib/skiw/accepted-digests`. Then append the
  logged line (replace `<line>`):
  `printf '%s\n' '<line>' | sudo tee -a /var/lib/skiw/accepted-digests >/dev/null`, and check that
  `lsattr -d` still shows `a`. Until then a rollback to this digest is refused.
- See [rollback.md](rollback.md).
