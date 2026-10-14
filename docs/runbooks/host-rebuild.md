# Host rebuild

Building a staging or production VPS from nothing, or rebuilding one after loss (spec §8.4).
Sections are added as M1 lands: secrets (M1d, below), database roles (M1e), host hardening (M1f);
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
- The secret store must be empty. Both modes refuse when any file, or the `.restored` marker,
  is already there. Run `bootstrap-secrets` first, then place the GHCR token, then `bootstrap-db`.

### New environment: `init`
```
sudo bootstrap-secrets init --env-file <path to env/<environment>.env>
```
It mints every app key as `v1`, writes `/srv/skiw/escrow/<UTC time>.bundle.age` (encrypted to the
recipients; the age header is checked), then installs the key files. If `age` or any write fails,
it removes everything it wrote and exits non-zero; fix the cause and run it again. Exit codes:
0 done, 2 refused (nothing written), 1 failed (nothing left). No key value is ever printed.

Then copy the new bundle off the host, apart from the dumps (H6; the automated pull is M6), and
check the owner can decrypt it on his own machine.

### Recovery: `restore`
On the owner's machine, decrypt the newest bundle and stream it over SSH; the plaintext never
touches the host's disk except as the 0400 key files, and the private key never reaches the host:
```
age --decrypt -i <offline escrow identity> <bundle>.bundle.age \
  | ssh <operator>@<host> sudo bootstrap-secrets restore --env-file <path to env/<environment>.env>
```
It checks the bundle first (every app key of the inventory present, nothing else, each version's
SHA-256, 32 bytes per version), writes nothing if anything is wrong, then writes a fresh escrow
bundle, installs every version verbatim and writes `/etc/skiw/secrets/.restored`.

It never mints a key. If a key is truly lost, the owner may add
`--allow-new-key-version <name>` (repeatable): it adds a new newest version of that key only
(`v1` if the bundle lacks it). Data encrypted under a lost version stays unreadable. The override
is written to stderr, the journal (`journalctl -t bootstrap-secrets`) and the deploy log
`/var/log/skiw/deploy.log`, with the key name and version only; record it in the recovery record.

### Placing `ghcr_read_token` (owner)
The owner issues the token (G10) and types it into the host; it is never in a file on his
machine, in shell history or in the repository:
```
sudo bash -c 'umask 077; t=/etc/skiw/secrets/.ghcr_read_token.tmp; \
  IFS= read -rs v && printf "%s\n" "$v" > "$t" && chmod 0400 "$t" \
  && mv "$t" /etc/skiw/secrets/ghcr_read_token'
```
Paste the token, press Enter. Owner and group stay root (only `skiw-deploy`, as root, reads it).
Rotate yearly and on suspicion (H3 step 11).

### Not verified yet
On a real VPS (M1k): the owner's recipients, the off-host copy of the bundle, a restore on a fresh
host, and `check-hardening` of owners and modes (M1f).
