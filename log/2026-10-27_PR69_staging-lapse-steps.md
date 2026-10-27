# PR 69 — docs: staging lapse clean-up steps (PR 68 deferred P2)

- **Merged:** 2026-10-27T14:06:30Z (GitHub) · **Merge commit:** `2f63a5b87cba62d2aaaa98c13e6091247cc77c03` · **Branch:** `docs/staging-lapse-steps` (final head `d3d0cdd2cc0f7cfe29b2042ffb85f544dd0cb9d1`)
- **Gate breaches:** none (1 file, +27 / −8, docs only)
- **Approval receipt:** `reviews/PR-69.receipt` on `agent-logs`, written 2026-10-27T12:37:38Z (before the merge, by 1 h 29 min); names head `d3d0cdd…`, review `reviews/PR-69.md` (hash `9e566e8e…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 69` → MERGED, merge commit `2f63a5b`, final head equals the reviewed head; `git merge-base --is-ancestor 2f63a5b origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved (Round 1)
- **Spec:** main spec v1.20, hash `92841ba555e9e857ac70e86a5b043cf9729ed371` · **Milestone:** M1 (before the purchase and M1k)

## What changed
`docs/runbooks/host-rebuild.md`: "When staging lapses" now has seven steps (staging deploy off, DNS, `ghcr_read_token`, bot token, `STAGING_DEPLOY_KEY`, UptimeRobot pause, destroy the VPS and note the date). "To bring it back" is renumbered 1–7 with a DNS step and the monitor un-pause.

## Review rounds
- R1: Approved. No P1, P2 or conditions.

## Deferred conditions
- None. This PR closes the PR 68 deferred P2 (due 2026-11-20); staging may now lapse.

## Decisions worth keeping
- The steps have not run on a real lapsed server [A]; the first real lapse is their test (M1k).

## Follow-ups
- Owner: Q44 production term; buy the VPSs; G-VENDOR email; Telegram bot per host and UptimeRobot monitors.
- PR 70 (M2 plan) waits for `review 70`.
