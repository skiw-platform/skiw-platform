# Health checks and alerts (spec §8.4 H7; plan §3 M1j; amendment 2026-10-24)

`skiw-health` checks the host every 5 minutes and alerts what is wrong; once a month it runs
`check-hardening` and the 5-minute run alerts a failure. Both run as root from systemd timers that
`apply` installs, enables and starts (host-rebuild.md "Host"). Nothing triggers them over HTTP
(UNI-19).

Alerts go to the journal first and then, when the host's `SKIW_ALERT_CHANNEL` is `telegram`, to the
owner's Telegram bot chat (G8 (b), UNI-11 recorded 2026-10-24). With the channel empty nothing
leaves the host: every due alert is written to the journal only, and the run exits 3 so the unit
shows as failed. While the channel is on, a `heartbeat` message is due once a week, so a channel
that stopped working is noticed by its silence. Outside the host, UptimeRobot calls `/healthz` and tells the owner when the
site or the whole host does not answer ("The uptime ping" below).

## What runs

| Unit | When | Runs |
|---|---|---|
| `skiw-health.timer` → `skiw-health.service` | every 5 minutes (`*:0/5`, up to 30 s random delay; a missed run is made up at boot) | `/usr/local/sbin/skiw-health` |
| `skiw-hardening.timer` → `skiw-hardening.service` | monthly (up to 1 h random delay; made up at boot) | `/usr/local/sbin/skiw-health --hardening` |

Both services are `Type=oneshot` and run as root: they read the Docker socket, the 0700 dump
directory of uid 10003, the full journal and the root-only bot token, and write a root-owned state
file. `skiw-health.service` keeps one capability (`CAP_DAC_READ_SEARCH`), sees the file system
read-only except `/var/lib/skiw`, may open outgoing IPv4 and IPv6 connections (the Bot API; the
host firewall does not filter outgoing traffic), and stops after 280 s. `skiw-hardening.service`
keeps all capabilities, because `check-hardening` runs `unshare --net`, `nft`, `sshd -T` and
`docker compose exec`; it stops after 900 s. It sends nothing: it writes `check-hardening`'s result
to `/var/lib/skiw/hardening.state`, and the next 5-minute run alerts it like any check, so an alert
that could not be delivered is tried again every 5 minutes, not next month.

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
| `security-updates` | `apt-get --simulate dist-upgrade` (no lock, no cache written) would install a package from a `-security` pocket; or the package lists were not updated for over 48 h (`package lists not updated for N h`), because old lists cannot show a new update. The age is that of `/var/lib/apt/periodic/update-success-stamp`, which apt touches only after an `apt-get update` without errors; no stamp is bad | 48 h bad (`unattended-upgrades` runs daily): stale lists alert after about 96 h |
| `reboot` | `/run/reboot-required` exists (G15: production does not reboot itself) | the first bad run |
| `deploy-alert` | never bad itself, unless the journal cannot be read; each run sends the **count** of new `skiw-deploy` alert lines (a failed switch, M1g), never their text | at once |
| `check-hardening` | the last monthly run did not pass: the message names the failed checks (`failed: secret-store, pg-hba`), `refused (exit 2)`, `exit N` or `timed out` (600 s); or the last monthly run is over 33 days old (`the last monthly run is N days old`: the monthly timer stopped). Before the first monthly run: fine (`no monthly run yet`) | the first bad run |
| `health-state` | (a message, not a check) the state file was unreadable or unsafe and was started fresh | at once |
| `heartbeat` | (a message, not a check) `N checks, M bad`, once a week while the channel is on ("The weekly heartbeat") | Monday |

**Repeats:** a bad check is alerted once, then reminded every 6 hours while it stays bad, and
`recovered: <value>` is sent once it has been fine for 2 runs in a row. A check that flips between
runs sends nothing new. A message that could not be delivered is tried again on every run; restart
and deploy-alert messages wait in the state file (at most 20). After the first failed delivery in a
run, the rest of that run's messages wait for the next run.

**A message** is three fields, nothing else, sent as plain text:

```
check: disk
host: production:<node name>
value: /var/lib/docker space 83% used
```

Before sending, anything shaped like an email address or an IC number (12 digits, with or without
dashes) in the value is replaced (`[email]`, `[ic]`), control characters are removed and the value
is cut at 200 characters (UNI-09).

**Exit codes:** 0 every check fine and every due message delivered; 1 a check is bad (its due
messages delivered); 2 refused, nothing checked (not root; `SKIW_ENVIRONMENT` or `SKIW_HOSTNAME`
invalid; `SKIW_ALERT_CHANNEL` neither `telegram` nor empty, empty with `SKIW_ALERT_TO` set, or
`SKIW_ALERT_TO` not a chat id; the env file a link, not root-owned or writable by others); 3 a due
message was not delivered (no channel, the token file missing or unsafe, or the channel failed) or
the state file could not be written. 3 wins over 1. `--hardening` exits 0 passed, 1 failed, 3 its
result not written. Any non-zero exit leaves the service `failed` until its next run.

State: `/var/lib/skiw/health.state` (per check when it went bad, whether it was announced, the
restart counts, the journal cursor, the waiting messages, the ISO week of the last delivered
heartbeat) and `/var/lib/skiw/hardening.state` (the last monthly result and its time), both root,
0644, JSON. They are written to a new file, synced and renamed into place, then the directory is
synced. A `health.state` that is a link, has more than one link, another owner or mode, is over
64 KiB or does not parse is replaced and reported as `health-state`; an unsafe `hardening.state`
makes the `check-hardening` check bad until the next monthly run rewrites it.

## Looking at it

```bash
systemctl list-timers 'skiw-*'                       # next and last runs
systemctl status skiw-health.service skiw-hardening.service
journalctl -t skiw-health --since -1d                 # every alert and every delivery failure
sudo /usr/local/sbin/skiw-health                     # a run by hand: one OK/BAD line per check
sudo /usr/local/sbin/skiw-health --hardening         # the monthly run now (the next run alerts it)
sudo /usr/local/sbin/skiw-health --test              # one `alert-test` message, nothing checked
```

A run by hand shares the state file with the timer. Two runs at the same moment can send a message
twice; they cannot hide one, because a check counts as announced only after its message was
delivered. To forget every announced alert and wait time (each bad check alerts again after its
grace, and the week's heartbeat is sent again): `sudo rm /var/lib/skiw/health.state`.

`check-hardening` itself and what each FAIL means: host-rebuild.md "Checking the host".

## Turning on the alert channel

Once per environment, by the owner. Production and staging each get **their own bot and token**
(a stolen staging token cannot post as production) and, by default, their own chat. Steps 2 to 4
and 6 to 8 run on the host over SSH.

1. **Make the bot.** In Telegram, open a chat with `@BotFather`, send `/newbot`, give it a name and
   a username (for example `skiw_production_alerts_bot`). BotFather answers with the bot's token.
   Leave it in that chat for step 2; do not paste it anywhere else (no note, no file, no message).
2. **Write the token to the host.** It never goes through shell history, a command argument or the
   environment: `read` and `printf` are shell built-ins, so the token is only in that shell's
   memory and then in the file.
   ```
   sudo bash -c 'umask 077; t=/etc/skiw/secrets/.alert_credential.tmp; \
     IFS= read -rs v && printf "%s\n" "$v" > "$t" && chmod 0400 "$t" \
     && mv "$t" /etc/skiw/secrets/alert_credential'
   ```
   Paste the token, press Enter. Owner and group stay root (only `skiw-health`, as root, reads it).
   `skiw-health` uses the file only while it is a regular root:root 0400 file with one link, of at
   most 128 bytes, holding one token (digits, `:`, then letters, digits, `_` or `-`); anything else
   is an unsafe file and nothing is sent.
3. **Start the chat.** For a private chat, open the bot in Telegram and send `/start`. For a group,
   make a private group, add the bot, and send `/start@<bot username>` in the group (a bot in a
   group sees only commands addressed to it).
4. **Find the chat id.** On the host, this reads the token from the file inside Python and prints
   only the chat ids of the bot's recent updates; the token is in no command line or output:
   ```
   sudo python3 - <<'PY'
   import json, urllib.request
   token = open("/etc/skiw/secrets/alert_credential").read().strip()
   try:
       with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10) as r:
           print(sorted({u["message"]["chat"]["id"] for u in json.load(r)["result"] if "message" in u}))
   except Exception as exc:
       print("failed:", type(exc).__name__)
   PY
   ```
   A private chat's id is a positive number; a group's is negative (a supergroup's starts with
   `-100`). An empty list: send `/start` again and rerun.
5. **Set the channel in the repository.** In `infra/host/env/<environment>.env` set
   `SKIW_ALERT_CHANNEL=telegram` and `SKIW_ALERT_TO=<chat id>` (the chat id is not a secret; the
   token is never in this file), and merge it through a PR.
6. **Apply it.** On the host, from the updated checkout:
   `sudo infra/host/apply --env-file infra/host/env/<environment>.env`.
7. **Check the store.** `sudo /usr/local/sbin/check-hardening`: `secret-store` passes only when
   `alert_credential` is there and `SKIW_ALERT_CHANNEL` is `telegram`, or neither (between steps 2
   and 6 it fails, as expected: `alert_credential is present, but SKIW_ALERT_CHANNEL is not
   telegram`).
8. **Test it.** `sudo /usr/local/sbin/skiw-health --test` sends one message and checks nothing;
   exit 0 means Telegram answered `ok`. In the chat:
   ```
   check: alert-test
   host: production:<node name>
   value: a test
   ```
   The week's first `heartbeat` follows on the next 5-minute run ("The weekly heartbeat").

**When a message is not delivered**, the journal line says why, by name only (the URL holds the
token, so it is never shown): `journalctl -t skiw-health --since -1h`.

| Journal shows `not sent off the host (...)` | Meaning, and what to do |
|---|---|
| `no alert channel` (no parentheses) | `SKIW_ALERT_CHANNEL` is empty on this host: steps 5 and 6 |
| `FileNotFoundError` | the token file is missing: step 2 |
| `UnsafeCredential` | the token file is a link, not root:root 0400, has more than one link, is too large, or does not hold one token: write it again with step 2 |
| `HTTPError 401` | the token was revoked or mistyped: "Rotating the token" |
| `HTTPError 403` | the bot was blocked or removed from the chat: send `/start` again, or add it to the group again |
| `HTTPError 400` | usually a wrong chat id: steps 4 and 5 |
| `HTTPError 429` | too many messages to the chat (Telegram allows about one per second per chat [A]); the rest are sent on the next runs |
| `HTTPError 3xx`, `Undelivered` | an answer that was not status 200 with `ok: true` (no redirect is followed) |
| `URLError gaierror`, `URLError ConnectionRefusedError`, `URLError SSLCertVerificationError`, `URLError TimeoutError`, `Deadline`, `TimeoutError` | no name resolution, no connection, a certificate that does not verify, or no answer within 10 s: the host's network or Telegram |
| `Undelivered` right after another failure in the same run | not tried: after the first failure a run sends nothing more |

### Rotating the token

Yearly, when a host is rebuilt, and at once if the token may have leaked (a leaked token lets
someone post fake alerts in the owner's chat; it cannot read anything). In `@BotFather` send
`/token` and choose the bot: BotFather issues a new token and the old one stops working. Write the
new one with step 2 (it replaces the file), then step 8. The chat id does not change.

To turn the channel off: empty both `SKIW_ALERT_*` values (step 5), apply (step 6), then
`sudo rm /etc/skiw/secrets/alert_credential` and step 7.

## The weekly heartbeat

Every **Monday**, the first run at or after **00:00 UTC (08:00 in Kuala Lumpur)** sends one
`heartbeat` message, value `N checks, M bad` (bad checks also have their own alerts). It is due on
every run until it is delivered; a week's heartbeat that was never delivered is replaced by the next
week's, not sent late. Each environment sends its own, told apart by the host name.

**Owner rule:** no heartbeat from a host in the chat by **Monday 10:00 Kuala Lumpur time** → check
that host: `systemctl status skiw-health.timer skiw-health.service` and `journalctl -t skiw-health
--since -2d` (the table above names the failure). This also catches a stopped timer, a revoked token
and a bot removed from the chat; silence off the host lasts at most a week.

The heartbeat starts when the channel is turned on (`SKIW_ALERT_CHANNEL=telegram`): the next
5-minute run after step 6 sends the week's first one. With the channel off there is no heartbeat
at all (no journal line, and a healthy host exits 0); real alerts still go to the journal and exit
3. With the channel on but the token file missing or unsafe, the heartbeat stays due and
undelivered, and every run exits 3 until step 2 is done.

## The uptime ping (UptimeRobot)

Covers what the host cannot report itself: the host or the site is down. One monitor per
environment, in the owner's UptimeRobot account (free plan; nothing about it is in the repository):

1. **Add New Monitor** → type **HTTP(s) - Keyword** (on the free plan [A]; else **HTTP(s)**,
   which checks the status only) → URL `https://<SKIW_HOSTNAME>/healthz` →
   keyword `ok`, alert when the keyword is **not** found → interval 5 minutes. `/healthz` answers
   `200`, `Content-Type: text/plain` and the body `ok`, nothing else (a test keeps it so); no
   header, token or login is needed.
2. Alert contact: the owner's own email or the UptimeRobot app. The owner confirms on the free
   account that one of them arrives (amendment §7), before M1k.
3. UptimeRobot learns the host name, up or down and its timing, and the owner's contact; no client
   data and no token.

**Deploys:** a deploy or a key rotation restarts `web`, and Caddy serves the 503 maintenance page
for a short time, so the monitor can report "down" during a deploy. That is expected. Either set a
maintenance window for the monitor in UptimeRobot before a planned deploy, or ignore a "down" that
clears within the deploy's time (deploy.md).

**Replacing the provider** (terms or the free plan change): make the same keyword monitor at another
provider and delete the UptimeRobot one; nothing on the host changes. Record the new service in
DECISIONS first (UNI-11).

## Telegram facts used (checked 2026-10-25)

- Bot API `sendMessage` (https://core.telegram.org/bots/api#sendmessage): `chat_id` and `text`
  (1-4096 characters after entity parsing) are required; `link_preview_options` is optional and is
  sent with `is_disabled: true`; no `parse_mode` is sent, so the text is plain. An answer is JSON with
  `ok`; only status 200 with `ok: true` counts as delivered.
- Limits (https://core.telegram.org/bots/faq): about one message per second in one chat; more is
  answered with 429 [A] (the FAQ gives it as guidance, not a contract).
- BotFather (https://core.telegram.org/bots/features#botfather): `/newbot` makes a bot; `/token`
  issues a new token for a bot, and the old one stops working.
- The token shape (https://core.telegram.org/bots/api, "Authorizing your bot"): the bot's number, a
  colon, then a secret of letters, digits, `_` and `-`. The lengths in `alert.TOKEN` are an
  assumption [A]: Telegram documents the shape, not the lengths.

## Not proven yet

Measured on a real host in M1k: the unit sandboxing with the real tools (docker CLI, `apt-get`,
`journalctl` under `ProtectSystem=strict`), the `apt-get --simulate` output format on the host, the
apt stamp file being present and touched on Ubuntu 24.04 (it comes with `update-notifier-common`
[A]) and the journal cursor across journal rotation. Delivery off the host: `skiw-health --test`
reaching the owner's chat from staging and production, and the UptimeRobot monitors reporting up,
and down while `web` is stopped.
