# Host rebuild

Building a staging or production VPS from nothing, or rebuilding one after loss (spec §8.4).
Sections are added as M1 lands: host files, users, packages and units (M1f-1a, M1f-1b), secrets (M1d),
database roles (M1e), the hardening check (M1f-2a, M1f-2b);
measured values in M1k. The operator is the owner (UNI-12); no agent holds a host credential.

## Host (`apply`, spec §8.4 H1, H2, H7)

Assumes Ubuntu 24.04 LTS (G4 (a)). First step on a new host, from the repository checkout:
`sudo infra/host/apply --env-file infra/host/env/<environment>.env`. It refuses (exit 2, nothing
installed) until these values are set: `SKIW_SSH_PORT` (not 22, 80, 443), `SKIW_SSH_POLICY` (G7:
`allowlist` with the operator's and the off-site host's CIDRs in `SKIW_SSH_ALLOW`, or `fail2ban`
with it empty) and `SKIW_AUTO_REBOOT` (G15). Rates and journal cap are [A] values, measured in M1k.

The same env file sets the session lifetime for `web`, `worker` and `migrate`:
`SKIW_SESSION_ABSOLUTE_H=12` (whole hours, 1 to 72) and `SKIW_SESSION_IDLE_MIN=30` (whole
minutes, 1 to 1440) (spec D6, §8.1; M2b). Compose refuses to render without them, and the app
refuses to start on a value outside the bounds. Keep the values in all three env files.

It also sets the interim auth values for the same three services (owner Q6 (a), M3b; bounds in
`app/config/settings.py`, meaning in `.env.example`): `SKIW_ARGON2_MEMORY_KIB=65536`,
`SKIW_ARGON2_TIME_COST=3`, `SKIW_ARGON2_PARALLELISM=1` (T5), `SKIW_AUTH_FAILS_PER_ACCOUNT=5`,
`SKIW_AUTH_FAILS_PER_IP=20`, `SKIW_AUTH_WINDOW_MIN=15`, `SKIW_AUTH_LOCK_AFTER=10`,
`SKIW_AUTH_LOCK_MIN=30`, `SKIW_TOTP_SKEW_STEPS=1` (Flow 5.1, T18), `SKIW_STEPUP_MAX_AGE_MIN=5`
(§8.1), `SKIW_LOGIN_PENDING_MIN=5` and `SKIW_ENROL_LINK_MIN=30` (builder values), and
`SKIW_PW_MIN_LENGTH=12` (owner 2026-11-05; 12 to 64). Each one is required, the same way.
Each verify takes `SKIW_ARGON2_MEMORY_KIB` of `web` memory.

Before the first run, as root: `apt-get install nftables gnupg`, then fetch Docker's apt key to
`/etc/apt/keyrings/docker.asc` (root, 0644):
`curl -fsSL -o /etc/apt/keyrings/docker.asc https://download.docker.com/linux/ubuntu/gpg`.
`apply` refuses (nothing changed) unless that file holds exactly one primary key with fingerprint
`9DC8 5822 9FC7 DD38 854A E2D8 8D81 803C 0EBF CD88`, is root-owned and not a link.

It renders the templates from the env file, checks the nftables, sshd and sudoers candidates with
`nft -c`, `sshd -t`, `visudo -c`, then installs, root-owned, only the
files that differ: configs under `/etc` (0644), `/etc/sudoers.d/skiw-ops` and `skiw-deploy` (0440),
the env file as `/etc/skiw/host.env`, the stack as `/srv/skiw/compose.yml` with `/srv/skiw/caddy/`
(0644), `bootstrap-secrets`, `bootstrap-db`, `check-hardening`, `skiw-deploy`, `skiw-deploy-ssh`,
`skiw-staging-status` and `skiw-health` in `/usr/local/sbin` (0755), the `skiw-health` and
`skiw-hardening` service and timer units in `/etc/systemd/system` (0644), and
`skiw_host/`, `db/` and the templates in `/usr/local/lib/skiw/`. It prints what it changed; a
second run changes nothing. A file counts as unchanged only when its content, mode, owner and group
all match and it is not a link; otherwise `apply` puts it back root-owned. It refuses (nothing
installed) when a directory on the way to a destination is a link, is not owned by `root:root`,
or can be written by group or others. Directories it creates are made 0755 in the `mkdir` call itself (never writable by others, not even
for an instant) and are `root:root`, whatever the umask. It refuses a link planted at a path it is about to create.
Exit 0 done, 1 failed (fix, run again), 2 refused.

**age** for `bootstrap-secrets` is a manual step for now: check `age-v1.3.2-linux-amd64.tar.gz`
with `sha256sum` against `docs/DECISIONS.md` (2026-10-14, M1d-1); install as `/usr/local/bin/age`
(root, 0755).

**Then, on every run:** users `skiw-deploy` and `skiw-ops` exist (`skiw-ops` in `sudo`; set its
password and SSH key by hand), and neither is in group `docker` (it is removed if found); Docker
Engine and the Compose plugin are installed from Docker's signed repository at the versions in
`apt/skiw-docker.pref`, with `nftables`, `unattended-upgrades` and, for `fail2ban`, `fail2ban`
(only what is missing or at another version; the Docker packages alone may be moved to a lower
version, with `--allow-downgrades`, so a host with a newer Docker returns to the reviewed pin); the
units are enabled, and under `fail2ban` the service is started if it is not active; ssh moves from `ssh.socket`
to `ssh.service` (on 24.04 the socket would keep listening on 22). A service restarts only when
its file changed: `nft -f /etc/nftables.conf` (never `systemctl reload nftables`: it flushes
Docker's rules too), ssh, docker (`live-restore` keeps containers running), journald, fail2ban;
`systemctl daemon-reload` when a unit file changed. Last, `systemctl enable --now
skiw-health.timer skiw-hardening.timer` (health-alerts.md).
Reloads owed are written first to `/var/lib/skiw/apply.pending` and removed when all succeed, so
after exit 1 run `apply` again and it redoes them. Under `allowlist`, a jail file left from
`fail2ban` is removed (printed) and fail2ban restarted if it runs; the package and its Ubuntu
default jail stay. On an SSH port change keep one session open and test the new port first.

### Checking the host: `check-hardening` (spec §8.4 H2, H4, H6)

Run after every `apply` and after any host change, as root: `sudo check-hardening` (installed by
`apply` in `/usr/local/sbin`; it reads `/etc/skiw/host.env`, or `--env-file <path>`; add
for `role-set` it uses `/srv/skiw/compose.yml`, or `--compose-file`, with `/var/lib/skiw/deploy.env`). It is
read-only: it changes nothing, deletes nothing, and loads the rendered nftables file only in a
throwaway network namespace (`unshare --net`). It prints one line per check, `PASS <name>` or
`FAIL <name>: <what>`, with non-secret values only. Exit 0 all passed, 1 a check failed, 2 refused
(not root, or the env file is invalid, a link, not root-owned or writable by others). A check whose
tool is missing, exits non-zero or prints what it cannot read fails; it never passes by default.
Files it reads must be regular files, not links, root-owned and not writable by group or others.

| Check | Passes when |
|---|---|
| `sshd` | `sshd -T` gives exactly the values of `00-skiw.conf` (one `port`, the host's), so a competing file is caught; and no `Match` block in `sshd_config` or its drop-ins sets a checked key, under its old name too (`ChallengeResponseAuthentication` is `KbdInteractiveAuthentication`); a line whose keyword has a quote (`"`, `'`) or a backslash fails at once, because sshd strips those and this scan does not (`sshd -T` shows only the global values, so a `Match` block would hide a weaker setting for one user, group or address), and no `Include` other than the drop-in directory (a `Match` block for forced commands is fine) |
| `nftables` | the live `table inet skiw` equals the rendered `nftables.conf` as nft prints it (handles and set entries ignored) |
| `unattended-upgrades` | the unit is enabled; `apt-config dump` has the daily periodic runs, only the security origin, the host's reboot value, and `APT::Periodic::Enable` not `0`; every key under `Allowed-Origins` and `Origins-Pattern` counts, so a named extra entry fails |
| `docker-daemon` | the running daemon (`docker info`): live-restore on, journald logs, `no-new-privileges` in its security options; `/etc/docker/daemon.json`: no-new-privileges, no TCP `hosts`; the docker unit's `ExecStart` (including drop-ins): only `fd://` or `unix://` hosts and no other `--config-file` |
| `listening-sockets` | `ss -tlnp` shows nothing on a non-loopback address except 80, 443 and the SSH port, and `dockerd` listens on no TCP address at all, loopback included |
| `docker-group` | neither `skiw-deploy` nor `skiw-ops` is in group `docker` |
| `stale-files` | no fail2ban jail under `allowlist`, no `/etc/sudoers.d/skiw*` but `skiw-ops` and `skiw-deploy`, no sshd drop-in sorting before `00-skiw.conf` that sets a checked key, no `/var/lib/skiw/apply.pending` (run `apply`) |
| `secret-store` | `/etc/skiw/secrets` is a root:root 0700 directory, not a link; it holds every inventory name (`skiw_host/secrets.py`) and nothing else but `.restored`; `alert_credential` if and only if `SKIW_ALERT_CHANNEL` is `telegram` (missing with the channel on, or present with it off, fails); each file is a regular file, mode 0400, owned by its inventory uid, group root |
| `container-env` | no running container's environment (`docker inspect`) holds a secret value: a secret line, or the part after `v<n>:`, of 16 characters or more is searched inside every value; a shorter credential is compared whole and also FAILs as unsupported (it cannot be searched safely), as does an empty secret file; each container from `docker ps` must be described exactly once, with a `Config` and an `Env` that is null or a list of strings; a FAIL names the secret file, container and variable, never the value |
| `role-set` | through the db socket as `postgres` (`docker compose exec db`, bootstrap-db's password file), the WHOLE role inventory: only the six roles of `roles.sql` (with their attributes, connection limits and settings), `postgres` (the bootstrap superuser, the only superuser) and PostgreSQL's predefined `pg_*` roles (made by initdb; none may log in, be superuser or bypass RLS); any other role, of any name, fails; memberships are exactly `roles.sql`'s grants (`skiw_backup` in `pg_read_all_data` with `admin_option` false, `inherit_option` true, `set_option` true; from M4c-1 `skiw_migrator` in `skiw_tenant_guard` and in `skiw_auth_lookup` with `admin_option` false, `inherit_option` false, `set_option` true) plus PostgreSQL 17.11's own after initdb (`pg_monitor` in `pg_read_all_settings`, `pg_read_all_stats` and `pg_stat_scan_tables`, each false, true, true); any other membership (also between `pg_*` roles, e.g. `pg_read_all_data` in `pg_write_all_data`), a missing one, one granted twice or changed options (`INHERIT FALSE`, `SET FALSE`, `ADMIN OPTION`; for the migrator also `INHERIT TRUE`) fails. A FAIL names only roles from that list and `roles.sql`'s settings; other roles are counted (find them with `\du`), and no setting value or database row is ever printed; fails while `/srv/skiw/compose.yml` (or `--compose-file`) or skiw-deploy's state file `/var/lib/skiw/deploy.env` (root, 0644) is missing or untrusted |
| `pg-hba` | `/etc/skiw/db/pg_hba.conf` (root, 0444) equals the template rendered from the env file; after a subnet change run `bootstrap-db prepare` again |
| `health-timers` | `skiw-health.timer` and `skiw-hardening.timer` are both `enabled` and `active` (a stopped timer alerts nothing; run `apply`) |

On a FAIL, fix the cause (usually: run `apply` again; for `secret-store` and `pg-hba` the
bootstrap steps below) and rerun the check. Before the secrets and the database exist, those four
checks fail, as expected. `skiw-hardening.timer` runs it monthly and `skiw-health` alerts a
failure by check name (health-alerts.md).

## Secrets (`bootstrap-secrets`, spec §8.4 H4)

The secret store is `/etc/skiw/secrets/` (root, 0700): one file per secret, owned by the uid of the
service that reads it, mode 0400. The inventory, with readers and owners, is
`infra/host/skiw_host/secrets.py`; Compose mounts each file only into the services listed there.

| Kind | Names | Created by | Escrowed |
|---|---|---|---|
| App keys (`v<n>:<base64>` lines, 32 random bytes each) | `django_secret_key`, `tenant_token_key`, `approval_mac_key`, `lookup_decoy_key`, `tenant_source_key`, `login_blob_key`, `audit_mac_key`, `field_kek`, `blind_index_key`, `crm_jar_kek` | `bootstrap-secrets init`, or `restore` from the escrow bundle | yes |
| DB passwords | `skiw_app_password`, `skiw_migrator_password`, `skiw_backup_password`, `postgres_password`, `skiw_readonly_password` | `bootstrap-db` (M1e), newly set on every rebuild | no |
| Owner-supplied | `ghcr_read_token` (G10); production only: `staging_status_key` (G11 (b)); while `SKIW_ALERT_CHANNEL` is `telegram`: `alert_credential` (the environment's own Telegram bot token, read by `skiw-health` as root) | the owner, by hand (below; `alert_credential`: health-alerts.md "Turning on the alert channel") | no |

**Not escrowed, re-issued on recovery:** DB passwords, deploy SSH keys, the staging status key, the
GHCR token, the alert bot token (BotFather `/token`, health-alerts.md "Rotating the token"). `check-hardening` expects `staging_status_key` on production and fails if staging holds
it.

### Rotating `tenant_source_key` (session MAC, M2c)
Every `django_session` row carries a MAC under this key, bound to the row's stored key and
`expire_date` (spec §4.1; `accounts.source_key`). `web` signs with the highest listed version and
accepts every listed one, and reads the file once at start-up (`TENANT_SOURCE_KEY_FILE`, set for
`web` and `worker` only; `migrate` never mounts it). So a rotation adds a new, higher `v<n>` line,
keeps the old line until every session signed with it has expired (at most
`SKIW_SESSION_ABSOLUTE_H` hours after the restart), then removes it; restart `web` and `worker`
after each change. Removing the old version at once, or replacing the file, logs every user out
(the next request gets an empty session and the cookie is deleted): that is the wanted effect when
the key may have leaked. No script rotates app keys yet, and the escrow after every rotation (spec
§8.4 H4) still applies.
Recovery codes (M3f-2) are MACs under this key too, with no expiry: a code made under a version
stops working once that version is removed. Each `user_factor.secret_ct` of kind `recovery` starts
with the version that signed it (4 bytes, big-endian; M3f-3a), so before removing a version count
the users it still signs. This is a break-glass read (one SELECT, no writes) as `postgres` over the
`db` socket, because row-level security hides every row from `skiw_readonly`. `pg_hba` asks
`postgres` for a password, so the wrapper builds a 0600 password file from the container's secret
(removed on exit; never in argv or the environment), as `restore.md` does:
```sh
sudo -v
running="$(sudo sed -n 's/^SKIW_IMAGE=//p' /var/lib/skiw/deploy.env)"; test -n "$running"
compose() { sudo env SKIW_IMAGE="$running" docker compose -f /srv/skiw/compose.yml \
  --env-file /etc/skiw/host.env "$@"; }
pg='set -eu; umask 077; f=$(mktemp); trap "rm -f \"\$f\"" EXIT
printf "*:*:*:postgres:%s\n" "$(sed -e "s/[\\\\:]/\\\\&/g" /run/secrets/postgres_password)" > "$f"
PGPASSFILE="$f" psql -X -At -U postgres -d "$POSTGRES_DB"'
compose exec -T db sh -c "$pg" <<'SQL'
SELECT (get_byte(secret_ct, 0)::bigint << 24) | (get_byte(secret_ct, 1) << 16)
  | (get_byte(secret_ct, 2) << 8) | get_byte(secret_ct, 3) AS version,
  count(DISTINCT user_id) AS users FROM user_factor WHERE kind = 'recovery'
  GROUP BY 1 ORDER BY 1;
SQL
```
To list the users of one version (to tell them), run the same with this SELECT, replacing the eight
hex digits with the version in four bytes (version 2 is `00000002`):
```sh
compose exec -T db sh -c "$pg" <<'SQL'
SELECT u.email FROM user_factor f JOIN app_user u ON u.id = f.user_id
  WHERE f.kind = 'recovery' AND substring(f.secret_ct FROM 1 FOR 4) = decode('00000001', 'hex')
  GROUP BY u.email ORDER BY u.email;
SQL
```
For a planned rotation, remove a version only when the report no longer lists it; users get the
newest version by regenerating their codes. In an emergency (the key may have leaked) remove it at
once: every code still under it is void, so tell those users to generate new ones at their next
sign-in.
Both `web` (`config.asgi`) and `worker` (`runworker`, from M3a) refuse to start when the file is
missing or malformed, before the migration check and without printing the key. A version number
has at most six digits (`v1` to `v999999`): the reader and `bootstrap-secrets restore` refuse a
larger one.

### Rotating `login_blob_key` (login and credential blobs, M3b)
`web` and `worker` read it from `LOGIN_BLOB_KEY_FILE` (`migrate` never mounts it) and refuse to
start when it is missing or malformed, before the migration check and without printing the key.
Its version must be at most `v65535`, because each blob binds the version in two bytes of its
AAD. The highest version seals new blobs; opening tries every listed version. Each
`app_user.login_blob_ct` and `user_factor.lookup_blob_ct` (from M3e and M3g) stays sealed under the
version that wrote it, so a rotation adds a new, higher line and keeps every old one until a later
job re-seals the blobs (spec T16; not built yet). A blob carries no version in clear (M3e-1a), so
SQL cannot show which version a row uses: before a version leaves the file, the re-seal job must
open every blob and report the version that opened it, and none may still report the old one.
Removing a version that still seals a blob makes that account's password login, or that passkey,
fail as if the account were unknown.
Restart `web` and `worker` after each change, then escrow (spec §8.4 H4).

### `tenant_token_key` and `lookup_decoy_key` (the guard key tables, M4c-3)
`migrate` reads both files (`TENANT_TOKEN_KEY_FILE`, `LOOKUP_DECOY_KEY_FILE`; `migrate` is the only
service that mounts `lookup_decoy_key`) and, after every run, writes them into
`guard.tenant_mac_key` and `guard.lookup_decoy_key` as the tables' NOLOGIN owners, in one
transaction (`tenancy.keys`; spec §4.1, §8.4 H4). `skiw-deploy` runs `migrate` on every forward
deploy; `migrate --plan` writes nothing. A missing or malformed file, a version whose bytes changed,
or a retired `tenant_token_key` version listed again stops `migrate` without writing anything and
without printing a key (the message names the key and version). `skiw-deploy` then reports
``failed: `migrate` exited <n>``, stops before the switch, and the old digest keeps serving.
- **Rotation:** add a new, higher `v<n>` line, deploy (`migrate` inserts it), restart `web` and
  `worker`, then remove the old line and deploy again: `migrate` sets `retired_at` on an unlisted
  `tenant_mac_key` version (`guard.current_agency()`, from M4c-4a, refuses a retired version) and
  deletes an unlisted `lookup_decoy_key` version. Never change a line's value in place (plan M4c-3:
  changed bytes stop `migrate`), and never list a retired `tenant_token_key` version again: it stops
  `migrate` whatever its bytes, with no override (owner decision 2026-11-03). The fix is to remove
  that line; a key that turns out to be safe goes back only under a new, higher version number,
  never by un-retiring the old one. Rotate yearly and on suspicion (spec §8.4 H4, T16). Escrow
  after each change (spec §8.4 H4).
  **`lookup_decoy_key` is different (M3e-1b):** `guard.auth_lookup_login` makes every decoy with the
  **oldest** listed version, so adding a version changes nothing. Removing the oldest changes every
  unknown email's decoy at once while real blobs stay the same, and anyone who compared lookups
  before and after could then tell the two apart. So remove the oldest `lookup_decoy_key` line only
  in the same deploy window as re-sealing every login blob (the re-seal job, not built yet); until
  that job exists, do not remove it.
  **Keep the two steps in separate deploys.** From M4c-4a `guard.current_agency()` reads
  `guard.tenant_mac_key` and refuses a retired version. If one deploy both adds the new line and
  removes the old one, `migrate` retires the old version before the switch, while the running
  `web` and `worker` still mint under it. Their tenant transactions then see no agency until they
  restart, and if the deploy stops after `migrate`, the old digest keeps serving with a key the
  database refuses. Remove the old line only after every `web` and `worker` container has
  restarted on the new key.
- **web and worker (M4c-4b):** both read `TENANT_TOKEN_KEY_FILE` once at start-up and refuse to start
  when it is missing or malformed (the message names the key, never the value). `with_agency()`
  mints every token under the **newest** listed version, so after the first deploy of a rotation
  the restarted containers already mint under the new version that `migrate` has just inserted.
- **After a restore:** dumps leave both tables' rows out (spec §8.4 H6; `predeploy` `EXCLUDE`), so a
  restored database has no key rows until `migrate` runs. Run a forward deploy (it runs `migrate`)
  before serving; with the restored secret store it rewrites both tables from the same files. The
  tables start empty, so no retired row exists that a listed version could conflict with: every
  listed version is written as active.
- **Rollback:** `skiw-deploy rollback` runs no `migrate`, so the tables keep what the last forward
  deploy wrote. A key file changed since then is written only by the next forward deploy.

### Before you start
- `age` v1.3.2 at `/usr/local/bin/age`, installed from `age-v1.3.2-linux-amd64.tar.gz` after
  checking its SHA-256 against the value in `docs/DECISIONS.md` (2026-10-14, M1d). The script
  refuses any other version.
- `SKIW_ESCROW_RECIPIENTS` in the host's `env/<environment>.env` holds the owner's **public** escrow
  recipient(s) (`age1…`, space-separated; G5). Staging uses its own staging-only identity. Never
  put a private identity (`AGE-SECRET-KEY-…`) on a host: the script refuses it without printing
  it; if that happens, treat the identity as exposed and make a new one.
- The secret store must be empty. `init` and `restore` both refuse when any file, or the
  `.restored` marker, is already there. Run `bootstrap-secrets` first, then place the GHCR token,
  then `bootstrap-db`.

### New environment: `init`
```
sudo bootstrap-secrets init --env-file <path to env/<environment>.env>
```
It mints every app key as `v1`, writes `/srv/skiw/escrow/<UTC time>.bundle.age` (encrypted to the
recipients; the age header is checked), makes the bundle's directory entry durable, then installs
the key files. If `age` or any write before that point fails, it removes everything it wrote and
exits non-zero; fix the cause and run it again. Exit codes: 0 done, 2 refused (nothing written),
1 failed (nothing left), 3 installed but the final log step failed. No key value is ever printed.

**Exit 3** means the keys and the bundle are installed and committed; only the line to the journal or
`/var/log/skiw/deploy.log` was not written. Do not run `init` again (it would refuse: the store is
not empty). Check the keys with `ls -l /etc/skiw/secrets`, fix the log problem (disk full, a file
where `/var/log/skiw` should be, permissions), note the install in the recovery record by hand,
and carry on with the off-host copy of the bundle.

Then copy the new bundle off the host, apart from the dumps (H6; the automated pull is M6), and
check the owner can decrypt it on the owner's own machine.

### Recovery: `restore`
On the owner's machine, decrypt the newest bundle and stream it over SSH; the plaintext never
touches the host's disk except as the 0400 key files, and the private identity never reaches the
host.

**Prerequisite: not on any host yet, so the command below is conditional and cannot be run today.**
The pipeline has no terminal and its stdin is the plaintext bundle, so `sudo` cannot ask for a
password (and `sudo -S` would read the bundle as the password). The operator account therefore
needs a narrow, noninteractive rule that allows this one command and nothing else: a `sudoers`
entry for the installed `bootstrap-secrets` only, not global passwordless `sudo`, not SSH root
login, and never a password sent in the bundle stream. `apply` installs that rule (M1f-1a, "Host"
below), M1f-1b creates the `skiw-ops` account, and M1k proves it on both hosts, including that a
missing rule refuses and changes nothing.

**Preflight, before you decrypt anything.** It must print exactly this rule line (the exit code
alone proves nothing: the operator's password `sudo` also lists the command):
```
ssh -T skiw-ops@<host> sudo -n -l | grep -Fx '    (root) NOPASSWD: /usr/local/sbin/bootstrap-secrets restore --env-file /etc/skiw/host.env'
```
If it prints nothing (a password would be needed, or the rule is absent or different), stop: fix the rule on the host
through the console or the normal operator login, then try again. Do not decrypt the bundle first.

```
age --decrypt -i <offline escrow identity> <bundle>.bundle.age \
  | ssh -T skiw-ops@<host> sudo -n /usr/local/sbin/bootstrap-secrets restore --env-file /etc/skiw/host.env
```
`sudo -n` fails closed: with no authorization it exits at once before `restore` starts, so nothing
is written on the host.

It checks the whole bundle in memory first: the `skiw-escrow-1` format, every app key of the
inventory present and nothing else (a DB password in the bundle is refused), each version a
well-formed `v<n>:<base64>` line, not repeated, matching its SHA-256 and at least 32 bytes. If
anything is wrong, or the store is not empty, or `.restored` exists, it writes nothing (not even a
directory) and exits 2; the message names the key and the entry number, never a value. Then it
writes a fresh escrow bundle (so the host's newest bundle matches what is installed), makes its
directory entry durable, installs every version verbatim (oldest first in each file), then writes
`/etc/skiw/secrets/.restored` (root, 0400). The marker is the last file before the commit point: if
any write up to and including it fails, everything the run wrote is removed (exit 1) and the run can
be repeated.

Exit codes: 0 restored; 2 refused (nothing written); 1 failed (nothing left; fix the cause and run
it again); 3 restored (keys, new bundle and `.restored` installed) but a final journal or
deploy-log line was not written. On **exit 3** do not run `restore` again (it would refuse:
`.restored` exists); check with `ls -la /etc/skiw/secrets`, fix the log problem, and write in the
recovery record by hand what the run printed, including any `Minted by override:` names. Then copy
the new bundle off the host as after `init`.

`restore` never mints a key by itself. If a key is truly lost (absent from every bundle the owner
holds), the owner, and only the owner, may add `--allow-new-key-version <name>` (repeatable, app-key
names only; `init` refuses the option). It adds one new newest version of that key from 32 random
bytes: `v1` if the bundle lacks the key, otherwise the next number after the newest version, which
the app then uses for new writes. **Data encrypted or signed under a lost version stays unreadable;**
the override does not recover it. Each override is one line, key name and version only, on stderr,
in the journal (`journalctl -t bootstrap-secrets`) and in `/var/log/skiw/deploy.log`, e.g.
`restore minted field_kek v2 (--allow-new-key-version)`. The owner records in the recovery record:
the date, the host, which bundle was restored, each overridden key and its new version, why the key
was lost, and that the new bundle was copied off the host.

### Placing `ghcr_read_token` (owner)
The owner issues the token (G10) and types it into the host; it is never in a file on the owner's
machine, in shell history or in the repository:
```
sudo bash -c 'umask 077; t=/etc/skiw/secrets/.ghcr_read_token.tmp; \
  IFS= read -rs v && printf "%s\n" "$v" > "$t" && chmod 0400 "$t" \
  && mv "$t" /etc/skiw/secrets/ghcr_read_token'
```
Paste the token, press Enter. Owner and group stay root (only `skiw-deploy`, as root, reads it).
Rotate yearly and on suspicion (H3 step 11).

### Making `staging_status_key` (owner, production only)
On **production**, make the key, copy its public line, then keep only the private half (0400):
```
sudo ssh-keygen -q -t ed25519 -N '' -C production-status -f /etc/skiw/secrets/staging_status_key
sudo cat /etc/skiw/secrets/staging_status_key.pub
sudo rm /etc/skiw/secrets/staging_status_key.pub
sudo chmod 0400 /etc/skiw/secrets/staging_status_key
```
(`check-hardening` fails while the `.pub` file is left in the secret store.) On **staging**, add the
copied line with the forced command in front (replace `<public line>` with the whole
`ssh-ed25519 AAAA... production-status` line):
```
sudo install -d -m 0700 -o skiw-deploy -g skiw-deploy /home/skiw-deploy/.ssh
printf '%s\n' 'restrict,command="/usr/local/sbin/skiw-staging-status" <public line>' \
  | sudo tee -a /home/skiw-deploy/.ssh/authorized_keys >/dev/null
sudo chown skiw-deploy:skiw-deploy /home/skiw-deploy/.ssh/authorized_keys
sudo chmod 0600 /home/skiw-deploy/.ssh/authorized_keys
```
Put staging's host key into production's host config: `SKIW_STAGING_HOST_KEY` is the first two
fields of staging's `/etc/ssh/ssh_host_ed25519_key.pub` (`awk '{print $1, $2}'` there). The key can
only read the last staging status line (deploy.md). Rotate with the deploy keys.

Staging must accept SSH from production. Under `SKIW_SSH_POLICY=allowlist` (G7), add production's
outbound address as a CIDR (`<address>/32`, or `/128` for IPv6) to `SKIW_SSH_ALLOW` in staging's
`infra/host/env/staging.env`, then re-run `sudo infra/host/apply --env-file
infra/host/env/staging.env` on staging. Without it nftables drops the connection and every
production deploy is refused with "the staging status call timed out". Under `fail2ban`, the jail
has no `ignoreip` here: three failed status logins from production within 10 minutes (for example
a wrong key on staging) ban production for an hour, and production deploys are refused until the
ban ends (`sudo fail2ban-client set sshd unbanip <address>` on staging lifts it).

### The deployment agency (M4c-5)
`SKIW_DEPLOYMENT_AGENCY_ID` and `SKIW_DEPLOYMENT_AGENCY_NAME` are non-secret host config in
`infra/host/env/<env>.env`, passed to `migrate`, `web` and `worker`. Each environment has its own
uuid; the owner gave the staging and production names (2026-11-03).
- **First deploy:** `migrate` inserts the agency into the empty `agency` table.
- **Every later deploy:** `migrate` finds the same id and writes nothing. The name is never updated
  by `migrate`; a rename waits for the admin helper (M5).
- **Never change the id on a host that holds data.** `migrate` then refuses (the message names the
  configured id and PROJECT §9's second-agency gate), writes nothing and exits ≠ 0, so the deploy
  stops before `web` switches. Put the old id back. A second agency needs the PROJECT §9 gate first.
- **After a restore:** the `agency` row is ordinary data and comes back with the dump, so the
  configured id must be the one the dump holds.
- **`/readyz`** binds `with_agency()` to the configured agency and answers 503 unless the verifier
  gives it back and its row is visible. A `tenant_token_key` that differs from the stored one, or a
  missing row, then fails the deploy health check and the deploy switches back.

### Enrol a user (M3e-3)
Until staff invites arrive with M4-rest ("Manage staff"), the operator invites each user of the
deployment agency with `accounts_invite`, run inside the running `web` container (it connects as
`skiw_app`, like `web`):
```sh
sudo -v
running="$(sudo sed -n 's/^SKIW_IMAGE=//p' /var/lib/skiw/deploy.env)"; test -n "$running"
sudo env SKIW_IMAGE="$running" docker compose -f /srv/skiw/compose.yml \
  --env-file /etc/skiw/host.env exec -T web \
  python app/manage.py accounts_invite '<email>' --name '<display name>'
```
- **Use `exec`, never `run`.** A `compose run` container's output goes to its logging driver
  (journald) as well as to your terminal, so the link would be kept in the journal. `exec` output
  reaches only your terminal.
- It prints one line, `https://<SKIW_HOSTNAME>/enrol#<token>`, and on stderr how long it is valid.
  A refusal (not an email address, a user who has already enrolled, an email the agency cannot
  see) exits 1 and creates nothing.
- **Two invites for the same new email at the same moment:** one makes the user and the other is
  told "this email cannot be invited". Run the command again: it then gives a new link for that
  invited user.
- **The link sets the user's password, so treat it as a password.** Send it only to that user,
  directly. Don't paste it into a ticket, a shared chat, the shell history of a shared account or
  this runbook, and don't keep a copy. The token is after `#`, so the browser never sends it in the
  request line, a `Referer` or the Caddy log.
- It works **once** and for `SKIW_ENROL_LINK_MIN` minutes (30). Setting the password ends it, and any
  other unused link for that user with it. The user stays `invited` (password login is refused)
  until they enrol an authenticator app (TOTP), which every user must do (spec v1.22). A passkey is
  optional and is added later (M3h).
- **After setting the password the user has `SKIW_LOGIN_PENDING_MIN` minutes (5) to finish.** In
  that time the page shows the authenticator secret and the user enters the first code; the
  confirmation signs them in and shows ten recovery codes, once. The time is not extended. If it
  runs out, or the browser is closed, the next step answers "enrolment expired", the password stays
  set and the user stays `invited`. Run the command above again for the same email: it gives a new
  link, and the user sets a new password and starts the authenticator step again. Nothing is kept
  from the first try, so an old authenticator entry is not valid.
- **Recovery codes are shown once**, in the answer to the first correct code. The operator cannot
  see or resend them. A user who lost the codes but still has the authenticator can make new ones
  once regenerating exists (M3h); the owner's reset (Flow 5.1, not built yet) is only for a user who
  lost the authenticator too.
- **Too many wrong codes** (`SKIW_AUTH_FAILS_PER_ACCOUNT`, 5, in `SKIW_AUTH_WINDOW_MIN`, 15 minutes)
  stop all code checks for that user, at enrolment and at sign-in alike (sign-in from M3f-3c), until
  the window ends. A new invite link does not shorten that, so tell the user to wait up to 15 minutes.
- **Ten wrong codes in a row** (`SKIW_AUTH_LOCK_AFTER`, across any number of windows, and not
  cleared by signing in with the password again; checked at sign-in from M3f-3c) lock that user's second factor for
  `SKIW_AUTH_LOCK_MIN` (30 minutes), TOTP and recovery codes alike. It writes a `factor.locked`
  event (HMACs of the email and IP, and the count) and a `second factor soft-locked` warning in the
  web log: that is the owner alert. Only a right code, after the lock ends, clears the run. A user
  who is locked out just waits; one who keeps being locked out may have a password someone else
  knows, so change it (the owner's reset, Flow 5.1, is not built yet).
- **The password must be at least `SKIW_PW_MIN_LENGTH` characters (12)**, with no other
  rules. A shorter one is refused with the same answer as a bad link and doesn't use the link up,
  so the user can try again with the same link while it is valid.
- **Expired or lost:** run the command again for the same email. A user who has not finished
  enrolling gets a new link (the stored name stays); one who has is refused, and a lost factor is
  the owner's reset (Flow 5.1, not built yet).
- **After raising `SKIW_ARGON2_*`:** each stored hash is re-made with the new values when its user
  next signs in. Until then, a wrong password for that account costs the old amount while an unknown
  email costs the new one, so the two can be told apart by timing. Raise the values only when a
  difference for users who have not signed in since is acceptable, or have them sign in soon after.

### The tenancy schema check (M4c-6b)
`skiw-deploy` runs `manage.py check_tenancy_schema` in the new image right after `migrate`, as
`skiw_migrator` (at most 120 s). Every table must be a listed global, the `agency` root, or a
compliant tenant table (spec §4.2). Output is never shown; the journal line names the step.
- **On failure** the deploy exits 1 before the switch and the old digest keeps serving. The bad
  table stays in the database, because migrations are never reversed.
- **CI runs the same check first** (`make migrate` ends with it), so a failure here means a CI
  result was missed. Run `make migrate` on that commit to see each `<table>: <reason>` line.
- **The fix** is a forward migration that makes the table compliant (or drops it), then a new
  deploy. Do not run a reverse migration on the host.

## Database roles (`bootstrap-db`, spec §8.4 H4, H6)

Run it in this order on a new or rebuilt host. It needs root, for the same reason as
`bootstrap-secrets`: it reads `/etc/skiw/secrets/`.

1. `bootstrap-secrets init` (or `restore`) has run.
2. `prepare` makes the DB password files and `/etc/skiw/db/pg_hba.conf`. Compose needs that file,
   so `db` cannot start before this step.
3. Start `db` with the same Compose file and environment file, and wait until it is healthy.
   Compose checks the whole file, so it refuses this step until `SKIW_HOSTNAME` (owner value G9)
   and `SKIW_IMAGE` have values. Before the first deploy there is no state file, so give the
   full `<repository>@sha256:<digest>` you will deploy to **both** commands below (`bootstrap-db
   apply` runs Compose too and passes its environment on; a variable set for one `sudo` command does
   not reach the next). After a deploy, use the image in `/var/lib/skiw/deploy.env`. On a real host this step is
   staged to M1g and M1k. CI runs it with `env/ci.env`, which sets both.
4. `apply` sets the roles and the passwords.

```
sudo infra/host/bootstrap-db prepare --env-file <env file>
image=ghcr.io/<owner>/<name>@sha256:<64 hex>   # the digest you will deploy
sudo env SKIW_IMAGE="$image" docker compose -f /srv/skiw/compose.yml \
  --env-file /etc/skiw/host.env up -d --wait db
sudo env SKIW_IMAGE="$image" bootstrap-db apply --env-file /etc/skiw/host.env \
  --compose-file /srv/skiw/compose.yml
```

- `prepare` makes each missing DB password file (32 random bytes, mode 0400, owner from the
  inventory). It never replaces a file that exists.
- `apply` runs `infra/host/db/roles.sql` in the db container as `postgres` over the socket. Then it
  sets each password. The SCRAM-SHA-256 verifier is computed in Python and sent on stdin: no
  password is in argv, in a file in the repo or in output. A second run changes no role.
- Exit codes: 0 done, 1 a step failed, 2 refused (a password file is missing or malformed; nothing
  reached the db), 3 done but its log line failed: do not repeat `prepare`/`apply` for that; fix
  the log problem as for `bootstrap-secrets` exit 3 and note the run by hand. Each run writes one
  value-free line to the journal (`journalctl -t bootstrap-db`) and `/var/log/skiw/deploy.log`.
- Roles: `skiw_migrator` (owns the schema; `migrate` only; SET-only member of the two NOLOGIN roles), `skiw_app` (web and worker), `skiw_readonly`,
  `skiw_backup` (read only, 2 connections), and the NOLOGIN `skiw_tenant_guard`, `skiw_auth_lookup`.
- `apply` signs in as `postgres` with a libpq password file: made inside the db container from
  `/run/secrets/postgres_password`, mode 0600, removed when psql ends. The password is never in an
  environment variable or in argv (H4).
- `roles.sql` refuses to run on drift: if any of the six roles belongs to a role it should not, or
  any role belongs to one of the six, it stops, changes nothing and names the membership. Exit 1.
  Allowed, each granted once: `skiw_backup` in `pg_read_all_data`, and `skiw_migrator` in
  `skiw_tenant_guard` and `skiw_auth_lookup` with `INHERIT FALSE, SET TRUE` and no `ADMIN OPTION`.
  A changed INHERIT, SET or `ADMIN OPTION` on the migrator's own grant stops it too (exit 1;
  psql exits 3, e.g. `unexpected role membership, nothing changed: skiw_migrator in
  skiw_auth_lookup`): the check runs before the migrator's GRANTs, so a run no longer resets
  drifted options silently (M4c-2a, PR 83 P3). A second grant of a pair stops it as well (its
  grantor needs `ADMIN OPTION` on the role, which is itself refused). A host that has no
  migrator membership yet (before M4c-1) gets both on its next run. A person reads the membership and revokes it
  by hand, then runs `apply` again.
- **Before the first M4c-2a deploy (once per existing host; plan M4c-1).** The M4c-1 `roles.sql`
  gives `skiw_migrator` a SET-only membership in `skiw_tenant_guard` and `skiw_auth_lookup`
  (owner Q1 (a), `docs/DECISIONS.md` "M4c-1"). Migrations from M4c-2a on run `SET LOCAL ROLE` to
  those roles. Install the new host config with `apply`, then run `bootstrap-db apply` as above
  before deploying any M4c-2a digest. A new host gets the membership from its first
  `bootstrap-db apply`.
  - Without it, the migration fails with `permission denied to set role "skiw_tenant_guard"` (or
    `"skiw_auth_lookup"`; the PostgreSQL 17 text, seen as the migrator on the local database).
    `skiw-deploy` reports only ``failed: `migrate` exited <n>`` (it withholds tool output), stops
    before the switch, so the old digest keeps serving, and exits 1. Run `bootstrap-db apply`, then
    deploy again.
  - Between the `apply` that installs this `roles.sql` and `bootstrap-db apply`, `check-hardening`
    `role-set` fails with `skiw_migrator is not a member of skiw_auth_lookup` (and of
    `skiw_tenant_guard`), because it reads the installed `roles.sql`. The monthly
    `skiw-hardening.timer` run would alert it through `skiw-health`. Run both steps together.
  - `bootstrap-db apply` also sets every DB password again from its file (unchanged files, so the
    same passwords).
  - Undoing it is a reviewed `roles.sql` change, then `REVOKE skiw_tenant_guard, skiw_auth_lookup
    FROM skiw_migrator;` as `postgres` before that older `roles.sql` is applied: an older file
    stops on these two memberships (its drift guard allows only `skiw_backup`).
- DB passwords are not escrowed. After a rebuild, run `prepare` then `apply` again: new passwords.
- `prepare` also renders `/etc/skiw/db/pg_hba.conf` (root, mode 0444, no secret) from
  `infra/host/db/pg_hba.conf` and the host's `env/<environment>.env`; it needs `--env-file`. Compose
  mounts that file read-only into `db` and starts Postgres with it. After a subnet change, run
  `prepare` again and restart `db`.
- Who may connect, from where (`scram-sha-256`; first match wins; all else is rejected):
  `skiw_app` and `skiw_migrator` only from the `app` network, `skiw_backup` only from `ops`,
  `skiw_readonly` and `postgres` only over the socket inside `db`. `skiw_backup` is refused from `app`,
  and `skiw_app` is refused from `ops` (TEN-02, TEN-10).

### Not verified yet
On a real VPS (M1k): the owner's recipients, the off-host copy of the bundle, a restore on a fresh
host, and `check-hardening` of owners and modes on both hosts (M1k).

## Staging on a monthly term (rebuild checklist)

Staging is a Hostinger KVM 1 on a monthly term (owner 2026-10-26, DECISIONS of that date); it may
lapse. Staging must exist and pass before each production deploy (D15), so while it is lapsed no
production deploy runs.

**When staging lapses**, do every step below **before the term ends**. A lapsed server's address can
go to another customer, and the old disk may not be wiped (G-VENDOR item 5), so nothing that points
at it or opens it may stay live.
1. **Turn the staging deploy off:**
   `gh variable delete SKIW_STAGING_DEPLOY --repo skiw-platform/skiw-platform`.
2. **DNS:** delete the staging site name (`SKIW_HOSTNAME` in `infra/host/env/staging.env`) and the
   staging SSH name (the host part of `SKIW_STAGING_SSH`), or point both away from the old IPv4.
   Otherwise whoever gets the address can obtain a certificate for the name and serve pages under the
   project's domain.
3. **GHCR token:** revoke staging's `ghcr_read_token` at GitHub (Settings, Developer settings,
   Personal access tokens). It reads every package its issuer can read (plan G10), so if production
   uses the same token, rotate production's too ("Placing `ghcr_read_token`" above).
4. **Telegram:** revoke staging's bot token with BotFather (`/revoke`). Each environment has its
   own bot.
5. **GitHub secret:** `gh secret delete STAGING_DEPLOY_KEY --repo skiw-platform/skiw-platform`.
6. **UptimeRobot:** pause staging's monitor, or it alerts every 5 minutes until someone does.
7. **Destroy the VPS** in the Hostinger panel (do not only let it expire) and note the date in
   `docs/DECISIONS.md`.

**To bring it back**, in this order:
1. **Buy** a KVM 1 in a Malaysian location, Ubuntu 24.04 LTS, automatic backups and snapshots off
   if Hostinger allows it (setting recorded, G-VENDOR item 3). Confirm the Malaysian location in
   writing (G-VENDOR item 1) before any real data.
2. **DNS:** point the staging site name and the staging SSH name at the new IPv4 **before** step 3,
   so the certificate request can succeed.
3. **Build the host** with this runbook from the top: `sudo infra/host/apply --env-file
   infra/host/env/staging.env`, `check-hardening`, then "Secrets" (`bootstrap-secrets`, with
   staging's own escrow recipient), `ghcr_read_token` and "Database roles" (`bootstrap-db`). Staging
   needs `SKIW_SSH_POLICY=fail2ban` to take CI deploys (deploy.md "Turn on the staging deploy",
   step 1).
4. **Address and host key**, in one PR: the new `SKIW_STAGING_SSH` and `SKIW_STAGING_HOST_KEY` in
   `infra/host/env/staging.env` **and** `infra/host/env/production.env` (a test fails if they
   differ; deploy.md step 3).
5. **Keys** (names only, never values): a new staging deploy key and the secret
   `STAGING_DEPLOY_KEY` (deploy.md step 2), and the production status key's line in staging's
   `authorized_keys` ("Making `staging_status_key`" above, the staging part).
6. **Alerts:** a new Telegram bot token for this host (health-alerts.md "Turning on the alert
   channel"), and the UptimeRobot monitor: un-pause it and set its address, or add it
   (health-alerts.md "The uptime ping (UptimeRobot)").
7. **Turn the staging deploy on:** `gh variable set SKIW_STAGING_DEPLOY --body enabled --repo
   skiw-platform/skiw-platform` (deploy.md step 4), and check that the next staging deploy passes
   before any production deploy.
