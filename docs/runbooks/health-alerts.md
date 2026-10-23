# Health checks and alerts (spec §8.4 H7; plan §3 M1j)

`skiw-health` checks the host every 5 minutes and alerts what is wrong; once a month it runs
`check-hardening` and alerts a failure. Both run as root from systemd timers that `apply` installs,
enables and starts (host-rebuild.md "Host"). Nothing triggers them over HTTP (UNI-19).

**Alerts do not leave the host yet.** Until the owner chooses the Q20 channel (G8: agency mail
provider or a Telegram bot), UNI-11 records it and its transport is built (M1j-2), the
`SKIW_ALERT_*` keys are empty: every alert is written to the journal only, and the run exits 3 so
the unit shows as failed.

## What runs

| Unit | When | Runs |
|---|---|---|
| `skiw-health.timer` → `skiw-health.service` | every 5 minutes (`*:0/5`, up to 30 s random delay; a missed run is made up at boot) | `/usr/local/sbin/skiw-health` |
| `skiw-hardening.timer` → `skiw-hardening.service` | monthly (up to 1 h random delay; made up at boot) | `/usr/local/sbin/skiw-health --hardening` |

Both services are `Type=oneshot` and run as root: they read the Docker socket, the 0700 dump
directory of uid 10003 and the full journal, and write a root-owned
state file. `skiw-health.service` keeps one capability (`CAP_DAC_READ_SEARCH`), sees the file system
read-only except `/var/lib/skiw`, and stops after 280 s. `skiw-hardening.service` keeps all
capabilities, because `check-hardening` runs `unshare --net`, `nft`, `sshd -T` and `docker compose
exec`; it stops after 900 s.

## Checks

A check that cannot read its input (a tool missing, timed out, non-zero, or printing what cannot be
parsed) is **bad**: it never passes by default. Tool output, database rows, application logs and
secret values never appear in a value.

| Check | Bad when | Alerts after |
|---|---|---|
| `disk` | space or inodes ≥ 80 % used on `/`, `/var/lib/docker`, `/srv/skiw` or `/var/log` (each file system once; space counted as `df` does) | the first bad run |
| `memory` | `MemAvailable` below 15 % of `MemTotal` | 2 bad runs in a row |
| `swap` | 50 % or more of swap used (no swap is fine) | 2 bad runs |
| `load` | the 15-minute load average above 1.0 per CPU | 2 bad runs |
| `containers` | one of `caddy`, `web`, `worker`, `db`, `clamav` (Compose project `skiw`) missing, not running, or with a healthcheck that is not `healthy`; restarts since the last run are sent as their own message (`restarted: web 2x`) | 2 bad runs; restarts at once |
| `readyz` | `GET /readyz` to Caddy on 127.0.0.1:443, for `SKIW_HOSTNAME` with the certificate verified, does not answer 200 within 10 s | 2 bad runs |
| `tls-certificate` | the certificate Caddy serves expires in under 14 days, or does not verify | the first bad run |
| `dump` | `/srv/skiw/backups/predeploy` is not 0700 owned by uid 10003; a dump without its `.sha256` (or the reverse); a temporary file older than 1 h; any other file. The newest dump's age is shown but not judged until M6 sets the backup cadence (Q34) | the first bad run |
| `security-updates` | `apt-get --simulate dist-upgrade` (no lock, no cache written) would install a package from a `-security` pocket | 48 h bad (`unattended-upgrades` runs daily) |
| `reboot` | `/run/reboot-required` exists (G15: production does not reboot itself) | the first bad run |
| `deploy-alert` | never bad itself, unless the journal cannot be read; each run sends the **count** of new `skiw-deploy` alert lines (a failed switch, M1g), never their text | at once |
| `health-state` | (a message, not a check) the state file was unreadable or unsafe and was started fresh | at once |
| `check-hardening` | monthly only: `check-hardening` did not exit 0; the message names the failed checks (`failed: secret-store, pg-hba`), `refused (exit 2)`, `exit N` or `timed out` (600 s) | the run it fails |

**Repeats:** a bad check is alerted once, then reminded every 6 hours while it stays bad, and
`recovered: <value>` is sent once it has been fine for 2 runs in a row (the monthly check: at once).
A check that flips between runs sends nothing new. A message that could not be delivered is tried
again on every run; restart and deploy-alert messages wait in the state file (at most 20).
After the first failed delivery in a run, the rest of that run's messages wait for the next run.

**A message** is three fields, nothing else:

```
check: disk
host: production:<node name>
value: /var/lib/docker space 83% used
```

Before sending, anything shaped like an email address or an IC number (12 digits, with or without
dashes) in the value is replaced (`[email]`, `[ic]`), control characters are removed and the value
is cut at 200 characters (UNI-09).

**Exit codes:** 0 every check fine and every due message delivered; 1 a check is bad (its due
messages delivered); 2 refused, nothing checked (not root; `SKIW_ENVIRONMENT`, `SKIW_HOSTNAME` or a
`SKIW_ALERT_*` key set, as no transport is built yet; the env file a link, not root-owned or
writable by others); 3 a due message was not delivered (no channel, or the channel failed) or the state file could not be written. 3 wins over 1. Any non-zero exit leaves the
service `failed` until its next run.

State: `/var/lib/skiw/health.state` and `/var/lib/skiw/hardening.state` (root, 0644, JSON: per check
when it went bad, whether it was announced, the restart counts, the journal cursor, the waiting
messages). They are written to a new file, synced and renamed into place, then the directory is
synced. A state file that is a link, has more than one link, another owner or mode, is over 64 KiB
or does not parse is replaced and reported as `health-state`.

## Looking at it

```bash
systemctl list-timers 'skiw-*'                       # next and last runs
systemctl status skiw-health.service skiw-hardening.service
journalctl -t skiw-health --since -1d                 # every alert and every delivery failure
sudo /usr/local/sbin/skiw-health                     # a run by hand: one OK/BAD line per check
sudo /usr/local/sbin/skiw-health --hardening         # the monthly run now
sudo /usr/local/sbin/skiw-health --test              # one `alert-test` message, nothing checked
```

A run by hand shares the state file with the timer. Two runs at the same moment can send a message
twice; they cannot hide one, because a check counts as announced only after its message was
delivered. To forget every announced alert and wait time (each bad check alerts again after its
grace): `sudo rm /var/lib/skiw/health.state`.

`check-hardening` itself and what each FAIL means: host-rebuild.md "Checking the host".

## The alert channel

Off. The `SKIW_ALERT_*` keys in `infra/host/env/*.env` stay empty (a test holds them empty) and
setting any of them makes `skiw-health` refuse (exit 2). The two transports for the G8 options (mail
over implicit TLS, a Telegram bot over HTTPS), their credential `alert_credential` and the steps
to turn one on arrive in M1j-2, after the owner answers G8 and the channel is recorded as an external
service (D17, D19, UNI-11).

## Not proven yet

Measured on a real host in M1k: the unit sandboxing with the real tools (docker CLI, `apt-get`,
`journalctl` under `ProtectSystem=strict`), the `apt-get --simulate` output format on the host and
the journal cursor across journal rotation. Delivery off the host: once M1j-2 and G8 are done.
