# PR 63 — docs(spec): adopt Q20 answers, Telegram alert channel and UptimeRobot ping (spec v1.19, amendment v1.2)

- **Merged:** 2026-10-25T03:20:48Z (GitHub) · **Merge commit:** `2f9288ce82c39344210aa85494f578255cbb4b39` · **Branch:** `docs/s1-alert-channel-spec` (final head `e9210227afab5477d3dd1e0e6e0088b2e012ac47`)
- **Gate breaches:** none (3 files, +135 / −10, docs only)
- **Approval receipt:** `reviews/PR-63.receipt` on `agent-logs`, written 2026-10-25T03:19:51Z (before the merge, by 57 seconds); names head `e921022…`, review `reviews/PR-63.md` (hash `badc2428…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 63` → MERGED, merge commit `2f9288c`, final head equals the reviewed head; `git merge-base --is-ancestor 2f9288c origin/main` succeeded.
- **Built by:** builder · **Final verdict:** Approved (Round 1)
- **Spec:** main spec now v1.19, hash `75ac19f61466445c35e4ff9341a0d0984a55249f` (v1.18 was `0edfb3cd…`); amendment `docs/specs/2026-10-24-alert-channel-and-uptime-ping.md` v1.2, hash `2e4333eae94bc1d8ca31be0d2ce15b6ea0b1fce8` · **Milestone:** M1j (S1, gates M1j-2)

## What changed
Main spec v1.18 → v1.19, text only: version line and changelog, D17, D19 flow (5), the cost table, H4 inventory (`alert_credential`), H7 (Telegram bot chat, weekly heartbeat, UptimeRobot ping), UNI-11, Q20 (answered). The amendment spec was added at v1.2 (Round 2 approved v1.1 `ea6ee2fb`; v1.2 takes its three P3 items: heartbeat value `N checks, M bad`, the Q20 check wording, the stale vendor line). DECISIONS "2026-10-24 — Q20 answered: Telegram alert channel and UptimeRobot uptime ping (UNI-11, D19 record)".

## Review rounds
- R1: Approved. One optional P3: the M1 plan still shows G8 open with email as the default.

## Deferred conditions
- none.

## Decisions worth keeping
- Telegram bot chat is the Q20 channel; UptimeRobot free plan is the uptime ping; weekly heartbeat every Monday (first run at or after 00:00 UTC). Owner rule: no heartbeat by Monday 10:00 Kuala Lumpur time → check the host.
- PDPA rule (a): the owner's own confirmation in the DECISIONS entry is enough, while only the owner's own contact data and system data cross.
- The main spec hash changed, so the next build needs `review spec` of v1.19 and then `setup`.

## Follow-ups
- Owner: `review spec docs/specs/2026-10-05-skiw-platform-stack-design.md`, then `setup`, then `build` M1j-2.
- Builder, before M1j-2: check the Telegram Bot API facts and cite them with a date.
- Owner, before M1k: create the bot and chat per host; add the UptimeRobot monitors; confirm email or app push works on the free account.
- Optional P3: correct the G8 row and default in `docs/plans/2026-10-12-m1-vps-infrastructure.md`.
