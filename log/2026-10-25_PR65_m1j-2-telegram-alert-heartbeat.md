# PR 65 — feat(infra): M1j-2 Telegram alert transport, weekly heartbeat, hardening retry and stale package lists

- **Merged:** 2026-10-25T07:14:20Z (GitHub) · **Merge commit:** `550b622829fdb953722f9237814d22ff19192009` · **Branch:** `feat/m1j-2-telegram-alert` (final head `9e86194db2be35b27fcb03262e47bc232490fba4`)
- **Gate breaches:** none (19 files, +1,261 / −168; about 286 code, 201 docs, 774 tests; owner chose one PR over about 400 non-test lines on 2026-10-25)
- **Approval receipt:** `reviews/PR-65.receipt` on `agent-logs`, written 2026-10-25T07:13:43Z (before the merge, by 37 seconds); names head `9e86194…`, review `reviews/PR-65.md` (hash `1d2922f3…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 65` → MERGED, merge commit `550b622`, final head equals the reviewed head; `git merge-base --is-ancestor 550b622 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved (Round 1)
- **Spec:** v1.19, hash `75ac19f61466445c35e4ff9341a0d0984a55249f`; amendment `docs/specs/2026-10-24-alert-channel-and-uptime-ping.md` v1.2 · **Milestone:** M1j (second half)

## What changed
Telegram transport in `skiw_host/alert.py` (stdlib; constant URL; `chat_id` and `text` only; no proxy, no redirect, TLS verified; 10 s deadline; delivered only on 200 and `ok: true`; failures name the type, never the URL or token). `channel()`/`credential()`: channel `telegram` or empty, chat id digits, token file opened `O_NOFOLLOW|O_NONBLOCK`, open file checked, token format checked. `alert_credential` is an owner-supplied inventory entry; `secret-store` requires it if and only if the channel is `telegram`. Weekly heartbeat (`N checks, M bad`, Monday 00:00 UTC, once per ISO week, retried, none without a channel). Monthly `check-hardening` result is written to `hardening.state` and read by a 12th check in the 5-minute run (retry every 5 minutes; older than 33 days is bad). `security-updates` is bad when the apt lists stamp is older than 48 h. `/healthz` body test. `SKIW_ALERT_SERVER` and `SKIW_ALERT_FROM` removed. Runbook "Turning on the alert channel", DECISIONS "2026-10-25 — M1j-2". After the first CI run a Linux-only test fix: the fake TLS server's `close()` now calls `shutdown` first.

## Review rounds
- R1: Approved. Three optional P3 items.

## Deferred conditions
- none.

## Decisions worth keeping
- Owner (2026-10-25): one PR; no channel means no heartbeat, so a healthy host with no channel exits 0; real alerts with no channel still go to the journal and exit 3.
- The heartbeat is not stored in the owed list; it is due while the state's week differs from the current week (an old week is replaced, never queued twice).
- Telegram API facts checked 2026-10-25; the token length bounds are an assumption [A].

## Follow-ups
- Optional P3: the runbook chat-id snippet can use an environment proxy and can list a stranger's chat.
- Optional P3: the apt stamp `/var/lib/apt/periodic/update-success-stamp` is an assumption; if it is missing, `security-updates` alerts forever (M1k proves it on Ubuntu 24.04).
- Optional P3 (from PR 63): the M1 plan still shows G8 open with email as the default.
- Open PR 60 P3: "a check failing on every other run never alerts" (not built; spec says no M1j-1 check changes).
- Add the two new alert value shapes (`package lists not updated for N h`, `the last monthly run is N days old`) to the amendment's "Alert values" table at the next spec change.
- The PR body still named head `2fb17ab` (text only).
- M1k: real Telegram delivery, UptimeRobot up/down, the unit sandbox with the network path, and the stamp file. Owner creates the bot and chat per host and the UptimeRobot monitors.
