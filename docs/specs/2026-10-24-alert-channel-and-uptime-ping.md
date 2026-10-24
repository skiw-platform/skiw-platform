# Alert channel (Telegram) and external uptime ping — design

- Date: 2026-10-24 · Author: Builder · Status: approved at 1.1 (review Round 2); 1.2 text fixes go in the S1 docs PR
- Version: 1.2 (1.1 fixed review Round 1 of 1.0, hash `c39fe297`: four P2 and six P3 items; 1.2 takes the three P3 items of Round 2 on `ea6ee2fb`: the heartbeat value, the wording of the Q20 check in decision 8, the stale vendor line)
- Supersedes: nothing. This is an **amendment to spec v1.18** (`docs/specs/2026-10-05-skiw-platform-stack-design.md`, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644`). It answers Q20 and fills the UNI-11 gap for two services. On approval it changes the v1.18 text listed in section 3, row 8 (the version line and changelog, H4, H7, D17, D19 (5), UNI-11, Q20 and the cost line). It changes nothing else.
- Owner answers (2026-10-24): G8 = **(b) a Telegram bot to the owner**; external uptime ping = **yes**; ping provider = **UptimeRobot, free plan**.

## 1. Goal
The `skiw-health` timer (merged in PR 60, M1j-1) can only write alerts to the host journal. The owner needs two outside paths so a problem reaches the owner's phone: (a) the host sends each alert to a Telegram bot chat of the owner; (b) an outside checker calls `/healthz` and tells the owner when the site, or the whole host, does not answer. Path (b) covers the case where the host is dead and cannot send anything. A weekly "alive" message (decision 12) covers the third case: the host is up, `/healthz` says `ok`, but alerts no longer reach the phone. Both paths carry no client data.

## 2. Non-goals
- No client or personal data of any data subject goes to either service (UNI-09).
- No Slack, WhatsApp or email channel. No second channel for failover.
- No Telegram bot that receives commands. The bot only sends. The host never reads a Telegram reply.
- This spec does not build the H6 off-site freshness alert. When M6 builds it on the off-site side, it uses the same Telegram channel with its own bot token (a separate owner-supplied secret on that side), recorded in that PR's DECISIONS entry. The H6 alarm is not dropped.
- No change to the checks, thresholds or payload built in M1j-1.
- No status page, no public monitor page, no push to any other service.

## 3. Decisions
| # | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 1 | The Q20 channel is **a Telegram bot owned by the owner**, sending to one chat of the owner (a private chat, or a private group of the owner's choosing). | Owner answer G8 (b). | Email through the agency's mail provider (the plan's default; owner declined). Slack, WhatsApp. |
| 2 | The host sends with one HTTPS `POST` to the Telegram Bot API `sendMessage` method, from `skiw-health` only, using the Python standard library. The request carries the chat id and the text. The text is the existing alert text: check name, host and value, after the UNI-09 scrubber. No other field is sent. The host reads the answer only for its status code and the `ok` flag, and never prints or journals the answer body. | Smallest surface: no library, no webhook, no inbound port. | A Telegram client library (new dependency, UNI-06). A webhook (needs an inbound route). |
| 3 | The **bot token is a secret** (UNI-07, UNI-08): the file `/etc/skiw/secrets/alert_credential`, root-owned, mode 0400, read only by `skiw-health` (root). It is never in the repository, in an environment file, in a log, in the journal, in a command line, or in a message. The chat id is not a secret and lives in `SKIW_ALERT_TO` in `infra/host/env/<environment>.env`. `SKIW_ALERT_CHANNEL` is `telegram`. | Same rule as every host secret (H4). | Token in an env file (UNI-07). |
| 4 | **One bot token per environment** (production and staging each have their own file and their own chat or topic). A stolen staging token then cannot post as production. | Limits the blast radius. | One token on both hosts. |
| 5 | The token is **owner-supplied**, not minted: it is added to the host secret inventory as an owner-supplied entry, like `ghcr_read_token`. It is not in the escrow bundle (a lost token is replaced through BotFather). | The token comes from Telegram, not from us. | Escrowing it (age bundle holds only keys we mint). |
| 6 | Telegram is **a service outside Malaysia that receives project data** (UNI-11). The only project data it receives is the alert text: a check name, a host name and a value built from numbers and names. Section 7 (table "Alert values") lists what each value can hold. Telegram also learns the existence and timing of the owner's alerts. | Required by UNI-11 and D19. | — |
| 7 | **External uptime ping = UptimeRobot, free plan**: one HTTPS monitor per environment on `https://<SKIW_HOSTNAME>/healthz`, expecting status 200 and the body `ok`, with alerts to the owner's own account contact. UptimeRobot receives the host name, the answer "up" or "down" and its timing, and the owner's contact details (the owner's own, not a client's). It is a second service outside Malaysia (UNI-11). | Owner answer; it is the only path that still works when the host is dead. | Telegram only (leaves the dead-host case to H6). Self-hosted checker (also needs a host outside the one it watches). |
| 8 | **Text changes to v1.18 on approval:** H7 (alerts go to "the Telegram bot chat of the owner (Q20)"; the external ping is "UptimeRobot on `/healthz`"); D17 (same two words: "only if Q20 adopts one" becomes "adopted 2026-10-24"); D19 flow (5) (the alert channel is Telegram and the uptime ping is UptimeRobot, both adopted); UNI-11 (remove "alert channel and uptime ping (Q20)" from "Not adopted until recorded" and add both with their data lists); Q20 (answered); **H4** (the inventory's exact names gain `alert_credential`: owner-supplied, root, not escrowed, one per environment; read only by `skiw-health`); **the cost table line** "alert channel and uptime ping per Q20" becomes "Telegram RM 0; UptimeRobot free plan RM 0". After the docs PR, every Q20 mention in v1.19 reads as answered or adopted. | Keeps one source of truth. | Leaving the spec stale. |
| 9 | `/healthz` is **already public** (Caddy proxies all paths; `app/health/views.py` returns the text `ok` and nothing else). No new route, no new Caddy rule. The monitor needs no secret and no login. A test keeps the body exactly `ok` (see section 7). | Nothing to build for the ping on our side. | A private route with a token (UptimeRobot's free plan cannot send a custom secret header reliably [A]; and the body has no data to protect). |
| 10 | **A failed send is never dropped on the host, and silence off the host is bounded.** Every alert goes to the journal first (already built). If Telegram does not answer with `ok` within the bound, the message stays owed, the run exits 3, and the next run tries again. At most 20 messages are owed and the oldest are dropped (`OWED_MAX`, built in M1j-1). A broken channel (revoked token, bot removed from the chat, wrong file mode, stopped timer) is silent off the host, and `/healthz` still says `ok`. The weekly heartbeat (decision 12) bounds that silence to one week. | UNI-03 fail closed; PR 60 review: nothing watches `skiw-health` itself. | Dropping the message. A dead-man service (a third UNI-11 service). |
| 11 | The two PR 60 deferred P2 items are part of the M1j-2 build, not this spec: the monthly `check-hardening` alert gets a retry that does not wait a month; `security-updates` is told when the package lists are stale. | Review R1 of PR 60. | — |
| 12 | **Weekly heartbeat (owner decision 2026-10-24: yes).** `skiw-health` sends one fixed message every **Monday**: the first run at or after **Monday 00:00 UTC (08:00 in Kuala Lumpur)**. Check name `heartbeat`, value `N checks, M bad` (N is the number of checks and M the number now bad, numbers only; the bad ones also have their own alerts). It uses the same sender, the same scrubber and the same owed rule. The state file keeps the ISO week of the last heartbeat that was **delivered**; a heartbeat from an earlier week that is still owed is replaced by the new week's, not queued twice. **Owner rule (runbook):** no heartbeat in the chat by Monday 10:00 Kuala Lumpur time → check the host, `systemctl status skiw-health.timer` and `journalctl -u skiw-health`. Each environment sends its own, so staging and production are told apart by the host name. This also covers a stopped timer. | Closes the silent-channel case (review R1 P2) with no new service. | A dead-man service (third UNI-11 record). A daily heartbeat (noise). |
| 13 | **When `alert_credential` must exist:** if and only if `SKIW_ALERT_CHANNEL` is `telegram`. The `secret-store` check of `check-hardening` fails when the file is missing while the channel is `telegram`, and fails when the file is present while the channel is empty. | One rule, testable. | Always required (fails on hosts with no channel yet). |
| 14 | **No UNI-11 service is added for the heartbeat.** It goes through the channel decided in row 1. | — | — |

## 4. Data model
None. No table, column or migration. The new host files are `/etc/skiw/secrets/alert_credential` (token) and one env value pair (`SKIW_ALERT_CHANNEL=telegram`, `SKIW_ALERT_TO=<chat id>`).

## 5. Flows
1. **Alert, delivered.** `skiw-health` finds a bad check. It scrubs the value, writes the journal line, reads the token file, sends one `sendMessage` request over TLS with certificate verification, gets status 200 and `ok`, records the message as delivered in the state file, exits 0 or 1 as built.
2. **Alert, not delivered.** The token file is missing or unsafe, the network fails, the answer is not 200 and `ok`, or the bound (a single 10 s deadline per message) passes. The message stays owed in the state file. The run exits 3. The next run (5 minutes later) tries again. The journal line already exists.
3. **Host dead.** The host cannot run anything. UptimeRobot gets no `ok` from `/healthz`, treats the monitor as down after its check interval and sends the owner its own alert. The owner sees it on the phone without the host's help.
4. **Telegram down.** Flow 2 repeats. UptimeRobot is not involved. The owner sees the journal when next on the host, and sees exit 3 in the `skiw-health` unit.
5. **Heartbeat.** On the first run at or after Monday 00:00 UTC, if no heartbeat was delivered this ISO week, the run sends `heartbeat` / `N checks, M bad` through flow 1 or 2. If it is not delivered, it stays owed and is retried; the owner sees no message by Monday 10:00 Kuala Lumpur time and follows the runbook rule (decision 12).
6. **Turn on (once per host, by the owner).** The owner creates the bot with BotFather, writes the token to `/etc/skiw/secrets/alert_credential` over SSH (the runbook gives the exact command; the token never goes through a shell history or an argument), puts the chat id in the env file, runs `apply`, then `skiw-health --test`. The test sends one `alert-test` message. The owner adds the UptimeRobot monitor in the web page of the account and confirms that email or app push alerts work on the free account.
7. **Rotate.** The owner revokes the token in BotFather, replaces the file, runs `skiw-health --test`. A leaked token lets a third party post fake alerts in the owner's chat; it cannot read anything.

## 6. Permissions
| Who | Action |
|---|---|
| Owner | Creates the bot and the UptimeRobot account, holds both logins, writes the token file (root over SSH), reads the alerts. |
| `skiw-health` (root on the host) | Reads the token file. Sends alerts. Nothing else touches the token. |
| Builder / agents | Never hold the token or the UptimeRobot login. Tests use a fake server and a token generated at test time (PROJECT §11). |
| Telegram, UptimeRobot | Receive what section 7 lists. They have no access to the host, the database or the app. |

## 7. Threat model
| Threat | Control (with concrete numbers) | How it's tested |
|---|---|---|
| Client data leaves in an alert | Payload is exactly three fields (check, host, value). Values come from numbers and names. Emails and IC-shaped text are replaced. The value is cut to 200 characters. | Built in M1j-1 (`test_the_payload_is_exactly_check_host_and_value`, scrubber and cap tests). M1j-2 re-runs them against the Telegram request body and adds a test that the request holds only the chat id and the text. |
| Bot token leaks (repo, log, process list, error text) | Token only in `/etc/skiw/secrets/alert_credential` 0400 root. Never an argument, env value, log line or exception text. The request is built so a failure message names the step, not the URL (the URL holds the token). Gitleaks stays on. The request is built with **no environment proxy** (`urllib.request.ProxyHandler({})`), so `https_proxy` can never route the URL, and the token, elsewhere. The token file must match the bot token format (digits, a colon, then letters, digits, `_` or `-`) before it goes into the URL; anything else counts as an unsafe file (flow 2) and the token is not used. The message is **plain text**: no `parse_mode`, link previews off. | Test: every failure path (DNS, TLS, timeout, status, bad answer) prints and journals no token and no URL. Test: the token appears nowhere in stdout, stderr, journal and state file. Generated token, no literal key. Test: a set `https_proxy` is ignored; a malformed token file is refused and never put in a URL; the request has no `parse_mode` and has link previews off. |
| Fake alerts posted by someone with the token | One token per environment; the owner rotates through BotFather (flow 7). Alerts name the host. | Runbook step tested by reading; no code. |
| Host sends to the wrong chat or a non-Telegram host | The URL is a constant (`https://api.telegram.org`). Only `SKIW_ALERT_TO` (digits, optional leading `-`) is configurable. Any other `SKIW_ALERT_CHANNEL` value refuses (exit 2). TLS verification on. No redirect followed. | Tests: bad chat id refused; channel other than `telegram` or empty refused; a redirect answer counts as not delivered. |
| Alert hangs the health run | One 10 s deadline per message; at most 20 owed messages (already built); the unit timeout stays 280 s. | Test with a fake that never answers: run ends inside the bound, exit 3. |
| Telegram or the network is down and nobody knows | Journal first; exit 3; message owed and retried every 5 min; UptimeRobot covers the dead-host case. | Built tests for the no-channel case; new test for a failing transport. |
| The channel is broken and the owner never knows (revoked token, bot removed, wrong file mode, stopped timer) | Weekly heartbeat (decision 12): Monday, first run at or after 00:00 UTC. The owner's runbook rule: no message by Monday 10:00 Kuala Lumpur time → check the host. At most 7 days of silence. | Tests with a fake clock: sent once in a new ISO week, not sent twice in a week, not marked delivered on a failed send and retried, an old owed heartbeat replaced by the new week's; a stopped-timer case is covered by the runbook rule (no code). |
| `/healthz` leaks data to the monitor or the public | The view returns the text `ok` and nothing else. | New test: body is exactly `ok` and `Content-Type` is `text/plain` (a test of the existing view, so a later change fails it). |
| UptimeRobot learns more than needed | It receives the public host name, answer and timing, and the owner's own contact. No token, no header, no client data. | Reviewed in this spec; the monitor is set by the owner, no code. |
| Cross-border transfer without a record (D19) | No client personal data crosses. The owner's own contact details go to UptimeRobot, and the owner's chat id goes to Telegram; both are the owner's own. The DECISIONS entry records this, the data lists and the owner's decision. **One rule (owner decision 2026-10-24):** the owner's own confirmation in the DECISIONS entry is enough; no adviser sign-off is needed before M1j-2 merges. D19's adviser-named condition applies to a cross-border flow of personal data of data subjects. Here only the owner's own contact data (the UptimeRobot account contact, the Telegram chat id) and system data (check names, host names, numbers) cross, and no data subject's data. If a later change puts a data subject's data into an alert, this rule no longer holds and D19's full process applies first. | The DECISIONS entry with the owner's confirmation exists before M1j-2 merges; the reviewer checks it. |
| Vendor terms change or the free plan ends | UptimeRobot is replaceable; the host does not depend on it. | Runbook lists the replacement step. |

**Alert values** (from `skiw_host/health.py`; the host is `<environment>:<node name>`; the UNI-11 record in DECISIONS cites this table):
| Check | Value shape |
|---|---|
| `disk` | mount path and percentage used (space or inodes) |
| `memory`, `swap`, `load` | percentage or load per CPU, as numbers |
| `containers` | Compose service name with a status or a restart count |
| `readyz` | `status <code>` |
| `tls-certificate` | `expires in N days` |
| `dump` | dump file name and age in hours |
| `security-updates` | `N security updates pending` |
| `reboot` | `reboot required` |
| `deploy-alert` | a count of alert lines (never their text) |
| `check-hardening` failures | the failing check names |
| `heartbeat` | `N checks, M bad` |
| any failure of a check | the step name or the exception type name, never the tool output |

**Deploys and UptimeRobot.** A deploy or a key rotation restarts `web` and Caddy serves a 503 maintenance page for a short time, so UptimeRobot can report "down" during a deploy. The runbook says this is expected, and tells the owner to use a maintenance window in UptimeRobot or to ignore a "down" that clears inside the deploy time.

**UptimeRobot facts, checked by the reviewer on 2026-10-24:** the terms (uptimerobot.com/terms §3, changelog 26 May 2026) allow any use, including commercial; the help article "Who Should Use UptimeRobot's Free Plan?" (modified 28 Sep 2026) gives 50 monitors and 5-minute checks and names internal tools; the pricing page (modified 10 Aug 2026) still says "hobby and non-profit projects". The pricing page does not show which alert contact types the free plan includes. The owner confirms that email or app push works on the free account before M1k, and the S1 DECISIONS entry records these facts and the date. Replacing the provider is a host-independent step.

Vendor facts not yet checked by the builder, to be checked and cited with a date before M1j-2 is built: the Telegram Bot API `sendMessage` request and answer format and its limits; BotFather token revocation; which alert contact types the UptimeRobot free plan includes (the owner confirms email or app push on the account; the interval and monitor count are recorded above).

## 8. Configurable values
| Value | Where |
|---|---|
| `SKIW_ALERT_CHANNEL` (`telegram`, or empty for no channel) | `infra/host/env/<environment>.env` (already present, empty) |
| `SKIW_ALERT_TO` (chat id) | same file |
| `SKIW_ALERT_SERVER`, `SKIW_ALERT_FROM` | removed in M1j-2 (only for mail; no transport uses them) |
| Bot token | `/etc/skiw/secrets/alert_credential` on each host (owner-supplied) |
| Send deadline: `SEND_S` **changes from 30 s (M1j-1) to 10 s** | named constant in `skiw_host/alert.py` (UNI-02) |
| Owed-message cap (20, `OWED_MAX`, unchanged) and the heartbeat day and time (Monday 00:00 UTC) | named constants in `health.py` (UNI-02) |
| UptimeRobot monitor, interval, contacts | the owner's UptimeRobot account (not in the repository) |

## 9. Milestones
| # | Scope | Done when (testable) |
|---|---|---|
| S1 | This spec reviewed and approved; v1.18 text changes (row 8) applied by the builder in a docs PR; DECISIONS entry with the UNI-11 and D19 record. | Review round approved; DECISIONS entry has both services, their data lists and the owner decision; v1.18 rows updated. |
| M1j-2 | Telegram transport in `skiw_host/alert.py` (standard library); `channel()` and `credential()`; `alert_credential` in the secret inventory; the weekly heartbeat (decision 12); the `secret-store` rule of decision 13; the two PR 60 P2 fixes; test for `/healthz` body; runbook (with the heartbeat owner rule and the deploy note) "Turning on the alert channel". Uses `.agent/patches/m1j-2-on-top-of-1.patch` as a start only, because that patch builds mail (SMTP) too and must be reduced to Telegram. | Section 7 tests pass (including the proxy, token-format, plain-text and heartbeat tests); `make lint typecheck test host-test` and Semgrep clean; no token anywhere in any output. |
| M1k | Real-host proof: `skiw-health --test` delivers to the owner's chat from staging and production; UptimeRobot monitors report up, and report down when the host's web container is stopped. | Owner sees the test message and a down alert; evidence in DECISIONS. |

## 10. Open questions
| # | Question | Default if not answered |
|---|---|---|
| 1 | One private chat for both environments, or one chat each? | One chat each, so a message shows its environment at a glance (the text already names the host). |
| 2 | ~~PDPA confirmation.~~ **Answered 2026-10-24 (review R1):** the owner's own confirmation in the DECISIONS entry is enough (section 7, PDPA row). No adviser sign-off before M1j-2 merges. | — |
| 3 | Is the UptimeRobot free plan's check interval enough as the "dead host" signal, or does the owner want a shorter one (paid plan)? | Free plan. |
