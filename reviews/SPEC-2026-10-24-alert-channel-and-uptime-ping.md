# Review — 2026-10-24-alert-channel-and-uptime-ping

## Round 1 — 2026-10-24 · scope: slice (amendment to spec v1.18: Q20 channel, uptime ping, UNI-11)

- **Spec review:** `docs/specs/2026-10-24-alert-channel-and-uptime-ping.md` · version 1.0 (draft) ·
  hash `c39fe297532bde3fdc64d9ef0beb8f77105e35f3` (working file, untracked in the main checkout; same
  hash at the start and the end of the review).
- **Amends:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.18, hash
  `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` (unchanged).
- **Repo state read:** `main` = `origin/main` = `2af8ff384975387470d7296f2fa2b6240a9c212e` (PR 61
  merged). Code read for the spec's "already built" claims: `infra/host/skiw_host/alert.py`,
  `health.py`, `hardening.py` `secret_store`, `secrets.py`, `infra/host/systemd/skiw-health.service`,
  `skiw-hardening.service`, `infra/host/nftables.conf`, `infra/host/caddy/edge.caddy`,
  `app/health/views.py`, `app/config/urls.py`.
- **Mode:** read only. No checkout was needed (no code under review). No file written except this one.
- **Owner answers recorded in the spec (2026-10-24):** G8 = Telegram bot; uptime ping = yes;
  provider = UptimeRobot free plan. Not reopened here.
- **Model used:** Claude Opus 5.5. **Switch model next step?** No — the fixes are text edits.

**Verdict:** Revision required

### Findings

No P0 or P1.

### [P2] A broken alert channel stays silent, and nothing tells the owner
- **Category:** material risk.
- **Rule:** spec §1 goal ("a problem reaches the owner's phone"); decision 10 ("Delivery failure is
  never silent"); UNI-03; PR 60 review residual risk "Nothing watches `skiw-health` itself".
- **Evidence:** flow 2 and flow 4: on any failure the message stays owed, the run exits 3, and "the
  owner sees the journal when next on the host". `alert.py` `deliver` journals only. UptimeRobot
  (decision 7) watches `/healthz`, served by `web`; it does not see `skiw-health`. `health.py` keeps
  at most `OWED_MAX = 20` owed messages and drops the oldest (`state.owed[-OWED_MAX:]`).
- **Failure scenario:** the token is revoked or mistyped during rotation (flow 6), the bot is
  removed from the chat, the token file gets the wrong mode, or `skiw-health.timer` stops. Telegram
  answers 401 or 403, or nothing is sent at all. Every run exits 3 into the journal. `/healthz` still
  says `ok`, so UptimeRobot says "up". The disk then fills or certificates expire, and the owner
  never learns of it.
- **Why it matters:** decision 10 says delivery failure is never silent. It is silent off the host,
  and that is the only place the owner looks.
- **Required correction:** the spec names how the owner learns, within a stated time, that alerts
  no longer reach the phone. Then it adds a test, and a runbook rule for the owner. The fix needs
  no new service. Example: `skiw-health` sends one fixed "alive" message (check `heartbeat`, value
  "N checks ok") once a week at a fixed time. The runbook says: no message by that time → check
  the host. This also covers a stopped timer. If the owner prefers a dead-man service, it is a third
  UNI-11 service and needs its own record. Decision 10 is reworded to match: silent off the host is
  possible, and the heartbeat bounds it.
- **Owner:** owner (choice); builder (spec text).
- **Verification:** the next round finds the mechanism, its interval, its test and the runbook rule.
- **Disposition:** before approval.
- **Owner decision (2026-10-24, in the reviewer session):** yes to the weekly "alive" message. The
  builder sets the day and time and writes it into the spec, the test and the runbook.
- **Status:** open.

### [P2] The H6 off-site freshness alert: two readings
- **Category:** spec ambiguity.
- **Rule:** spec v1.18 §8.4 H6 ("Freshness (dead-man) alert, off the production host"), H7 ("The
  freshness alert of H6 runs on the off-site side, so a dead production host still raises it").
- **Evidence:** §2 non-goal: "No alert for the H6 off-site freshness check. That check stays as in
  v1.18 H6." Decision 8 changes H7 and D19 (5) to "the alert channel is Telegram" for the whole
  spec.
- **Failure scenario:** one builder reads "this spec does not wire the H6 alert, and M6 will use
  Telegram". Another reads "the H6 freshness check gets no alert", which drops the backup dead-man
  alarm. Also, an off-site sender of that alert would be a second Telegram sender with its own token,
  so UNI-11 and the secret inventory are affected.
- **Required correction:** reword the non-goal. Example: "This spec does not build the H6
  freshness alert. When M6 builds it on the off-site side, it uses the same Telegram channel with
  its own bot token, recorded then." Or name a different route. Either way, the reader gets one
  reading.
- **Owner:** builder (text); owner (if a different route).
- **Verification:** the next round reads one meaning.
- **Disposition:** before approval.
- **Status:** open.

### [P2] Two rules for the PDPA confirmation
- **Category:** spec ambiguity (a gate two people can read two ways).
- **Rule:** spec v1.18 D19 (cross-border record, adviser sign-off for personal data); UNI-11.
- **Evidence:** §7, last threat row: "The owner's PDPA adviser confirms there is no s129 transfer
  of data subjects' data (Q14)", and "the reviewer checks it" before M1j-2 merges. §10 Q2 default:
  "Treated as no data-subject data; the owner confirms in the DECISIONS entry."
- **Failure scenario:** at the M1j-2 merge, the DECISIONS entry has the owner's confirmation but no
  adviser sign-off. Under §7 the merge is blocked. Under §10 it passes.
- **Required correction:** one rule. Either (a) the owner's own confirmation is enough, because
  only the owner's own contact data and system data cross (state why D19's adviser condition does
  not apply), or (b) an adviser sign-off is needed before M1j-2 merges. Make §7 and §10 say the same
  thing.
- **Owner:** owner (choice); builder (text).
- **Verification:** §7 and §10 agree; the gate is one sentence.
- **Disposition:** before approval.
- **Owner decision (2026-10-24, in the reviewer session):** option (a). The owner's own
  confirmation in the DECISIONS entry is enough; no adviser sign-off before M1j-2 merges. The spec
  states why: only the owner's own contact data and system data cross, no data subject's data.
- **Status:** open.

### [P2] Decision 8 misses two places in v1.18 that must change
- **Category:** documentation consistency.
- **Rule:** decision 8 ("Keeps one source of truth"); header ("It changes nothing else").
- **Evidence:** spec v1.18 line 637 (cost table: "alert channel and uptime ping per Q20") and §8.4 H4
  "Inventory (exact names …)": it ends with "the GHCR read token; later the AI and Drive credentials".
  Decision 3 adds `alert_credential` to the inventory. Decision 8 lists H7, D17, D19 (5), UNI-11 and
  Q20 only.
- **Failure scenario:** the S1 docs PR follows decision 8 exactly. H4's "exact names" list then
  lacks a secret that the host holds, and the cost line still points at an open question.
- **Required correction:** add H4 (inventory: `alert_credential`, owner-supplied, root, not
  escrowed, one per environment) and the cost line (Telegram RM 0; UptimeRobot free RM 0) to
  decision 8.
- **Owner:** builder.
- **Verification:** decision 8 lists both; `grep -n "Q20"` on v1.18 after the S1 PR shows only
  "answered".
- **Disposition:** before approval.
- **Status:** open.

### [P3] Decision 6 says §7 lists the alert values; it does not
- **Evidence:** decision 6: "Section 7 lists what the value can hold." §7 says only "Values come
  from numbers and names". The checks' values (`health.py`): mount paths and percentages,
  "N% available", load per CPU, Compose service names with status or restart counts, "status
  <code>", "expires in N days", dump file names and age in hours, "N security updates pending",
  "reboot required", failing `check-hardening` check names, error messages with no data, exception
  type names; the host is `<environment>:<node name>`.
- **Suggested correction:** add this list as a table (check → value shape). The UNI-11 record in
  DECISIONS (S1) can then cite it.

### [P3] The send deadline changes from 30 s to 10 s without saying so
- **Evidence:** `alert.py` `SEND_S = 30`; spec §5 flow 2, §7 and §8: "10 s". §7 calls the bounds
  "already built".
- **Suggested correction:** say "`SEND_S` changes from 30 to 10" in §8.

### [P3] Three request details for the token path
- **Evidence:** §7 rows "Bot token leaks" and "Host sends to the wrong chat". The token sits in the
  URL path.
- **Suggested correction:** state and test: (1) no proxy from the environment (for example
  `urllib.request.ProxyHandler({})`), so `https_proxy` can never route the URL elsewhere; (2) the
  token file must match the bot token format before it goes into the URL; anything else counts as
  "unsafe" (flow 2); (3) plain text only: no `parse_mode`, and link previews off.

### [P3] When `alert_credential` must exist
- **Evidence:** `hardening.py` `secret_store`: every name in `held(environment)` must exist.
  The spec does not say whether `alert_credential` is required when `SKIW_ALERT_CHANNEL` is empty.
- **Suggested correction:** one rule. Example: required if and only if the channel is `telegram`;
  present while the channel is empty → `secret-store` fails.

### [P3] Deploys will raise UptimeRobot alerts
- **Evidence:** `edge.caddy` `handle_errors 502 503 504` → 503 maintenance page; H4 rotation and
  each deploy restart `web` ("short outage").
- **Suggested correction:** the runbook says a short "down" during a deploy is expected, or uses a
  maintenance window in UptimeRobot.

### [P3] Cite the UptimeRobot plan facts with a date
- **Evidence (checked by the reviewer, 2026-10-24):** uptimerobot.com/terms §3 (changelog May 26,
  2026): "UptimeRobot is available for any use, including commercial and business use." The help
  article "Who Should Use UptimeRobot's Free Plan?" (modified 2026-09-28) names "internal tools" and
  gives 50 monitors, 5-minute checks and keyword monitors. Conflict: the pricing page (modified
  2026-08-10) still calls Free "Good for hobby and non-profit projects". A free-plan non-commercial
  rule existed from late 2024 (third-party reports). The pricing page does not show which alert
  contact types Free includes.
- **Suggested correction:** record these with the date in the S1 DECISIONS entry. Have the owner
  confirm email or app push works on the free account. Keep the "replaceable" note.

### Injection check
No text in the spec addresses an AI agent or asks to skip a gate.

### Checks against the code (the spec's "already built" claims)
| Claim | Found |
|---|---|
| Journal first, then the channel | yes, `alert.deliver` |
| Failure named by type only | yes, `alert.failure` |
| Owed messages kept and retried; cap 20 | yes, `OWED_MAX = 20`; the oldest are dropped (see P2 1) |
| A failed channel is not retried for each message | yes (PR 60 mutant H17 killed) |
| Payload exactly check, host, value; value cap 200 | yes, `Alert.payload`, `VALUE_MAX = 200` |
| `/healthz` returns `ok`, `text/plain`, public | yes, `app/health/views.py`; Caddy proxies all paths |
| Unit timeout 280 s | yes, `skiw-health.service` |
| Egress allowed | yes: nftables has an input policy drop only; the unit allows `AF_INET`/`AF_INET6` |
| Owner-supplied secret kind exists | yes, `Kind.OWNER_SUPPLIED` (`ghcr_read_token`) |
| Send deadline 10 s | no, 30 s today (P3) |

### Self-check audit
A spec has no builder self-check table. My applicability list for this spec: UNI-03, UNI-06,
UNI-07 (hard), UNI-08, UNI-09, UNI-11, UNI-16, UNI-19; spec v1.18 D17, D19, H4, H6, H7, Q14, Q20.
Each is addressed. The gaps are the four P2 items above.

### Verification performed
| Check | Result |
|---|---|
| `git hash-object` of the spec, start and end | `c39fe297…` both times |
| v1.18 hash | `0edfb3cd…`, unchanged |
| v1.18 text for Q20, D17, D19, H4, H6, H7, UNI-11, cost line | read; P2 2 and 4 |
| Code facts (table above) | 9 match, 1 differs |
| UptimeRobot terms, help article, pricing page (web, 2026-10-24) | commercial use allowed by the terms; pricing wording conflicts |

Not checked: Telegram Bot API facts (the spec marks them [A] and requires them checked and cited
before M1j-2 is built, which is acceptable).

### Residual risks
- The SIGALRM deadline may not interrupt a blocking DNS lookup in C (`getaddrinfo`). A slow
  resolver can make one send last longer than 10 s. The 280 s unit timeout still bounds the run.
- Telegram keeps bot messages on its servers, without end-to-end encryption. They hold no client
  data.

### Required before approval
- The four P2 items.

### Optional improvements
- The six P3 items.
