# Runbook — deploy

iCore VPS, spec §8.4 H3. Host side for staging and production (M1g); CI publish, the staging deploy
job and the owner's `scripts/deploy-prod` (M1h); real hosts and the measured outage in M1k. Nothing
deploys before then: the staging deploy job is off until the owner turns it on (below).

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
- Production also: `SKIW_STAGING_SSH` (staging's DNS name and SSH port as `<name>:<port>`; a DNS
  name, not an IP address), `SKIW_STAGING_HOST_KEY` (staging's
  `ssh-ed25519 AAAA...` host key: the first two fields of `/etc/ssh/ssh_host_ed25519_key.pub`
  there), `SKIW_DEPLOY_KEY_FINGERPRINT` (the owner's production deploy key, from
  `ssh-keygen -lf <key>.pub` on the owner's machine: the `SHA256:...` field, G6), and
  `staging_status_key` (host-rebuild.md). Staging must accept SSH from production: under
  `allowlist`, staging's `SKIW_SSH_ALLOW` must hold production's outbound address (see
  host-rebuild.md "Making `staging_status_key`"); otherwise every production deploy is refused with
  "the staging status call timed out". `/var/lib/skiw/accepted-digests` is made append-only
  (`chattr +a`, checked with `lsattr -d`) by the first production deploy; a file system without
  that attribute is refused.
- `SKIW_BACKUP_IMAGE` (the published predeploy image, by digest: "Publish the pre-migration dump
  image" below; Compose refuses every command while it is empty) and `SKIW_DUMP_RECIPIENTS`
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
4. A deploy of an image that does not ship every migration in `/var/lib/skiw/applied-contracts`
   is refused (exit 2) before the dump, as a rollback would be: an older digest cannot be deployed
   across a contract migration. The image's contract migrations join `/var/lib/skiw/applied-contracts` (synced), **before**
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

## CI: publish and the staging deploy
Workflow `.github/workflows/ci.yml` ([ci.md](ci.md)). On a push to `main`, after `checks`,
`security`, `image` and `host` pass, job **`publish`** (the only job with `packages: write`):
1. builds the app image once and runs `python app/manage.py migration_labels` inside it (no
   network, no database). `skiw_host.labels` checks that answer exactly as skiw-deploy does and
   gives the labels `org.opencontainers.image.revision=<commit>`,
   `skiw.migration-head=<head, comma-joined>` and
   `skiw.contract-migrations=<contracts, comma-joined, empty if none>`, which are added to the image
   config (same layers, with `org.opencontainers.image.source`);
2. runs Trivy (HIGH/CRITICAL, as the `image` job) on that exact image; the push step first checks
   that the image ID is the one scanned;
3. pushes `ghcr.io/skiw-platform/skiw-platform:<commit>` with the job's own token, reads the pushed
   digest (exactly one `sha256:` repo digest of that repository), writes it to the job summary and
   uploads the artifact **`image-digest`**: one file, `digest.txt`, holding exactly the digest
   (kept 30 days). When the owner has turned it on (below), the same job also builds, scans and
   pushes the pre-migration dump image `ghcr.io/skiw-platform/skiw-predeploy:<commit>` and uploads
   **`predeploy-digest`** the same way. A Trivy finding in either image fails the job, and nothing
   reaches staging.

Job **`deploy-staging`** (`contents: read` only) is skipped unless the repository variable
`SKIW_STAGING_DEPLOY` is `enabled`. It writes the secret `STAGING_DEPLOY_KEY` to a 0600 file in a
temporary directory (removed after) and runs `ssh skiw-deploy@<staging> deploy <digest> <run id>`
with `BatchMode`, `StrictHostKeyChecking=yes` and a known_hosts file that holds only
`SKIW_STAGING_HOST_KEY` from `infra/host/env/staging.env` (the address is `SKIW_STAGING_SSH` there),
bounded at 3600 s. Staging deploys run one at a time. A running publish or deploy is never
cancelled; a waiting run is replaced by a newer push, so that commit gets no image (the wrapper
refuses a run that did not succeed). The host's exit code is the job's result; its one-line result
is in the job log. If the job is cut (timeout or cancel) while the host deploy runs on, the host
still writes its journal and deploy-log line: `journalctl -t skiw-deploy` on staging.

### Turn on the staging deploy (owner, M1k)
Needs the staging host built (host-rebuild.md) with its `ghcr_read_token`, `SKIW_BACKUP_IMAGE` set
(next section) and `check-hardening` passing.
1. **SSH from GitHub's runners.** GitHub-hosted runners connect from changing addresses, so staging
   cannot use `SKIW_SSH_POLICY=allowlist` (G7) and still take CI deploys: set staging to `fail2ban`
   (key-only from anywhere, the nftables rate limit and the fail2ban jail) and re-run `apply` there.
   Under `allowlist` the job fails with a connection timeout.
2. **The staging deploy key** (T25). On the owner's machine, in an empty directory:
   ```
   ssh-keygen -q -t ed25519 -N '' -C staging-deploy -f ./staging-deploy
   gh secret set STAGING_DEPLOY_KEY --repo skiw-platform/skiw-platform < ./staging-deploy
   cat ./staging-deploy.pub
   rm ./staging-deploy ./staging-deploy.pub
   ```
   It has no passphrase because CI uses it unattended; it opens only the staging forced command.
   On **staging**, add the copied line with the forced command in front (replace `<public line>`
   with the whole `ssh-ed25519 AAAA... staging-deploy` line):
   ```
   sudo install -d -m 0700 -o skiw-deploy -g skiw-deploy /home/skiw-deploy/.ssh
   printf '%s\n' 'restrict,command="/usr/local/sbin/skiw-deploy-ssh --key staging" <public line>' \
     | sudo tee -a /home/skiw-deploy/.ssh/authorized_keys >/dev/null
   sudo chown skiw-deploy:skiw-deploy /home/skiw-deploy/.ssh/authorized_keys
   sudo chmod 0600 /home/skiw-deploy/.ssh/authorized_keys
   ```
3. **Staging's address and host key**, in a PR: in `infra/host/env/staging.env` set
   `SKIW_STAGING_SSH=<staging DNS name>:<staging SKIW_SSH_PORT>` and `SKIW_STAGING_HOST_KEY=<the
   first two fields of staging's /etc/ssh/ssh_host_ed25519_key.pub>` (`awk '{print $1, $2}'` on the
   staging console, never `ssh-keyscan`). `production.env` holds the same two values; a test fails
   if they differ.
4. **Turn it on:** `gh variable set SKIW_STAGING_DEPLOY --body enabled --repo
   skiw-platform/skiw-platform`. The next push to `main` deploys. Check it with
   `gh run list --repo skiw-platform/skiw-platform --workflow ci --branch main --limit 1` and then
   `gh run view <run id> --repo skiw-platform/skiw-platform --log | grep 'skiw-deploy:'`, which shows
   the host's `... deployed; previous ...; staging checks passed` line.

Turn it off: `gh variable delete SKIW_STAGING_DEPLOY --repo skiw-platform/skiw-platform`. Rotate the
key yearly and on suspicion: repeat step 2 and remove the old line from staging's `authorized_keys`.
No production credential is ever a secret or a variable (Q42): `gh secret list --repo
skiw-platform/skiw-platform` shows only `STAGING_DEPLOY_KEY`, and
`gh api repos/skiw-platform/skiw-platform/environments` shows no environment secret.

### Publish the pre-migration dump image and set `SKIW_BACKUP_IMAGE` (owner)
The image in `infra/host/backup/predeploy/` passes the Trivy gate (DECISIONS 2026-10-23, "Dump
image passes the Trivy gate"); the `image` job scans it on every PR, so a new finding fails there
first. Do these in order, once that fix is merged: first `SKIW_PUBLISH_PREDEPLOY`, then
`SKIW_BACKUP_IMAGE` (no deploy runs while it is empty).
1. `gh variable set SKIW_PUBLISH_PREDEPLOY --body enabled --repo skiw-platform/skiw-platform`.
2. After the next green push to `main`, read the digest (replace `<run id>`):
   ```
   d=$(mktemp -d)
   gh run download <run id> --repo skiw-platform/skiw-platform -n predeploy-digest -D "$d"
   cat "$d/digest.txt"; echo; rm -r "$d"
   ```
   The `publish` job summary shows the same `pushed ghcr.io/skiw-platform/skiw-predeploy@sha256:…`.
3. In a PR, set `SKIW_BACKUP_IMAGE=ghcr.io/skiw-platform/skiw-predeploy@<that digest>` in
   `infra/host/env/staging.env` and `production.env`, then install the env file on each host as
   usual. The hosts' `ghcr_read_token` must be able to read this package too (G10; a new package
   is private and is linked to the repository by its `org.opencontainers.image.source` label).

A new dump image (a base or `age` update) is published the same way, and the value changed again.

## Production
The owner deploys, on the owner's machine, only a digest that staging reports as running with
`checks=passed` (the host checks again), through `scripts/deploy-prod` (Python 3.12 stdlib, the
owner's own `gh` login; spec H3 step 8, PROJECT §11).

One-time config, outside the repository, readable and writable by you only (replace each `<...>`):
```
mkdir -p ~/.config/skiw
printf '%s\n' 'SKIW_PROD_SSH=<production DNS name or IPv4>:<production SKIW_SSH_PORT>' \
  'SKIW_PROD_HOST_KEY=<first two fields of production /etc/ssh/ssh_host_ed25519_key.pub>' \
  'SKIW_PROD_DEPLOY_KEY=<absolute path of your production deploy key>' \
  > ~/.config/skiw/deploy-prod.env
chmod 600 ~/.config/skiw/deploy-prod.env
```
Read the host key on the production console (never with `ssh-keyscan`). The key file must be yours
and not readable by group or others. Each deploy:
1. Find the green `main` run of the digest that staging runs:
   `gh run list --repo skiw-platform/skiw-platform --workflow ci --branch main --event push --status success --limit 5`.
   Its digest is in the `publish` job summary, or:
   `d=$(mktemp -d); gh run download <run id> --repo skiw-platform/skiw-platform -n image-digest -D "$d"; cat "$d/digest.txt"; echo; rm -r "$d"`.
   Check staging with the smoke test below.
2. From the repository root: `scripts/deploy-prod <digest> <run id>` (`--config <file>` for another
   config file). It refuses (exit 2, nothing sent to production) unless `gh run view` shows that run
   as `success`, `push`, `main`, workflow `ci`; the run's commit is on `main` (`gh api
   .../compare/<commit>...main` answers `ahead` or `identical` with `behind_by` 0); the run has
   exactly one unexpired `image-digest` artifact; and that artifact, downloaded into a fresh
   temporary directory, holds only `digest.txt` with exactly that digest. Each `gh` call is bounded
   (60 s; the download 120 s). A failure, a timeout or output it cannot read refuses, and `gh`'s
   output is never shown: run the `gh` command it names by hand to see why.
3. It then runs `ssh -i <key> -p <port> skiw-deploy@<host> deploy <digest> <run id>` with
   production's host key pinned (`StrictHostKeyChecking=yes`, a temporary known_hosts, nothing else
   trusted). ssh asks for the key's passphrase; the host's one result line is printed. Exit 0
   deployed; 2 refused (by the script or the host: nothing changed); 1 failed (the host's exit 1;
   the host's exit 3 "deployed but the accepted-digest line failed", see "If it goes wrong"; ssh
   255: the connection or the host key). The call is bounded at 3600 s. After a timeout the deploy
   may still run on the host: read `sudo journalctl -t skiw-deploy` there before trying again (a
   second deploy meanwhile is refused by the deploy lock).

Rollback: [rollback.md](rollback.md).

## Smoke tests
`/readyz` and the worker are checked by the deploy itself; on staging the status line records the
G12 checks. From production, with the values of `SKIW_STAGING_SSH` (`<host>:<port>`):
```
known=$(mktemp)
echo "skiw-staging <SKIW_STAGING_HOST_KEY>" > "$known"
sudo ssh -F /dev/null -i /etc/skiw/secrets/staging_status_key -p <port> -o IdentitiesOnly=yes \
  -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known" \
  -o HostKeyAlias=skiw-staging -o HostKeyAlgorithms=ssh-ed25519 skiw-deploy@<host> status
rm -f "$known"
```
prints the one status line with `running=yes|no`. It pins staging's host key the same way the
deploy does (replace `<SKIW_STAGING_HOST_KEY>` with that value, `ssh-ed25519 AAAA...`); a wrong key
fails with exit 255 and nothing is stored.

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
  If the last line already equals the logged line (the write landed and only its sync failed), stop
  here: the record is complete. If the last line is cut short (it does not end in `key=SHA256:…`), remove it, keeping the file
  append-only otherwise: `sudo chattr -a /var/lib/skiw/accepted-digests && sudo sed -i '$d'
  /var/lib/skiw/accepted-digests && sudo chattr +a /var/lib/skiw/accepted-digests`. Then append the
  logged line (replace `<line>`):
  `printf '%s\n' '<line>' | sudo tee -a /var/lib/skiw/accepted-digests >/dev/null`, and check that
  `lsattr -d` still shows `a`. Until then a rollback to this digest is refused.
- See [rollback.md](rollback.md).
