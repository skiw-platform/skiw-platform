# Runbook — deploy

iCore VPS, spec §8.4 H3. M1g-1 builds the host side for **staging**; production (staging check
G11, accepted-digest record), the pre-migration dump image and the CI trigger follow in M1g-2 and
M1h; measured outage in M1k. Nothing deploys before then.

## How a deploy reaches the host
Each deploy key's `authorized_keys` line for user `skiw-deploy` fixes its own role:
```
restrict,command="/usr/local/sbin/skiw-deploy-ssh --key staging" ssh-ed25519 AAAA... staging-deploy
```
(`--key production` on the production host, with the owner's key, G6.) The caller can send only
`deploy <digest> [<run-id>]` or `rollback <digest>` (`sha256:` + 64 lowercase hex; run id digits);
anything else, including `id`, an empty command, extra words or shell characters, exits 2 and runs
nothing. The forced command then runs `sudo -n /usr/local/sbin/skiw-deploy --key <role> ...`, the one
command `/etc/sudoers.d/skiw-deploy` allows (its arguments pinned by a regular expression).

## Before you deploy
- `apply` has run (it installs `skiw-deploy`, `skiw-deploy-ssh`, the sudoers rule and
  `/srv/skiw/compose.yml` with `/srv/skiw/caddy/`); `check-hardening` passes.
- Host config in `/etc/skiw/host.env`: `SKIW_ENVIRONMENT` (`staging` or `production`, must equal the
  key role), `SKIW_IMAGE_REPOSITORY` (the one repository, `ghcr.io/<owner>/<name>`; the login user is
  `<owner>`), `SKIW_HOSTNAME` (G9), `SKIW_DEPLOY_HEALTH_TIMEOUT_S` (60).
- `/etc/skiw/secrets/ghcr_read_token` placed (host-rebuild.md), root, 0400.
- First deploy only: `bootstrap-db prepare`, start `db` and `bootstrap-db apply` (host-rebuild.md,
  "Database roles"), giving the digest you are about to deploy as `SKIW_IMAGE`.

## Staging: what `skiw-deploy` does
1. Refuses (exit 2, nothing changed) a bad digest or run id, a key role other than the host's,
   production (until M1g-2), a bad host value, any file that is a link, not root-owned or writable by
   group or others (env file, compose file, token, state file, the directories on the way), or a held
   lock (`/run/skiw-deploy.lock`, `flock`: one deploy at a time).
2. Pulls `<repository>@<digest>`: `docker login` with the token on stdin into a temporary 0700
   config directory, removed after the pull; checks the image carries that digest.
3. `migrate --plan` in the new image. If anything is planned, the pre-migration dump runs (the
   `backup` service's `predeploy` command, built in M1g-2); it must print
   `predeploy <time>.dump.age <sha256>`. **Until M1g-2 any deploy with a pending migration stops
   here** (exit 1, nothing changed).
4. `migrate` as `skiw_migrator`. A failure stops the deploy; the old containers keep serving.
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
   switch|health check; switched back to <digest>` or `... RECOVERY FAILED ...`, and exits 1; the
   deploy lock is released. Migrations are never reversed (UNI-15 keeps the previous digest valid
   on the new schema).
8. One line to the journal (`journalctl -t skiw-deploy`) and `/var/log/skiw/deploy.log`: action,
   digest, key role, run id, result, previous digest. No tool output, no secret value.

Exit codes: 0 deployed; 1 failed (read the log line; the previous digest serves unless the alert
says RECOVERY FAILED; fix and deploy again); 2 refused, nothing changed; 3 deployed but the log line failed (record it by hand).

## Production
Refused until M1g-2 adds the G11 staging check and the accepted-digest record (spec H3 steps 3, 9).

## Smoke tests
`/readyz` is checked by the deploy itself; the G12 staging checks arrive in M1g-2.

## If it goes wrong
- "RECOVERY FAILED": the state file already holds the previous content (or is removed on a first
  deploy). Run `sudo env SKIW_IMAGE=<previous> docker compose -f /srv/skiw/compose.yml --env-file
  /etc/skiw/host.env up -d` by hand (first deploy: `... stop web worker`), then find the cause in
  `journalctl -u docker` and the container logs. Re-running the same digest is safe: it succeeds
  once the running worker's heartbeat is fresh and `/readyz` answers.
- See [rollback.md](rollback.md).
