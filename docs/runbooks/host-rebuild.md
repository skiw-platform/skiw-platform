# Host rebuild

Building a staging or production VPS from nothing, or rebuilding one after loss (spec §8.4).
Sections are added as M1 lands: secrets (M1d, below), database roles (M1e-1, below; pg_hba M1e-2), host hardening (M1f);
measured values in M1k. The operator is the owner (UNI-12); no agent holds a host credential.

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

**Prerequisite: not provisioned yet, so the command below is conditional and cannot be run today.**
The pipeline has no terminal and its stdin is the plaintext bundle, so `sudo` cannot ask for a
password (and `sudo -S` would read the bundle as the password). The operator account therefore
needs a narrow, noninteractive rule that allows this one command and nothing else: a `sudoers`
entry for the installed `bootstrap-secrets` only, not global passwordless `sudo`, not SSH root
login, and never a password sent in the bundle stream. M1f (host hardening) provisions that rule
and M1k proves it on both hosts, including that a missing rule refuses and changes nothing.

**Preflight, before you decrypt anything.** It must succeed and print nothing secret:
```
ssh -T <operator>@<host> sudo -n -l bootstrap-secrets
```
If it fails (a password would be needed, or the rule is absent), stop: fix the rule on the host
through the console or the normal operator login, then try again. Do not decrypt the bundle first.

```
age --decrypt -i <offline escrow identity> <bundle>.bundle.age \
  | ssh -T <operator>@<host> sudo -n bootstrap-secrets restore --env-file <path to env/<environment>.env>
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

Run after `bootstrap-secrets init` (or `restore`) and after `docker compose up -d db`. It needs
root, for the same reason as `bootstrap-secrets`: it reads `/etc/skiw/secrets/`.

```
sudo infra/host/bootstrap-db prepare
sudo infra/host/bootstrap-db apply --env-file <env file> --compose-file <compose.yml>
```

- `prepare` makes each missing DB password file (32 random bytes, mode 0400, owner from the
  inventory). It never replaces a file that exists. Run it before the first `up db`.
- `apply` runs `infra/host/db/roles.sql` in the db container as `postgres` over the socket. Then it
  sets each password. The SCRAM-SHA-256 verifier is computed in Python and sent on stdin: no
  password is in argv, in a file in the repo or in output. A second run changes no role.
- Exit codes: 0 done, 1 a step failed, 2 refused (a password file is missing or malformed; nothing
  reached the db).
- Roles: `skiw_migrator` (owns the schema; `migrate` only), `skiw_app` (web and worker), `skiw_readonly`,
  `skiw_backup` (read only, 2 connections), and the NOLOGIN `skiw_tenant_guard`, `skiw_auth_lookup`.
- DB passwords are not escrowed. After a rebuild, run `prepare` then `apply` again: new passwords.
- The per-role network rules (`pg_hba.conf`) arrive in M1e-2.

### Not verified yet
On a real VPS (M1k): the owner's recipients, the off-host copy of the bundle, a restore on a fresh
host, and `check-hardening` of owners and modes (M1f).
