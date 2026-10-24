# PR 60 — feat(infra): M1j-1 host health checks, state file, journal-only alert sender and systemd timers

- **Merged:** 2026-10-24T05:59:34Z (GitHub) · **Merge commit:** `6ed964122032ce276202dd2720217ab5b6f0ed70` · **Branch:** `feat/m1j-health-alerts` (final head `330aecdb37a91a957d6e82604bfc8510930c36b0`)
- **Gate breaches:** none (owner chose to split M1j; M1j-1 is about 2,100 lines, about 1,110 tests)
- **Approval receipt:** `reviews/PR-60.receipt` on `agent-logs`, written 2026-10-24T05:45:57Z (before the merge); names head `330aecd…`, review `reviews/PR-60.md` (hash `a74d9c39…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 60` → MERGED, merge commit `6ed9641`, final head equals the reviewed head; `git merge-base --is-ancestor 6ed9641 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved with conditions (Round 1)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1j (first half)

## What changed
`skiw-health` and `skiw_host/health.py`: eleven checks every 5 minutes (disk, memory, swap, load, containers, readyz, tls-certificate, dump, security-updates, reboot, deploy-alert); `--hardening` monthly; `--test`. Every input is injectable and fail closed. State file `/var/lib/skiw/health.state` opened `O_NOFOLLOW`, checked, written with fsync. `skiw_host/alert.py`: payload exactly check/host/value, emails and IC numbers replaced, journal first, no transport built; any `SKIW_ALERT_*` value refuses (exit 2); with no channel a due message is undelivered and the run exits 3. Four systemd units; `apply` installs them and enables the timers; `check-hardening` gains `health-timers`. Runbook `docs/runbooks/health-alerts.md`; DECISIONS "2026-10-23 — M1j: health checks and alert sender".

## Review rounds
- R1 (Approved with conditions): P2 a failed monthly `check-hardening` alert is retried only monthly; P2 `security-updates` is blind to stale package lists; P3 a check that fails every other run never alerts; P3 "journal first" is untested once a transport exists.

## Deferred conditions
- Monthly `check-hardening` alert retry → M1j-2.
- `security-updates` and stale package lists → M1j-2.
- Optional: the two P3 items.

## Decisions worth keeping
- Dump age is shown, not judged, until M6 sets the Q34 cadence.
- Until a channel exists, every host exits 3 while a check is due. This is by design (fail closed).
- The M1j-2 patch (`.agent/patches/m1j-2-on-top-of-1.patch`) also reverts DECISIONS, runbook and env comments to the unsplit text; rewrite them as M1j-2 docs.

## Follow-ups
- M1j-2: SMTP and Telegram transports, `alert_credential`, turn-on runbook. Needs G8 (channel) and the UNI-11 record. Take the two deferred P2s there.
- M1k: real-host proof (unit sandboxing, `apt-get --simulate` format, journal cursor across rotation, monthly run).
- Out of scope noted: `apply.untrusted` checks parents, not the final path component.
