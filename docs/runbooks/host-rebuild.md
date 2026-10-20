# Host rebuild

Building a staging or production VPS from nothing, or rebuilding one after loss (spec §8.4).
Sections are added as M1 lands: host files, users, packages and units (M1f-1a, M1f-1b), secrets (M1d),
database roles (M1e), the hardening check (M1f-2a; secret and database checks M1f-2b);
measured values in M1k. The operator is the owner (UNI-12); no agent holds a host credential.

## Host (`apply`, spec §8.4 H1, H2, H7)

Assumes Ubuntu 24.04 LTS (G4 (a)). First step on a new host, from the repository checkout:
`sudo infra/host/apply --env-file infra/host/env/<environment>.env`. It refuses (exit 2, nothing
installed) until these values are set: `SKIW_SSH_PORT` (not 22, 80, 443), `SKIW_SSH_POLICY` (G7:
`allowlist` with the operator's and the off-site host's CIDRs in `SKIW_SSH_ALLOW`, or `fail2ban`
with it empty) and `SKIW_AUTO_REBOOT` (G15). Rates and journal cap are [A] values, measured in M1k.

Before the first run, as root: `apt-get install nftables gnupg`, then fetch Docker's apt key to
`/etc/apt/keyrings/docker.asc` (root, 0644):
`curl -fsSL -o /etc/apt/keyrings/docker.asc https://download.docker.com/linux/ubuntu/gpg`.
`apply` refuses (nothing changed) unless that file holds exactly one primary key with fingerprint
`9DC8 5822 9FC7 DD38 854A E2D8 8D81 803C 0EBF CD88`, is root-owned and not a link.

It renders the templates from the env file, checks the nftables, sshd and sudoers candidates with
`nft -c`, `sshd -t`, `visudo -c`, then installs, root-owned, only the
files that differ: configs under `/etc` (0644), `/etc/sudoers.d/skiw-ops` (0440), the env file as
`/etc/skiw/host.env`, `bootstrap-secrets` and `bootstrap-db` in `/usr/local/sbin` (0755), and
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
Docker's rules too), ssh, docker (`live-restore` keeps containers running), journald, fail2ban.
Reloads owed are written first to `/var/lib/skiw/apply.pending` and removed when all succeed, so
after exit 1 run `apply` again and it redoes them. Under `allowlist`, a jail file left from
`fail2ban` is removed (printed) and fail2ban restarted if it runs; the package and its Ubuntu
default jail stay. On an SSH port change keep one session open and test the new port first.

### Checking the host: `check-hardening` (spec §8.4 H2)

Run after every `apply` and after any host change, as root: `sudo check-hardening` (installed by
`apply` in `/usr/local/sbin`; it reads `/etc/skiw/host.env`, or `--env-file <path>`). It is
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
| `stale-files` | no fail2ban jail under `allowlist`, no other `/etc/sudoers.d/skiw*`, no sshd drop-in sorting before `00-skiw.conf` that sets a checked key, no `/var/lib/skiw/apply.pending` (run `apply`) |

On a FAIL, fix the cause (usually: run `apply` again) and rerun the check. Coming in M1f-2b: the
secret store owners and modes, no secret value in any container environment, the database role set
and `pg_hba.conf` against the env file. The health timer runs it monthly from M1j.

## Secrets (`bootstrap-secrets`, spec §8.4 H4)

The secret store is `/etc/skiw/secrets/` (root, 0700): one file per secret, owned by the uid of the
service that reads it, mode 0400. The inventory, with readers and owners, is
`infra/host/skiw_host/secrets.py`; Compose mounts each file only into the services listed there.

| Kind | Names | Created by | Escrowed |
|---|---|---|---|
| App keys (`v<n>:<base64>` lines, 32 random bytes each) | `django_secret_key`, `tenant_token_key`, `approval_mac_key`, `lookup_decoy_key`, `tenant_source_key`, `login_blob_key`, `audit_mac_key`, `field_kek`, `blind_index_key`, `crm_jar_kek` | `bootstrap-secrets init`, or `restore` from the escrow bundle | yes |
| DB passwords | `skiw_app_password`, `skiw_migrator_password`, `skiw_backup_password`, `postgres_password`, `skiw_readonly_password` | `bootstrap-db` (M1e), newly set on every rebuild | no |
| Owner-supplied | `ghcr_read_token` (G10) | the owner, by hand (below) | no |

**Not escrowed, re-issued on recovery:** DB passwords, deploy SSH keys, the GHCR token. The
staging-check secret (G11) is not in the inventory until its mechanism is decided.

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

## Database roles (`bootstrap-db`, spec §8.4 H4, H6)

Run it in this order on a new or rebuilt host. It needs root, for the same reason as
`bootstrap-secrets`: it reads `/etc/skiw/secrets/`.

1. `bootstrap-secrets init` (or `restore`) has run.
2. `prepare` makes the DB password files and `/etc/skiw/db/pg_hba.conf`. Compose needs that file,
   so `db` cannot start before this step.
3. Start `db` with the same Compose file and environment file, and wait until it is healthy.
   Compose checks the whole file, so it refuses this step until `SKIW_HOSTNAME` (owner value G9)
   and `SKIW_IMAGE` (written by `skiw-deploy`, M1g) have values. On a real host this step is
   staged to M1g and M1k. CI runs it with `env/ci.env`, which sets both.
4. `apply` sets the roles and the passwords.

```
sudo infra/host/bootstrap-db prepare --env-file <env file>
sudo docker compose -f <compose.yml> --env-file <env file> up -d --wait db
sudo infra/host/bootstrap-db apply --env-file <env file> --compose-file <compose.yml>
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
- Roles: `skiw_migrator` (owns the schema; `migrate` only), `skiw_app` (web and worker), `skiw_readonly`,
  `skiw_backup` (read only, 2 connections), and the NOLOGIN `skiw_tenant_guard`, `skiw_auth_lookup`.
- `apply` signs in as `postgres` with a libpq password file: made inside the db container from
  `/run/secrets/postgres_password`, mode 0600, removed when psql ends. The password is never in an
  environment variable or in argv (H4).
- `roles.sql` refuses to run on drift: if any of the six roles belongs to a role it should not
  (only `skiw_backup` in `pg_read_all_data` is allowed), it stops, changes nothing and names the
  role. Exit 1. A person reads the membership and revokes it by hand, then runs `apply` again.
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
host, and `check-hardening` of owners and modes (M1f).
